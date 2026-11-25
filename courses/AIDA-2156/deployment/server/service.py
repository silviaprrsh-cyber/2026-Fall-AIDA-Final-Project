"""Continuous collector and read-only JSON API for the Red Deer research display."""
from __future__ import annotations
import argparse
import copy
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hmac
import ipaddress
import json
import logging
import math
import os
import re
import sys
from threading import Event, Lock, Thread
from urllib.parse import urlsplit

from .inference import FrozenModel, METHOD, REQUIRED_HOURS, features, valid_at
from .schema import FLOWS, RAIN_ID, RAIN_NAME, UTC, WARNING, Observation, aware, iso
from .store import MemoryStore, PgStore

START_HOURS = 84
STEADY_HOURS = 3
SOURCE_CODES = {f"flow:{s}" for s in FLOWS} | {f"rain:{RAIN_ID}"}
LOG = logging.getLogger("red_deer.live")

def now_utc():
    return datetime.now(UTC)

def _age(a, b):
    return max(0, int((a-b).total_seconds()))

def _parse_utc(s):
    return aware(datetime.fromisoformat(s.replace("Z", "+00:00")))

def demo_poll(clock, history_hours=84, timeout=10):
    """Generated, not observed. Use the same storage and original-weight inference paths."""
    del timeout
    z = int(aware(clock).timestamp())
    end = z//300*300
    rows = []
    for stamp in range(end-history_hours*3600, end+1, 300):
        at = datetime.fromtimestamp(stamp, UTC)
        signal = math.sin(stamp/43200)
        for i, (station, base) in enumerate(zip(FLOWS, (52.0,8.2,3.1,72.0))):
            v = base + base*.07*signal + base*.015*math.cos(stamp/10800+i)
            rows.append(Observation(station, "flow", at, clock, v, "Synthetic demonstration", None, clock))
    for stamp in range(z//3600*3600-history_hours*3600, z//3600*3600, 3600):
        at = datetime.fromtimestamp(stamp, UTC)
        rows.append(Observation(RAIN_ID,"rain",at,clock,float((stamp//3600)%31==2)*.4,
                      "Synthetic demonstration",3600,clock))
    return rows, []

def make_snapshot(mode, rows, t, estimate, *, errors=(), flow_ttl=3600, rain_ttl=10800, internal_error=None):
    t = aware(t)
    safe = [z for z in rows if z.observed_at <= t and z.retrieved_at <= t and
            (z.available_at is None or z.available_at <= t)]
    latest = {}
    for o in safe:
        if o.kind == "rain" and o.observed_at + timedelta(hours=1)>t:
            continue
        if o.station_id not in latest or (o.observed_at, o.retrieved_at)>(latest[o.station_id].observed_at,latest[o.station_id].retrieved_at):
            latest[o.station_id] = o

    def record(k, name, rain=False):
        o = latest.get(k)
        period = timedelta(hours=1) if rain else timedelta(0)
        age = _age(t, o.observed_at+period) if o else None
        x = {"station_id":k,"name":name,"value":o.value if o else None,
             "unit":"mm" if rain else "m3/s","observed_at":iso(o.observed_at) if o else None,
             "retrieved_at":iso(o.retrieved_at) if o else None,
             "available_at":iso(o.available_at) if o else None,"source":o.source if o else None,
             "status":"missing" if o is None else "stale" if age > (rain_ttl if rain else flow_ttl) else "ok",
             "age_seconds":age}
        if rain:
            x.update(period="1 h accumulation",period_seconds=3600,
                     window_end_at=iso(o.observed_at+period) if o else None)
        return x

    flow_rows = [record(k,v) for k,v in FLOWS.items()]
    rain = record(RAIN_ID,RAIN_NAME,True)
    def group(hours):
        bound = iso(valid_at(t,hours))
        if internal_error:
            out, audit = None, {"unavailable_reason":internal_error}
        else:
            values, audit = features(safe,t,hours)
            out = estimate(values) if values is not None else None
        state = "experimental" if out is not None else "unavailable"
        notes = {
            0: "Current-time depth estimate from lagged stored observations. Non-equivalent to the historical V4 View.",
            3: "Experimental +3 h projection using only observations already available at issuance, not validated lead.",
            9: ("Experimental +9 h projection. Availability depends on river travel time "
                "and when source readings arrive; later upstream flow cannot be inferred from available observations."),
        }
        reasons = {
            "future_upstream_observations_required": "Required source observations are later than the issue time.",
            "little_exact_sample_unavailable_at_issuance": "The required Little Red Deer flow reading was not available at issue time.",
            "dickson_exact_sample_unavailable_for_projection": "The required Dickson flow reading was not available at issue time.",
            "short_route_rain_window_incomplete_for_projection": "The historical rain window is incomplete.",
            "medicine_candidate_source_span_incomplete": "The required Medicine River observations are incomplete.",
            "medicine_rain_window_incomplete_for_projection": "The historical Medicine River rain window is incomplete.",
        }
        note = notes[hours]
        if audit.get("unavailable_reason") in reasons:
            note = reasons[audit["unavailable_reason"]] + " " + note
        dep=[{"node_id":f"P{i+1:02d}","station_id":"05CC002" if i==5 else None,
              "value":out[i] if out is not None else None,"unit":"m","valid_at":bound,"status":state,
              "kind":"terminal_stage_proxy" if i==5 else "latent"} for i in range(6)]
        inf={"method":METHOD,"status":state,"valid_at":bound,"generated_at":iso(t),
             "note":note,"provenance":audit}
        return {"hours":hours,"depths":dep,"inference":inf}
    base,advance,longterm=(group(h) for h in (0,3,9))
    primary=base["inference"]["status"]=="experimental"
    status = "ok" if primary and all(q["status"]=="ok" for q in [*flow_rows,rain]) and not errors else (
        "partial" if primary or any(q["value"] is not None for q in [*flow_rows,rain]) else "unavailable")
    return {"schema_version":1,"mode":mode,"generated_at":iso(t),"status":status,
            "warning":WARNING + (" Synthetic source observations." if mode=="demo" else ""),
            "flows":flow_rows,"rain":rain,"depths":base["depths"],"inference":base["inference"],"horizons":[advance,longterm],
            "collection":{"status":"unavailable" if internal_error else "partial" if errors else "ok",
                          "failed_sources": sorted(set(errors)&SOURCE_CODES),"internal_error":internal_error,
                          "flow_stale_after_seconds":flow_ttl,"rain_stale_after_seconds":rain_ttl}}

class Collector:
    def __init__(self, mode, store, poll, estimate, *, interval=600, timeout=10, flow_ttl=3600,
                 rain_ttl=10800, clock=now_utc):
        self.mode, self.store, self.poll, self.estimate = mode, store, poll, estimate
        self.interval, self.timeout, self.clock = interval, timeout, clock
        self.flow_ttl, self.rain_ttl = flow_ttl, rain_ttl
        self.lock, self.stop = Lock(), Event()
        self.snapshot = self.last_store_ok = self.last_cycle = self.worker = None
        self.pipeline_error = None
        self.need_backfill = True
        self.failures = self.source_failures = 0

    def history48h(self):
        t = aware(self.clock())
        since = t - timedelta(hours=48)
        try:
            rows = self.store.read(since, t)
        except Exception:
            rows = []
        flows = {sid: [] for sid in FLOWS}
        rain = []
        for r in rows:
            ts_str = iso(r.observed_at)
            if r.kind == "flow" and r.station_id in flows:
                flows[r.station_id].append([ts_str, round(float(r.value), 3)])
            elif r.kind == "rain" and r.station_id == RAIN_ID:
                rain.append([ts_str, round(float(r.value), 3)])
        # Thin 5-min flow series to ~30-min cadence for compact 48h sparklines (<=96 pts)
        for sid in list(flows.keys()):
            pts = flows[sid]
            if len(pts) > 96:
                stride = max(1, len(pts) // 96)
                thinned = pts[::stride]
                if thinned[-1] != pts[-1]:
                    thinned.append(pts[-1])
                flows[sid] = thinned
        levels = {}
        if self.mode == "live":
            try:
                from .provider import get_recent_levels
                levels = get_recent_levels(t, hours=48)
                for sid in list(levels.keys()):
                    pts = levels[sid]
                    if len(pts) > 96:
                        stride = max(1, len(pts) // 96)
                        thinned = pts[::stride]
                        if thinned[-1] != pts[-1]:
                            thinned.append(pts[-1])
                        levels[sid] = thinned
            except Exception:
                levels = {}
        else:
            # Deterministic synthetic stage curve aligned with demo flows
            base_lvl = {"05CB007": 1.35, "05CB001": 0.88, "05CC007": 0.72, "05CC002": 2.45}
            for sid, pts in flows.items():
                b = base_lvl.get(sid, 1.2)
                levels[sid] = [[ts, round(b + 0.008 * val, 3)] for ts, val in pts]
        # Compute past 48h hourly V4 depth estimates (up to 49 points)
        depths = {f"P{i+1:02d}": [] for i in range(6)}
        if rows:
            end_h = t.replace(minute=0, second=0, microsecond=0)
            for h_back in range(48, -1, -2):
                at = end_h - timedelta(hours=h_back)
                if at > t:
                    continue
                try:
                    vals, _ = features(rows, at, 0)
                    out = self.estimate(vals) if vals is not None else None
                except Exception:
                    out = None
                if out is not None:
                    ts_str = iso(at)
                    for i in range(6):
                        depths[f"P{i+1:02d}"].append([ts_str, round(float(out[i]), 3)])
        return {
            "schema_version": 1,
            "mode": self.mode,
            "as_of": iso(t),
            "levels": levels,
            "flows": flows,
            "rain": rain,
            "depths": depths,
            "level_datum_note": "ECCC assumed gauge datum (stage, m); not geodetic water depth.",
        }

    def restore(self):
        t = self.clock()
        try:
            x = self.store.load_snapshot()
        except Exception:
            LOG.warning("Could not read the deployment snapshot cache.")
            return
        if (x and x.get("schema_version")==1 and x.get("mode")==self.mode and
            [h.get("hours") for h in x.get("horizons",[])]==[3,9] and
            x.get("generated_at") and _parse_utc(x["generated_at"])<=aware(t)):
            with self.lock:
                self.snapshot = x

    def once(self):
        poll_started = self.clock()
        h = START_HOURS if self.need_backfill else STEADY_HOURS
        try:
            batch, errors = self.poll(poll_started, h, self.timeout)
        except Exception:
            batch, errors = [], sorted(SOURCE_CODES)
        try:
            self.store.save(batch)
            issue = self.clock()
            rows = self.store.read(issue-timedelta(hours=REQUIRED_HOURS),issue)
        except Exception:
            with self.lock:
                self.pipeline_error, self.last_cycle = "database_unavailable", self.clock()
                self.failures += 1
                self.need_backfill = True
            LOG.warning("Deployment database read/write failed; no new snapshot committed.")
            return False
        try:
            x = make_snapshot(self.mode,rows,issue,self.estimate,errors=errors,flow_ttl=self.flow_ttl,rain_ttl=self.rain_ttl)
        except Exception:
            x = make_snapshot(self.mode,rows,issue,self.estimate,errors=errors,flow_ttl=self.flow_ttl,
                              rain_ttl=self.rain_ttl,internal_error="inference_failed")
        try:
            self.store.save_snapshot(x)
        except Exception:
            with self.lock:
                self.pipeline_error, self.last_cycle = "database_unavailable", self.clock()
                self.failures += 1
                self.need_backfill = True
            LOG.warning("Deployment snapshot commit failed; retaining last stored snapshot.")
            return False
        with self.lock:
            self.snapshot, self.last_store_ok, self.last_cycle = x, self.clock(), self.clock()
            self.pipeline_error=x["collection"]["internal_error"]
            self.failures = self.failures+1 if len(errors)==len(SOURCE_CODES) or self.pipeline_error else 0
            self.source_failures = self.source_failures+1 if errors else 0
            # Recover recent gaps beyond the three-hour incremental window when the provider returns.
            self.need_backfill = len(errors)==len(SOURCE_CODES) or (
                bool(errors) and self.source_failures>0 and self.source_failures % 12 == 0)
        LOG.info("Collection cycle %s: status=%s, provider failures=%d, available depth=%s",
                 iso(issue), x["status"], len(errors), x["inference"]["status"])
        return True

    def _loop(self):
        while not self.stop.is_set():
            self.once()
            self.stop.wait(min(1800, self.interval*(2**min(max(self.failures-1,0),4))))

    def start(self):
        if self.worker is not None:
            raise RuntimeError("One collector per process")
        self.worker = Thread(target=self._loop, name="independent-collector", daemon=True)
        self.worker.start()

    def current(self):
        t = self.clock()
        with self.lock:
            data = copy.deepcopy(self.snapshot)
            error = self.pipeline_error
        if data is None:
            return make_snapshot(self.mode,[],t,self.estimate,internal_error=error or "waiting_for_first_poll",
                                 flow_ttl=self.flow_ttl,rain_ttl=self.rain_ttl)
        for item in [*data["flows"], data["rain"]]:
            ending = item.get("window_end_at") or item["observed_at"]
            if ending:
                item["age_seconds"] = _age(t, _parse_utc(ending))
                if item["age_seconds"] > (self.rain_ttl if item["unit"]=="mm" else self.flow_ttl):
                    item["status"] = "stale"
        stale_depth = _age(t, _parse_utc(data["generated_at"])) > self.interval*2+60
        if error or stale_depth:
            for g in [data,*data.get("horizons",[])]:
                g["inference"]["status"]="unavailable"
                g["inference"]["provenance"]["unavailable_reason"]=error or "cached_snapshot_stale"
                for row in g["depths"]:
                    row.update(value=None,status="unavailable")
            data["collection"]["internal_error"]=error or "cached_snapshot_stale"
        if data["status"]=="ok" and (data["inference"]["status"]!="experimental" or
              any(item["status"]!="ok" for item in [*data["flows"],data["rain"]])):
            data["status"]="partial"
        return data

    def health(self):
        t=self.clock()
        with self.lock:
            cyc, last, error, x = self.last_cycle, self.last_store_ok,self.pipeline_error,self.snapshot
        healthy = bool(last and not error and cyc and _age(t,cyc)<=max(2100,self.interval*3))
        body={"schema_version":1,"mode":self.mode,"status":"ok" if healthy else "degraded" if cyc else "starting",
              "last_collection_cycle_at":iso(cyc),"last_database_commit_at":iso(last),
              "snapshot_status":x["status"] if x else "unavailable"}
        return (200 if healthy else 503),body

def transport(collector, token):
    class Handler(BaseHTTPRequestHandler):
        server_version="RedDeerResearch/1"
        sys_version=""
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=="/healthz":
                self.reply(*collector.health())
                return
            if path not in ("/api/v1/snapshot", "/api/v1/history48h"):
                self.reply(404, {"error":"not_found"})
                return
            info=self.headers.get("Authorization","")
            if token and not hmac.compare_digest(info.encode("utf-8"), ("Bearer "+token).encode("utf-8")):
                self.reply(401,{"error":"authorization_required"}, challenge=True)
                return
            if path=="/api/v1/history48h":
                self.reply(200,collector.history48h())
                return
            self.reply(200,collector.current())

        def reply(self,status,body,challenge=False):
            raw=json.dumps(body,ensure_ascii=False,allow_nan=False,separators=(",",":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(raw)))
            self.send_header("Cache-Control","no-store")
            self.send_header("X-Content-Type-Options","nosniff")
            if challenge:
                self.send_header("WWW-Authenticate",'Bearer realm="RedDeerResearch"')
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError,ConnectionResetError):
                pass

        def log_message(self, format, *args):
            return  # Avoid logging private paths, arbitrary headers or bearer credentials.

    return Handler

def _read_local_dotenv():
    from pathlib import Path
    out={}
    candidates=[Path.cwd()/".env"]
    try:
        candidates.append(Path(__file__).resolve().parents[4]/".env")
    except IndexError:
        pass
    for p in candidates:
        if not p.is_file():
            continue
        for raw in p.read_text(encoding="utf-8",errors="ignore").splitlines():
            line=raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k,v=line.split("=",1)
            k=k.strip()
            v=v.strip().strip('"').strip("'")
            if k and k not in out:
                out[k]=v
        break
    return out

def tls_connection_string(allow_local_pg=False):
    import psycopg.conninfo as pg
    secret=os.environ.get("RDR_DEPLOYMENT_DSN")
    if not secret and allow_local_pg:
        dot=_read_local_dotenv()
        secret=dot.get("RDR_DEPLOYMENT_DSN")
        if not secret:
            host=(os.environ.get("PGHOST") or dot.get("PGHOST") or "").strip()
            dbname=(os.environ.get("PGDATABASE") or dot.get("PGDATABASE") or "").strip()
            user=(os.environ.get("PGUSER") or dot.get("PGUSER") or "").strip()
            port=(os.environ.get("PGPORT") or dot.get("PGPORT") or "5432").strip()
            pwd=os.environ.get("PGPASSWORD") if "PGPASSWORD" in os.environ else dot.get("PGPASSWORD","")
            if host.lower() in ("127.0.0.1","localhost","::1") and dbname and user:
                kw={"host":host,"port":port,"dbname":dbname,"user":user,"sslmode":"prefer",
                    "connect_timeout":"5","application_name":"rdr_research_snapshot"}
                if pwd:
                    kw["password"]=pwd
                return pg.make_conninfo(**kw)
    if not secret:
        raise ValueError("Define the deployment database secret")
    try:
        data=pg.conninfo_to_dict(secret)
        host=str(data.get("host") or "").strip().lower()
        is_loopback=host in ("127.0.0.1","localhost","::1")
        if not host or not data.get("dbname") or not data.get("user"):
            raise ValueError
        if allow_local_pg and is_loopback:
            data.setdefault("sslmode","prefer")
        else:
            if data.get("sslmode")!="verify-full":
                raise ValueError
            ca=data.get("sslrootcert") or os.environ.get("RDR_DB_SSLROOTCERT")
            if not ca or not (ca=="system" or os.path.isfile(ca)):
                raise ValueError
            data.update(sslrootcert=ca)
        data.update(connect_timeout=data.get("connect_timeout","5"),
                    application_name="rdr_research_snapshot")
        return pg.make_conninfo(**data)
    except Exception:
        raise ValueError("Use an explicit host/dbname/user, sslmode=verify-full and configured server CA") from None

def main(argv=None):
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument("--mode",choices=("live","demo"),default=os.environ.get("RDR_MODE","demo"))
    a.add_argument("--host",default=os.environ.get("RDR_HOST","127.0.0.1"))
    a.add_argument("--port",type=int,default=os.environ.get("RDR_PORT","8765"))
    a.add_argument("--interval",type=int,default=os.environ.get("RDR_POLL_SECONDS","600"))
    a.add_argument("--timeout",type=float,default=os.environ.get("RDR_SOURCE_TIMEOUT","10"))
    a.add_argument("--local-pg",action="store_true",default=os.environ.get("RDR_ALLOW_LOCAL_PG")=="1",
                   help="Allow loopback-only local PostgreSQL connection without remote TLS CA verification")
    a.add_argument("--init-db",action="store_true",help="Versioned schema migration only; exits without serving")
    a.add_argument("--once",action="store_true",help="Run one cycle, emit one JSON snapshot and exit")
    z=a.parse_args(argv)
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(message)s")
    try:
        if z.host!="127.0.0.1":
            a.error("Bind to 127.0.0.1 and put a TLS reverse proxy in front on the server")
        if z.mode not in ("live","demo") or not 300<=z.interval<=3600 or not 0<z.timeout<=30 or not 1<=z.port<=65535:
            a.error("Invalid instance configuration (poll interval must be 300–3600 seconds)")
        if z.init_db and z.mode!="live":
            a.error("--init-db may be used only with live mode and the dedicated deployment DB")
        if z.mode=="live":
            store=PgStore(tls_connection_string(allow_local_pg=z.local_pg))
            if z.init_db:
                store.initialize()
                LOG.info("Dedicated versioned deployment schema initialized.")
                return 0
            from .provider import poll
        else:
            store,poll=MemoryStore(),demo_poll
        model=FrozenModel()
        c=Collector(z.mode,store,poll,model,interval=z.interval,timeout=z.timeout)
        if z.once:
            c.restore()
            c.once()
            print(json.dumps(c.current(),ensure_ascii=True,allow_nan=False))
            return 0 if c.health()[0]==200 else 2
        token=os.environ.get("RDR_API_TOKEN","")
        if token and (not 24<=len(token)<=256 or re.fullmatch(r"[A-Za-z0-9._~+/\-]+=*",token) is None):
            a.error("Configured API token must be 24–256 characters in the Bearer alphabet")
        server=ThreadingHTTPServer((z.host,z.port),transport(c,token))
        c.restore()
        c.start()
        LOG.info("Serving a %s research snapshot on loopback port %d.", z.mode, server.server_address[1])
        try:
            server.serve_forever(poll_interval=.25)
        finally:
            c.stop.set()
            server.server_close()
    except KeyboardInterrupt:
        return 0
    except Exception as e:
        if isinstance(e,ValueError) and str(e) in ("Define the deployment database secret",
            "Use an explicit host/dbname/user, sslmode=verify-full and configured server CA"):
            LOG.error("%s.",e)
        else:
            LOG.error("Service could not start (%s); check local configuration, pinned model and database permissions.",type(e).__name__)
        return 2
    return 0

if __name__=="__main__":
    sys.exit(main())
