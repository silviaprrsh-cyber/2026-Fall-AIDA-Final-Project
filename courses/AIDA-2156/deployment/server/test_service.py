"""Network-local, PostgreSQL-free unit and contract tests."""
from dataclasses import replace
from datetime import datetime, timedelta
import json
import os
from http.server import ThreadingHTTPServer
from threading import Event,Thread
from urllib.error import HTTPError
from urllib.request import urlopen,Request
import unittest
from .inference import FrozenModel, features, valid_at
from .schema import UTC, Observation, FLOWS
from .service import Collector, demo_poll, make_snapshot, transport, tls_connection_string
from .store import MemoryStore
from .provider import HYDRO, RAIN, parse_page

T=datetime(2026,11,20,3,42,15,tzinfo=UTC)
def local_model(vals):
    return [sum(vals)/100+q/10 for q in range(6)]

class TimingTests(unittest.TestCase):
    def setUp(self):
        self.rows,_=demo_poll(T)

    def test_provenance_now_and_projection(self):
        for h in (0,3,9):
            target=valid_at(T,h)
            data,p=features(self.rows,T,h)
            self.assertEqual(len(data),12)
            self.assertEqual(datetime.fromisoformat(p["dickson_flow_used_at"]),target-timedelta(hours=10.5))
            self.assertEqual(datetime.fromisoformat(p["little_flow_used_at"]),target-timedelta(hours=9))
            self.assertLess(datetime.fromisoformat(p["medicine_latest_source_at"]),T)
            for name in ("dickson","little"):
                self.assertLessEqual(datetime.fromisoformat(p[name+"_rain_last_bucket"])+timedelta(hours=1),
                                     datetime.fromisoformat(p[name+"_flow_used_at"]))
        self.assertEqual(datetime.fromisoformat(p["little_requested_at"]),valid_at(T,0))

    def test_late_or_missing_current_little_sample_abstains_at_nine(self):
        required=valid_at(T,0)
        little=[o for o in self.rows if o.station_id=="05CB001" and o.observed_at==required][0]
        kept=[o for o in self.rows if o!=little]
        variants=(kept, kept+[replace(little,retrieved_at=T+timedelta(seconds=1))],
                  kept+[replace(little,available_at=T+timedelta(seconds=1))])
        for rows in variants:
            x, audit = features(rows,T,9)
            self.assertIsNone(x)
            self.assertEqual(audit["unavailable_reason"],"little_exact_sample_unavailable_at_issuance")
            self.assertEqual(datetime.fromisoformat(audit["little_requested_at"]),required)
            self.assertIsNotNone(features(rows,T,3)[0])
            wire=make_snapshot("demo",rows,T,local_model)["horizons"][1]
            self.assertEqual(wire["hours"],9)
            self.assertEqual(datetime.fromisoformat(wire["inference"]["valid_at"]),valid_at(T,9))
            self.assertTrue(all(p["value"] is None for p in wire["depths"]))
        # Same retrieval instant is eligible; no future sample is necessary.
        self.assertIsNotNone(features(kept+[replace(little,retrieved_at=T,available_at=T)],T,9)[0])

    def test_past_data_cannot_change_using_terminal_or_unavailable_revisions(self):
        changed=[replace(o,value=800.) if o.station_id=="05CC002" else o for o in self.rows]
        changed += [replace(o,value=999.,available_at=T+timedelta(hours=1)) for o in self.rows if o.kind=="flow"]
        for h in (0,3,9):
            self.assertEqual(features(self.rows,T,h),features(changed,T,h))

    def test_missing_D_observation_not_zero(self):
        rows=[o for o in self.rows if o.station_id!="05CB007"]
        s=make_snapshot("demo",rows,T,local_model)
        self.assertIsNone(s["flows"][0]["value"])
        self.assertEqual(s["flows"][0]["status"],"missing")
        self.assertTrue(s["inference"]["provenance"]["dickson_zero_imputed"])
        self.assertEqual(s["depths"][-1]["status"],"experimental")
        self.assertTrue(all(row["value"] is None for g in s["horizons"] for row in g["depths"]))

    def test_stale_missing_and_bad_transport(self):
        rows=[o for o in self.rows if o.station_id!="05CB001"]
        old=[o for o in rows if o.observed_at<T-timedelta(hours=5)]
        s=make_snapshot("live",old,T,local_model,errors=["flow:05CB001","secret_or_path"])
        self.assertEqual(s["status"],"partial")
        self.assertEqual(s["collection"]["failed_sources"],["flow:05CB001"])
        self.assertTrue(all(it["value"] is None for it in s["depths"]))
        self.assertEqual(s["flows"][0]["status"],"stale")

    def test_frozen_model_http_response_contract(self):
        model=FrozenModel()
        s=make_snapshot("demo",self.rows,T,model)
        self.assertEqual(s["schema_version"],1)
        self.assertEqual(len(s["depths"]),6)
        self.assertEqual(s["depths"][-1]["kind"],"terminal_stage_proxy")
        self.assertEqual(s["depths"][-1]["station_id"],"05CC002")
        self.assertEqual(s["horizons"][0]["hours"],3)
        self.assertTrue(all(x["value"] is not None for x in s["horizons"][0]["depths"]))
        self.assertEqual(s["horizons"][1]["hours"],9)
        self.assertTrue(all(x["value"] is not None for x in s["horizons"][1]["depths"]))

class RuntimeTests(unittest.TestCase):
    def test_independent_cycles_and_transport(self):
        reached=Event()
        calls=[]
        def source(t,h,timeout):
            calls.append(h)
            if len(calls)>=3:
                reached.set()
            return demo_poll(t,h,timeout)
        collector=Collector("demo",MemoryStore(),source,local_model,interval=.03)
        collector.start()
        srv,worker=None,None
        try:
            self.assertTrue(reached.wait(4),"worker must start without any client")
            self.assertEqual(calls[:3],[84,3,3])
            srv=ThreadingHTTPServer(("127.0.0.1",0),transport(collector,"aoq0-private-fixture-token"))
            worker=Thread(target=srv.serve_forever,kwargs={"poll_interval":.01},daemon=True)
            worker.start()
            base="http://127.0.0.1:"+str(srv.server_address[1])
            with urlopen(base+"/healthz",timeout=3) as f:
                self.assertEqual(f.status,200)
            with self.assertRaises(HTTPError) as e:
                urlopen(base+"/api/v1/snapshot",timeout=3)
            self.assertEqual(e.exception.code,401)
            with urlopen(Request(base+"/api/v1/snapshot",headers={
                         "Authorization":"Bearer aoq0-private-fixture-token"}),timeout=3) as f:
                d=json.load(f)
            self.assertEqual(d["mode"],"demo")
            self.assertEqual(len(d["flows"]),4)
            self.assertEqual(len(d["horizons"]),2)
        finally:
            collector.stop.set()
            collector.worker.join(timeout=5)
            if srv is not None:
                srv.shutdown();srv.server_close()
            if worker is not None:
                worker.join(timeout=2)

    def test_restore_and_degrade_when_database_fails(self):
        class FailRead(MemoryStore):
            failed=False
            def read(self,since,asof):
                if self.failed:
                    raise ValueError("do not leak backend information")
                return super().read(since,asof)
        pg=FailRead()
        c=Collector("demo",pg,demo_poll,local_model,clock=lambda:T)
        self.assertTrue(c.once())
        after=Collector("demo",pg,demo_poll,local_model,clock=lambda:T+timedelta(minutes=22))
        after.restore()
        self.assertEqual(after.current()["generated_at"],c.current()["generated_at"])
        self.assertTrue(all(row["value"] is None for row in after.current()["depths"]))
        self.assertTrue(all(row["value"] is None for g in after.current()["horizons"] for row in g["depths"]))
        pg.failed=True
        self.assertFalse(after.once())
        self.assertEqual(after.health()[0],503)
        self.assertEqual(after.current()["collection"]["internal_error"],"database_unavailable")

class ProviderTests(unittest.TestCase):
    def test_release_and_repeat_semantics(self):
        hours=timedelta(hours=1)
        at=T.replace(minute=0,second=0)
        rain={"type":"FeatureCollection","features":[{"properties":{"CLIMATE_IDENTIFIER":"3025484",
              "UTC_DATE":at.strftime("%Y-%m-%dT%H:%M:%S"),"PRECIP_AMOUNT":.1,"PRECIP_AMOUNT_FLAG":None}}]}
        early=parse_page(rain,RAIN,"3025484",T-2*hours,T,T)[0]
        late=parse_page(rain,RAIN,"3025484",T-2*hours,T,T+2*hours)[0]
        self.assertEqual(early.available_at,at+hours)
        self.assertEqual(late.available_at,early.available_at)
        s=MemoryStore()
        s.save([early,late])
        self.assertEqual(s.read(at,T),[])
        self.assertEqual(s.read(at,T+2*hours)[0].retrieved_at,T)

    def test_empty_and_mismatched_station_are_not_zero(self):
        base={"type":"FeatureCollection","features":[{"properties":{"STATION_NUMBER":"05CB001",
              "DATETIME":"2026-11-20T03:40:00Z","DISCHARGE":None}}]}
        self.assertEqual(parse_page(base,HYDRO,"05CB001",T-timedelta(hours=1),T,T),[])
        with self.assertRaises(ValueError):
            parse_page(base,HYDRO,"05CB007",T-timedelta(hours=1),T,T)

if __name__=="__main__":
    unittest.main()
