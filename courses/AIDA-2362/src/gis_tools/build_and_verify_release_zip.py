"""Assemble AIDA2362_FinalProject_Miles_Zhang.zip and verify clean extraction in QGIS 3.44.14.

Run with QGIS Python from repository root:
  & 'C:\\Program Files\\QGIS 3.44.14\\bin\\python-qgis-ltr.bat' -B courses/AIDA-2362/src/gis_tools/build_and_verify_release_zip.py
"""
from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import sys
import tempfile
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

MD_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)]+)\)")


def sanitize_zip_md(rel_path: str, text: str, members: set[str]) -> str:
    dirs: set[str] = set()
    for m in members:
        parts = m.split("/")
        for k in range(1, len(parts)):
            dirs.add("/".join(parts[:k]))
    base = posixpath.dirname(rel_path)

    def repl(match: re.Match[str]) -> str:
        label, raw = match.group(1), match.group(2).strip()
        if raw.startswith(("http://", "https://", "#", "mailto:")):
            return match.group(0)
        tgt = urllib.parse.unquote(raw.split("#")[0]).rstrip("/")
        if not tgt:
            return match.group(0)
        norm = posixpath.normpath(posixpath.join(base, tgt)) if base else posixpath.normpath(tgt)
        if norm in members or norm in dirs:
            return match.group(0)
        return f"{label} (`{raw}` — see full repository; omitted from standalone ZIP)"

    return MD_LINK_RE.sub(repl, text)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from qgis.core import (  # noqa: E402
    Qgis,
    QgsApplication,
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
)

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from validate_course_package import (  # noqa: E402
    ALBERTA_METRIC_AREA,
    LOCAL,
    PROJECT_NAME,
    SURVEY_3TM_AREA,
    decision_check,
    file_hash,
    need,
    read_json,
    require_relative_xml,
    scan_layer,
)

COURSE = Path(__file__).resolve().parents[2]
RELEASE_DIR = COURSE / "data" / "processed" / "gis_release_20261123"
ZIP_NAME = "AIDA2362_FinalProject_Miles_Zhang.zip"
ZIP_PATH = RELEASE_DIR / ZIP_NAME
MANIFEST_PATH = COURSE / "submission-manifest.txt"
VAL_OUT = COURSE / "outputs" / "zip-extraction-validation.json"

PACKAGE_MEMBERS = [
    "README.md",
    "ai-use-declaration.md",
    "decision-brief.md",
    "governance-review.md",
    "release-checklist.md",
    "data/README.md",
    "data/layer-inventory.csv",
    "data/layer-inventory.md",
    "docs/README.md",
    "docs/gis-project-report.docx",
    "outputs/README.md",
    "outputs/Overhead view.pdf",
    "outputs/Overhead view - Dickson to Joffre.pdf",
    "outputs/Overhead view - Original full project.pdf",
    "outputs/current-qgis-validation.json",
    "outputs/map-feature-equivalent.csv",
    "outputs/map-text-equivalent.md",
    "outputs/qgis-reopen-and-demo.md",
    "outputs/section-proximity-sensitivity.csv",
    "outputs/section-proximity-sensitivity.md",
    "project/README.md",
    "project/dickson_to_joffre.qgz",
    "project/manifest.json",
    "project/map_overview.png",
    "project/alberta_flood_surveys/county_markerville/cross_section_lines.geojson",
    "project/alberta_flood_surveys/red_deer/cross_section_lines.geojson",
    "project/derived_prediction_targets/prediction_points.geojson",
    "project/derived_weather_associations/areas.geojson",
    "project/eccc_hydrometric_geomet/historical_tributary_stations.geojson",
    "project/eccc_hydrometric_geomet/stations.geojson",
    "project/eccc_weather_geomet/stations.geojson",
    "project/nrcan_nhn/selected_rivers.geojson",
    "src/gis_tools/build_prediction_points.py",
    "src/gis_tools/section_proximity_sensitivity.py",
    "src/gis_tools/validate_course_package.py",
    "src/gis_tools/build_and_verify_release_zip.py",
]


def write_manifest(member_hashes: list[tuple[str, str]], zip_sha: str | None = None, zip_bytes: int | None = None) -> None:
    now_utc = datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "AIDA 2362: verified portable GIS submission manifest",
        "",
        f"Manifest UTC: {now_utc}",
        f"QGIS version verified: {Qgis.QGIS_VERSION}",
        f"Archive name: {ZIP_NAME}",
        "Status: READY FOR D2L UPLOAD (pending Week 15 live QGIS demo, classmate peer review of two projects, and final D2L upload).",
        "Survey clearance: Alberta Environment and Protected Areas (EPA) confirmed on 2026-11-23 that the provided Red Deer River survey data is publicly available information and may be used in this course submission with EPA attribution. Private email correspondence (Protected A) and original raw geodatabases are excluded.",
        "Active QGIS entry inside extracted ZIP: project/dickson_to_joffre.qgz (current Dickson Dam to 05CC002 reach, ~56.0 km, P01-P05).",
        "Excluded from ZIP: project/history/, original government geodatabases/reports, OSM tile caches, private emails, credentials, virtual environments, Chinese local companions (*CN.md/*CN.docx), and unrelated course folders.",
    ]
    if zip_sha and zip_bytes is not None:
        lines.append(f"Verified ZIP SHA-256: {zip_sha} ({zip_bytes} bytes)")
        lines.append("Clean-extraction QGIS audit: outputs/zip-extraction-validation.json (8 relative local vector layers, 246 features, 0 invalid geometries, 2 layouts, 25 m / 50 m Select by Expression passed).")
    lines.extend(["", "SHA-256  relative file"])
    for rel, digest in member_hashes:
        lines.append(f"{digest}  {rel}")
    MANIFEST_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_zip(members: list[str], staged_bytes: dict[str, bytes]) -> tuple[str, int]:
    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(ZIP_PATH, "w", compression=ZIP_DEFLATED) as zf:
        for rel in members:
            if rel in staged_bytes:
                zf.writestr(rel, staged_bytes[rel])
            else:
                src = COURSE / rel
                need(src.is_file(), f"Missing package member: {rel}")
                zf.write(src, arcname=rel)
    return file_hash(ZIP_PATH), ZIP_PATH.stat().st_size


def verify_extracted_zip(zip_path: Path, expected_hashes: dict[str, str]) -> dict:
    with tempfile.TemporaryDirectory(prefix=".qgis-zip-test-", dir=COURSE) as tmp_dir:
        extract_root = Path(tmp_dir).resolve()
        with ZipFile(zip_path, "r") as zf:
            need(zf.testzip() is None, "ZIP CRC check failed.")
            names = sorted(zf.namelist())
            need(not any("history/" in n or "CN.md" in n or ".gdb" in n for n in names), "Forbidden file found inside ZIP.")
            zf.extractall(extract_root)

        # Verify every extracted file hash matches source
        for rel, digest in expected_hashes.items():
            ep = extract_root / rel
            need(ep.is_file() and file_hash(ep) == digest, f"Extracted member mismatch: {rel}")

        proj_dir = (extract_root / "project").resolve()
        qgz = proj_dir / PROJECT_NAME
        xml = require_relative_xml(qgz)
        need(xml.findtext("./projectCrs/spatialrefsys/authid") == "EPSG:3857", "Unexpected display CRS.")
        mf = read_json(proj_dir / "manifest.json")
        expected_counts = {r["path"]: r["count"] for r in mf["layers"]}

        prefix = os.environ.get("QGIS_PREFIX_PATH")
        if prefix:
            QgsApplication.setPrefixPath(prefix, True)
        app = QgsApplication([], False, str(extract_root / ".qgis_profile"))
        app.initQgis()
        project = QgsProject.instance()
        try:
            need(project.read(str(qgz)), "Extracted ZIP QGIS project failed to open.")
            layouts = sorted(layout.name() for layout in project.layoutManager().layouts())
            need(layouts == ["Overhead view", "Simple OSM overview"], f"Unexpected layouts: {layouts}")
            need(project.filePathStorage() == Qgis.FilePathType.Relative, "Not relative path storage.")

            vector = {}
            basemap = []
            for layer in project.mapLayers().values():
                if layer.providerType() == "ogr":
                    src = Path(layer.source().split("|", 1)[0]).resolve()
                    need(src.is_relative_to(proj_dir), f"{layer.name()} resolved outside extracted ZIP: {src}")
                    need(layer.isValid(), f"Invalid layer in extracted ZIP: {layer.name()}")
                    vector[src.relative_to(proj_dir).as_posix()] = layer
                else:
                    basemap.append({"name": layer.name(), "provider": layer.providerType(), "rendered_or_fetched": False})

            need(vector.keys() == LOCAL.keys() and len(vector) == 8, "Expected 8 local vector layers.")
            geo = QgsCoordinateReferenceSystem("EPSG:4326")
            metric = QgsCoordinateReferenceSystem("EPSG:3400")
            fwd = QgsCoordinateTransform(geo, metric, project)
            inv = QgsCoordinateTransform(metric, geo, project)

            features, summaries = {}, []
            for rel in LOCAL:
                rows, res = scan_layer(vector[rel], rel, fwd, inv, expected_counts[rel])
                features[rel] = rows
                summaries.append(res)

            sections = {}
            for rel, rows in features.items():
                if rel.startswith("alberta_flood_surveys/"):
                    sections.update(rows)

            expected_comp, decision = decision_check(features, sections, fwd)
            target_layer = vector["derived_prediction_targets/prediction_points.geojson"]
            selections = {}
            for threshold in (25, 50):
                target_layer.selectByExpression(f'abs("nearest_section_along_river_offset_m") <= {threshold}')
                selections[str(threshold)] = sorted(f["target_id"] for f in target_layer.selectedFeatures())
                need(
                    selections[str(threshold)] == sorted(k for k, row in expected_comp.items() if row[f"passes_{threshold}m"] == "yes"),
                    f"Extracted ZIP selection mismatch at {threshold} m.",
                )
            target_layer.removeSelection()
            decision["qgis_select_by_expression_ids"] = selections

            invalid_total = sum(len(s["invalid_geos_geometry_ids"]) for s in summaries)
            empty_total = sum(len(s["empty_geometry_ids"]) for s in summaries)
            total_features = sum(s["count"] for s in summaries)
            need(invalid_total == 0 and empty_total == 0 and total_features == 246, "Geometry/count assertion failed.")

            return {
                "validation_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "qgis_version": Qgis.QGIS_VERSION,
                "archive_name": zip_path.name,
                "archive_sha256": file_hash(zip_path),
                "archive_bytes": zip_path.stat().st_size,
                "archive_member_count": len(names),
                "extracted_qgz_reopened": True,
                "all_vector_layers_resolved_inside_extracted_zip": True,
                "relative_file_path_storage": True,
                "display_crs": "EPSG:3857",
                "vector_storage_crs": "EPSG:4326",
                "distance_crs": "EPSG:3400 (metres)",
                "area_checks": {"EPSG:3400_bbox_wsen": ALBERTA_METRIC_AREA, "EPSG:3780_bbox_wsen": SURVEY_3TM_AREA},
                "local_vector_layers": len(vector),
                "total_vector_features": total_features,
                "invalid_geos_geometries": invalid_total,
                "empty_geometries": empty_total,
                "remote_layers_not_rendered": basemap,
                "layouts": layouts,
                "qgis_select_by_expression_ids": selections,
                "nearest_section_links_resolved": decision["nearest_section_links_resolved"],
                "usable_mainstem_section_point_crossings": decision["usable_mainstem_section_point_crossings"],
                "max_offset_delta_m": decision["maximum_difference_from_stored_along_river_offset_m"],
                "survey_attribution_clearance": (
                    "Alberta Environment and Protected Areas (EPA) confirmed 2026-11-23 that the provided Red Deer River "
                    "survey data is publicly available information and may be used in this course submission with EPA credit."
                ),
            }
        finally:
            project.clear()
            app.exitQgis()


def main() -> int:
    # Step 1: Sanitize out-of-ZIP cross-repo links inside staged .md copies only (workspace files remain untouched)
    base_members = sorted(PACKAGE_MEMBERS)
    final_members = sorted(base_members + ["submission-manifest.txt"])
    member_set = set(final_members)
    staged_bytes: dict[str, bytes] = {}
    base_hashes: list[tuple[str, str]] = []
    for rel in base_members:
        src = COURSE / rel
        need(src.is_file(), f"Missing package member: {rel}")
        if rel.endswith(".md"):
            clean_b = sanitize_zip_md(rel, src.read_text(encoding="utf-8"), member_set).encode("utf-8")
            staged_bytes[rel] = clean_b
            base_hashes.append((rel, hashlib.sha256(clean_b).hexdigest()))
        else:
            base_hashes.append((rel, file_hash(src)))
    write_manifest(base_hashes)

    # Step 2: Assemble final portable ZIP (all 36 curated deliverables + submission-manifest.txt)
    manifest_bytes = MANIFEST_PATH.read_bytes()
    staged_bytes["submission-manifest.txt"] = manifest_bytes
    zip_sha, zip_bytes = build_zip(final_members, staged_bytes)

    # Step 3: Extract that EXACT final ZIP into a brand-new empty directory and run a SINGLE QGIS 3.44.14 session
    expected_final = dict(base_hashes)
    expected_final["submission-manifest.txt"] = hashlib.sha256(manifest_bytes).hexdigest()
    final_audit = verify_extracted_zip(ZIP_PATH, expected_final)
    VAL_OUT.write_text(json.dumps(final_audit, indent=2) + "\n", encoding="utf-8")

    # Step 4: Write workspace manifest with repository-file hashes and verified final ZIP SHA-256 summary
    repo_hashes = [(rel, file_hash(COURSE / rel)) for rel in base_members]
    write_manifest(repo_hashes, zip_sha=zip_sha, zip_bytes=zip_bytes)

    print(
        f"VERIFIED FINAL ZIP: {ZIP_PATH}\n"
        f"  Size: {zip_bytes:,} bytes | SHA-256: {zip_sha}\n"
        f"  Members: {final_audit['archive_member_count']} | Layers: {final_audit['local_vector_layers']} | "
        f"Features: {final_audit['total_vector_features']} | Invalid GEOS: {final_audit['invalid_geos_geometries']}\n"
        f"  Select <=25 m: {final_audit['qgis_select_by_expression_ids']['25']}\n"
        f"  Select <=50 m: {final_audit['qgis_select_by_expression_ids']['50']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
