"""Fetch bounded station samples and official metadata for a map review."""

from project_paths import resolve_runtime_path, archive_relative
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from API.client import fetch
from API.snapshot_scope import sample

from project_paths import ROOT
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-run", help="Reuse a previous run's successful station responses")
    args = parser.parse_args()
    rules = json.loads((resolve_runtime_path(ROOT / "config/map_station_selection.json")).read_text())
    folder = resolve_runtime_path(ROOT / rules["map_folder"])
    ids = set()
    for name in ("stations.geojson", "historical_tributary_stations.geojson"):
        for feature in json.loads((folder / "eccc_hydrometric_geomet" / name).read_text())["features"]:
            ids.add(feature["properties"]["station_id"])
    ids -= set(rules["excluded_station_ids"])
    run = args.resume_run or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not all(c.isdigit() or c in "TZ" for c in run):
        raise ValueError("Invalid run identifier")
    report = {"run": run, "continuous": False, "query_limit_per_source": 48,
              "query_note": "Latest numeric sample can prove recent availability; an empty sample alone cannot prove a full three-month absence.",
              "results": [], "coordinate_sources": []}
    def station_sample(sid):
        archived = resolve_runtime_path(ROOT / f"data/sources/eccc_hydrometric_geomet/raw/scope_snapshot/{run}/{sid}.json")
        if args.resume_run and archived.exists():
            from API.observations import numeric
            features = json.loads(archived.read_text())["features"]
            if any(f["properties"]["STATION_NUMBER"] != sid for f in features):
                raise ValueError("Station identity mismatch")
            valid = [f for f in features if any(numeric(f["properties"].get(k)) for k in ("LEVEL", "DISCHARGE"))]
            latest = max(valid, key=lambda f: f["properties"]["DATETIME"]) if valid else None
            return {"station_id": sid, "status": "numeric_observations" if valid else "no_numeric_observations",
                    "raw_path": archive_relative(archived, ROOT).as_posix(), "numeric_record_count": len(valid),
                    "latest_observation": latest["properties"]["DATETIME"] if latest else None,
                    "latest_properties": latest["properties"] if latest else None}
        return sample(("water", sid), run)
    directory = resolve_runtime_path(ROOT / "data/reports/map_station_review" / run)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "source_review.json"
    with ThreadPoolExecutor(max_workers=4) as pool:
        report["results"] = list(pool.map(station_sample, sorted(ids)))
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    for sid in rules["location_review_station_ids"]:
        path = fetch("https://api.weather.gc.ca/collections/hydrometric-stations/items",
                     f"raw/map_review/{run}/{sid}_metadata.json",
                     {"STATION_NUMBER": sid, "f": "json", "limit": 10}, reuse=True, timeout=30)
        report["coordinate_sources"].append(archive_relative(path, ROOT).as_posix())
        path = fetch("https://wateroffice.ec.gc.ca/station_metadata/reference_index_e.html",
                     f"raw/map_review/{run}/{sid}_reference_index.html", {"stnNum": sid}, reuse=True, timeout=30)
        report["coordinate_sources"].append(archive_relative(path, ROOT).as_posix())
    query = '[out:json][timeout:25];way["waterway"](52.29,-114.13,52.35,-113.98);out geom;'
    path = fetch("https://overpass-api.de/api/interpreter", f"raw/map_review/{run}/sylvan_waterways.json",
                 {"data": query}, reuse=True, timeout=35)
    report["coordinate_sources"].append(archive_relative(path, ROOT).as_posix())
    path = directory / "source_review.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
