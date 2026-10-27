"""Export archived spatial data into source-separated WGS84 GeoJSON layers.

Run with the project virtual environment. This performs no acquisition or ETL
rebuild. The separate render_qgis_project.py uses the installed QGIS runtime.
"""

from project_paths import resolve_runtime_path, archive_relative
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

from pyproj import datadir
from pyproj.transformer import AreaOfInterest, TransformerGroup
from shapely.geometry import box, mapping, shape
from shapely.ops import transform
from shapely import make_valid, is_valid_reason

from project_paths import ROOT
AUDIT = "data/reports/geographic_inventory_verification_20261011.json"
DATUM = "data/reports/horizontal_datum_comparison_20261011.json"
STUDIES = {
    "red_deer": ("Red Deer", "#b43b76"),
    "upper_red_deer": ("Upper Red Deer", "#de7620"),
    "drumheller": ("Drumheller", "#7849b0"),
    "county_markerville": ("County and Markerville", "#008f91"),
}


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="data/processed/qgis_layers_20261011")
    args = parser.parse_args()
    output = (resolve_runtime_path(ROOT / args.output)).resolve()
    if not output.is_relative_to((resolve_runtime_path(ROOT / "data/processed")).resolve()):
        raise ValueError("Output must be inside data/processed")
    if output.exists():
        raise FileExistsError(f"Use a new output folder: {output}")
    output.mkdir(parents=True)
    inputs = {}
    layers = []
    operations = {}
    transformers = {}
    datadir.append_data_dir(str(resolve_runtime_path(ROOT / "data/sources/proj_geodetic_grids/static/coordinate_datums_20261011")))

    def read(relative):
        path = resolve_runtime_path(ROOT / relative)
        inputs[relative] = sha(path)
        return json.loads(path.read_text(encoding="utf-8-sig"))

    def project_geometry(geometry, crs):
        if crs not in transformers:
            group = TransformerGroup(crs, 4326, always_xy=True, allow_ballpark=False,
                                     area_of_interest=AreaOfInterest(-116, 50, -109, 53))
            if not group.transformers or not group.best_available:
                raise ValueError(f"Preferred non-ballpark operation unavailable: {crs}")
            transformers[crs] = group.transformers[0]
            operations[crs] = {"operation": group.transformers[0].description,
                               "pipeline": group.transformers[0].definition,
                               "operation_accuracy_m": group.transformers[0].accuracy,
                               "best_available": group.best_available,
                               "note": "Operation accuracy is not source survey accuracy."}
        return mapping(transform(transformers[crs].transform, shape(geometry)))

    def feature(identifier, geometry, properties):
        return {"type": "Feature", "id": str(identifier), "geometry": geometry,
                "properties": {"feature_id": str(identifier), **properties}}

    def point(x, y):
        return {"type": "Point", "coordinates": [x, y]}

    def export(source, stem, title, features, style, visible=True, color=None):
        if not features:
            raise ValueError(f"Empty output layer: {stem}")
        path = output / source / f"{stem}.geojson"
        path.parent.mkdir(parents=True, exist_ok=True)
        types = Counter()
        invalid = 0
        repairs = []
        bounds = [180., 90., -180., -90.]
        ids = set()
        for item in features:
            if item["id"] in ids:
                raise ValueError(f"Duplicate feature ID in {stem}: {item['id']}")
            ids.add(item["id"])
            geom = shape(item["geometry"])
            if geom.is_empty:
                raise ValueError(f"Empty geometry in {stem}")
            if not geom.is_valid and geom.geom_type in {"Polygon", "MultiPolygon"}:
                reason = is_valid_reason(geom)
                repaired = make_valid(geom)
                if repaired.is_empty or not repaired.is_valid or repaired.geom_type not in {"Polygon", "MultiPolygon"}:
                    raise ValueError(f"Polygon repair requires manual review: {stem}/{item['id']}")
                area_delta = abs(repaired.area - geom.area) / geom.area if geom.area else None
                if area_delta is None or area_delta > 1e-8:
                    raise ValueError(f"Polygon repair changes area materially: {stem}/{item['id']}")
                item["geometry"] = mapping(repaired)
                item["properties"]["geometry_repair"] = "Shapely make_valid; original source preserved"
                item["properties"]["original_geometry_issue"] = reason
                repairs.append({"id": item["id"], "issue": reason, "relative_planar_area_change": area_delta})
                geom = repaired
            x0, y0, x1, y1 = geom.bounds
            if not all(math.isfinite(v) for v in geom.bounds) or not (-180 <= x0 <= x1 <= 180 and -90 <= y0 <= y1 <= 90):
                raise ValueError(f"Invalid geographic bounds: {stem}")
            bounds = [min(bounds[0], x0), min(bounds[1], y0), max(bounds[2], x1), max(bounds[3], y1)]
            types[geom.geom_type] += 1
            invalid += not geom.is_valid
            item["properties"]["source_dataset"] = source
            item["properties"]["output_crs"] = "EPSG:4326"
        payload = {"type": "FeatureCollection", "name": stem, "bbox": bounds, "features": features}
        path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")), encoding="utf-8")
        layers.append({"path": path.relative_to(output).as_posix(), "source": source,
                       "title": title, "count": len(features), "geometry_types": dict(types),
                       "invalid_geometries": invalid, "bbox": bounds, "style": style,
                       "geometry_repairs": repairs, "visible": visible, "color": color, "sha256": sha(path)})
        print(f"Exported {stem}: {len(features)} features; {invalid} invalid", flush=True)

    audit = read(AUDIT)
    read(DATUM)
    inventory_path = audit["output_verification"]["csv_path"]
    inputs[inventory_path] = sha(resolve_runtime_path(ROOT / inventory_path))
    assert inputs[inventory_path] == audit["output_verification"]["sha256"]
    stations = {r["station_id"]: r for r in read("data/processed/station_master.json")}
    rows = {(r["type"], r["id"]): r for r in audit["rows"]}
    hydro_layers = defaultdict(list)
    for row in audit["rows"]:
        if row["type"] != "hydrometric":
            continue
        confirmed = row["coordinate_datum_confirmed"]
        source = "eccc_hydrometric_geomet" if confirmed else "eccc_wateroffice"
        props = {k: v for k, v in row.items() if k not in {"type", "coordinate_datum_review", "data_evidence"}}
        props.update(station_id=row["id"], station_kind=stations[row["id"]]["kind"],
                     selected_mainstem=row["id"] in {"05CA009", "05CC002", "05CE001", "05CK004"},
                     coordinate_source=source,
                     source_crs="OGC:CRS84" if confirmed else "unknown",
                     coordinate_status="source_declared_geographic" if confirmed else "unconfirmed_WGS84_display_assumption",
                     has_data_any=row["has_data"],
                     data_snapshot="2026-10-11 local inventory; not live station status",
                     provenance=AUDIT)
        props["has_data"] = "Y" if row.get("data_evidence", {}).get("original_geomet_records", 0) else "N"
        props["data_scope"] = "Finite archived GeoMet level/discharge" if confirmed else "Historical coordinate index only"
        hydro_layers[source].append(feature(row["id"], point(row["longitude"], row["latitude"]), props))
        count = row.get("data_evidence", {}).get("original_datamart_records", 0)
        if count:
            dm = dict(props, has_data="Y", archived_numeric_record_count=count,
                      data_scope="Finite archived Datamart level/discharge; repeated downloads may overlap",
                      coordinate_source=source)
            hydro_layers["eccc_hydrometric_datamart"].append(feature(row["id"], point(row["longitude"], row["latitude"]), dm))
    export("eccc_hydrometric_geomet", "hydrometric_stations", "GeoMet hydrometric stations", hydro_layers["eccc_hydrometric_geomet"], "hydro")
    export("eccc_wateroffice", "historical_stations_datum_unconfirmed", "Historical stations - DATUM UNCONFIRMED", hydro_layers["eccc_wateroffice"], "uncertain", color="#e59a00")
    export("eccc_hydrometric_datamart", "archived_observation_sites", "Datamart archived observation sites (overlap GeoMet)", hydro_layers["eccc_hydrometric_datamart"], "hydro", visible=False)

    sections = read("data/processed/etl/sections.json")
    survey_points = read("data/processed/etl/survey_points.json")
    for study, (title, color) in STUDIES.items():
        source = f"alberta_flood_surveys/{study}"
        lines, locations, measurements = [], [], []
        for section in sections:
            if section["study"] != study:
                continue
            row = rows[("section", section["section_id"])]
            props = {k: v for k, v in section.items() if k != "geometry"}
            props.update(has_data=row["has_data"], csv_row=row["csv_row"],
                         sort_status=row["sort_status"], distance_to_outlet_m=row.get("distance_to_outlet_m"),
                         source_crs=section["horizontal_crs"], coordinate_datum_confirmed=True,
                         geometry_role="survey_or_planned_section_line",
                         provenance="data/processed/etl/sections.json")
            lines.append(feature(section["section_id"], project_geometry(section["geometry"], section["horizontal_crs"]), props))
            locations.append(feature(section["section_id"], point(row["longitude"], row["latitude"]),
                                     dict(props, geometry_role="representative_location", coordinate_basis=row["coordinate_basis"])))
        for p in survey_points:
            if p["study"] != study:
                continue
            props = {k: v for k, v in p.items() if k != "source_attributes"}
            props.update(source_crs=p["horizontal_crs"], coordinate_datum_confirmed=True,
                         geometry_role="survey_measurement_point", provenance="data/processed/etl/survey_points.json",
                         elevation_note="CGVD28 elevation is an attribute, not a WGS84 ellipsoidal Z coordinate")
            measurements.append(feature(p["point_key"], project_geometry(point(p["x_m"], p["y_m"]), p["horizontal_crs"]), props))
        export(source, "cross_section_lines", f"{title} - cross-section lines", lines, "sections", color=color)
        export(source, "section_locations", f"{title} - representative section locations", locations, "locations", False, color)
        export(source, "survey_points", f"{title} - surveyed measurement points", measurements, "measurements", False, color)

    links = read("data/processed/weather_links.json")
    link_ids = defaultdict(list)
    for link in links:
        if link.get("weather_id"):
            link_ids[link["weather_id"]].append(link["station_id"])
    weather_path = "data/sources/eccc_weather_geomet/raw/discovery/swob_stations.json"
    weather = read(weather_path)
    intervals = read("data/processed/etl/precipitation_intervals.json")
    valid_counts = Counter(p["station_id"] for p in intervals if p.get("valid") and isinstance(p.get("amount_mm"), (float, int)) and math.isfinite(p["amount_mm"]))
    selected = []
    for f in weather["features"]:
        sid = str(f["id"])
        if sid not in link_ids:
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        props = dict(f["properties"], station_id=sid, source_crs="OGC:CRS84",
                     coordinate_datum_confirmed=True, linked_water_stations=", ".join(link_ids[sid]),
                     has_data="Y" if valid_counts[sid] else "N", archived_valid_precipitation_intervals=valid_counts[sid],
                     data_scope="Archived ETL valid precipitation intervals; not current availability",
                     data_snapshot="2026-09-30 ETL", provenance=weather_path,
                     location_note="Weather station location; not the linked hydrometric location")
        selected.append(feature(sid, point(lon, lat), props))
    assert len(selected) == len(link_ids)
    export("eccc_weather_geomet", "linked_weather_stations", "GeoMet linked precipitation stations", selected, "weather", color="#168057")

    partners = []
    for path in sorted((resolve_runtime_path(ROOT / "data/sources/eccc_weather_datamart/raw/validation/partners")).glob("*.xml")):
        relative = archive_relative(path, ROOT).as_posix()
        inputs[relative] = sha(path)
        root = ET.parse(path).getroot()
        values = {e.get("name"): e.get("value") for e in root.iter() if e.tag.endswith("}element")}
        if not values.get("lat") or not values.get("long"):
            continue
        precip = {k: v for k, v in values.items() if k and k.startswith("pcpn_amt") and v}
        numeric = {}
        for k, v in precip.items():
            try:
                if math.isfinite(float(v)) and float(v) >= 0:
                    numeric[k] = float(v)
            except ValueError:
                pass
        sid = values.get("msc_id") or path.stem
        props = dict(station_id=sid, name=values.get("stn_nam"), provider=values.get("data_pvdr"),
                     observation_time=values.get("date_tm"), provenance=relative,
                     source_crs="not specified in archived XML", coordinate_datum_confirmed=False,
                     coordinate_status="unconfirmed_WGS84_display_assumption",
                     precipitation_fields=", ".join(numeric), has_data="Y" if numeric else "N",
                     data_scope="Numeric precipitation present in exploratory XML; quality not validated",
                     selected_for_calculation=False)
        partners.append(feature(sid, point(float(values["long"]), float(values["lat"])), props))
    if partners:
        export("eccc_weather_datamart", "exploratory_partner_weather_sites", "Partner weather - exploratory, datum unconfirmed", partners, "partner", False, "#827a35")

    reference_layers = [
        ("alberta_geospatial", "basin_boundary", "Basin boundary", "EPSG:4326", "boundary", True),
        ("alberta_geospatial", "streams", "Perennial streams", "EPSG:4326", "streams", False),
        ("alberta_geospatial", "intermittent", "Intermittent streams", "EPSG:4326", "streams", False),
        ("alberta_geospatial", "waterbodies", "Lakes and river polygons", "EPSG:4326", "water", True),
        ("nrcan_nhn", "nhn_named_rivers", "NHN named river network", "EPSG:4617", "network", True),
    ]
    for source, stem, title, crs, style, visible in reference_layers:
        relative = f"data/processed/{stem}.geojson"
        data = read(relative)
        features = []
        for i, f in enumerate(data["features"]):
            props = dict(f.get("properties", {}), source_crs=crs, provenance=relative,
                         coordinate_datum_confirmed=True)
            if source == "nrcan_nhn":
                props["connectivity_note"] = "Reference geometry; network direction and ordering remain provisional."
            geom = project_geometry(f["geometry"], crs)
            features.append(feature(f.get("id", i + 1), geom, props))
        export(source, stem, title, features, style, visible)

    for item in audit["satellite_coverage"]:
        quality = resolve_runtime_path(ROOT / item["path"])
        inputs[item["path"]] = sha(quality)
        batch = quality.parent.name
        geom = box(*item["bounds"])
        geom = geom.segmentize(256)
        props = {k: v for k, v in item.items() if k not in {"bounds"} and not k.startswith("representative_locations")}
        props.update(batch_id=batch, source_crs=item["crs"], coordinate_datum_confirmed=True,
                     has_data="Y" if item["finite_reflectance_valid_pixels"] else "N",
                     provenance=item["path"], geometry_role="downloaded_raster_extent_only",
                     coverage_note="Footprint is not a water mask or proof of valid pixels everywhere.")
        export("copernicus_sentinel2", f"coverage_{batch}", f"Sentinel-2 extent - {batch} ({props['has_data']})",
               [feature(batch, project_geometry(mapping(geom), item["crs"]), props)], "satellite",
               visible=props["has_data"] == "Y", color="#6b47cb")

    for relative, expected in inputs.items():
        assert sha(resolve_runtime_path(ROOT / relative)) == expected, relative
    manifest = dict(created_at_utc=datetime.now(timezone.utc).isoformat(), output_crs="EPSG:4326",
                    coordinate_order="longitude, latitude", geometry_dimensions=2,
                    source_inputs=[dict(path=p, sha256=h) for p, h in inputs.items()],
                    transformations=operations, layers=layers,
                    counts={"layers": len(layers), "features": sum(x["count"] for x in layers),
                            "unique_inventory_stations": 102, "unique_sections": len(sections),
                            "survey_measurement_points": len(survey_points)},
                    limitations=[
                        "Four historical water sites retain original coordinates under an explicit WGS84 display assumption; their source datum is unconfirmed.",
                        "Exploratory partner XML coordinates also lack an explicit datum and are separated, labelled and disabled by default.",
                        "The same station may appear in GeoMet and Datamart source layers; do not sum layer counts as unique sites.",
                        "Y/N is archived data availability for the stated layer scope, not live station health or hydraulic suitability.",
                        "csv_row preserves the prior provisional ordering; neighboring rows do not prove hydraulic connectivity.",
                        "Elevations retain their original vertical datum as attributes; no vertical datum conversion was performed.",
                        "Satellite polygons represent downloaded raster extents, not satellite pixels or surveyed sections.",
                        "Reference layers cover their archived query areas; they are not newly clipped or made hydraulically consistent.",
                    ], originals_unchanged=True,
                    excluded_nonspatial_material="Documents, HTML indexes, catalog descriptions, credentials and nonspatial time-series rows are not map geometries.")
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(f"Complete: {len(layers)} layers in {output}")


if __name__ == "__main__":
    main()
