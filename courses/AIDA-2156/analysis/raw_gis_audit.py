"""Inspect the original Alberta survey geodatabases, then audit current GIS links."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

COURSE = Path(__file__).resolve().parents[1]
GIS_COURSE = COURSE.parent / "AIDA-2362"
REPO = COURSE.parents[1]
MANUAL = GIS_COURSE / "data/sources/alberta_flood_surveys/manual"
WORKING = GIS_COURSE / "project"
DEFAULT_OUTPUT = COURSE / "output/raw_data_eda"
MAINSTEM = "RED DEER RIVER"
MISSING = "<missing>"


@dataclass(frozen=True)
class Archive:
    key: str
    path: str
    point_layer: str
    elevation: str
    point_fields: tuple[str, ...]
    line_layer: str
    line_id: str
    line_river: str
    line_fields: tuple[str, ...]
    line_status: str
    report: str
    report_pages: str


ARCHIVES = (
    Archive(
        "red_deer", "Red Deer/SURVEY_DATA.gdb",
        "Survey_Points", "Elevation", ("Class", "Date"), "Survey_Cross_Sections",
        "CS_ID", "RiverCode", ("Date", "RiverCode"), "surveyed",
        "ep-draft-red-deer-survey-base-data-report-mar-2021.pdf", "8",
    ),
    Archive(
        "county_markerville", "Red Deer County and Markerville/A_FieldSurvey.gdb",
        "FLD_CrossSectionTopoSurvey", "Elevation", ("PtType",), "FLD_ProposedCrossSectionLines",
        "NodeName", "RiverName", ("RiverName",), "planned",
        "epa-draft-red-deer-county-markerville-main-report-mar-2024.pdf", "13–14",
    ),
    Archive(
        "upper_red_deer", "Upper Red Deer/SURVEY_DATA.gdb",
        "Survey_Points", "Elevation", ("Class", "Date"), "Survey_Cross_Sections",
        "CS_ID", "RiverCode", ("Year", "RiverCode"), "surveyed",
        "ep-draft-upper-red-deer-survey-base-data-report-jun-2022.pdf", "8",
    ),
    Archive(
        "drumheller", "Drumheller/Geodatabase_v104/DrumhellerRHS_Survey.gdb",
        "CrossSection", "ELEV", ("CODE", "SURV_DATE"), "XS_Planned",
        "NAME", "RIVER", ("RIVER",), "planned",
        "ep-draft-drumheller-survey-base-data-report-mar-2020.pdf", "11, 13",
    ),
)

LAYER_COLUMNS = (
    "archive", "geodatabase", "layer", "count", "geometry_type",
    "crs_name", "epsg", "horizontal_epsg", "vertical_crs_name", "fields",
)
VALUE_COLUMNS = ("archive", "layer", "field", "value", "count")
SECTION_COLUMNS = (
    "archive", "section_id", "river", "scope_chainage_m", "source_layer",
    "source_fid", "expected_source_id", "actual_source_id", "actual_source_river",
    "source_line_status", "source_survey_date", "source_line_nonempty",
    "link_verified_by_fid_id_river_geometry", "raw_id_linked_cross_section_points",
    "derived_candidate_point_count", "derived_assignment_status",
    "derived_profile_verified", "derived_bank_elevations_verified",
    "derived_both_bank_candidates_present",
)
TARGET_COLUMNS = (
    "target_id", "name", "selection_method", "chainage_m", "on_section_id",
    "nearest_section_id", "nearest_section_along_river_offset_m",
    "mapped_section_resolves", "associated_line_status", "vertical_datum_verified",
    "hydraulic_transfer_verified",
)


def source_path(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def field_text(feature, key: str) -> str:
    value = feature.GetField(key)
    return "" if value is None else str(value).strip()


def field_value(feature, key: str) -> str:
    value = field_text(feature, key)
    if key in {"Date", "SURV_DATE"}:
        match = re.match(r"^(\d{4})[-/](\d{2})[-/](\d{2})(?:\D|$)", value)
        if match:
            return "-".join(match.groups())
    return value or MISSING


def geometry_present(geometry) -> bool:
    return geometry is not None and not geometry.IsEmpty()


def layer_inventory(archive: Archive, path: Path, dataset, ogr) -> list[dict]:
    rows = []
    for layer in dataset:
        definition = layer.GetLayerDefn()
        srs = layer.GetSpatialRef()
        epsg = srs.GetAuthorityCode(None) if srs and srs.GetAuthorityName(None) == "EPSG" else None
        horizontal_epsg = epsg
        if srs and srs.IsCompound() and srs.GetAuthorityName("PROJCS") == "EPSG":
            horizontal_epsg = srs.GetAuthorityCode("PROJCS")
        rows.append({
            "archive": archive.key,
            "geodatabase": source_path(path),
            "layer": layer.GetName(),
            "count": layer.GetFeatureCount(),
            "geometry_type": ogr.GeometryTypeToName(definition.GetGeomType()),
            "crs_name": srs.GetName() if srs else None,
            "epsg": epsg,
            "horizontal_epsg": horizontal_epsg,
            "vertical_crs_name": srs.GetAttrValue("VERT_CS") if srs else None,
            "fields": ";".join(
                definition.GetFieldDefn(i).GetName() for i in range(definition.GetFieldCount())
            ),
        })
    return sorted(rows, key=lambda row: row["layer"])


def require_layer(dataset, name: str):
    layer = dataset.GetLayerByName(name)
    if layer is None:
        raise ValueError(f"Missing required source layer: {name}")
    layer.ResetReading()
    return layer


def source_points(archive: Archive, layer) -> tuple[dict, dict[str, Counter], Counter]:
    counts = {key: Counter() for key in archive.point_fields}
    section_point_counts: Counter = Counter()
    coordinate_keys = set()
    elevations = []
    duplicate_records = 0
    empty_geometry = 0
    surveyed_points = 0
    for feature in layer:
        for key, tally in counts.items():
            tally[field_value(feature, key)] += 1
        elevation = feature.GetField(archive.elevation)
        finite = isinstance(elevation, (int, float)) and math.isfinite(elevation)
        if finite:
            elevations.append(elevation)
        geometry = feature.GetGeometryRef()
        if not geometry_present(geometry):
            empty_geometry += 1
        elif finite:
            key = (geometry.GetX(), geometry.GetY(), elevation)
            if key in coordinate_keys:
                duplicate_records += 1
            else:
                coordinate_keys.add(key)
        if "Class" in counts and field_text(feature, "Class") == "Cross Section":
            surveyed_points += 1
            section_point_counts[field_text(feature, "CS_ID")] += 1
    total = layer.GetFeatureCount()
    summary = {
        "layer": archive.point_layer,
        "count": total,
        "typed_cross_section_points": surveyed_points if "Class" in counts else None,
        "elevation_field": archive.elevation,
        "finite_elevation_count": len(elevations),
        "missing_or_nonfinite_elevations": total - len(elevations),
        "elevation_min_m": min(elevations, default=None),
        "elevation_max_m": max(elevations, default=None),
        "empty_geometry_count": empty_geometry,
        "duplicate_records_beyond_first_by_exact_xy_and_elevation": duplicate_records,
    }
    return summary, counts, section_point_counts


def source_lines(archive: Archive, layer, section_point_counts: Counter) -> tuple[dict, dict[str, Counter]]:
    counts = {key: Counter() for key in archive.line_fields}
    line_ids = Counter()
    empty_geometry = 0
    for feature in layer:
        for key, tally in counts.items():
            tally[field_value(feature, key)] += 1
        line_ids[field_text(feature, archive.line_id)] += 1
        if not geometry_present(feature.GetGeometryRef()):
            empty_geometry += 1
    total = layer.GetFeatureCount()
    summary = {
        "layer": archive.line_layer,
        "count": total,
        "status": archive.line_status,
        "empty_geometry_count": empty_geometry,
        "missing_section_id_count": line_ids.get("", 0),
        "section_id_duplicates_beyond_first_within_archive": sum(
            n - 1 for key, n in line_ids.items() if key and n > 1
        ),
    }
    if archive.line_id == "CS_ID":
        common = section_point_counts.keys() & (line_ids.keys() - {""})
        summary["points_matched_by_original_section_id"] = sum(section_point_counts[s] for s in common)
        summary["points_unmatched_by_original_section_id"] = sum(
            section_point_counts[s] for s in section_point_counts.keys() - common
        )
        summary["line_records_with_matching_section_id"] = sum(line_ids[s] for s in common)
    return summary, counts


def value_rows(archive: Archive, layer: str, counters: dict[str, Counter]) -> list[dict]:
    return [
        {"archive": archive.key, "layer": layer, "field": key, "value": value, "count": n}
        for key, count in counters.items()
        for value, n in sorted(count.items())
    ]


def json_read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def scope_lines(archive: Archive, layer, point_counts: Counter) -> list[dict]:
    path = WORKING / "alberta_flood_surveys" / archive.key / "cross_section_lines.geojson"
    rows = []
    for item in json_read(path)["features"]:
        properties = item["properties"]
        fid = int(properties["source_fid"])
        feature = layer.GetFeature(fid)
        actual_id = field_text(feature, archive.line_id) if feature else None
        actual_river = field_text(feature, archive.line_river).upper() if feature else None
        nonempty = feature is not None and geometry_present(feature.GetGeometryRef())
        expected_id = properties["source_section_id"]
        river = properties["river"].upper()
        valid = (
            nonempty and actual_id == expected_id and actual_river == river
            and properties["source_layer"] == archive.line_layer
            and properties["line_status"] == archive.line_status
        )
        rows.append({
            "archive": archive.key,
            "section_id": properties["section_id"],
            "river": river,
            "scope_chainage_m": properties["selected_river_chainage_m"],
            "source_layer": archive.line_layer,
            "source_fid": fid,
            "expected_source_id": expected_id,
            "actual_source_id": actual_id,
            "actual_source_river": actual_river,
            "source_line_status": archive.line_status,
            "source_survey_date": field_value(feature, "Date") if feature and "Date" in archive.line_fields else None,
            "source_line_nonempty": nonempty,
            "link_verified_by_fid_id_river_geometry": valid,
            "raw_id_linked_cross_section_points": point_counts[actual_id] if valid and archive.line_id == "CS_ID" else None,
            "derived_candidate_point_count": properties.get("point_count"),
            "derived_assignment_status": properties.get("assignment_status"),
            "derived_profile_verified": properties.get("profile_verified"),
            "derived_bank_elevations_verified": properties.get("bank_elevations_verified"),
            "derived_both_bank_candidates_present": (
                properties.get("bank_a_candidate_elevation_m") is not None
                and properties.get("bank_b_candidate_elevation_m") is not None
            ),
        })
    return rows


def scope_targets(sections: dict[str, dict]) -> list[dict]:
    path = WORKING / "derived_prediction_targets/prediction_points.geojson"
    rows = []
    for feature in json_read(path)["features"]:
        p = feature["properties"]
        section = sections.get(p.get("on_section_id") or p.get("nearest_section_id"))
        rows.append({
            "target_id": p["target_id"],
            "name": p["name"],
            "selection_method": p["selection_method"],
            "chainage_m": p["chainage_from_dickson_m"],
            "on_section_id": p.get("on_section_id"),
            "nearest_section_id": p.get("nearest_section_id"),
            "nearest_section_along_river_offset_m": p.get("nearest_section_along_river_offset_m"),
            "mapped_section_resolves": section is not None and section["link_verified_by_fid_id_river_geometry"],
            "associated_line_status": section["source_line_status"] if section else None,
            "vertical_datum_verified": p.get("vertical_datum_verified"),
            "hydraulic_transfer_verified": p.get("hydraulic_transfer_verified"),
        })
    return sorted(rows, key=lambda row: row["target_id"])


def summarize_chainages(rows: list[dict]) -> dict:
    mainstem = sorted(
        (r for r in rows if r["river"] == MAINSTEM),
        key=lambda r: (r["scope_chainage_m"], r["section_id"]),
    )
    spans: dict[str, list] = defaultdict(list)
    for row in mainstem:
        spans[row["archive"]].append(row["scope_chainage_m"])
    adjacent = [
        {
            "upstream_id": a["section_id"],
            "downstream_id": b["section_id"],
            "distance_m": round(b["scope_chainage_m"] - a["scope_chainage_m"], 3),
            "cross_archive": a["archive"] != b["archive"],
        }
        for a, b in zip(mainstem, mainstem[1:])
    ]
    return {
        "basis": "Existing QGIS scope chainages, not a new channel routing calculation.",
        "mainstem_spans_m_by_archive": {
            key: {"min_m": round(min(values), 3), "max_m": round(max(values), 3)}
            for key, values in sorted(spans.items())
        },
        "largest_gap_between_adjacent_mainstem_lines": max(
            adjacent, key=lambda row: row["distance_m"], default=None
        ),
        "closest_adjacent_mainstem_pair_across_archives": min(
            (r for r in adjacent if r["cross_archive"]),
            key=lambda row: row["distance_m"], default=None,
        ),
    }


def write_csv(path: Path, columns: tuple[str, ...], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run(output: Path, gdal, ogr) -> bool:
    gdal.UseExceptions()
    if gdal.GetDriverByName("OpenFileGDB") is None:
        raise RuntimeError("This GDAL installation does not provide the OpenFileGDB driver.")
    scope = json_read(GIS_COURSE / "data/reports/scope_05CC002.json")
    layers, values, sections = [], [], []
    archive_results = {}
    for archive in ARCHIVES:
        path = MANUAL / archive.path
        if not path.is_dir():
            raise FileNotFoundError(f"Original geodatabase not found: {path}")
        dataset = gdal.OpenEx(str(path), gdal.OF_VECTOR | gdal.OF_READONLY, ["OpenFileGDB"])
        if dataset is None:
            raise RuntimeError(f"OpenFileGDB could not open {path}")
        layers.extend(layer_inventory(archive, path, dataset, ogr))
        point_summary, point_values, point_ids = source_points(
            archive, require_layer(dataset, archive.point_layer)
        )
        raw_lines = require_layer(dataset, archive.line_layer)
        line_summary, line_values = source_lines(archive, raw_lines, point_ids)
        values.extend(value_rows(archive, archive.point_layer, point_values))
        values.extend(value_rows(archive, archive.line_layer, line_values))
        if archive.key in {"red_deer", "county_markerville"}:
            sections.extend(scope_lines(archive, raw_lines, point_ids))
        report = MANUAL / Path(archive.path).parts[0] / archive.report
        archive_results[archive.key] = {
            "source_database": source_path(path),
            "principal_points": point_summary,
            "principal_lines": line_summary,
            "source_report_reference": source_path(report),
            "source_report_pdf_pages": archive.report_pages,
            "source_report_present": report.is_file(),
        }
        raw_lines = None
        dataset = None

    sections.sort(key=lambda row: (row["archive"], row["river"], row["scope_chainage_m"], row["section_id"]))
    indexed = {row["section_id"]: row for row in sections}
    targets = scope_targets(indexed)
    by_status = Counter(row["source_line_status"] for row in sections)
    by_river_and_status: dict[str, Counter] = defaultdict(Counter)
    for row in sections:
        by_river_and_status[row["river"]][row["source_line_status"]] += 1
    verified = sum(row["link_verified_by_fid_id_river_geometry"] for row in sections)
    expected_targets = sorted(scope["scope_change"]["retained_target_ids"])
    checks = {
        "working_line_count_matches_scope_register": len(sections) == scope["section_count"],
        "working_section_ids_unique": len(indexed) == len(sections),
        "working_sources_used_only_once": len({(r["archive"], r["source_fid"]) for r in sections}) == len(sections),
        "all_working_lines_match_original_source": verified == len(sections) and bool(sections),
        "working_targets_match_scope_register": [r["target_id"] for r in targets] == expected_targets,
        "all_target_section_references_resolve": bool(targets) and all(r["mapped_section_resolves"] for r in targets),
    }
    summary = {
        "scope_id": scope["scope_id"],
        "scope_start": scope["start"],
        "scope_end": scope["end"],
        "scope_mainstem_length_m": scope["mainstem_length_m"],
        "scope_gauge_to_centerline_distance_m": scope["gauge_to_centerline_distance_m"],
        "scope_register": source_path(GIS_COURSE / "data/reports/scope_05CC002.json"),
        "gdal_version": gdal.VersionInfo("RELEASE_NAME"),
        "source_layer_and_table_count": len(layers),
        "source_archives": archive_results,
        "scope_line_count": len(sections),
        "verified_source_line_links": verified,
        "scope_lines_by_status": dict(by_status),
        "scope_lines_by_river_and_status": {k: dict(v) for k, v in sorted(by_river_and_status.items())},
        "scope_raw_surveyed_lines_by_date": dict(sorted(Counter(
            r["source_survey_date"] for r in sections if r["source_survey_date"] is not None
        ).items())),
        "scope_survey_points_linked_by_original_id": sum(r["raw_id_linked_cross_section_points"] or 0 for r in sections),
        "scope_lines_marked_profile_verified": sum(r["derived_profile_verified"] is True for r in sections),
        "scope_lines_marked_bank_elevations_verified": sum(r["derived_bank_elevations_verified"] is True for r in sections),
        "scope_lines_with_both_bank_candidates": sum(r["derived_both_bank_candidates_present"] for r in sections),
        "scope_mainstem_chainage": summarize_chainages(sections),
        "target_count": len(targets),
        "targets_marked_on_section": sum(bool(r["on_section_id"]) for r in targets),
        "checks": checks,
        "interpretation": [
            "Source links validate the source feature ID, section ID, river name and nonempty source geometry; "
            "they do not compare the source and mapped geometries vertex by vertex.",
            "A proposed line with candidate topographic survey points is not a verified surveyed profile. "
            "County points lack a shared line ID and a per-feature survey date.",
            "Check the referenced survey PDFs for vertical datum and campaign dates; this script does not parse PDF text. "
            "Horizontal CRS or line proximity does not establish comparable gauge zero or hydraulic transfer.",
            "Target relationships and profile/bank verification flags are read from the working GIS layers. "
            "P-series targets are not observed gauges.",
            "Exact duplicate XY/elevation tuples do not determine why the records repeat.",
        ],
    }
    output.mkdir(parents=True, exist_ok=True)
    write_csv(output / "gis_source_layers.csv", LAYER_COLUMNS, layers)
    write_csv(output / "gis_source_value_counts.csv", VALUE_COLUMNS, values)
    write_csv(output / "gis_scope_cross_sections.csv", SECTION_COLUMNS, sections)
    write_csv(output / "gis_scope_targets.csv", TARGET_COLUMNS, targets)
    (output / "gis_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(f"GIS audit: {verified}/{len(sections)} source links, {len(targets)} derived targets; {output}")
    return all(checks.values())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    for source in (MANUAL, WORKING):
        if output.is_relative_to(source.resolve()):
            parser.error("The output directory must be outside the source geodatabases and working GIS layers.")
    qgis_root = os.environ.get("OSGEO4W_ROOT")
    if qgis_root:
        proj_data = Path(qgis_root) / "share/proj"
        if (proj_data / "proj.db").is_file():
            # Use QGIS's matching database even if PostGIS added another version to the shell.
            os.environ["PROJ_DATA"] = os.environ["PROJ_LIB"] = str(proj_data)
    try:
        from osgeo import gdal, ogr
    except ImportError:
        parser.exit(2, "GDAL Python bindings unavailable; run with QGIS Python or a GDAL-enabled interpreter.\n")
    return 0 if run(output, gdal, ogr) else 1


if __name__ == "__main__":
    raise SystemExit(main())
