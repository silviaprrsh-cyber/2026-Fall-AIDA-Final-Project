"""Causal route approximation for the frozen V4 architecture; not its historical View."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import hashlib
import math
from .schema import aware, iso

D, L, M = "05CB007", "05CB001", "05CC007"
REQUIRED_HOURS = 84
PIN = "611348b30e5312f3aba087c1c327a58cdf21c853afc89bcaf52aab4052c66479"
METHOD = "v4_60_20_20_frozen_nominal_short_routes_source_only_medicine_v1"

def _stamp(t):
    return math.floor(aware(t).timestamp())

def _utc(t):
    return datetime.fromtimestamp(t, timezone.utc)

def _ceil_div(n, d):
    return -(n // -d)

def _known(o, asof):
    return (o.observed_at <= asof and o.retrieved_at <= asof and
            (o.available_at is None or o.available_at <= asof))

class FrozenModel:
    """Load only the pinned state dictionary; never use a web- or client-supplied model path."""
    def __init__(self, path=None):
        import torch
        from .v4_chain import RoutingDepthChain
        p = Path(path) if path is not None else Path(__file__).with_name("model_60_20_20.pt")
        if hashlib.sha256(p.read_bytes()).hexdigest() != PIN:
            raise ValueError("The fixed V4 model hash does not match")
        torch.set_num_threads(1)
        state = torch.load(p, weights_only=True, map_location="cpu")
        if any(not torch.isfinite(v).all() for v in state.values()):
            raise ValueError("Non-finite model parameters")
        model = RoutingDepthChain(state["center"], state["scale"], state["distances"])
        model.load_state_dict(state, strict=True)
        self.model = model.eval()
        self.torch = torch

    def __call__(self, values):
        if len(values) != 12 or any(not math.isfinite(x) or x < 0 for x in values):
            raise ValueError("Expected 12 finite nonnegative V4 inputs")
        with self.torch.inference_mode():
            out = self.model(self.torch.as_tensor([values], dtype=self.torch.float32))[0].tolist()
        if len(out) != 6 or any(not math.isfinite(x) or x < 0 for x in out):
            raise ValueError("Invalid model output")
        return out

def _rain_at(source, rain, asof):
    end = (source // 3600)*3600
    seen = 0
    total = 0.0
    windows = []
    for i in range(1, 25):
        start = end - 3600*i
        o = rain.get(start)
        if o and start+3600 <= asof and start+3600 <= source:
            total += o.value
            seen += 1
        if i in (1, 6, 24):
            windows.append(total)
    return windows, seen, end-3600

def _lag_centers(flow, first, last):
    """Upstream observations and past-only six-hour rise; preserve the trained rule."""
    from bisect import bisect_left, bisect_right
    times = sorted(flow)
    gaps = [0]
    for j in range(1, len(times)):
        gaps.append(gaps[-1] + int(times[j]-times[j-1] > 1800))
    for j in range(bisect_left(times, first), bisect_right(times, last)):
        s = times[j]
        lag = 603
        for k in range(4):
            previous = s - 21600 - k*300
            a = bisect_left(times, previous)
            if a == len(times) or times[a] != previous:
                continue
            baseline = flow[previous].value
            expected = (s - previous)//300 + 1
            if (j-a+1) >= 0.75*expected and gaps[j] == gaps[a]:
                rise = flow[s].value - baseline
                weight = max(0.0, min(1.0, (rise-.6)/.6, (rise/max(baseline,.1)-.05)/.05))
                lag = math.floor(603 - 243*weight + .5)
            break
        yield s, s + lag*300

def valid_at(issue, hours=0):
    cut = _stamp(issue)//300*300
    return _utc(cut+hours*3600)

def features(rows, issue, hours=0):
    """Return (12 values or None, public provenance). Never read 05CC002 for inference."""
    t0 = aware(issue)
    if hours not in (0,3,9):
        raise ValueError("Unknown estimate horizon")
    t = _stamp(valid_at(t0,hours))
    asof = t0.timestamp()
    if t-540*60 > asof or t-630*60 > asof:
        return None, {"method":METHOD, "valid_at":iso(_utc(t)), "unavailable_reason":"future_upstream_observations_required",
                      "dickson_requested_at":iso(_utc(t-630*60)), "little_requested_at":iso(_utc(t-540*60))}
    q = {k: {} for k in (D, L, M)}
    rain = {}
    for o in rows:
        if not _known(o, t0):
            continue
        clock = _stamp(o.observed_at)
        if o.observed_at.microsecond or clock % (300 if o.kind=="flow" else 3600):
            continue
        if o.kind == "rain":
            rain[clock] = o
        elif o.station_id in q:
            q[o.station_id][clock] = o
    td, tl = t-630*60, t-540*60
    d, l = q[D].get(td), q[L].get(tl)
    a, ac, ax = _rain_at(td, rain, asof)
    b, bc, bx = _rain_at(tl, rain, asof)
    s0, s1 = t-639*300, t-324*300  # min/max 30–50h15 center ±3h
    m = q[M]
    observed_candidate = sum(s in m for s in range(s0, s1+1, 300))
    candidate_count = (s1-s0)//300+1
    candidates = sorted(s for s in m if s0<=s<=s1)
    max_gap = max((b0-a0 for a0,b0 in zip(candidates,candidates[1:])), default=0)
    # Missing even a minority of candidate parcels can materially bias peak estimates.
    # A fully observed candidate span is required for this intentionally conservative live adapter.
    m_complete = observed_candidate == candidate_count
    audit = {"valid_at":iso(_utc(t)), "method":METHOD, "dickson_zero_imputed":d is None,
             "dickson_flow_used_at": iso(d.observed_at) if d else None,
             "little_flow_used_at": iso(l.observed_at) if l else None,
             "dickson_requested_at":iso(_utc(td)), "little_requested_at":iso(_utc(tl)),
             "dickson_rain_last_bucket":iso(_utc(ax)), "little_rain_last_bucket":iso(_utc(bx)),
             "dickson_rain_hours_present":ac, "little_rain_hours_present":bc,
             "medicine_candidate_coverage":{"observed":observed_candidate,"required":candidate_count,
                                             "largest_between_donors_seconds":max_gap},
             "medicine_latest_source_at":None,"medicine_first_source_at":None,
             "medicine_contributing_parcels":0,"medicine_weighted_rain_hours_present":None}
    if hours and d is None:
        audit["unavailable_reason"] = "dickson_exact_sample_unavailable_for_projection"
        return None, audit
    if l is None:
        audit["unavailable_reason"] = ("little_exact_sample_unavailable_at_issuance"
                                      if hours else "little_exact_nominal_sample_absent")
        return None, audit
    if hours and (ac != 24 or bc != 24):
        audit["unavailable_reason"] = "short_route_rain_window_incomplete_for_projection"
        return None, audit
    if not m_complete:
        audit["unavailable_reason"] = "medicine_candidate_source_span_incomplete"
        return None, audit
    meter = 0.0
    rain_m = [0.0,0.0,0.0]
    rain_seen, first, last, n, m_all_rain = 0.0, None, None, 0, True
    for source, center in _lag_centers(m, s0, s1):
        k = (t-center)//300
        if abs(k)>36:
            continue
        w = (37-abs(k))/1369
        mass = m[source].value * w
        r, seen, _ = _rain_at(source, rain, asof)
        meter += mass
        rain_seen += mass*seen
        m_all_rain &= seen == 24
        for j, amt in enumerate(r):
            rain_m[j] += amt*mass
        first = source if first is None else first
        last = source
        n += 1
    if not n:
        audit["unavailable_reason"] = "medicine_no_arriving_parcels"
        return None, audit
    if meter:
        rain_m = [j/meter for j in rain_m]
    audit.update(medicine_first_source_at=iso(_utc(first)),medicine_latest_source_at=iso(_utc(last)),
                 medicine_contributing_parcels=n,
                 medicine_weighted_rain_hours_present=(rain_seen/meter if meter else None))
    if hours and not m_all_rain:
        audit["unavailable_reason"] = "medicine_rain_window_incomplete_for_projection"
        return None, audit
    return [d.value if d else 0.0,l.value,meter,*a,*b,*rain_m],audit
