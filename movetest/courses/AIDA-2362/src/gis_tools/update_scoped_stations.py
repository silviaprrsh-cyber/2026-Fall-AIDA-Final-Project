"""Apply reviewed station exclusions and mutually exclusive recency map layers."""

from project_paths import resolve_runtime_path, archive_relative
import calendar
from copy import deepcopy
from datetime import date, datetime, time, timezone
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from pyproj import Transformer
from shapely.geometry import LineString, Point
from shapely.ops import transform

from project_paths import ROOT
def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def window_start(day, months, zone):
    ordinal = day.year * 12 + day.month - 1 - months
    year, month = divmod(ordinal, 12)
    month += 1
    start = date(year, month, min(day.day, calendar.monthrange(year, month)[1]))
    return datetime.combine(start, time.min, ZoneInfo(zone))


def recent(value, start, end):
    if not value:
        return False
    if len(value) == 10:
        return start.date() <= date.fromisoformat(value) <= end.astimezone(start.tzinfo).date()
    stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if stamp.tzinfo is None:
        raise ValueError("Instantaneous observations must specify a time zone")
    return start <= stamp <= end


def partition(stations, summaries, results, rules, end):
    start = window_start(date.fromisoformat(rules["as_of_local_date"]), rules["recent_calendar_months"], rules["time_zone"])
    excluded = set(rules["excluded_station_ids"])
    points = {}
    for s in summaries:
        if (s["role"] != "tributary_channel_station" and s["station_id"] not in rules.get("reference_station_ids", [])) or s["has_data"] != "Y":
            continue
        points[s["station_id"]] = {"type": "Feature", "id": s["station_id"],
            "geometry": {"type": "Point", "coordinates": [s["longitude"], s["latitude"]]},
            "properties": deepcopy(s)}
    for f in stations:
        sid = f["properties"]["station_id"]
        merged = deepcopy(f)
        merged["id"] = sid
        merged["properties"] = {**points.get(sid, {}).get("properties", {}), **merged["properties"]}
        points[sid] = merged
    by_id = {r["station_id"]: r for r in results}
    blue, yellow = [], []
    for sid, f in sorted(points.items()):
        if sid in excluded:
            continue
        p = f["properties"]
        result = by_id.get(sid, {})
        evidence = []
        if p.get("latest_observation_utc") and not (result.get("status") == "numeric_observations" and result.get("latest_observation")):
            evidence.append((p["latest_observation_utc"], p.get("raw_path")))
        if result.get("status") == "numeric_observations" and result.get("latest_observation"):
            evidence.append((result["latest_observation"], result.get("raw_path")))
            latest = result.get("latest_properties") or {}
            p.update(level_m=latest.get("LEVEL"), discharge_m3_s=latest.get("DISCHARGE"),
                     latest_observation_utc=result["latest_observation"], raw_path=result.get("raw_path"))
        for key in ("discharge_m3_s_last_date", "level_m_last_date"):
            if p.get(key):
                evidence.append((p[key], "data/processed/tributary_history_20261012/station_summary.json"))
        matching = [(d, source) for d, source in evidence if recent(d, start, end)]
        is_recent = bool(matching)
        p.update(recent_data="Y" if is_recent else "N", map_color="blue" if is_recent else "yellow",
                 recency_start_local=start.isoformat(), recency_checked_at_utc=end.isoformat(),
                 recent_evidence=json.dumps(matching), current_query_status=result.get("status", "not_queried"),
                 recency_note="Numeric observation in window" if is_recent else
                 "No recent observation found; archived history and latest API sample checked. Empty realtime responses alone do not prove a complete three-month absence.")
        if sid in rules.get("yellow_reference_ids", []):
            p.update(map_color="yellow", display_role="lake_level_reference",
                     recent_data="Y" if is_recent else ("unknown" if not result else "N"),
                     recency_note="Yellow denotes the requested lake-level reference, not confirmed absence of recent data.",
                     map_label=f"{sid} (lake)")
            yellow.append(f)
            continue
        (blue if is_recent else yellow).append(f)
    return blue, yellow


def coordinate_review(source):
    metadata_path = next(p for p in source["coordinate_sources"] if p.endswith("_metadata.json"))
    metadata = read(resolve_runtime_path(ROOT / metadata_path))["features"]
    station = next(f for f in metadata if f["properties"]["STATION_NUMBER"] == "05CC004")
    coord = station["geometry"]["coordinates"]
    wateroffice_path = next(p for p in source["coordinate_sources"] if p.endswith("_reference_index.html"))
    html = (resolve_runtime_path(ROOT / wateroffice_path)).read_text(encoding="utf-8")
    assert "52&deg;19'00" in html and "114&deg;04'00" in html
    osm_path = next(p for p in source["coordinate_sources"] if p.endswith("sylvan_waterways.json"))
    metric = Transformer.from_crs(4326, 3400, always_xy=True).transform
    point = Point(metric(*coord))
    candidates = []
    for way in read(resolve_runtime_path(ROOT / osm_path))["elements"]:
        if way.get("tags", {}).get("name") != "Sylvan Creek" or len(way.get("geometry", [])) < 2:
            continue
        line = transform(metric, LineString([(v["lon"], v["lat"]) for v in way["geometry"]]))
        candidates.append((point.distance(line), way["id"]))
    distance, way_id = min(candidates)
    return {"station_id": "05CC004", "official_lon_lat": coord,
            "wateroffice_coordinate_text": "52 degrees 19 minutes 00 seconds N; 114 degrees 04 minutes 00 seconds W",
            "coordinate_status": "official_coordinate_verified_exact_historical_site_unresolved",
            "nearest_osm_sylvan_creek_distance_m": distance, "nearest_osm_way_id": way_id,
            "note": "GeoMet agrees with Wateroffice's whole-minute coordinates. The point is approximately 255 m from the mapped creek. Coarse historical coordinates are a possible explanation, not a proven error model. No surveyed replacement location was found; do not snap or treat as an exact hydraulic transfer point.",
            "coordinate_moved": False, "sources": [metadata_path, wateroffice_path, osm_path]}


def update_map(folder=None, summaries=None):
    rules = read(resolve_runtime_path(ROOT / "config/map_station_selection.json"))
    folder = folder or resolve_runtime_path(ROOT / rules["map_folder"])
    if folder.resolve() != (resolve_runtime_path(ROOT / rules["map_folder"])).resolve():
        raise ValueError("Map selection rules do not apply to this folder")
    summaries = summaries or read(resolve_runtime_path(ROOT / "data/processed/tributary_history_20261012/station_summary.json"))
    source = read(resolve_runtime_path(ROOT / rules["source_review"]))
    end = datetime.strptime(source["run"], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    assert end.astimezone(ZoneInfo(rules["time_zone"])).date().isoformat() == rules["as_of_local_date"]
    stations = []
    for name in ("stations.geojson", "historical_tributary_stations.geojson"):
        stations.extend(read(folder / "eccc_hydrometric_geomet" / name)["features"])
    blue, yellow = partition(stations, summaries, source["results"], rules, end)
    review = coordinate_review(source)
    for f in blue + yellow:
        if f["properties"]["station_id"] == "05CC004":
            f["geometry"]["coordinates"] = review["official_lon_lat"]
            f["properties"].update(coordinate_status=review["coordinate_status"],
                coordinate_note=review["note"], nearest_mapped_creek_distance_m=review["nearest_osm_sylvan_creek_distance_m"],
                map_label="05CC004 (location approximate)")
    manifest = read(folder / "manifest.json")
    for name, features, style, title in (
        ("stations.geojson", blue, "hydro", "Water stations - data in last 3 months (blue)"),
        ("historical_tributary_stations.geojson", yellow, "historical", "Historical / lake reference stations (yellow)"),
    ):
        path = folder / "eccc_hydrometric_geomet" / name
        write(path, {"type": "FeatureCollection", "features": features})
        relative = path.relative_to(folder).as_posix()
        entry = next(e for e in manifest["layers"] if e["path"] == relative)
        entry.update(count=len(features), sha256=hashlib.sha256(path.read_bytes()).hexdigest(), style=style, title=title)
    assert not ({f["id"] for f in blue} & {f["id"] for f in yellow})
    report = {"as_of_local_date": rules["as_of_local_date"], "source_review": rules["source_review"],
              "blue_ids": [f["id"] for f in blue], "yellow_ids": [f["id"] for f in yellow],
              "excluded_ids": rules["excluded_station_ids"], "duplicate_station_ids": [], "archived_coordinate_review": review,
              "yellow_reference_ids": rules.get("yellow_reference_ids", [])}
    manifest["station_display_review"] = report
    start = window_start(date.fromisoformat(rules["as_of_local_date"]), rules["recent_calendar_months"], rules["time_zone"])
    manifest["recency_legend"] = (f"Blue: observation since {start.date()}; yellow: historical / lake reference. "
                                  f"Checked {rules['as_of_local_date']}.")
    write(folder / "manifest.json", manifest)
    write(folder / "station_display_review.json", report)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    update_map()
