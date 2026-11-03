"""Create display-only weather association areas from existing station links.

Voronoi cells belong to hydrometric sites, inherit their already assigned weather
station, and are dissolved by weather ID and clipped to the archived basin.
This is not a meteorological footprint, catchment delineation or new linkage.
"""

from project_paths import resolve_runtime_path, archive_relative
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from pyproj import Transformer
from shapely import voronoi_polygons, make_valid
from shapely.geometry import MultiPoint, Point, mapping, shape
from shapely.ops import transform, unary_union

from project_paths import ROOT, is_gis_output_path
def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", default="data/processed/qgis_layers_20261011")
    args = parser.parse_args()
    folder = (resolve_runtime_path(ROOT / args.folder)).resolve()
    if not is_gis_output_path(folder):
        raise ValueError("Output folder must be a permitted GIS output directory")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    inputs = {}

    def read(path):
        inputs[archive_relative(path, ROOT).as_posix()] = sha(path)
        return json.loads(path.read_text(encoding="utf-8"))

    links = read(resolve_runtime_path(ROOT / "data/processed/weather_links.json"))
    link_by_water = {row["station_id"]: row["weather_id"] for row in links}
    hydro = []
    for relative in ["eccc_hydrometric_geomet/hydrometric_stations.geojson",
                     "eccc_wateroffice/historical_stations_datum_unconfirmed.geojson"]:
        hydro.extend(read(folder / relative)["features"])
    weather = read(folder / "eccc_weather_geomet/linked_weather_stations.geojson")
    names = {f["id"]: f["properties"].get("name", f["id"]) for f in weather["features"]}
    basin_source = read(folder / "alberta_geospatial/basin_boundary.geojson")
    to_metric = Transformer.from_crs(4326, 3400, always_xy=True, allow_ballpark=False)
    to_wgs = Transformer.from_crs(3400, 4326, always_xy=True, allow_ballpark=False)
    basin = transform(to_metric.transform, unary_union([shape(f["geometry"]) for f in basin_source["features"]]))
    unique_sites = {}
    for f in hydro:
        xy = tuple(f["geometry"]["coordinates"])
        wid = link_by_water[f["id"]]
        if xy in unique_sites and unique_sites[xy]["weather_id"] != wid:
            raise ValueError("Coincident hydrometric sites have conflicting weather links")
        unique_sites.setdefault(xy, {"weather_id": wid, "stations": []})["stations"].append(f["id"])
    site_items = list(unique_sites.items())
    seeds = [Point(*to_metric.transform(*xy)) for xy, _ in site_items]
    cells = voronoi_polygons(MultiPoint(seeds), extend_to=basin.envelope, ordered=True)
    assert len(cells.geoms) == len(seeds)
    grouped, station_ids = defaultdict(list), defaultdict(list)
    outside = []
    for (xy, item), seed, cell in zip(site_items, seeds, cells.geoms):
        assert cell.covers(seed)
        clipped = cell.intersection(basin)
        if not clipped.is_empty:
            grouped[item["weather_id"]].append(clipped)
        station_ids[item["weather_id"]].extend(item["stations"])
        if not basin.covers(seed):
            outside.extend(item["stations"])
    features, metric_areas = [], {}
    for wid in sorted(grouped):
        area = unary_union(grouped[wid])
        assert area.is_valid and area.geom_type in {"Polygon", "MultiPolygon"}
        metric_areas[wid] = area
        geographic = transform(to_wgs.transform, area)
        repaired = not geographic.is_valid
        if repaired:
            geographic = make_valid(geographic, method="structure", keep_collapsed=False)
        assert geographic.is_valid and geographic.geom_type in {"Polygon", "MultiPolygon"}
        features.append({"type": "Feature", "id": wid,
                         "geometry": mapping(geographic),
                         "properties": {"feature_id": wid, "weather_id": wid,
                                        "weather_name": names[wid],
                                        "source_dataset": "derived_weather_associations",
                                        "linked_water_ids": ", ".join(sorted(station_ids[wid])),
                                        "linked_water_count": len(station_ids[wid]),
                                        "area_km2": area.area / 1e6, "output_crs": "EPSG:4326",
                                        "calculation_crs": "EPSG:3400", "official_coverage": False,
                                        "collapsed_geographic_fragments_removed": repaired,
                                        "use": "cartographic association schematic only",
                                        "method": "Hydrometric-site Voronoi cells, grouped by existing weather assignment, basin-clipped",
                                        "limitations": "Not sensor coverage, a weather footprint, rainfall representativeness or catchment; four water coordinates have unconfirmed datum.",
                                        "provenance": "data/processed/weather_links.json"}})
    combined = unary_union(list(metric_areas.values()))
    gap = basin.symmetric_difference(combined).area
    overlap = sum(a.area for a in metric_areas.values()) - combined.area
    assert gap / basin.area < 1e-10 and abs(overlap) / basin.area < 1e-10
    for (xy, item), seed in zip(site_items, seeds):
        if basin.covers(seed):
            assert metric_areas[item["weather_id"]].buffer(0.001).covers(seed)
    destination = folder / "derived_weather_associations/weather_association_areas.geojson"
    destination.parent.mkdir(parents=True, exist_ok=True)
    bounds = unary_union([shape(f["geometry"]) for f in features]).bounds
    destination.write_text(json.dumps({"type": "FeatureCollection", "name": "weather_association_areas",
                                       "bbox": bounds, "features": features}, ensure_ascii=False, allow_nan=False,
                                      separators=(",", ":")), encoding="utf-8")
    relative = destination.relative_to(folder).as_posix()
    manifest["layers"] = [e for e in manifest["layers"] if e["path"] != relative]
    manifest["layers"].append({"path": relative, "source": "derived_weather_associations",
                               "title": "Weather association areas (schematic)", "count": len(features),
                               "geometry_types": {"MultiPolygon": sum(f["geometry"]["type"] == "MultiPolygon" for f in features),
                                                  "Polygon": sum(f["geometry"]["type"] == "Polygon" for f in features)},
                               "invalid_geometries": 0, "bbox": bounds, "style": "weather_areas",
                               "geometry_repairs": [], "visible": True, "color": "#439986", "sha256": sha(destination)})
    manifest["counts"]["layers"] = len(manifest["layers"])
    manifest["counts"]["features"] = sum(e["count"] for e in manifest["layers"])
    manifest["weather_area_derivation"] = {"report": "weather_area_validation.json", "official_coverage": False}
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    for path, expected in inputs.items():
        assert sha(resolve_runtime_path(ROOT / path)) == expected
    report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "areas": len(features),
              "linked_hydrometric_stations": len(hydro), "unique_seed_locations": len(seeds),
              "existing_links_preserved": True, "all_areas_valid": True,
              "basin_partition_gap_m2": gap, "basin_partition_overlap_m2": overlap,
              "stations_outside_archived_basin": outside,
              "method": "Hydrometric Voronoi in EPSG:3400, grouped by existing weather links, clipped to archived basin",
              "scope": "Display-only schematic; no meteorological coverage or new station associations inferred",
              "four_historical_water_positions_remain_unconfirmed": True,
              "inputs": [{"path": p, "sha256": h} for p, h in inputs.items()],
              "output": relative, "sha256": sha(destination)}
    (folder / "weather_area_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "inputs"}, indent=2))


if __name__ == "__main__":
    main()
