"""Build the full 18-month matched historical replay bundle using real ECCC observations and the pinned V4 FrozenModel.

Usage (from repository root):
  python -B courses/AIDA-2156/deployment/client/build_replay_dataset.py
"""
from __future__ import annotations

import bisect
import csv
import gzip
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
DEPLOY_DIR = WORKSPACE / "courses" / "AIDA-2156" / "deployment"
sys.path.insert(0, str((WORKSPACE / ".venv" / "Lib" / "site-packages").resolve()))
sys.path.insert(0, str(DEPLOY_DIR))

from server.inference import FrozenModel  # noqa: E402

HIST_DIR = WORKSPACE / "courses" / "AIDA-2156" / "data" / "processed" / "model_unit_history" / "20261103T070414Z"
RAIN_DIR = WORKSPACE / "courses" / "AIDA-2156" / "data" / "sources" / "eccc_climate_hourly" / "raw" / "20250501_20261104_3025484_monthly"
OUT_PATH = Path(__file__).resolve().parent / "assets" / "replay_history.json.gz"

UTC = timezone.utc


def parse_ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(UTC).timestamp())


def load_station_csv(station_id: str) -> tuple[dict[int, float], dict[int, float]]:
    q_map: dict[int, float] = {}
    l_map: dict[int, float] = {}
    p = HIST_DIR / f"{station_id}_observations.csv"
    with p.open("r", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            ts = parse_ts(row["observed_at"])
            q_raw = row.get("discharge_m3_s")
            l_raw = row.get("level_m")
            if q_raw not in ("", None):
                v = float(q_raw)
                if math.isfinite(v) and v >= 0:
                    q_map[ts] = v
            if l_raw not in ("", None):
                v = float(l_raw)
                if math.isfinite(v):
                    l_map[ts] = v
    return q_map, l_map


def load_rain_json() -> dict[int, float]:
    rain: dict[int, float] = {}
    for jf in sorted(RAIN_DIR.glob("20*.json")):
        if jf.name.endswith(".meta.json"):
            continue
        obj = json.loads(jf.read_text(encoding="utf-8"))
        for feat in obj.get("features", []):
            p = feat.get("properties", {})
            if p.get("CLIMATE_IDENTIFIER") != "3025484":
                continue
            if p.get("PRECIP_AMOUNT_FLAG") not in (None, ""):
                continue
            v = p.get("PRECIP_AMOUNT")
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
                continue
            ut = p.get("UTC_DATE")
            if not isinstance(ut, str):
                continue
            dt = datetime.fromisoformat(ut.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=UTC)
            ts = int(dt.astimezone(UTC).timestamp())
            if ts % 3600 == 0:
                rain[ts] = float(v)
    return rain


def precompute_medicine_centers(m_q: dict[int, float]) -> tuple[list[int], list[int]]:
    """Precompute lag-adjusted arrival center for every 5-min Medicine River observation (identical to server.inference)."""
    times = sorted(m_q.keys())
    gaps = [0]
    for j in range(1, len(times)):
        gaps.append(gaps[-1] + int(times[j] - times[j - 1] > 1800))
    centers = []
    for j, s in enumerate(times):
        lag = 603
        for k in range(4):
            prev = s - 21600 - k * 300
            a = bisect.bisect_left(times, prev)
            if a == len(times) or times[a] != prev:
                continue
            baseline = m_q[prev]
            expected = (s - prev) // 300 + 1
            if (j - a + 1) >= 0.75 * expected and gaps[j] == gaps[a]:
                rise = m_q[s] - baseline
                weight = max(0.0, min(1.0, (rise - 0.6) / 0.6, (rise / max(baseline, 0.1) - 0.05) / 0.05))
                lag = math.floor(603 - 243 * weight + 0.5)
            break
        centers.append(s + lag * 300)
    return times, centers


def rain_windows(source_ts: int, rain: dict[int, float], asof: int) -> tuple[list[float], int]:
    end = (source_ts // 3600) * 3600
    seen = 0
    total = 0.0
    wins = []
    for i in range(1, 25):
        start = end - 3600 * i
        v = rain.get(start)
        if v is not None and start + 3600 <= asof and start + 3600 <= source_ts:
            total += v
            seen += 1
        if i in (1, 6, 24):
            wins.append(total)
    return wins, seen


def build_features(
    issue_ts: int,
    hours: int,
    q_d: dict[int, float],
    q_l: dict[int, float],
    q_m: dict[int, float],
    m_times: list[int],
    m_centers: list[int],
    rain: dict[int, float],
) -> list[float] | None:
    t = (issue_ts // 300) * 300 + hours * 3600
    asof = issue_ts
    td, tl = t - 630 * 60, t - 540 * 60
    if tl > asof or td > asof:
        return None
    d_val = q_d.get(td)
    l_val = q_l.get(tl)
    if hours and d_val is None:
        return None
    if l_val is None:
        return None
    a, ac = rain_windows(td, rain, asof)
    b, bc = rain_windows(tl, rain, asof)
    if hours and (ac != 24 or bc != 24):
        return None
    s0, s1 = t - 639 * 300, t - 324 * 300
    i0 = bisect.bisect_left(m_times, s0)
    i1 = bisect.bisect_right(m_times, s1)
    required = (s1 - s0) // 300 + 1
    if (i1 - i0) != required:
        return None
    meter = 0.0
    rain_m = [0.0, 0.0, 0.0]
    n = 0
    m_all_rain = True
    for idx in range(i0, i1):
        source = m_times[idx]
        center = m_centers[idx]
        k = (t - center) // 300
        if abs(k) > 36:
            continue
        w = (37 - abs(k)) / 1369.0
        mass = q_m[source] * w
        r, seen = rain_windows(source, rain, asof)
        meter += mass
        m_all_rain &= (seen == 24)
        for j in range(3):
            rain_m[j] += r[j] * mass
        n += 1
    if not n:
        return None
    if meter:
        rain_m = [j / meter for j in rain_m]
    if hours and not m_all_rain:
        return None
    return [d_val if d_val is not None else 0.0, l_val, meter, *a, *b, *rain_m]


def main() -> None:
    print("Loading 18-month historical observations...")
    q_d, l_d = load_station_csv("05CB007")
    q_l, l_l = load_station_csv("05CB001")
    q_m, l_m = load_station_csv("05CC007")
    q_r, l_r = load_station_csv("05CC002")
    _, l_lk = load_station_csv("05CC003")
    rain = load_rain_json()

    print(f"Loaded stations & rain ({len(rain)} hourly rain rows). Precomputing Medicine lag centers...")
    m_times, m_centers = precompute_medicine_centers(q_m)

    # All matched hourly timestamps where all 4 river discharges exist (18 months!)
    common_hours = sorted(ts for ts in (set(q_d) & set(q_l) & set(q_m) & set(q_r)) if ts % 3600 == 0)
    print(f"Matched 4-river hourly slots: {len(common_hours)}")

    fm = FrozenModel()
    torch = fm.torch

    # Gather features in batch for 0h, +3h, +9h
    kept_ts: list[int] = []
    feat_batches: dict[int, list[tuple[int, list[float]]]] = {0: [], 3: [], 9: []}

    for idx_t, ts in enumerate(common_hours):
        f0 = build_features(ts, 0, q_d, q_l, q_m, m_times, m_centers, rain)
        if f0 is None:
            continue
        out_i = len(kept_ts)
        kept_ts.append(ts)
        feat_batches[0].append((out_i, f0))
        f3 = build_features(ts, 3, q_d, q_l, q_m, m_times, m_centers, rain)
        if f3 is not None:
            feat_batches[3].append((out_i, f3))
        f9 = build_features(ts, 9, q_d, q_l, q_m, m_times, m_centers, rain)
        if f9 is not None:
            feat_batches[9].append((out_i, f9))

    N = len(kept_ts)
    print(f"Full V4-matched historical hourly frames: {N} (0h={len(feat_batches[0])}, +3h={len(feat_batches[3])}, +9h={len(feat_batches[9])})")

    depths: dict[int, list[list[float | None]]] = {
        h: [[None] * N for _ in range(6)] for h in (0, 3, 9)
    }
    for h in (0, 3, 9):
        batch = feat_batches[h]
        if not batch:
            continue
        idxs = [b[0] for b in batch]
        x = torch.as_tensor([b[1] for b in batch], dtype=torch.float32)
        with torch.inference_mode():
            y = fm.model(x).tolist()
        for row_i, vals in zip(idxs, y):
            for k in range(6):
                depths[h][k][row_i] = round(vals[k], 3)

    # Compact columnar payload
    payload = {
        "span_start": datetime.fromtimestamp(kept_ts[0], UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "span_end": datetime.fromtimestamp(kept_ts[-1], UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": N,
        "ts": kept_ts,
        "q": {
            "05CB007": [round(q_d[t], 2) for t in kept_ts],
            "05CB001": [round(q_l[t], 2) for t in kept_ts],
            "05CC007": [round(q_m[t], 2) for t in kept_ts],
            "05CC002": [round(q_r[t], 2) for t in kept_ts],
        },
        "lvl": {
            "05CB007": [round(l_d[t], 3) if t in l_d else None for t in kept_ts],
            "05CB001": [round(l_l[t], 3) if t in l_l else None for t in kept_ts],
            "05CC007": [round(l_m[t], 3) if t in l_m else None for t in kept_ts],
            "05CC002": [round(l_r[t], 3) if t in l_r else None for t in kept_ts],
            "05CC003": [round(l_lk[t], 3) if t in l_lk else None for t in kept_ts],
        },
        "rain": [round(rain[t - 3600], 2) if (t - 3600) in rain else None for t in kept_ts],
        "d0": depths[0],
        "d3": depths[3],
        "d9": depths[9],
    }

    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    gz = gzip.compress(raw, compresslevel=9, mtime=0)
    OUT_PATH.write_bytes(gz)
    print(f"Saved {OUT_PATH.name}: raw={len(raw):,} B -> gz={len(gz):,} B ({len(gz)/1024:.1f} KB)")


if __name__ == "__main__":
    main()
