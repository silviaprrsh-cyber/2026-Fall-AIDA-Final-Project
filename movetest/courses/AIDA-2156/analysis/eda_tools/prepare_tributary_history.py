"""Validate archived daily records and export historical station GIS metadata."""

from project_paths import resolve_runtime_path, archive_relative
import argparse
import csv
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import sys

from project_paths import ROOT

def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path, rows):
    """Rebuild a flat scientific table without replacing nulls with zero."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def numeric(value):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"Invalid numeric measurement: {value!r}")
    return value


def normalize(features, sid, raw_path, received_at):
    rows = []
    for feature in features:
        p = feature["properties"]
        if p["STATION_NUMBER"] != sid:
            raise ValueError("Station mismatch")
        day = p["DATE"]
        if date.fromisoformat(day).isoformat() != day:
            raise ValueError("Expected a daily date, not an instantaneous timestamp")
        rows.append({"station_id": sid, "date": day,
                     "discharge_m3_s": numeric(p.get("DISCHARGE")),
                     "level_m": numeric(p.get("LEVEL")),
                     "discharge_symbol": p.get("DISCHARGE_SYMBOL_EN"),
                     "level_symbol": p.get("LEVEL_SYMBOL_EN"),
                     "record_id": p.get("IDENTIFIER") or feature.get("id"),
                     "raw_path": raw_path, "received_at_utc": received_at})
    return rows


def summarize(candidate, rows):
    dates = [r["date"] for r in rows]
    if dates != sorted(set(dates)):
        raise ValueError("Repeated or unordered daily dates")
    result = {k: v for k, v in candidate.items() if k != "index_periods"}
    result["parent_chain"] = " > ".join(candidate["parent_chain"])
    result.update(returned_rows=len(rows), first_returned_date=min(dates, default=None),
                  last_returned_date=max(dates, default=None), download_complete=True)
    for field in ("discharge_m3_s", "level_m"):
        valid = [r["date"] for r in rows if r[field] is not None]
        result[field + "_count"] = len(valid)
        result[field + "_first_date"] = min(valid, default=None)
        result[field + "_last_date"] = max(valid, default=None)
    result["both_missing_rows"] = sum(r["level_m"] is None and r["discharge_m3_s"] is None for r in rows)
    result["has_data"] = "Y" if len(rows) > result["both_missing_rows"] else "N"
    result["unreturned_calendar_days"] = ((date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days + 1 - len(dates)) if dates else 0
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--map-folder", default="data/processed/qgis_dickson_joffre_20261012")
    args = parser.parse_args()
    report = read(resolve_runtime_path(ROOT / args.manifest))
    candidates_file = resolve_runtime_path(ROOT / report["candidate_file"])
    folder = candidates_file.parent
    candidates = {r["station_id"]: r for r in read(candidates_file)}
    summaries = []
    for result in report["results"]:
        if not result["complete"]:
            raise ValueError("Incomplete download: " + result["station_id"])
        sid = result["station_id"]
        rows = []
        for relative in result["pages"]:
            path = resolve_runtime_path(ROOT / relative)
            meta = read(path.with_suffix(path.suffix + ".meta.json"))
            if hashlib.sha256(path.read_bytes()).hexdigest() != meta["sha256"]:
                raise ValueError("Raw checksum mismatch")
            rows.extend(normalize(read(path)["features"], sid, relative, meta["received_at_utc"]))
        if len(rows) != result["record_count"] or (result.get("number_matched") is not None and len(rows) != result["number_matched"]):
            raise ValueError("Daily row count mismatch")
        summary = summarize(candidates[sid], rows)
        summaries.append(summary)
        output = folder / "daily" / (sid + ".csv")
        if rows:
            write_csv(output, rows)
    if set(candidates) != {s["station_id"] for s in summaries}:
        raise ValueError("Missing candidate downloads")
    write(folder / "station_summary.json", summaries)
    write_csv(folder / "station_summary.csv", summaries)
    map_folder = resolve_runtime_path(ROOT / args.map_folder)
    selection = resolve_runtime_path(ROOT / "config/map_station_selection.json")
    if selection.exists() and map_folder.resolve() == (resolve_runtime_path(ROOT / read(selection)["map_folder"])).resolve():
        from gis_tools.update_scoped_stations import update_map
        update_map(map_folder, summaries)
        return
    features = [{"type": "Feature", "id": s["station_id"],
                 "geometry": {"type": "Point", "coordinates": [s["longitude"], s["latitude"]]},
                 "properties": {**s, "dataset_role": "historical_daily_reference_not_live_input",
                                "daily_csv": "../../tributary_history_20261012/daily/" + s["station_id"] + ".csv"}}
                for s in summaries if s["role"] == "tributary_channel_station" and s["has_data"] == "Y"]
    layer = map_folder / "eccc_hydrometric_geomet/historical_tributary_stations.geojson"
    write(layer, {"type": "FeatureCollection", "features": features})
    manifest = read(map_folder / "manifest.json")
    relative = layer.relative_to(map_folder).as_posix()
    manifest["layers"] = [e for e in manifest["layers"] if e["path"] != relative]
    manifest["layers"].append({"path": relative, "sha256": hashlib.sha256(layer.read_bytes()).hexdigest(),
        "count": len(features), "source": "eccc_hydrometric_geomet", "style": "historical",
        "title": "Historical tributary stations - daily data (yellow)"})
    manifest["historical_download_manifest"] = args.manifest
    write(map_folder / "manifest.json", manifest)
    print(json.dumps({"stations": len(summaries), "historical_map_points": len(features),
                      "returned_rows": sum(s["returned_rows"] for s in summaries),
                      "numeric_rows": sum(s["returned_rows"] - s["both_missing_rows"] for s in summaries)}, indent=2))
    for s in summaries:
        print(s["station_id"], s["discharge_m3_s_count"], s["level_m_count"], s["discharge_m3_s_first_date"], s["discharge_m3_s_last_date"])


if __name__ == "__main__":
    main()
