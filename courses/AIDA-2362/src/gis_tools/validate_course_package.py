"""Validate the active GIS layers in QGIS using an isolated relative-path copy."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZipFile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    NULL, Qgis, QgsApplication, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsGeometry, QgsPointXY, QgsProject,
    QgsWkbTypes,
)

COURSE = Path(__file__).resolve().parents[2]
PROJECT = COURSE / "project"
PROJECT_NAME = "dickson_to_joffre.qgz"
TARGETS = ["P01", "P02", "P03", "P04", "P05"]
LOCAL = {
    "nrcan_nhn/selected_rivers.geojson": (
        "river", ("role",), "Line",
    ),
    "eccc_hydrometric_geomet/stations.geojson": (
        "station_id", ("name", "river", "role", "latest_observation_utc"), "Point",
    ),
    "eccc_hydrometric_geomet/historical_tributary_stations.geojson": (
        "station_id", ("name", "river", "role"), "Point",
    ),
    "eccc_weather_geomet/stations.geojson": (
        "station_id", ("name", "latest_observation_utc", "data_snapshot"), "Point",
    ),
    "alberta_flood_surveys/red_deer/cross_section_lines.geojson": (
        "section_id", ("source_section_id", "river", "line_status", "survey_date", "source_fid"), "Line",
    ),
    "alberta_flood_surveys/county_markerville/cross_section_lines.geojson": (
        "section_id", ("source_section_id", "river", "line_status", "source_fid"), "Line",
    ),
    "derived_prediction_targets/prediction_points.geojson": (
        "target_id", ("name", "nearest_section_id", "nearest_section_along_river_offset_m", "chainage_from_dickson_m"), "Point",
    ),
    "derived_weather_associations/areas.geojson": (
        "weather_id", ("meaning", "cartographic_buffer_m", "not_official_coverage", "not_a_catchment"), "Polygon",
    ),
}
ALBERTA_METRIC_AREA = (-120.0, 48.99, -109.98, 60.0)  # EPSG:3400 area of use
SURVEY_3TM_AREA = (-115.5, 48.99, -112.5, 60.0)  # EPSG:3780 area of use
TABLE_COLUMNS = (
    "layer_title", "feature_id", "label_or_river", "display_role", "line_status",
    "reference_date_utc_or_survey_date", "geometry_type", "longitude_if_point",
    "latitude_if_point", "bbox_west", "bbox_south", "bbox_east", "bbox_north",
    "recorded_chainage_or_length_m", "nearest_section_id", "absolute_along_river_offset_m",
    "kept_at_25m", "kept_at_50m", "decision_or_interpretation",
)


def need(condition, message):
    if not condition:
        raise ValueError(message)


def is_missing(v):
    return v is None or v == NULL or (isinstance(v, str) and not v.strip())


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def file_hash(path):
    with path.open("rb") as fp:
        return hashlib.file_digest(fp, "sha256").hexdigest()


def require_relative_xml(path):
    with ZipFile(path) as z:
        root = ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith(".qgs"))))
    paths = root.findall("./projectlayers/maplayer")
    files = {p.findtext("datasource") for p in paths if p.findtext("provider") == "ogr"}
    need(files == {"./" + name for name in LOCAL}, "Project XML uses missing, extra or non-relative local paths.")
    others = [(p.findtext("layername"), p.findtext("provider")) for p in paths if p.findtext("provider") != "ogr"]
    need(others == [("OpenStreetMap", "wms")], "Unexpected live/remote layer.")
    return root


def in_bounds(p, bounds):
    west, south, east, north = bounds
    return west <= p.x() <= east and south <= p.y() <= north


def scan_layer(layer, rel, transform, reverse, expected):
    id_field, required, wanted_type = LOCAL[rel]
    fields = [f.name() for f in layer.fields()]
    need(set((id_field, *required)) <= set(fields), f"{rel}: missing required columns.")
    need(layer.crs().authid() == "EPSG:4326", f"{rel}: unexpected storage CRS.")
    missing = Counter()
    ids = Counter()
    invalid = []
    empty = []
    wrong_kind = []
    offsite = []
    bad_transform = []
    verts = 0
    max_roundtrip = 0.0
    rows = {}
    for f in layer.getFeatures():
        p = {key: val for key, val in zip(fields, f.attributes()) if not is_missing(val)}
        missing.update(key for key in fields if key not in p)
        ident = str(p.get(id_field, ""))
        ids[ident] += 1
        g = f.geometry()
        if g.isNull() or g.isEmpty():
            empty.append(ident)
            continue
        if QgsWkbTypes.geometryDisplayString(g.type()) != wanted_type:
            wrong_kind.append(ident)
        if not g.isGeosValid():
            invalid.append(ident)
        out_of_area = False
        transform_ok = True
        for v in g.vertices():
            verts += 1
            xy = QgsPointXY(v.x(), v.y())
            if not in_bounds(xy, ALBERTA_METRIC_AREA) or (rel.startswith("alberta_flood_surveys/") and not in_bounds(xy, SURVEY_3TM_AREA)):
                out_of_area = True
            try:
                metric = transform.transform(xy)
                lonlat = reverse.transform(metric)
                roundtrip = math.hypot(xy.x() - lonlat.x(), xy.y() - lonlat.y())
                if not all(math.isfinite(v) for v in (metric.x(), metric.y(), roundtrip)):
                    transform_ok = False
                    continue
                max_roundtrip = max(max_roundtrip, roundtrip)
            except Exception:
                transform_ok = False
        if out_of_area:
            offsite.append(ident)
        if not transform_ok:
            bad_transform.append(ident)
        rows[ident] = (p, QgsGeometry(g))
    result = {
        "source_relative_to_project": rel,
        "display_name": layer.name(),
        "geometry_kind_expected": wanted_type,
        "storage_crs": layer.crs().authid(),
        "count": int(layer.featureCount()), "expected_count": expected,
        "id_field": id_field, "duplicate_ids": sorted(k for k, n in ids.items() if n > 1),
        "blank_id_count": ids[""],
        "required_decision_fields": [id_field, *required],
        "missing_required_values": {k: missing[k] for k in (id_field, *required) if missing[k]},
        "blank_or_null_by_field": dict(sorted(missing.items())),
        "empty_geometry_ids": empty, "invalid_geos_geometry_ids": invalid,
        "wrong_geometry_type_ids": wrong_kind, "outside_applicable_bbox_ids": offsite,
        "transform_error_ids": bad_transform,
        "transformed_vertices": verts, "max_roundtrip_error_degrees": max_roundtrip,
    }
    return rows, result


def geom_metric(g, transform):
    g = QgsGeometry(g)
    need(int(g.transform(transform)) == 0, "QGIS geometry transform failed.")
    return g


def nonempty_cross_points(g):
    if g.isNull() or g.isEmpty():
        return []
    if g.type() == Qgis.GeometryType.Point:
        return [QgsGeometry.fromPointXY(QgsPointXY(v.x(), v.y())) for v in g.vertices()]
    if QgsWkbTypes.flatType(g.wkbType()) == Qgis.WkbType.GeometryCollection:
        return [p for part in g.asGeometryCollection() for p in nonempty_cross_points(part)]
    return []


def decision_check(layers, section_rows, transform):
    network = layers["nrcan_nhn/selected_rivers.geojson"]
    centerline = geom_metric(network["RED DEER RIVER"][1], transform)
    crossings = []
    no_crossings = []
    for ident, (p, g) in section_rows.items():
        if p["river"] != "RED DEER RIVER":
            continue
        points = nonempty_cross_points(centerline.intersection(geom_metric(g, transform)))
        if not points:
            no_crossings.append(ident)
        for pt in points:
            chainage = centerline.lineLocatePoint(pt)
            need(math.isfinite(chainage) and chainage >= 0, f"{ident}: bad river-section projection.")
            crossings.append((ident, chainage))
    with (COURSE / "outputs/section-proximity-sensitivity.csv").open(encoding="utf-8", newline="") as f:
        expected = {r["target_id"]: r for r in csv.DictReader(f)}
    target_rel = "derived_prediction_targets/prediction_points.geojson"
    targets = layers[target_rel]
    need(sorted(targets) == sorted(expected) == TARGETS, "Wrong target identifiers.")
    distance_sources = []
    max_delta = 0.0
    for ident, (p, g) in targets.items():
        near_id = p["nearest_section_id"]
        need(near_id in section_rows, f"{ident}: nearest section does not resolve.")
        need(p.get("on_section_id", near_id) == near_id, f"{ident}: on-section relation disagrees.")
        point = geom_metric(g, transform)
        need(centerline.distance(point) < 0.001, f"{ident}: target not on the mainstem.")
        chainage = centerline.lineLocatePoint(point)
        near, saved = min(crossings, key=lambda r: abs(r[1] - chainage))
        offset = saved - chainage
        delta = abs(offset - p["nearest_section_along_river_offset_m"])
        max_delta = max(max_delta, delta)
        need(near_id == near and delta < 0.001, f"{ident}: saved offset or nearest section mismatched.")
        need(expected[ident]["section_id"] == near_id
             and expected[ident]["section_status"] == section_rows[near_id][0]["line_status"]
             and abs(float(expected[ident]["signed_offset_m"]) - offset) < 0.001,
             f"{ident}: sensitivity table did not reconcile.")
        distance_sources.append(near_id)
    need(len(set(distance_sources)) == len(TARGETS), "Duplicate nearest-section associations.")
    need(len(crossings) == 145 and len({item[0] for item in crossings}) == 145, "Unexpected projected point-crossing counts.")
    return expected, {
        "nearest_section_links_resolved": len(distance_sources),
        "usable_mainstem_section_point_crossings": len(crossings),
        "mapped_mainstem_sections_without_point_crossing": sorted(no_crossings),
        "maximum_difference_from_stored_along_river_offset_m": max_delta,
        "mainstem_length_m_recomputed_epsg3400": centerline.length(),
        "mainstem_length_difference_m_from_layer_field": abs(centerline.length() - network["RED DEER RIVER"][0]["length_m"]),
        "target_to_section_proximity_does_not_verify_datum": True,
        "profile_flags_marked_verified": sum(bool(row[0]["profile_verified"]) for row in section_rows.values()),
        "bank_flags_marked_verified": sum(bool(row[0]["bank_elevations_verified"]) for row in section_rows.values()),
    }


def table_row(layer_name, ident, p, g, comparison):
    b = g.boundingBox()
    point = g.asPoint() if g.type() == Qgis.GeometryType.Point and not g.isMultipart() else None
    interpretation = p.get("meaning") or p.get("recency_note") or p.get("location_note") or p.get("geometry_role") or ""
    if comparison:
        interpretation = (
            "Added in the broader screen; review surveyed section record first."
            if comparison["changed"] == "added" else
            "Retained in both screens; proposed line still needs a surveyed profile."
        )
    return {
        "layer_title": layer_name, "feature_id": ident,
        "label_or_river": p.get("name", p.get("river", ident)),
        "display_role": p.get("display_role", p.get("role", p.get("geometry_role", "weather_context"))),
        "line_status": p.get("line_status"),
        "reference_date_utc_or_survey_date": p.get("survey_date", p.get("latest_observation_utc", p.get("last_returned_date"))),
        "geometry_type": QgsWkbTypes.displayString(g.wkbType()),
        "longitude_if_point": point.x() if point is not None else None,
        "latitude_if_point": point.y() if point is not None else None,
        "bbox_west": b.xMinimum(), "bbox_south": b.yMinimum(), "bbox_east": b.xMaximum(), "bbox_north": b.yMaximum(),
        "recorded_chainage_or_length_m": p.get("chainage_from_dickson_m", p.get("selected_river_chainage_m", p.get("length_m"))),
        "nearest_section_id": comparison["section_id"] if comparison else None,
        "absolute_along_river_offset_m": comparison["absolute_offset_m"] if comparison else None,
        "kept_at_25m": comparison["passes_25m"] if comparison else None,
        "kept_at_50m": comparison["passes_50m"] if comparison else None,
        "decision_or_interpretation": interpretation,
    }


def validate(scratch):
    mf = read_json(PROJECT / "manifest.json")
    expected = {r["path"]: (r["count"], r["sha256"]) for r in mf["layers"]}
    need(expected.keys() == LOCAL.keys(), "Layer manifest and validator layer list disagree.")
    src_files = {PROJECT_NAME: file_hash(PROJECT / PROJECT_NAME)}
    src_files.update({rel: expected_hash for rel, (_, expected_hash) in expected.items()})
    for rel, digest in src_files.items():
        source = (PROJECT / rel).resolve()
        need(source.is_relative_to(PROJECT) and source.is_file() and file_hash(source) == digest, f"{rel}: missing input or hash differs.")
        path = scratch / "project" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, path)
    qgz = scratch / "project" / PROJECT_NAME
    xml = require_relative_xml(qgz)
    need(xml.findtext("./projectCrs/spatialrefsys/authid") == "EPSG:3857", "Unexpected project display CRS.")
    prefix = os.environ.get("QGIS_PREFIX_PATH")
    if prefix:
        QgsApplication.setPrefixPath(prefix, True)
    app = QgsApplication([], False, str(scratch / "qgis_profile"))
    app.initQgis()
    project = QgsProject.instance()
    try:
        need(project.read(str(qgz)), "Independent project copy did not open.")
        layouts = sorted(layout.name() for layout in project.layoutManager().layouts())
        need(layouts == ["Overhead view", "Simple OSM overview"], "Expected layouts not found.")
        need(project.filePathStorage() == Qgis.FilePathType.Relative, "QGIS path mode is not relative.")
        all_layers = list(project.mapLayers().values())
        vector = {}
        basemap = []
        for layer in all_layers:
            if layer.providerType() == "ogr":
                src = Path(layer.source().split("|", 1)[0]).resolve()
                need(src.is_relative_to((scratch / "project").resolve()), f"{layer.name()}: absolute resolution outside independently copied project.")
                need(layer.isValid(), f"{layer.name()}: could not open layer.")
                vector[src.relative_to(scratch / "project").as_posix()] = layer
            else:
                basemap.append({"name": layer.name(), "provider": layer.providerType(), "rendered_or_fetched": False})
        need(vector.keys() == LOCAL.keys() and len(all_layers) == 9, "Wrong local layer count.")
        geo = QgsCoordinateReferenceSystem("EPSG:4326")
        metric = QgsCoordinateReferenceSystem("EPSG:3400")
        need(metric.isValid() and metric.mapUnits() == Qgis.DistanceUnit.Meters and geo.isGeographic(), "Unexpected coordinate or distance units.")
        fwd = QgsCoordinateTransform(geo, metric, project)
        inv = QgsCoordinateTransform(metric, geo, project)
        features, summaries = {}, []
        for rel in LOCAL:
            records, result = scan_layer(vector[rel], rel, fwd, inv, expected[rel][0])
            features[rel] = records
            summaries.append(result)
        sections = {}
        for rel, rows in features.items():
            if rel.startswith("alberta_flood_surveys/"):
                need(not sections.keys() & rows.keys(), "Cross-section identifiers are not globally unique.")
                sections.update(rows)
        expected_comp, decision = decision_check(features, sections, fwd)
        target_layer = vector["derived_prediction_targets/prediction_points.geojson"]
        selections = {}
        for threshold in (25, 50):
            expression = f'abs("nearest_section_along_river_offset_m") <= {threshold}'
            target_layer.selectByExpression(expression)
            selections[str(threshold)] = sorted(f["target_id"] for f in target_layer.selectedFeatures())
            need(selections[str(threshold)] == sorted(k for k, row in expected_comp.items()
                                                    if row[f"passes_{threshold}m"] == "yes"),
                 f"QGIS attribute selection is inconsistent at {threshold} m.")
        target_layer.removeSelection()
        decision["qgis_select_by_expression_ids"] = selections
        displayed = [
            table_row(vector[rel].name(), ident, p, g, expected_comp.get(ident))
            for rel, rows in features.items() for ident, (p, g) in sorted(rows.items())
        ]
        need(all(file_hash(PROJECT / rel) == digest and file_hash(scratch / "project" / rel) == digest
                 for rel, digest in src_files.items()), "Original or copied source mutated during checking.")
        hard = ("duplicate_ids", "blank_id_count", "missing_required_values", "empty_geometry_ids",
                "wrong_geometry_type_ids", "outside_applicable_bbox_ids", "transform_error_ids")
        failed = [
            {k: x[k] for k in ("source_relative_to_project", "count", "expected_count", "max_roundtrip_error_degrees", *hard)}
            for x in summaries
            if x["count"] != x["expected_count"] or any(x[key] for key in hard) or x["max_roundtrip_error_degrees"] >= 1e-8
        ]
        need(not failed, f"Current-scope geometry/ID/field/CRS/layer assertions failed: {failed}")
        need(len(displayed) == sum(x["count"] for x in summaries), "Map-equivalent table is incomplete.")
        return displayed, {
            "scope": "dickson_to_05CC002",
            "validation_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "qgis_version": Qgis.QGIS_VERSION,
            "procedure": "Independent relative-path copy; no release ZIP created or extracted by this check.",
            "copied_qgz_reopened": True, "relative_file_path_storage": True,
            "display_crs": "EPSG:3857", "vector_storage_crs": "EPSG:4326",
            "distance_crs": "EPSG:3400 (metres)",
            "area_checks": {"EPSG:3400_bbox_wsen": ALBERTA_METRIC_AREA, "EPSG:3780_bbox_wsen_for_survey_layers": SURVEY_3TM_AREA},
            "local_vector_layers": len(vector), "map_equivalent_feature_rows": len(displayed),
            "remote_layers_not_rendered": basemap, "layouts": layouts, "layer_checks": summaries,
            "section_and_target_checks": decision,
            "known_exceptions": [
                "County proposed lines have no individual survey date. Null stage/flow/risk for GIS targets is intentional.",
                "Reference 05CC012 lacks optional display_role and map_label. The table falls back to its populated role and station_id.",
                "RDR087 is mapped as a near-route section line but does not intersect the mainstem.",
                "QGIS GEOS validation addresses geometric structure, not authoritative survey accuracy or hydraulic connectivity.",
                "The OSM basemap was not requested; the boxed weather corridor is schematic.",
                "The hosted release ZIP, its licences, peer review, and the student's in-class QGIS demo are separate checks.",
            ],
            "source_hashes_verified": src_files,
        }
    finally:
        project.clear()
        app.exitQgis()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-only", action="store_true", help="Do not write validation JSON or the equivalent CSV.")
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix=".qgis-readiness-", dir=COURSE) as folder:
        scratch = Path(folder).resolve()
        need(scratch.is_relative_to(COURSE) and scratch.name.startswith(".qgis-readiness-"), "Unsafe scratch location.")
        table, report = validate(scratch)
    if not args.check_only:
        report_path = COURSE / "outputs/current-qgis-validation.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2) + "\n", encoding="utf-8")
        with (COURSE / "outputs/map-feature-equivalent.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=TABLE_COLUMNS)
            writer.writeheader()
            writer.writerows(table)
    invalid = sum(len(r["invalid_geos_geometry_ids"]) for r in report["layer_checks"])
    print(f"QGIS reopened the separate copy: {report['local_vector_layers']} relative layers, "
          f"{report['map_equivalent_feature_rows']} features, {invalid} invalid GEOS geometries, 5/5 offset links reconciled.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
