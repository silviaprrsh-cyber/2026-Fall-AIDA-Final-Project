"""Retrospective, discharge-only hydrograph association, not a forecasting dataset.

Standard library + NumPy. Raw downloads, models and databases are read-only.
See the English/Chinese companions and generated READMEs for interpretation.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import math

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
DATA = ROOT / "courses/AIDA-2156/data"
RUNS = ("20261103T070414Z", "20261111T030808Z")
STATIONS = ("05CB007", "05CB001", "05CC007", "05CC002")
SOURCES = STATIONS[:3]
TARGET = STATIONS[3]
NAMES = dict(zip(STATIONS, ("Dickson", "Little Red Deer", "Medicine", "Red Deer terminal")))
LIMITS = {"05CB007": (2., 30.), "05CB001": (1., 36.), "05CC007": (6., 144.)}
EXPECTED = dict(zip(STATIONS, (156057, 157682, 156388, 158574)))


def stamp(hour):
    if hour is None or not np.isfinite(hour):
        return ""
    return datetime.fromtimestamp(round(float(hour)*3600), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_hour(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()/3600


def clean(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return round(float(value), 6) if np.isfinite(value) else ""
    return value


def write_csv(path, rows, fields=None):
    rows = iter(rows)
    first = next(rows, None)
    if fields is None:
        fields = list(first or {})
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        if first is not None:
            writer.writerow({k: clean(v) for k, v in first.items()})
        for row in rows:
            writer.writerow({k: clean(v) for k, v in row.items()})


@dataclass
class Series:
    station: str
    time: np.ndarray
    q: np.ndarray
    flags: list
    approval: list
    provenance: np.ndarray
    stats: dict
    hour: np.ndarray | None = None
    smooth: np.ndarray | None = None
    segment: np.ndarray | None = None


def read_sources():
    """Latest dated run wins overlapping numeric Q; keep older unmatched tails."""
    data, manifest = {}, []
    next_id = 0
    for station in STATIONS:
        merged = {}
        raw_count = nonnumeric = duplicate = revisions = quality_revisions = 0
        for run in RUNS:
            folder = DATA / "sources/eccc_wateroffice/raw/unit_values" / run / station
            for file in sorted(folder.glob("*.csv")):
                next_id += 1
                fid = next_id
                raw = file.read_bytes()
                manifest.append({"source_file_id": fid, "station_id": station, "acquisition_run": run,
                                 "path": file.relative_to(ROOT).as_posix(), "bytes": len(raw),
                                 "sha256": hashlib.sha256(raw).hexdigest()})
                with file.open(encoding="utf-8-sig", newline="") as handle:
                    for row in csv.reader(handle):
                        if len(row) < 9 or row[2] != "47":
                            continue
                        raw_count += 1
                        try:
                            q = float(row[3])
                            if not math.isfinite(q):
                                raise ValueError
                        except ValueError:
                            nonnumeric += 1
                            continue
                        t = row[1]
                        flags = ";".join(f"{key}={value}" for key, value in
                                         zip(("qualifier", "symbol", "grade", "qualifiers"),
                                             (row[4], row[5], row[7], row[8])) if value)
                        record = (q, flags, row[6], fid)
                        if t in merged:
                            duplicate += 1
                            revisions += merged[t][0] != q
                            quality_revisions += merged[t][1:3] != record[1:3]
                        merged[t] = record
        times = sorted(merged)
        records = [merged[t] for t in times]
        t = np.array([parse_hour(x) for x in times])
        q = np.array([x[0] for x in records])
        stats = {"numeric_unique_records": len(t), "raw_q_parameter_rows": raw_count,
                 "nonnumeric_raw_q_rows": nonnumeric, "duplicate_numeric_keys": duplicate,
                 "overlapping_q_value_revisions": revisions,
                 "overlapping_quality_revisions": quality_revisions,
                 "first": times[0], "last": times[-1],
                 "quality_flag_counts": dict(Counter(x[1] or "none" for x in records)),
                 "approval_counts": dict(Counter(x[2] for x in records)),
                 "q_min": float(q.min()), "q_max": float(q.max()),
                 "gaps_over_1h": int(np.count_nonzero(np.diff(t) > 1.00001)),
                 "largest_gap_hours": float(np.diff(t).max())}
        data[station] = Series(station, t, q, [x[1] for x in records], [x[2] for x in records],
                               np.array([x[3] for x in records]), stats)
        print(f"Read {station}: {len(t):,} numeric Q records; revisions={revisions}", flush=True)
    return data, manifest


def finite_runs(values):
    mask = np.isfinite(values)
    boundaries = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return list(zip(boundaries[::2], boundaries[1::2]))


def hourly(series, first, last):
    """Hourly medians need >=3 measurements; never interpolate missing Q."""
    grid = np.arange(first, last+1, dtype=float)
    bins = np.floor(series.time).astype(int)-first
    changes = np.r_[0, np.flatnonzero(np.diff(bins))+1, len(bins)]
    result = np.full(len(grid), np.nan)
    for a, b in zip(changes[:-1], changes[1:]):
        if b-a >= 3:
            result[bins[a]] = np.median(series.q[a:b])
    smooth = result.copy()
    segments = np.full(len(grid), -1, dtype=int)
    for sid, (a, b) in enumerate(finite_runs(result)):
        segments[a:b] = sid
        # A three-hour median removes single-hour spikes without a peak-distance rule.
        if b-a >= 3:
            smooth[a+1:b-1] = np.median(np.lib.stride_tricks.sliding_window_view(result[a:b], 3), axis=1)
    series.hour, series.smooth, series.segment = grid+0.5, smooth, segments


def detect_events(series, relative_prominence=.08):
    """Prominence-based complete waves; no fixed exclusion interval between peaks."""
    y, grid = series.smooth, series.hour
    events = []
    floor = .2 if series.station in ("05CB007", "05CC002") else .015
    for sid, (a, b) in enumerate(finite_runs(y)):
        if b-a < 12:
            continue
        diff = np.diff(y[a:b])
        noise = np.median(np.abs(diff-np.median(diff)))*1.4826
        # Collapsing equal-valued runs allows a plateau to have a central peak.
        starts = np.r_[a, a+1+np.flatnonzero(np.diff(y[a:b]) != 0)]
        ends = np.r_[starts[1:], b]
        candidates = []
        for j in range(1, len(starts)-1):
            u, v = int(starts[j]), int(ends[j])
            if not (y[u] > y[starts[j-1]] and y[u] > y[starts[j+1]]):
                continue
            peak = (u+v-1)//2
            lo, hi = max(a, peak-240), min(b-1, peak+240)
            # Standard topographic prominence, bounded to avoid old unrelated peaks.
            greater_left = np.flatnonzero(y[lo:u] > y[peak])
            greater_right = np.flatnonzero(y[v:hi+1] > y[peak])
            if len(greater_left): lo += int(greater_left[-1])
            if len(greater_right): hi = v+int(greater_right[0])
            left_min = lo+int(np.argmin(y[lo:peak+1]))
            right_min = peak+int(np.argmin(y[peak:hi+1]))
            base = max(y[left_min], y[right_min])
            prominence = y[peak]-base
            if prominence < max(floor, relative_prominence*max(base, floor), 6*noise):
                continue
            threshold = base+.1*prominence
            left = [k for k in range(left_min, peak-2) if np.all(y[k:k+3] <= threshold)]
            right = [k for k in range(peak+1, right_min+1) if k+3 <= b and np.all(y[k:k+3] <= threshold)]
            if not left or not right:
                continue
            start, end = left[-1]+3, right[0]
            if peak-start < 2 or end-peak < 3 or end-start < 8:
                continue
            candidates.append({"station_id": series.station, "segment_id": sid,
                "start_index": start, "peak_index": peak, "end_index": end,
                "start_h": grid[start], "peak_h": grid[peak], "end_h": grid[end],
                "baseline_q": base, "peak_q": y[peak], "prominence_q": prominence,
                "threshold_q": threshold, "noise_q": noise,
                "duration_hours": end-start})
        # Suppress nested shoulders only when >75% of the smaller interval overlaps.
        # Separate waves can be much closer than 72 hours.
        selected = []
        for event in sorted(candidates, key=lambda e: e["prominence_q"], reverse=True):
            if any(max(0, min(event["end_h"], old["end_h"])-max(event["start_h"], old["start_h"])) /
                   min(event["duration_hours"], old["duration_hours"]) > .75 for old in selected):
                continue
            selected.append(event)
        events.extend(selected)
    events.sort(key=lambda x: x["peak_h"])
    for n, event in enumerate(events, 1):
        event["event_id"] = f"{series.station}_W{n:04d}"
    return events


def correlation(a, b):
    good = np.isfinite(a) & np.isfinite(b)
    if good.sum() < 8 or np.std(a[good]) < 1e-9 or np.std(b[good]) < 1e-9:
        return np.nan
    return float(np.corrcoef(a[good], b[good])[0, 1])


def sample_shape(series, event, size=61):
    # Preserve both limbs with the same number of rise/fall samples.
    t = np.r_[np.linspace(event["start_h"], event["peak_h"], size//2+1),
              np.linspace(event["peak_h"], event["end_h"], size//2+1)[1:]]
    return np.interp(t, series.hour, series.smooth)


def compare_wave(source, target, se, te):
    lags = np.array([te[k]-se[k] for k in ("start_h", "peak_h", "end_h")])
    bounds = LIMITS[source.station]
    peak_lag = lags[1]
    if not bounds[0] <= peak_lag <= bounds[1]:
        return None
    shift_time = target.hour[te["start_index"]:te["end_index"]+1]-peak_lag
    source_y = np.interp(shift_time, source.hour, source.smooth, left=np.nan, right=np.nan)
    target_y = target.smooth[te["start_index"]:te["end_index"]+1]
    coverage = float(np.mean(np.isfinite(source_y)))
    warped = correlation(sample_shape(source, se), sample_shape(target, te))
    shift = correlation(source_y, target_y)
    duration_ratio = se["duration_hours"]/te["duration_hours"]
    spread = float(lags.max()-lags.min())
    limit_spread = 36 if source.station == "05CC007" else 20
    score = (.65*shift+.35*warped-.12*abs(math.log(duration_ratio))
             -.10*min(spread/limit_spread, 2)) if np.isfinite(shift+warped) else -9.
    # A weak empirical prior helps disambiguate, but cannot replace the waveform gates.
    if source.station == "05CB007": score -= .015*abs(peak_lag-12)
    if source.station == "05CB001": score -= .008*abs(peak_lag-9)
    reasons = []
    if coverage < .98: reasons.append("source_hourly_gap")
    if np.any(lags <= 0): reasons.append("noncausal_boundary")
    if np.any(lags > bounds[1]*1.5): reasons.append("boundary_lag_too_long")
    if spread > limit_spread: reasons.append("inconsistent_limb_lags")
    if not .40 <= duration_ratio <= 2.5: reasons.append("incompatible_duration")
    threshold = .82 if source.station != "05CC007" else .88
    if not np.isfinite(shift) or shift < threshold: reasons.append("weak_shifted_whole_wave")
    if not np.isfinite(warped) or warped < .88: reasons.append("weak_rise_fall_shape")
    if score < (.66 if source.station != "05CC007" else .72): reasons.append("weak_combined_score")
    return {"source_event": se, "score": score, "shift_correlation": shift,
            "shape_correlation": warped, "coverage": coverage, "duration_ratio": duration_ratio,
            "start_lag_hours": lags[0], "peak_lag_hours": lags[1], "end_lag_hours": lags[2],
            "lag_spread_hours": spread, "reasons": reasons}


def match_events(data, events):
    audits, accepted = [], {s: [] for s in SOURCES}
    for station in SOURCES:
        used, last_source_end, last_target_end = set(), -np.inf, -np.inf
        for te in events[TARGET]:
            candidates = [c for se in events[station] if (c := compare_wave(data[station], data[TARGET], se, te)) is not None]
            candidates.sort(key=lambda c: c["score"], reverse=True)
            viable = []
            for c in candidates:
                se = c["source_event"]
                if se["event_id"] in used: c["reasons"].append("source_event_already_used")
                if se["start_h"] <= last_source_end or te["start_h"] <= last_target_end:
                    c["reasons"].append("overlapping_or_nonmonotone_event")
                if not c["reasons"]: viable.append(c)
            best = viable[0] if viable else (candidates[0] if candidates else None)
            alternative = viable[1] if len(viable) > 1 else None
            ambiguous = alternative is not None and best["score"]-alternative["score"] < .04
            status = "accepted_wave_association" if viable and not ambiguous else ("ambiguous_wave" if ambiguous else "no_credible_wave")
            row = {"source_station": station, "target_event_id": te["event_id"], "status": status,
                   "target_start_utc": stamp(te["start_h"]), "target_peak_utc": stamp(te["peak_h"]),
                   "target_end_utc": stamp(te["end_h"]), "target_peak_q_m3_s": te["peak_q"],
                   "candidate_count": len(candidates), "viable_candidate_count": len(viable),
                   "source_event_id": "", "source_start_utc": "", "source_peak_utc": "", "source_end_utc": "",
                   "start_lag_hours": "", "peak_lag_hours": "", "end_lag_hours": "", "lag_spread_hours": "",
                   "shift_correlation": "", "shape_correlation": "", "score": "", "duration_ratio": "",
                   "alternative_source_event_id": alternative["source_event"]["event_id"] if alternative else "",
                   "score_margin": best["score"]-alternative["score"] if alternative else "",
                   "rejection_reasons": "no_source_peak_in_search_window" if best is None else ";".join(best["reasons"])}
            if best:
                se = best["source_event"]
                row.update({"source_event_id": se["event_id"], "source_start_utc": stamp(se["start_h"]),
                            "source_peak_utc": stamp(se["peak_h"]), "source_end_utc": stamp(se["end_h"])})
                for key in ("start_lag_hours", "peak_lag_hours", "end_lag_hours", "lag_spread_hours",
                            "shift_correlation", "shape_correlation", "score", "duration_ratio"):
                    row[key] = best[key]
                if status == "accepted_wave_association":
                    accepted[station].append({"target": te, **best})
                    used.add(se["event_id"])
                    last_source_end, last_target_end = se["end_h"], te["end_h"]
            audits.append(row)
        print(f"Matched {station}: {len(accepted[station])}/{len(events[TARGET])} terminal waves", flush=True)
    return audits, accepted


def segment_at(series, time):
    i = np.floor(time-series.hour[0]+.5).astype(int)
    valid = (i >= 0) & (i < len(series.segment))
    result = np.full(np.shape(time), -1, dtype=int)
    result[valid] = series.segment[i[valid]]
    return result


def directional_limb_matches(data):
    """Independent partial-wave tier for release steps and distorted recessions.

    A 36-hour observed window must agree in both levels and six-hour changes.
    Flat/ramp windows without an identifiable time shift are rejected.
    """
    target = data[TARGET]
    y = target.smooth
    dy = np.full(len(y), np.nan)
    dy[3:-3] = y[6:]-y[:-6]
    centers = []
    for i in range(21, len(y)-21):
        local = np.abs(dy[i-6:i+7])
        if not np.all(np.isfinite(local)):
            continue
        if abs(dy[i]) < max(.03*max(y[i], 1), .3):
            continue
        if i-6+int(np.argmax(local)) != i:
            continue
        if not np.all(np.isfinite(y[i-18:i+19])):
            continue
        centers.append(i)
    audits, matches = [], {s: [] for s in SOURCES}
    for station in SOURCES:
        source = data[station]
        sy = source.smooth
        sd = np.full(len(sy), np.nan)
        sd[3:-3] = sy[6:]-sy[:-6]
        low, high = [int(x) for x in LIMITS[station]]
        used_source_features = set()
        last_source_center = -np.inf
        for number, i in enumerate(centers, 1):
            candidates = []
            for lag in range(low, high+1):
                j = i-lag
                if j < 21 or j+21 >= len(sy):
                    continue
                if not np.all(np.isfinite(sy[j-21:j+22])):
                    continue
                if sd[j]*dy[i] <= 0 or abs(sd[j]) < max(.01*max(sy[j], .01), .01):
                    continue
                a = correlation(y[i-18:i+19], sy[j-18:j+19])
                b = correlation(dy[i-18:i+19], sd[j-18:j+19])
                if np.isfinite(a+b):
                    candidates.append({"lag": lag, "raw": a, "derivative": b, "score": .5*(a+b), "index": j})
            candidates.sort(key=lambda c: c["score"], reverse=True)
            best = candidates[0] if candidates else None
            row = {"source_station": station, "limb_id": f"{station}_L{number:04d}",
                   "target_center_utc": stamp(target.hour[i]), "target_window_start_utc": stamp(target.hour[i-18]),
                   "target_window_end_utc": stamp(target.hour[i+18]), "target_center_q_m3_s": y[i],
                   "direction": "rise" if dy[i] > 0 else "fall", "target_six_hour_change": dy[i],
                   "source_center_utc": "", "lag_hours": "", "level_shape_correlation": "",
                   "six_hour_change_correlation": "", "score": "", "alternative_lag_margin": "",
                   "shift_comparison_status": "no_candidate",
                   "near_optimal_lag_min_hours": "", "near_optimal_lag_max_hours": "",
                   "status": "no_credible_limb", "rejection_reasons": "no_gap_free_candidate"}
            if best:
                margin_candidates = [c for c in candidates if abs(c["lag"]-best["lag"]) > 3]
                margin = best["score"]-margin_candidates[0]["score"] if margin_candidates else np.nan
                close = [c["lag"] for c in candidates if c["score"] >= best["score"]-.015]
                j = best["index"]
                feature = j-3+int(np.argmax(np.abs(sd[j-3:j+4])))
                reasons = []
                if best["raw"] < (.9 if station != "05CC007" else .94): reasons.append("weak_level_shape")
                if best["derivative"] < (.75 if station != "05CC007" else .85): reasons.append("weak_directional_change_shape")
                if np.isfinite(margin) and margin < .015: reasons.append("poorly_identified_shift")
                if best["lag"] in (low, high): reasons.append("search_boundary_solution")
                if feature in used_source_features: reasons.append("source_directional_feature_already_used")
                if source.hour[j] <= last_source_center: reasons.append("nonmonotone_anchor")
                row.update({"source_center_utc": stamp(source.hour[j]), "lag_hours": best["lag"],
                            "level_shape_correlation": best["raw"], "six_hour_change_correlation": best["derivative"],
                            "score": best["score"], "alternative_lag_margin": margin,
                            "shift_comparison_status": "distant_alternatives_compared" if margin_candidates else "no_valid_distant_alternative_restricted_support",
                            "near_optimal_lag_min_hours": min(close), "near_optimal_lag_max_hours": max(close),
                            "rejection_reasons": ";".join(reasons)})
                if not reasons:
                    row["status"] = "accepted_directional_limb_only"
                    used_source_features.add(feature)
                    last_source_center = source.hour[j]
                    matches[station].append({"target_h": target.hour[i], "source_h": source.hour[j],
                        "target_segment": target.segment[i], "source_segment": source.segment[j],
                        "lag": best["lag"], "limb_id": row["limb_id"], "score": best["score"]})
            audits.append(row)
        print(f"Directional windows {station}: {len(matches[station])}/{len(centers)} accepted partial-wave anchors", flush=True)
    return audits, matches


def assignments(source, target, accepted, limbs=(), *, include_hints=False):
    """Infer times only, then pick actual Q within half a five-minute interval.

    ``include_hints`` also preserves the proposed association before observation
    lookup and chronology checks, so a database view can perform those checks.
    The default result and the original matching calculation are unchanged.
    """
    n = len(target.time)
    lag = np.full(n, np.nan)
    method = np.full(n, "unmatched_no_supported_lag", dtype=object)
    event_id = np.full(n, "", dtype=object)
    support_days = np.full(n, np.nan)
    confidence = np.full(n, "none", dtype=object)
    target_seg = segment_at(target, target.time)
    # Entire observed terminal range is represented, including long quiet/low-flow periods.
    # Only the two short routes have a user-supplied empirical fallback.
    if source.station in ("05CB007", "05CB001"):
        q25, q75 = np.quantile(target.q, [.25, .75])
        if source.station == "05CB007":
            lag[:] = np.interp(target.q, [q25, q75], [14., 10.5])
        else:
            lag[:] = np.interp(target.q, [q25, q75], [11., 7.])
        method[:] = "empirical_regime_prior_approximation"
        confidence[:] = "low_prior_not_wave_validated"
    # Directional matches support release steps or a limb, never an unverified full
    # recession. Their 36-hour shape and derivative windows are separately audited.
    limb_distance = np.full(n, np.inf)
    for match in limbs:
        distance = np.abs(target.time-match["target_h"])
        use = (distance < limb_distance) & (distance <= 7*24)
        use &= target_seg == match["target_segment"]
        use &= segment_at(source, target.time-match["lag"]) == match["source_segment"]
        lag[use], method[use] = match["lag"], "nearby_directional_limb_lag_approximation"
        confidence[use] = "low_partial_wave_anchor_extrapolation"
        event_id[use], support_days[use] = match["limb_id"], distance[use]/24
        limb_distance[use] = distance[use]
    for match in limbs:
        distance = np.abs(target.time-match["target_h"])
        use = (distance <= 18) & (distance <= limb_distance+1e-9)
        use &= target_seg == match["target_segment"]
        use &= segment_at(source, target.time-match["lag"]) == match["source_segment"]
        lag[use], method[use] = match["lag"], "directional_limb_window_association"
        confidence[use] = "moderate_partial_shape_not_full_wave_or_causal_proof"
        event_id[use], support_days[use] = match["limb_id"], distance[use]/24
    # Nearest accepted wave supports an approximation for quiet periods, never Q interpolation.
    nearest = np.full(n, -1, dtype=int)
    distances = np.full(n, np.inf)
    for j, match in enumerate(accepted):
        te = match["target"]
        d = np.abs(target.time-te["peak_h"])
        valid = (target_seg == te["segment_id"]) & (d < distances)
        nearest[valid], distances[valid] = j, d[valid]
    for j, match in enumerate(accepted):
        te, se = match["target"], match["source_event"]
        max_days = 14 if source.station != "05CC007" else 7
        use = (nearest == j) & (distances <= max_days*24)
        proposed = target.time-match["peak_lag_hours"]
        use &= segment_at(source, proposed) == se["segment_id"]
        lag[use] = match["peak_lag_hours"]
        method[use] = "nearby_wave_lag_approximation"
        confidence[use] = "low_inferred_between_waves"
        event_id[use], support_days[use] = te["event_id"], distances[use]/24
    # Medicine has no fixed default: only a tight, local group of >=3 accepted waves
    # permits an explicitly uncertain extension beyond the seven-day neighborhood.
    if source.station == "05CC007" and len(accepted) >= 3:
        peaks = np.array([m["target"]["peak_h"] for m in accepted])
        plags = np.array([m["peak_lag_hours"] for m in accepted])
        for j, match in enumerate(accepted):
            local = np.abs(peaks-peaks[j]) <= 45*24
            local &= np.array([m["target"]["segment_id"] == match["target"]["segment_id"] for m in accepted])
            if local.sum() < 3 or np.ptp(plags[local]) > 18:
                continue
            use = ~np.isfinite(lag) & (nearest == j) & (distances <= 30*24)
            median = float(np.median(plags[local]))
            use &= segment_at(source, target.time-median) == match["source_event"]["segment_id"]
            lag[use], method[use] = median, "local_wave_cluster_approximation"
            confidence[use] = "very_low_extrapolated_association"
            event_id[use], support_days[use] = match["target"]["event_id"], distances[use]/24
    # Exact wave knots are stronger than quiet-period approximations. These knots are
    # themselves retrospective estimates, not tracked parcels of water.
    for match in accepted:
        te, se = match["target"], match["source_event"]
        use = (target.time >= te["start_h"]) & (target.time <= te["end_h"])
        knots = [te[k] for k in ("start_h", "peak_h", "end_h")]
        source_knots = [se[k] for k in ("start_h", "peak_h", "end_h")]
        lag[use] = target.time[use]-np.interp(target.time[use], knots, source_knots)
        method[use], confidence[use] = "whole_wave_piecewise_time_association", "moderate_shape_evidence_not_causal_proof"
        event_id[use], support_days[use] = te["event_id"], np.abs(target.time[use]-te["peak_h"])/24
    desired = target.time-lag
    hints = {"desired_source_time": desired.copy(), "proposed_method": method.copy(),
             "proposed_confidence": confidence.copy()} if include_hints else {}
    idx = np.searchsorted(source.time, np.nan_to_num(desired, nan=source.time[0]))
    left, right = np.clip(idx-1, 0, len(source.time)-1), np.clip(idx, 0, len(source.time)-1)
    selected = np.where(np.abs(source.time[left]-desired) <= np.abs(source.time[right]-desired), left, right)
    error = np.abs(source.time[selected]-desired)
    valid = np.isfinite(lag) & (error <= 2.5/60+1e-7) & (source.time[selected] < target.time)
    reason = np.where(np.isfinite(lag), "unmatched_source_gap_or_outside_archive", "unmatched_no_supported_lag").astype(object)
    reason[np.isfinite(lag) & (error <= 2.5/60+1e-7) & (source.time[selected] >= target.time)] = "unmatched_future_source_forbidden"
    # Do not force backward jumps or copy/alter discharge to hide discontinuities.
    # A bounded transition hole is safer than a chronological reversal.
    last_time = -np.inf
    for i in range(n):
        if valid[i]:
            if source.time[selected[i]] < last_time-1e-8:
                valid[i] = False
                reason[i] = "unmatched_nonmonotone_lag_transition"
            else:
                last_time = source.time[selected[i]]
    selected[~valid] = -1
    method[~valid] = reason[~valid]
    confidence[~valid] = "none"
    observed_lag = np.full(n, np.nan)
    observed_lag[valid] = target.time[valid]-source.time[selected[valid]]
    reuse = np.zeros(n, dtype=bool)
    previous = -1
    for i in np.flatnonzero(valid):
        reuse[i] = selected[i] == previous
        previous = selected[i]
    return {"index": selected, "lag": observed_lag, "desired_lag": lag, "method": method,
            "confidence": confidence, "event": event_id, "support_days": support_days,
            "time_error_minutes": error*60, "reuse": reuse, **hints}


def short_route_arrival_hints(data, *, include_audit=False):
    """Reproduce v2 Dickson/Little Red Deer timing from supplied observations.

    ``data`` maps all four ``STATIONS`` to ``Series`` objects, each containing
    finite Q and strictly increasing, unique UTC epoch-hour ``time`` values.
    Callers may build these series from PostgreSQL; no files or database are
    read or written here. The common hourly grid is rebuilt exactly as in the
    original full-history workflow, updating only each series' hourly fields.

    Return a station-keyed dictionary for 05CB007 and 05CB001. Every array is
    indexed in ``data[TARGET].time`` order. ``desired_source_time`` contains
    the proposed source epoch hour, and ``proposed_method`` / confidence are
    captured BEFORE actual-observation lookup and monotonicity rejection.
    The original ``index`` (or -1), ``method`` and other assignment arrays are
    retained for parity checks, not for replacing lookup in a database view.
    With ``include_audit=True``, return ``(hints, audit)`` instead, including
    wave/limb evidence for both short routes and detected-wave counts.

    This retains retrospective terminal-flow priors and wave-shape evidence;
    it is not a learned arrival forecast. No new fixed-lag fallback is added.
    """
    for station in STATIONS:
        series = data[station]
        if (series.station != station or series.time.ndim != 1 or series.q.ndim != 1
                or len(series.time) == 0 or len(series.time) != len(series.q)
                or not np.all(np.isfinite(series.time)) or not np.all(np.isfinite(series.q))
                or np.any(np.diff(series.time) <= 0)):
            raise ValueError(f"{station}: expected finite Q and unique increasing epoch-hour times")
    first = int(min(data[s].time[0] for s in STATIONS))
    last = int(max(data[s].time[-1] for s in STATIONS))
    for station in STATIONS:
        hourly(data[station], first, last)
    events = {s: detect_events(data[s]) for s in STATIONS}
    wave_audit, accepted = match_events(data, events)
    limb_audit, limbs = directional_limb_matches(data)
    short_routes = ("05CB007", "05CB001")
    hints = {s: assignments(data[s], data[TARGET], accepted[s], limbs[s], include_hints=True)
             for s in short_routes}
    if not include_audit:
        return hints
    audit = {"wave": [row for row in wave_audit if row["source_station"] in short_routes],
             "limb": [row for row in limb_audit if row["source_station"] in short_routes],
             "detected_waves": {s: len(events[s]) for s in STATIONS},
             "accepted_waves": {s: len(accepted[s]) for s in short_routes},
             "accepted_directional_limb_anchors": {s: len(limbs[s]) for s in short_routes}}
    return hints, audit


def synthetic_tests():
    """Deterministic asymmetric waves, close waves, gap, causality and lag recovery."""
    h = np.arange(240., dtype=float)
    def pulse(t, peak):
        return np.where(t <= peak, np.exp(-.5*((t-peak)/6)**2), np.exp(-.5*((t-peak)/10)**2))
    q = 20+25*pulse(h, 50)+18*pulse(h, 100)+35*pulse(h, 175)
    source = Series("05CB007", h, q, [], [], np.zeros(len(h)), {})
    target = Series(TARGET, h+11, q, [], [], np.zeros(len(h)), {})
    for s in (source, target):
        s.hour, s.smooth, s.segment = s.time.copy(), s.q.copy(), np.zeros(len(h), dtype=int)
    se, te = detect_events(source), detect_events(target)
    assert len(se) >= 2 and len(te) == len(se), (len(se), len(te))
    recovered = [compare_wave(source, target, s, t) for s, t in zip(se, te)]
    assert all(c is not None and not c["reasons"] and abs(c["peak_lag_hours"]-11) < 1e-8 for c in recovered)
    assert any(np.diff([e["peak_h"] for e in se]) < 72), "Close waves were suppressed"
    target.time = np.arange(0., 239.9, 1/12)
    target.q = np.interp(target.time, h+11, q)
    source.time = np.arange(0., 228.9, 1/12)
    source.q = np.interp(source.time, h, q)
    keep = ~((source.time > 70) & (source.time < 75))
    source.time, source.q = source.time[keep], source.q[keep]
    matches = [{"source_event": s, "target": t, **c} for s, t, c in zip(se, te, recovered)]
    a = assignments(source, target, matches)
    valid = a["index"] >= 0
    assert np.all(source.time[a["index"][valid]] < target.time[valid])
    assert np.all(np.diff(source.time[a["index"][valid]]) >= 0)
    intended_gap = (target.time > 81.1) & (target.time < 85.9)
    assert not np.any(valid[intended_gap]), "Missing source observations were fabricated"
    assert np.all(a["index"][target.time < 10] == -1), "Future source fallback occurred"
    hinted = assignments(source, target, matches, include_hints=True)
    for key, values in a.items():
        np.testing.assert_equal(hinted[key], values, err_msg=f"Hints changed legacy {key}")
    np.testing.assert_equal(hinted["desired_source_time"], target.time-a["desired_lag"])
    assert all(not method.startswith("unmatched_") for method in hinted["proposed_method"][intended_gap])
    assert np.all(hinted["method"][intended_gap] == "unmatched_source_gap_or_outside_archive")
    assert not np.shares_memory(hinted["method"], hinted["proposed_method"])
    limb_data = {}
    for station in STATIONS:
        values = np.interp(h-11, h, q, left=np.nan) if station == TARGET else q.copy()
        test_series = Series(station, h, values, [], [], np.zeros(len(h)), {})
        test_series.hour, test_series.smooth = h.copy(), values
        test_series.segment = np.where(np.isfinite(values), 0, -1)
        limb_data[station] = test_series
    _, limb_matches = directional_limb_matches(limb_data)
    assert all(limb_matches[s] for s in SOURCES), "No synthetic directional anchors recovered"
    assert all(m["lag"] == 11 for s in SOURCES for m in limb_matches[s]), "Directional lag not recovered"
    return {"passed": True, "recovered_lag_hours": 11, "source_wave_count": len(se),
            "close_waves_under_72h_retained": True, "source_gap_not_filled": True,
            "future_source_forbidden": True, "chronology_nondecreasing": True,
            "directional_window_lag_recovered": True, "arrival_hints_preserve_legacy_assignments": True}


def timeline_rows(data, matches):
    target = data[TARGET]
    q25, q75 = np.quantile(target.q, [.25, .75])
    for i, t in enumerate(target.time):
        row = {"terminal_observed_at_utc": stamp(t), "terminal_q_m3_s": target.q[i],
               "terminal_quality_flags": target.flags[i], "terminal_approval": target.approval[i],
               "terminal_source_file_id": target.provenance[i],
               "terminal_flow_regime": "low_q25" if target.q[i] <= q25 else ("high_q75" if target.q[i] >= q75 else "middle"),
               "matched_source_count": sum(matches[s]["index"][i] >= 0 for s in SOURCES),
               "retrospective_target_hindsight_not_training_ready": 1}
        for s in SOURCES:
            a, source = matches[s], data[s]
            j = int(a["index"][i])
            row.update({f"{s}_observed_at_utc": stamp(source.time[j]) if j >= 0 else "",
                        f"{s}_q_m3_s": source.q[j] if j >= 0 else "", f"{s}_lag_hours": a["lag"][i],
                        f"{s}_status": a["method"][i], f"{s}_confidence": a["confidence"][i],
                        f"{s}_support_target_event_id": a["event"][i],
                        f"{s}_support_time_distance_days": a["support_days"][i],
                        f"{s}_quality_flags": source.flags[j] if j >= 0 else "",
                        f"{s}_approval": source.approval[j] if j >= 0 else "",
                        f"{s}_source_file_id": source.provenance[j] if j >= 0 else "",
                        f"{s}_nearest_time_error_minutes": a["time_error_minutes"][i] if j >= 0 else "",
                        f"{s}_reuses_previous_source_record": int(a["reuse"][i])})
        yield row


def source_usage_rows(data, matches):
    for station in SOURCES:
        source = data[station]
        selected = matches[station]["index"]
        counts = np.bincount(selected[selected >= 0], minlength=len(source.time))
        first = np.full(len(source.time), -1, dtype=int)
        last = first.copy()
        for i in np.flatnonzero(selected >= 0):
            j = selected[i]
            if first[j] < 0: first[j] = i
            last[j] = i
        for j, t in enumerate(source.time):
            yield {"station_id": station, "observed_at_utc": stamp(t), "q_m3_s": source.q[j],
                   "quality_flags": source.flags[j], "approval": source.approval[j],
                   "source_file_id": source.provenance[j], "terminal_rows_using_record": counts[j],
                   "first_terminal_utc": stamp(data[TARGET].time[first[j]]) if first[j] >= 0 else "",
                   "last_terminal_utc": stamp(data[TARGET].time[last[j]]) if last[j] >= 0 else "",
                   "inventory_status": "used_observed_value" if counts[j] else "unselected_no_accepted_target_association"}


def coverage(data, matches, mask, label, kind):
    n = int(mask.sum())
    valid = np.array([matches[s]["index"] >= 0 for s in SOURCES])
    row = {"group_type": kind, "group": label, "terminal_rows": n,
           "three_sources_complete": int(np.all(valid[:, mask], axis=0).sum()),
           "terminal_q_min": float(data[TARGET].q[mask].min()),
           "terminal_q_max": float(data[TARGET].q[mask].max())}
    for k, s in enumerate(SOURCES):
        row[f"{s}_matched"] = int(valid[k, mask].sum())
        row[f"{s}_coverage_pct"] = float(valid[k, mask].mean()*100)
        row[f"{s}_whole_wave_rows"] = int(np.count_nonzero(mask & (matches[s]["method"] == "whole_wave_piecewise_time_association")))
    return row



# Forward Medicine scenario, independent of the retrospective event matcher.
STEP_S = 300
MED_NORMAL = 603
MED_FAST = 360
MED_RISE = 72
MED_SPREAD = 36


def medicine_parcels(slots, flows):
    """One five-minute observed-Q parcel, one lag center; use past observations only."""
    assert slots.ndim == 1 and len(slots) == len(flows) and len(slots)
    assert np.all(np.diff(slots) > 0) and np.all(np.isfinite(flows)) and np.all(flows >= 0)
    prior = np.full(len(flows), np.nan)
    # A few missing observations do not erase a visible rise. Use the last
    # actual observation at/before the lookback, without interpolating any Q.
    left = np.searchsorted(slots, slots - MED_RISE, side="right") - 1
    j = np.flatnonzero(left >= 0)
    i = left[j]
    span = slots[j] - slots[i]
    wide_gap_prefix = np.concatenate(([0], np.cumsum(np.diff(slots) > 6)))
    supported = ((span <= MED_RISE + 3) & (j-i+1 >= 0.75*(span+1)) &
                 (wide_gap_prefix[j] == wide_gap_prefix[i]))
    prior[j[supported]] = flows[i[supported]]
    rise = flows - prior
    fraction = np.divide(rise, np.maximum(prior, 0.1))
    intensity = np.clip(np.minimum((rise - 0.6)/0.6, (fraction - 0.05)/0.05), 0, 1)
    intensity = np.nan_to_num(intensity, nan=0.0)
    lag = np.rint(MED_NORMAL - (MED_NORMAL - MED_FAST)*intensity).astype(int)
    return lag, prior, rise


def medicine_arrivals(slots, flows, lag, first, last, spread=MED_SPREAD):
    centers = slots + lag
    idx = centers - first
    assert np.all(idx >= spread) and np.all(idx < last-first+1-spread)
    volumes = flows * STEP_S
    central_volume = np.bincount(idx, weights=volumes, minlength=last-first+1)
    central_count = np.bincount(idx, minlength=last-first+1)
    offsets = np.arange(-spread, spread+1)
    weights = (spread+1-np.abs(offsets)).astype(float)
    weights /= weights.sum()
    arrived = np.convolve(central_volume, weights, mode="same")
    support = np.convolve(central_count, np.ones(weights.size, dtype=np.int64), mode="same")
    assert math.isclose(float(arrived.sum()), float(volumes.sum()), rel_tol=1e-12)
    assert int(central_count.sum()) == len(slots)
    return centers, arrived, central_count, support


def medicine_forward_tests():
    slots = np.array([0, MED_NORMAL - MED_FAST])
    flows = np.array([1.0, 2.0])
    lags = np.array([MED_NORMAL, MED_FAST])
    centers, arrived, counts, support = medicine_arrivals(slots, flows, lags, 0, 900)
    assert centers[0] == centers[1] == MED_NORMAL and counts[MED_NORMAL] == 2
    assert support[MED_NORMAL] == 2 and math.isclose(float(arrived.sum()), 900)
    _, unspread, _, _ = medicine_arrivals(slots, flows, lags, 0, 900, spread=0)
    assert unspread[MED_NORMAL] == 900
    hours = np.arange(MED_RISE + 1)
    rising = np.linspace(10.0, 11.2, len(hours))
    # Provide a strictly above-threshold change to avoid a roundoff boundary.
    rising[-1] = 11.21
    assert medicine_parcels(hours, rising)[0][-1] == MED_FAST
    hole = np.r_[0:30, 38:73]
    assert medicine_parcels(hours[hole], rising[hole])[0][-1] == MED_NORMAL
    sparse = np.delete(hours, [18, 36, 54])
    assert medicine_parcels(hours[sparse], rising[sparse])[0][-1] == MED_FAST
    return ["same_bin_overlap_counts_two_distinct_parcels_once",
            "conserves_volume_before_and_after_spread", "causal_rise_tolerates_small_gaps_but_rejects_long_gaps"]


def run_medicine_forward(source_dir, output, test_only):
    tests = medicine_forward_tests()
    print("Medicine forward checks:", tests, flush=True)
    if test_only:
        return
    output = output.resolve()
    if output.exists():
        raise SystemExit(f"Output already exists: {output}")
    with (source_dir/"upstream_record_inventory.csv").open(newline="", encoding="utf-8-sig") as handle:
        source = [r for r in csv.DictReader(handle) if r["station_id"] == "05CC007"]
    with (source_dir/"terminal_alignment.csv").open(newline="", encoding="utf-8-sig") as handle:
        target = list(csv.DictReader(handle))
    assert len(source) == EXPECTED["05CC007"] and len(target) == EXPECTED[TARGET]

    def slot(timestamp):
        raw = parse_hour(timestamp)*3600/STEP_S
        assert abs(raw-round(raw)) < 1e-6
        return round(raw)

    slots = np.array([slot(r["observed_at_utc"]) for r in source])
    target_slots = np.array([slot(r["terminal_observed_at_utc"]) for r in target])
    assert np.all(np.diff(target_slots) > 0)
    flow = np.array([float(r["q_m3_s"]) for r in source])
    lag, prior, rise = medicine_parcels(slots, flow)
    first = min(int(target_slots[0]), int(slots[0] + MED_FAST - MED_SPREAD))
    last = max(int(target_slots[-1]), int(slots[-1] + MED_NORMAL + MED_SPREAD))
    centers, arrived, n_center, support = medicine_arrivals(slots, flow, lag, first, last)
    _, fixed, _, fixed_support = medicine_arrivals(slots, flow, np.full_like(lag, MED_NORMAL), first, last)
    ti = target_slots-first
    # Conservative envelope: an unobserved upstream slot anywhere in the feasible lag
    # range could contribute. Actual arrivals in these bins are partial, not set to zero.
    u_first = first - MED_NORMAL - MED_SPREAD
    u_last = last - MED_FAST + MED_SPREAD
    measured = np.zeros(u_last-u_first+1, dtype=np.int64)
    relevant = (slots >= u_first) & (slots <= u_last)
    measured[slots[relevant]-u_first] = 1
    prefix = np.concatenate(([0], np.cumsum(measured)))
    all_slots = np.arange(first, last+1)
    aa = all_slots - MED_NORMAL - MED_SPREAD - u_first
    bb = all_slots - MED_FAST + MED_SPREAD - u_first + 1
    missing_possible = prefix[bb]-prefix[aa] != bb-aa

    def iso(s):
        return stamp(s*STEP_S/3600)

    def labels():
        for i, row in enumerate(source):
            yield {
                "source_station": "05CC007", "source_time_utc": row["observed_at_utc"],
                "observed_q_m3_s": flow[i], "parcel_volume_m3": flow[i]*STEP_S,
                "source_file_id": row["source_file_id"], "quality_flags": row["quality_flags"],
                "approval": row["approval"], "six_hour_change_m3_s": rise[i],
                "tier": ("insufficient_history_normal_prior" if not np.isfinite(prior[i])
                         else "fast_rise" if lag[i] == MED_FAST else "normal" if lag[i] == MED_NORMAL
                         else "rising_transition"),
                "lag_hours": lag[i]*STEP_S/3600, "arrival_center_utc": iso(centers[i]),
                "first_supported_bin_utc": iso(centers[i]-MED_SPREAD),
                "last_supported_bin_utc": iso(centers[i]+MED_SPREAD),
            }

    def destination_fields(idx):
        return {"medicine_routed_q_m3_s": arrived[idx]/STEP_S if support[idx] else "",
                "medicine_fixed_lag_q_m3_s": fixed[idx]/STEP_S if fixed_support[idx] else "",
                "medicine_center_parcels": n_center[idx], "medicine_contributing_parcels": support[idx],
                "medicine_possible_source_gap": int(missing_possible[idx]),
                "medicine_status": ("no_modeled_arrival" if not support[idx]
                                    else "modeled_arrival_possible_partial_source"
                                    if missing_possible[idx] else "modeled_arrival")}

    def terminal_rows():
        for idx, row in zip(ti, target):
            combined = {k: row[k] for k in ("terminal_observed_at_utc", "terminal_q_m3_s",
                        "terminal_flow_regime", "05CB007_q_m3_s", "05CB001_q_m3_s")}
            combined["medicine_old_associated_q_m3_s"] = row["05CC007_q_m3_s"]
            combined.update(destination_fields(idx))
            yield combined

    target_mask = np.zeros(last-first+1, dtype=bool)
    target_mask[ti] = True
    span = (all_slots >= target_slots[0]) & (all_slots <= target_slots[-1])
    source_volume = float(np.sum(flow*STEP_S))
    partitions = {
        "before_target_window": float(arrived[all_slots < target_slots[0]].sum()),
        "bins_with_target_observation": float(arrived[target_mask].sum()),
        "target_window_bins_without_observation": float(arrived[span & ~target_mask].sum()),
        "after_target_window": float(arrived[all_slots > target_slots[-1]].sum()),
    }
    assert math.isclose(sum(partitions.values()), source_volume, rel_tol=1e-12)
    fast = lag == MED_FAST
    ordinary = lag == MED_NORMAL
    target_q = np.array([float(row["terminal_q_m3_s"]) for row in target])
    old_med = np.array([bool(row["05CC007_q_m3_s"]) for row in target])
    others = np.array([bool(row["05CB007_q_m3_s"]) and bool(row["05CB001_q_m3_s"]) for row in target])
    has = support[ti] > 0
    event = (slots >= slot("2026-06-29T12:00:00Z")) & (slots < slot("2026-06-30T00:00:00Z"))
    summary = {
        "purpose": "unvalidated_forward_volume_routing_scenario_not_training_or_peak_attribution",
        "source_artifact": source_dir.name,
        "parameters": {"source_bin_seconds": STEP_S, "normal_lag_hours": 50.25,
                       "fast_lag_hours": 30, "rise_lookback_hours": 6, "spread_half_width_hours": 3,
                       "transition_absolute_rise_bounds_m3_s": [0.6, 1.2],
                       "transition_relative_rise_bounds": [0.05, 0.10],
                       "rise_history_minimum_coverage": 0.75,
                       "rise_history_maximum_gap_minutes": 30,
                       "rise_baseline_maximum_lookback_tolerance_minutes": 15},
        "medicine_observed_parcels": len(slots),
        "normal_or_insufficient_history_parcels": int(ordinary.sum()),
        "normal_prior_due_to_insufficient_history_parcels": int(np.isnan(prior).sum()),
        "transition_parcels": int((~fast & ~ordinary).sum()),
        "fast_parcels": int(fast.sum()),
        "june29_12_to_24_utc_source_parcels": int(event.sum()),
        "june29_12_to_24_utc_fast_parcels": int((event & fast).sum()),
        "june29_12_to_24_utc_lag_min_max_hours": [float(lag[event].min()*STEP_S/3600),
                                                float(lag[event].max()*STEP_S/3600)],
        "arrival_bins_with_two_or_more_parcel_centers": int((n_center >= 2).sum()),
        "observed_source_volume_m3": source_volume,
        "total_routed_volume_m3": float(arrived.sum()),
        "volume_partition_m3": partitions,
        "terminal_comparison": {
            "observed_rows": len(target), "prior_medicine_associated_rows": int(old_med.sum()),
            "forward_rows_with_arrival": int(has.sum()),
            "forward_rows_with_arrival_and_no_possible_source_gap": int((has & ~missing_possible[ti]).sum()),
            "observed_q_ge_200_rows": int((target_q >= 200).sum()),
            "observed_q_ge_200_rows_with_arrival": int(((target_q >= 200) & has).sum()),
            "three_source_rows_using_original_other_station_associations": int((others & has).sum()),
            "three_source_rows_ge_200_using_original_other_station_associations":
                int((others & has & (target_q >= 200)).sum())},
        "synthetic_tests": tests,
    }
    output.mkdir(parents=True)
    write_csv(output/"medicine_source_parcels.csv", labels())
    write_csv(output/"medicine_arrival_grid.csv", (
        {"arrival_bin_start_utc": iso(s), **destination_fields(i), "target_observed": int(target_mask[i])}
        for i, s in enumerate(all_slots)
    ))
    write_csv(output/"terminal_medicine_forward_marks.csv", terminal_rows())
    (output/"summary.json").write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DATA/"processed/wave_time_alignment_full_history_v2_20261117")
    parser.add_argument("--test-only", action="store_true")
    parser.add_argument("--strict-wave-only", action="store_true",
                        help="Sensitivity specification: omit partial directional-window anchors")
    parser.add_argument("--medicine-forward-from", type=Path, metavar="PRIOR_OUTPUT",
                        help="Route Medicine volume forward from a full-history inventory")
    args = parser.parse_args()
    if args.medicine_forward_from is not None:
        if args.strict_wave_only:
            parser.error("--strict-wave-only does not apply in Medicine forward mode")
        run_medicine_forward(args.medicine_forward_from.resolve(), args.output, args.test_only)
        return
    tests = synthetic_tests()
    print("Synthetic checks:", tests, flush=True)
    if args.test_only:
        return
    output = args.output.resolve()
    if output.exists():
        raise SystemExit(f"Output already exists; choose a new --output to preserve audit history: {output}")
    data, manifest = read_sources()
    for s in STATIONS:
        assert len(data[s].time) == EXPECTED[s], (s, len(data[s].time), EXPECTED[s])
    first = int(min(s.time[0] for s in data.values()))
    last = int(max(s.time[-1] for s in data.values()))
    for s in data.values(): hourly(s, first, last)
    events = {s: detect_events(data[s]) for s in STATIONS}
    print("Detected waves:", {s: len(events[s]) for s in STATIONS}, flush=True)
    audits, accepted = match_events(data, events)
    limb_audits, limbs = ([], {s: [] for s in SOURCES}) if args.strict_wave_only else directional_limb_matches(data)
    matches = {s: assignments(data[s], data[TARGET], accepted[s], limbs[s]) for s in SOURCES}
    output.mkdir(parents=True)
    write_csv(output/"source_manifest.csv", manifest)
    write_csv(output/"terminal_alignment.csv", timeline_rows(data, matches))
    write_csv(output/"upstream_record_inventory.csv", source_usage_rows(data, matches))
    write_csv(output/"wave_match_audit.csv", audits)
    if limb_audits:
        write_csv(output/"limb_match_audit.csv", limb_audits)
    event_rows = []
    for s in STATIONS:
        for e in events[s]:
            event_rows.append({"station_id": s, "event_id": e["event_id"], "segment_id": e["segment_id"],
                               "start_utc": stamp(e["start_h"]), "peak_utc": stamp(e["peak_h"]), "end_utc": stamp(e["end_h"]),
                               **{k: e[k] for k in ("baseline_q", "peak_q", "prominence_q", "threshold_q", "noise_q", "duration_hours")}})
    write_csv(output/"station_wave_inventory.csv", event_rows)
    target = data[TARGET]
    months = np.array([stamp(t)[:7] for t in target.time])
    q25, q75, q90 = np.quantile(target.q, [.25, .75, .9])
    coverage_rows = [coverage(data, matches, months == month, month, "calendar_month") for month in np.unique(months)]
    for label, mask in (("low_q25", target.q <= q25), ("middle_q25_q75", (target.q > q25) & (target.q < q75)),
                        ("high_q75", target.q >= q75), ("very_high_q90", target.q >= q90),
                        ("q_at_least_100", target.q >= 100), ("q_at_least_200", target.q >= 200)):
        coverage_rows.append(coverage(data, matches, mask, label, "endpoint_observed_flow_regime"))
    write_csv(output/"coverage_by_month_and_flow.csv", coverage_rows)
    summary = {"method_version": "2.0", "directional_limb_tier_enabled": not args.strict_wave_only,
               "purpose": "retrospective_discharge_time_association_not_forecast_or_training_ready",
               "source_precedence": "latest dated acquisition wins each overlapping numeric station/time/Q record; older nonoverlapping tails retained; probes excluded",
               "all_numeric_q_rows_preserved": True, "all_target_rows": len(target.time),
               "sources": {s: data[s].stats for s in STATIONS}, "synthetic_tests": tests,
               "detected_waves": {s: len(events[s]) for s in STATIONS},
               "accepted_waves": {s: len(accepted[s]) for s in SOURCES},
               "accepted_directional_limb_anchors": {s: len(limbs[s]) for s in SOURCES},
               "wave_status_counts": dict(Counter(r["status"] for r in audits)),
               "flow_thresholds_m3_s": {"q25": q25, "q75": q75, "q90": q90},
               "complete_source_count_distribution": {}, "alignment": {},
               "method_parameters": {"hourly_min_observations": 3, "smoothing_median_hours": 3,
                 "relative_prominence": .08, "boundary_prominence_fraction": .10,
                 "sustained_boundary_hours": 3, "maximum_prominence_search_each_side_hours": 240,
                 "fixed_peak_exclusion_hours": None, "nearest_actual_record_tolerance_minutes": 2.5,
                 "search_peak_lag_bounds_hours": LIMITS, "bounds_are_exploratory_not_validated_physics": True,
                 "directional_window_hours_each_side": 18, "directional_change_hours": 6,
                 "directional_min_relative_change": .03,
                 "directional_correlation_short_routes": {"level": .90, "change": .75},
                 "directional_correlation_medicine": {"level": .94, "change": .85},
                 "directional_min_shift_score_margin_outside_3h": .015,
                 "nearby_directional_max_days": 7,
                 "nearby_wave_days": {"05CB007": 14, "05CB001": 14, "05CC007": 7}}}
    counts = np.zeros(len(target.time), dtype=int)
    for s in SOURCES:
        a = matches[s]
        valid = a["index"] >= 0
        counts += valid
        times = data[s].time[a["index"][valid]]
        assert np.all(times < target.time[valid]), "Future source observed time"
        assert np.all(np.diff(times) >= -1e-8), "Reversed source chronology"
        assert np.all(a["time_error_minutes"][valid] <= 2.50001), "Unbounded nearest match"
        summary["alignment"][s] = {"matched_rows": int(valid.sum()), "coverage_pct": float(valid.mean()*100),
            "unique_source_records_used": int(len(np.unique(a["index"][valid]))),
            "unused_source_records": len(data[s].time)-int(len(np.unique(a["index"][valid]))),
            "reused_source_rows": int(a["reuse"].sum()), "method_counts": dict(Counter(a["method"])),
            "lag_hours_quantiles": dict(zip(("min", "p25", "median", "p75", "max"),
                [float(x) for x in np.quantile(a["lag"][valid], [0,.25,.5,.75,1])])) if valid.any() else {},
            "source_chronology_nondecreasing": True, "future_source_count": 0}
    summary["complete_source_count_distribution"] = dict(sorted(Counter(str(x) for x in counts).items()))
    (output/"summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    write_readmes(output, summary)
    print(json.dumps({"output": str(output), "rows": len(target.time), "complete_counts": summary["complete_source_count_distribution"],
                      "matched": {s: summary["alignment"][s]["matched_rows"] for s in SOURCES}}, indent=2), flush=True)


def write_readmes(output, summary):
    counts = summary["complete_source_count_distribution"]
    text = f"""# Full-history retrospective wave-time associations

All {summary['all_target_rows']:,} unique numeric terminal discharge observations are present, from May 3, 2025 through November 11, 2026. Numeric source observations are never removed because stage, geometry, another station, model split or seasonal criteria are missing. Rain/high-flow and quiet/low-flow periods are processed alike. Monthly and observed-flow-quantile tables avoid labeling a calendar season as drought. Full three-source associations: {counts.get('3', 0):,} rows. Missing associations remain blank.

## Read first: observed values, inferred times

Every nonblank Q and observation timestamp is copied from an actual WaterOffice record. Only the association between upstream and terminal records is inferred. This is a retrospective diagnostic using the observed terminal waveform, including future peak/recession information. It is **not training-ready and not an operational forecast input**. Event similarity is not causal proof of travel time, and combined tributaries, reservoir operations, attenuation and ice/ratings can distort waveforms. Numeric qualifier/grade and approval flags are preserved without assuming their meanings. Provisional data and revisions remain provisional.

Correlation thresholds and search windows are exploratory, not statistically calibrated confidence probabilities. Searching many lags/windows creates false-match risk, especially for Medicine. Broadly varying Medicine lags do not establish a single travel-time law; directional-window and nearby approximations should be treated as hypotheses for review. No multiple-comparison correction or independent hydrologic validation has been performed.

## Method

1. Merge the two complete dated acquisition runs, latest-run numeric Q taking precedence for duplicate station/timestamp keys; preserve older unmatched records. The probe directory is excluded. Read discharge independently of stage and geometry. Source hashes and per-source revision counts are retained.
2. Hourly medians require at least three observations, followed by a three-hour median. Missing hours split the series; there is no Q interpolation. Identify significant topographic peaks using 8% local prominence, an absolute floor and a robust noise threshold. Search at most 240 hours each side. Rise/end boundaries are local baseline + 10% prominence with three consecutive below-threshold hours. Complete waves only; nested shoulders with >75% overlap are removed, but there is no 72-hour or other fixed peak-separation rule.
3. For each terminal wave, test earlier source waves using start/peak/end lags, both whole-wave shifted correlation and separate rise/fall normalized-shape correlation, duration ratio and boundary consistency. Dickson peak search 2–30 h, Little Red Deer 1–36 h and Medicine 6–144 h are broad exploratory bounds, not validated physical limits. Ambiguous alternatives within 0.04 score are withheld. Source waves cannot be reused and accepted events must preserve both chronologies. `wave_match_audit.csv` also records failed candidates and reasons.
   Separately, `limb_match_audit.csv` finds strong six-hour rises/falls in the terminal series and compares 36-hour observed windows against source shifts. Both level-shape and six-hour-change correlation must pass (0.90/0.75 for short routes, 0.94/0.85 for Medicine). The best score must exceed alternatives more than three hours away by 0.015. Boundary solutions, repeated source directional features and reversed anchors are rejected. These are partial-shape associations, not accepted three-boundary full waves. They can support nearby low-confidence approximations for at most seven days, in the same gap-separated segments. This tier detects reservoir steps/plateaus and distorted recessions without pretending the full waveform matched.
4. Inside accepted waves, piecewise time mapping passes through rise, peak and fall knots. Outside waves, nearby accepted peak lags may support clearly low-confidence approximations within 14 days for Dickson/Little Red Deer and 7 days for Medicine, only in the same uninterrupted hourly segments. Dickson's user-supplied approximate high-/low-flow prior is 10.5–14 h; Little's observed candidate range is 7–11 h. These fill otherwise unsupported short-route periods, labeled empirical prior, not verified event matches.
5. Medicine has **no fixed fallback**. Beyond seven days, an uncertain local-cluster extension needs at least three accepted events within 45 days with lag range <=18 h, and may extend no more than 30 days from the nearest anchor in the same gap-separated segments. Otherwise Medicine remains unmatched. No 23-day association is allowed.
6. For inferred times, select an actual observation within 2.5 minutes, strictly earlier than terminal time. Never interpolate or invent discharge or bridge source archive gaps by nearest-neighbor extrapolation. Chronological reversals when lag estimates change are withheld with `unmatched_nonmonotone_lag_transition`. Repeated actual records from time stretching/5-minute quantization are explicitly flagged and inventoried.

## Files

- `terminal_alignment.csv`: one row per numeric terminal observation; three source observation times/Q/status/confidence/quality/provenance fields, support distance, reuse flags and complete count. All UTC, Q in m³/s, lags in hours. A support distance is time to the supporting wave peak, not a statistical confidence interval.
- `station_wave_inventory.csv`: detected rise/peak/end boundaries and local prominence/noise.
- `wave_match_audit.csv`: every terminal wave × source, selected or best rejected candidate, alternative ambiguity, correlations and limb lags. A rejected candidate's lag is not an accepted association.
- `limb_match_audit.csv`: distinct partial-shape tier, including all accepted/rejected directional windows, correlation gates, lag-identification margin and near-optimal lag range.
  When there is no valid candidate more than three hours from the best lag, the margin is blank and comparison status says restricted support. This is not a large observed margin or proof that missing/gap-contaminated alternatives were ruled out.
- `upstream_record_inventory.csv`: every unique numeric upstream observation, count and first/last terminal use. Unused observations are not deleted or declared invalid; no target association selected them.
- `coverage_by_month_and_flow.csv`: full denominators by month and observed endpoint-flow regime.
- `source_manifest.csv`: original file IDs, paths, sizes and SHA256.
- `summary.json`: source coverage/revisions, exact method parameters, statuses, lag distributions and synthetic tests.

## Reproduction and validation

From repository root: `.venv\\Scripts\\python.exe -B courses\\AIDA-2156\\analysis\\eda_tools\\wave_time_alignment.py --output <new-output-directory>`.
`--test-only` checks an 11-hour known synthetic shift, distinct waves less than 72 hours apart, a missing-data gap, no future-source lookup and nondecreasing source chronology. The actual run asserts full independently counted source totals, source causality/chronology and nearest-time tolerance. Existing output directories are refused, and no model, raw input, cache, database or Git state is changed. This diagnostic does not establish identification, out-of-sample predictive value or calibrated travel times. Whole-wave matching can miss real associations when terminal mixing hides a tributary wave; unmatched coverage is evidence, not a reason to force a match.

The short-route empirical prior uses full-history terminal Q quartiles to interpolate between its stated low/high-flow values. This is additional target hindsight, not deployable calibration. The prior sensitivity run without directional windows is retained in the sibling `wave_time_alignment_full_history_20261117` directory. Its small three-source coverage must not be interpreted as absence of upstream water.
"""
    (output/"README.md").write_text(text, encoding="utf-8")
    cn = f"""# 全历史波形时间关联（回溯诊断）

保留终点全部 {summary['all_target_rows']:,} 条唯一数值流量观测，范围为 2025-05-03 至 2026-11-11。不因水位、几何、其他站点或模型筛选缺失而剔除流量，不只处理汛期。按月份及终点实际流量分位数报告覆盖率，不能把某些月份直接称为旱季。三个来源均有关联的行数为 {counts.get('3', 0):,}。无法关联的部分保持空白。

## 真实观测与估计关联必须区分

所有非空流量和观测时间均来自真实 WaterOffice 原始记录，没有插补流量。估计的只有上下游记录之间的时间关联。本结果利用终点已知波形，包括事后才能看到的峰值及退水，因此不是可直接用于训练或实时预测的数据。波形相似不等于已证明传播时间或因果关系。支流叠加、水库调节、衰减及冰情/评级变化都可能干扰波形。保留原始 qualifier/grade/approval，不擅自解释数值质量代码。

## 方法与覆盖

合并两个完整日期批次，重叠时间优先使用较新的数值流量，保留旧批次不重叠的尾部，排除 probe。逐时中位数至少需要三个真实观测，再做三小时中位数降噪；缺失小时将序列分段，不跨空档插补。用局部基线、8% 显著度、噪声和绝对下限识别波峰；以基线加10%波幅和持续三小时的阈值条件确定起涨/退水边界，每侧最多搜索240小时。只剔除大幅嵌套肩峰，没有固定72小时排他规则。

逐个终点波形比较较早的来源波形：整段平移相关、上升/下降形状、持续时间、起涨/峰值/结束三个时差均需合理。Dickson 搜索2–30小时，Little Red Deer 1–36小时，Medicine 6–144小时，这些仅是探索搜索范围，不是已经验证的物理常数。相近候选有歧义则不强行匹配；同一来源事件不重复用于不同终点事件，时间顺序不能倒退。

另设局部涨/落水形状证据层：检测显著六小时变化，在36小时真实观测窗口内同时比较流量形状及六小时变化形状。较短两路线阈值为0.90/0.75，Medicine更严格为0.94/0.85；距离最佳时差超过三小时的其他候选，评分至少低0.015。搜索边界最优、重复来源变化特征及时间倒退均拒绝。这个证据层可发现放水台阶、平台或退水失真的关联，但不冒充起涨/峰值/结束均匹配的完整波形。仅允许同一连续观测段内最多七天的低可信度邻近延伸，详见 `limb_match_audit.csv`。

已接受事件内部以起涨、峰值和结束三个时间锚点做分段时间映射。安静期可用同一连续观测段内的邻近事件时差，Dickson/Little最多14天，Medicine最多7天。两条较短路线无事件支持时，使用用户给出的低可信度经验范围：Dickson高流量约10.5小时、低流量约14小时；Little约7–11小时。字段明确标注为经验近似，不声称精确。

Medicine没有固定默认时差。只有局部45天范围内至少三个已接受事件、时差极差不超过18小时，才允许在最近事件30天范围内作更低可信度延伸，且仍限同一无缺口时间段。其他时段保持未匹配，绝不使用23天默认。

在估计来源时间附近2.5分钟内查找真实观测，必须早于终点时间。跨缺口找不到记录则留空；时差切换导致来源时间倒退则标注并留空。时间拉伸或五分钟量化可能重复使用真实记录，逐行标记并单独统计。

## 查看文件

- `terminal_alignment.csv`：每个终点观测一行，含三个来源实际时间/流量、时差、方法、置信度、质量、出处、支持事件距离、复用标记及匹配数量。
- `wave_match_audit.csv`：每个终点事件×来源的起涨/峰值/结束、三个时差、相关性、候选歧义和拒绝理由。被拒绝候选的时差不能视作已接受结果。
- `station_wave_inventory.csv`：四站识别出的事件边界、基线和噪声。
- `upstream_record_inventory.csv`：全部上游真实观测及使用次数，未使用不表示数据无效。
- `coverage_by_month_and_flow.csv`：各月和低/中/高流量分组的完整分母与覆盖。
- `source_manifest.csv`、`summary.json`：原始文件哈希、版本优先级、修订计数、参数、分布和验证。

所有时间为UTC、流量为m³/s、时差为小时。支持距离是距离支持事件峰值的天数，不是统计置信区间。复现命令见英文README；必须指定不存在的新输出目录，程序拒绝覆盖旧结果。合成测试检查11小时已知时差、72小时内的相邻独立波形、数据缺口、不得使用未来来源以及时间不倒退。原始文件、模型、缓存、数据库和Git均未改动。真实数据覆盖与数值完整性已检查，不代表已完成传播时间标定或预测验证。

两条较短路线经验近似采用全历史终点流量四分位数在给定高/低流量时差之间插值，这也使用了目标事后信息，不能直接部署。不含局部涨落水证据层的保守敏感性结果保留在同级 `wave_time_alignment_full_history_20261117` 目录。
"""
    (output/"READMECN.md").write_text(cn, encoding="utf-8")


if __name__ == "__main__":
    main()
