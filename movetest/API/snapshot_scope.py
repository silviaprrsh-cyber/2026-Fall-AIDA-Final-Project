"""Fetch one bounded latest-observation sample for a specified station set."""

from project_paths import resolve_runtime_path, archive_relative
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path

from API.client import fetch
from API.observations import numeric, precipitation

from project_paths import ROOT
def sample(job, run):
    kind, sid = job
    water = kind == "water"
    collection = "hydrometric-realtime" if water else "swob-realtime"
    source = "eccc_hydrometric_geomet" if water else "eccc_weather_geomet"
    id_key = "STATION_NUMBER" if water else "msc_id-value"
    time_key = "DATETIME" if water else "date_tm-value"
    result = {"kind": kind, "station_id": sid, "actual_transmission_time": None,
              "transmission_time_note": "Not exposed by this endpoint."}
    try:
        path = fetch(f"https://api.weather.gc.ca/collections/{collection}/items",
                     f"raw/scope_snapshot/{run}/{sid}.json",
                     {id_key: sid, "sortby": "-" + time_key, "limit": 48, "f": "json"},
                     reuse=False, timeout=25)
        obj = json.loads(path.read_text(encoding="utf-8-sig"))
        if "features" not in obj:
            raise ValueError("Response lacks features")
        features = obj["features"]
        if any(str(f["properties"].get(id_key)) != sid for f in features):
            raise ValueError("Station filter mismatch")
        valid = [f for f in features if (
            any(numeric(f["properties"].get(k)) for k in ("LEVEL", "DISCHARGE"))
            if water else precipitation(f["properties"]) is not None)]
        latest = max(valid, key=lambda f: f["properties"].get(time_key) or "") if valid else None
        result.update(source=source, raw_path=archive_relative(path, ROOT).as_posix(),
                      record_count=len(features), numeric_record_count=len(valid),
                      status="numeric_observations" if valid else "no_numeric_observations",
                      latest_observation=latest["properties"].get(time_key) if latest else None,
                      latest_properties=latest["properties"] if latest else None,
                      geometry=latest.get("geometry") if latest else None)
    except Exception as exc:
        result.update(status="request_failed", error=str(exc))
    print(f"{kind} {sid}: {result['status']} {result.get('latest_observation')}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station", action="append", help="Override the active scope with explicit candidate IDs")
    args = parser.parse_args()
    links = json.loads((resolve_runtime_path(ROOT / "data/processed/weather_links.json")).read_text(encoding="utf-8"))
    scope_path = resolve_runtime_path(ROOT / "config/active_scope.json")
    if args.station:
        selected = set(args.station)
    elif scope_path.exists():
        selected = set(json.loads(scope_path.read_text(encoding="utf-8"))["station_ids"])
    else:
        parser.error("Provide --station or create config/active_scope.json")
    weather = {x["weather_id"] for x in links if x.get("station_id") in selected and x.get("weather_id")}
    jobs = [("water", s) for s in sorted(selected)] + [("weather", s) for s in sorted(weather)]
    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = resolve_runtime_path(ROOT / "data/reports/scope_snapshot" / run)
    folder.mkdir(parents=True, exist_ok=False)
    report = {"run": run, "query_limit_per_source": 48, "continuous": False,
              "note": "Candidate acquisition is not the final geographic selection. No historical fallback.",
              "results": []}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(lambda job: sample(job, run), jobs):
            report["results"].append(result)
            (folder / "results.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(str(folder / "results.json"))


if __name__ == "__main__":
    main()
