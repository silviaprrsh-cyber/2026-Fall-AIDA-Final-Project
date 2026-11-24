"""Prepare/resume a separate, bounded cloudy/seasonal Sentinel-2 extension.

Default invocation is OFFLINE ONLY. Network access requires --execute. This file
never modifies the original downloader, its manifest, or archived source data.
Cross-tile union is a sampling policy, not a claim of identical pixel values.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import re
import tarfile
import time

# Use this interpreter's bundled GIS databases, never an inherited PostGIS/QGIS
# installation. This changes only the current Python process environment.
_rasterio_spec = importlib.util.find_spec("rasterio")
if _rasterio_spec is not None and _rasterio_spec.origin:
    _rasterio_root = Path(_rasterio_spec.origin).parent
    if (_rasterio_root / "proj_data/proj.db").is_file():
        os.environ["PROJ_DATA"] = str(_rasterio_root / "proj_data")
        os.environ["PROJ_LIB"] = str(_rasterio_root / "proj_data")
    if (_rasterio_root / "gdal_data").is_dir(): os.environ["GDAL_DATA"] = str(_rasterio_root / "gdal_data")

import numpy as np
from pyproj import Transformer, datadir as _pyproj_data
from rasterio.features import geometry_mask
from rasterio.io import MemoryFile
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union

_pyproj_spec = importlib.util.find_spec("pyproj")
if _pyproj_spec is not None and _pyproj_spec.origin:
    _pyproj_bundle = Path(_pyproj_spec.origin).parent / "proj_dir/share/proj"
    if (_pyproj_bundle / "proj.db").is_file(): _pyproj_data.set_data_dir(str(_pyproj_bundle))


BANDS = ["B04", "B03", "B02", "B08", "SCL", "dataMask"]
STAGES = {1: "stage_1_seasonal_and_thin_cloud", 2: "stage_2_higher_cloud_pilot", 3: "stage_3_optional_extension"}
RESERVE_PU = 5000.0
HEADROOM_PU = 250.0
HARD_TOTAL_CAP = 2000.0
QUARANTINE_SPEC = {
    "job_id": "13f94f63550aa569b0789b12",
    "evidence_name": "disconnect_evidence_20261111T0901Z.json",
    "evidence_sha256": "58e9a192d34e1f808c35c72caea28b11b540b2586d8e257e8a1fe793949f52e8",
    "snapshot_name": "manifest_at_disconnect_20261111T0901Z.json",
    "snapshot_sha256": "cc7f8d335f6f856e8cd91edc22675c3c47c44175ae8fa6d6eb2383610ce42899",
    "request_sha256": "6a801d832142c4b9ed8d7eb59a7e827582c796e8ddf00ff3cae78ef79f8aa180",
    "geometry_index_sha256": "515d4b46c299b4136864cda01881c62ef47f8de369acaec9d44d99c635267b0e",
    "hold_pu": 5.096435546875,
    "hold_requests": 1,
}
FINISHED = {"downloaded", "no_data", "skipped_covered", "skipped_small_fragment"}
UNCERTAIN = {"in_progress", "needs_review", "stopped_http"}
EVAL = '''//VERSION=3
function setup(){return {input:[{bands:["B04","B03","B02","B08","SCL","dataMask"]}],mosaicking:"TILE",output:{id:"image",bands:6,sampleType:"UINT16"}};}
function evaluatePixel(samples){let s=samples.find(x=>x.dataMask===1);return s?[Math.max(0,s.B04)*10000,Math.max(0,s.B03)*10000,Math.max(0,s.B02)*10000,Math.max(0,s.B08)*10000,s.SCL,s.dataMask]:[0,0,0,0,0,0];}
function updateOutputMetadata(scenes,inputMetadata,outputMetadata){outputMetadata.userData={tiles:scenes.tiles};}
'''


class GuardError(RuntimeError):
    """A safety prerequisite is unmet; no automatic workaround or paid retry."""


@dataclass(frozen=True)
class Paths:
    repo: Path

    @property
    def base(self): return self.repo / "courses/AIDA-2154"
    @property
    def raw(self): return self.base / "data/sources/copernicus_sentinel2/raw"
    @property
    def source(self): return self.base / "data/reports/cv_extended_plan_20261111"
    @property
    def output(self): return self.raw / "cv_extended_fill_20261111"
    @property
    def original(self): return self.raw / "cv_gap_fill_20261111"
    @property
    def river(self): return self.repo / "courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson"


def now(): return datetime.now(timezone.utc).isoformat()
def instant(value): return datetime.fromisoformat(value.replace("Z", "+00:00"))
def digest(data): return hashlib.sha256(data).hexdigest()
def encoded(value): return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
def read(path): return json.loads(path.read_bytes())


def sha_file(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): h.update(chunk)
    return h.hexdigest()


def save(path, value):
    """Atomic replacement only for files inside this new run directory."""
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(encoded(value))
    for attempt in range(20):
        try:
            temp.replace(path)
            return
        except PermissionError:
            if attempt == 19: raise
            time.sleep(0.25)


def write_new(path, value):
    with path.open("xb") as handle: handle.write(encoded(value))


def acquisition(product):
    parts = product.removesuffix(".SAFE").split("_")
    if len(parts) != 7: raise GuardError("Unrecognized product identity")
    return "_".join([parts[0], parts[2], parts[4]])


def finite_nonnegative(value):
    try: number = float(value)
    except (ValueError, TypeError): raise GuardError("Invalid numeric accounting value") from None
    if not math.isfinite(number) or number < 0: raise GuardError("Invalid numeric accounting value")
    return number


def validate_usage(usage):
    for name in ["processingUnitsMonthly", "processingUnitsOverage", "requestsMonthly", "requestsOverage"]:
        if name not in usage: raise GuardError("Incomplete official quota response")
        for field in ["configuration", "consumed", "remaining"]: finite_nonnegative(usage[name].get(field))
    for name in ["processingUnitsOverage", "requestsOverage"]:
        if any(float(usage[name][field]) != 0 for field in ["configuration", "consumed", "remaining"]):
            raise GuardError("Overage is not zero; stop without changing the account")
    if float(usage["processingUnitsMonthly"]["configuration"]) != 30000:
        raise GuardError("Free monthly PU configuration changed; review required")
    return usage


def budget_stop(spent, next_guard, cap, effective_remaining, requests_remaining, quarantine_pu=0, quarantine_requests=0):
    if not 0 < cap <= HARD_TOTAL_CAP: raise GuardError("Cumulative PU cap must be in (0, 2000]")
    for value in [spent, next_guard, effective_remaining, requests_remaining, quarantine_pu, quarantine_requests]: finite_nonnegative(value)
    if spent + next_guard > cap + 1e-9: return "cumulative_actual_cap_precheck"
    if effective_remaining - next_guard < RESERVE_PU + HEADROOM_PU + quarantine_pu: return "account_reserve_precheck"
    if requests_remaining < 100 + quarantine_requests: return "request_reserve_precheck"
    return None


def validate_original_quarantine(paths, original, allowed_id, expected_jobs=2751):
    """Exactly one pinned original request may remain UNKNOWN, never retried.

    This does not alter original state or admit a second/new exception. All
    evidence fingerprints below were reviewed before enabling this exception.
    """
    spec = QUARANTINE_SPEC
    if allowed_id != spec["job_id"]: raise GuardError("Original unknown request is blocked without its exact explicit quarantine option")
    jobs = original.get("jobs", [])
    if len(jobs) != expected_jobs: raise GuardError("Quarantine requires the complete original plan")
    unknown = [j for j in jobs if j.get("status") not in {"downloaded", "no_data"}]
    if len(unknown) != 1 or unknown[0]["id"] != spec["job_id"]:
        raise GuardError("Only the one pinned unknown original request may be isolated; other original jobs must be complete")
    if any(j.get("error_type") or j.get("billed_pu_unknown") for j in jobs if j["id"] != spec["job_id"]):
        raise GuardError("Another original exception exists; quarantine cannot ignore it")
    evidence_path, snapshot_path = paths.original / spec["evidence_name"], paths.original / spec["snapshot_name"]
    if sha_file(evidence_path) != spec["evidence_sha256"] or sha_file(snapshot_path) != spec["snapshot_sha256"]:
        raise GuardError("Pinned disconnect evidence changed")
    evidence, snapshot = read(evidence_path), read(snapshot_path)
    snapshot_jobs = [j for j in snapshot.get("jobs", []) if j["id"] == spec["job_id"]]
    if len(snapshot_jobs) != 1 or unknown[0] != snapshot_jobs[0] or unknown[0] != evidence["job"]:
        raise GuardError("Original unknown status or immutable request evidence changed")
    job = unknown[0]
    if job.get("status") != "needs_review" or job.get("error_type") != "ConnectionError" or any(k in job for k in ["processing_units", "http_status", "received_at", "archive_sha256", "image_sha256"]):
        raise GuardError("The pinned disconnect no longer has its reviewed unknown outcome")
    if evidence["manifest_sha256"] != spec["snapshot_sha256"] or evidence["request_sha256"] != spec["request_sha256"] or job["estimated_pu"] != spec["hold_pu"]:
        raise GuardError("Quarantine fingerprint or hold differs from reviewed evidence")
    folder = paths.original / spec["job_id"]
    if {p.name for p in folder.iterdir()} != {"request.json"} or sha_file(folder / "request.json") != spec["request_sha256"]:
        raise GuardError("Unknown request artifacts changed; inspect the outcome again")
    geometry_path = paths.original / original["geometry_index"]
    if sha_file(geometry_path) != spec["geometry_index_sha256"]: raise GuardError("Quarantined geometry index changed")
    geometry = read(geometry_path)[spec["job_id"]]
    request = read(folder / "request.json")
    if request["input"]["bounds"]["geometry"] != geometry or request["input"]["bounds"]["bbox"] != job["bounds"]:
        raise GuardError("Quarantine request geometry differs from its original plan")
    files = {str(p.relative_to(paths.repo)): sha_file(p) for p in [evidence_path, snapshot_path, folder / "request.json"]}
    return {"job_id": spec["job_id"], "outcome": "unknown_not_retried", "original_status": "needs_review", "original_job": job,
            "acquisition_key": acquisition(job["product_id"]), "geometry": geometry, "geometry_sha256": digest(encoded(geometry)),
            "hold_pu": spec["hold_pu"], "hold_requests": spec["hold_requests"], "actual_processing_units": None,
            "evidence_hashes": files, "original_final_manifest_sha256": sha_file(paths.original / "manifest.json"),
            "note": "Exception is restricted to this exact original disconnect. Geometry remains forbidden; no status/evidence changes and no retry. Hold is an estimate, not a measured charge or provider maximum."}


def quarantine_holds(plan, allowed_id):
    records = plan.get("quarantined_original_requests", [])
    if not records:
        if allowed_id is not None: raise GuardError("Quarantine option supplied but this frozen plan has no quarantined request")
        return 0.0, 0
    spec = QUARANTINE_SPEC
    if allowed_id != spec["job_id"] or len(records) != 1 or records[0]["job_id"] != spec["job_id"]:
        raise GuardError("This frozen plan requires the exact original-quarantine option on every invocation")
    if records[0]["hold_pu"] != spec["hold_pu"] or records[0]["hold_requests"] != spec["hold_requests"]:
        raise GuardError("Quarantine hold was altered")
    return spec["hold_pu"], spec["hold_requests"]


def verify_quarantine_artifacts(paths, plan):
    for record in plan.get("quarantined_original_requests", []):
        for relative, expected in record["evidence_hashes"].items():
            if sha_file(paths.repo / relative) != expected: raise GuardError("Frozen quarantine evidence changed")
        folder = paths.original / record["job_id"]
        if {p.name for p in folder.iterdir()} != {"request.json"}: raise GuardError("New evidence appeared for the unknown request; stop for review")
        if sha_file(paths.original / "manifest.json") != record["original_final_manifest_sha256"]:
            raise GuardError("Original final manifest changed after isolation; recheck all outcomes")


def verify_quarantine_exclusions(plan, geometries):
    for record in plan.get("quarantined_original_requests", []):
        forbidden = shape(record["geometry"])
        if digest(encoded(record["geometry"])) != record["geometry_sha256"]: raise GuardError("Frozen quarantine geometry changed")
        for job in plan["jobs"]:
            if job.get("status", "pending") in {"skipped_covered", "skipped_small_fragment"} or not job.get("geometry_id"): continue
            if acquisition(job["product_id"]) == record["acquisition_key"] and shape(geometries[job["geometry_id"]]).intersection(forbidden).area > 1e-6:
                raise GuardError("A planned request intersects the quarantined same-pass geometry")


def original_gate(paths, expected_jobs=2751, allow_original_quarantine=None):
    manifest = read(paths.original / "manifest.json")
    jobs = manifest.get("jobs", [])
    if len(jobs) != expected_jobs or len({j["id"] for j in jobs}) != expected_jobs:
        raise GuardError("Original 2751-job plan identity/count changed")
    has_unknown = any(j.get("status") not in {"downloaded", "no_data"} for j in jobs)
    quarantine = validate_original_quarantine(paths, manifest, allow_original_quarantine, expected_jobs) if has_unknown or allow_original_quarantine else None
    if any((j.get("error_type") or j.get("billed_pu_unknown")) and (not quarantine or j["id"] != quarantine["job_id"]) for j in jobs):
        raise GuardError("Original plan contains unresolved exceptions")
    if manifest.get("stop_reason") not in {"bounded_batch_finished", "no_pending_jobs", "finished"}:
        raise GuardError("Original plan has no normal final stop record")
    stopped = manifest.get("last_stopped_at")
    if not stopped or any(instant(j["received_at"]) > instant(stopped) for j in jobs if not quarantine or j["id"] != quarantine["job_id"]):
        raise GuardError("Original downloader has not written its final checkpoint")
    quota = read(paths.original / "quota_after.json")
    if instant(quota["checked_at"]) < instant(stopped):
        raise GuardError("Original downloader has not completed its final accounting check")
    validate_usage(quota["quota"])
    if manifest["river_sha256"] != sha_file(paths.river): raise GuardError("River geometry changed")
    original_geometry = paths.original / manifest["geometry_index"]
    geometry_hash = sha_file(original_geometry)
    source_summary = read(paths.source / "summary.json")
    pinned_hash = source_summary["source_hashes"][str(original_geometry.relative_to(paths.repo))]
    if geometry_hash != manifest["geometry_index_sha256"] or geometry_hash != pinned_hash:
        raise GuardError("Original immutable geometry index changed")
    geometries = read(original_geometry)
    if set(geometries) != {j["id"] for j in jobs}: raise GuardError("Original geometry/job identities changed")
    for job in jobs:
        identity = {k: job[k] for k in ["observation_key", "product_id", "bounds", "bands", "pixel_size_m", "crs", "scene_time"]}
        identity["geometry"] = geometries[job["id"]]
        if digest(json.dumps(identity, sort_keys=True).encode())[:24] != job["id"]:
            raise GuardError("Original job product/date/range/band/resolution identity changed")
    return manifest


def source_coverage(paths, original, quarantine=None):
    """Archived successful requests, plus a separate no-data retry exclusion.

    Geometries mean archived request coverage, not a guarantee that each pixel is
    valid/visible. Original pending reservations are never called downloaded.
    """
    coverage, hashes, archives = defaultdict(list), {}, []
    pinned_sources = read(paths.source / "summary.json")["source_hashes"]
    mutable_inputs = {str((paths.original / name).relative_to(paths.repo)) for name in ["manifest.json", "quota_after.json"]}

    def record(path):
        relative, actual = str(path.relative_to(paths.repo)), sha_file(path)
        if relative in pinned_sources and relative not in mutable_inputs and actual != pinned_sources[relative]:
            raise GuardError("Immutable source provenance differs from the audited planning snapshot")
        hashes[relative] = actual
        return read(path)

    def archived(path, expected):
        if not path.is_file() or not expected: raise GuardError("Archived coverage lacks file/hash evidence")
        # Full archive hashes are checked once while freezing, before any API call.
        if sha_file(path) != expected: raise GuardError("Archived source checksum mismatch")
        st = path.stat()
        archives.append({"path": str(path.relative_to(paths.repo)), "sha256": expected, "bytes": st.st_size, "mtime_ns": st.st_mtime_ns})

    record(paths.original / "manifest.json")
    record(paths.original / "quota_after.json")
    geompath = paths.original / original["geometry_index"]
    if sha_file(geompath) != original["geometry_index_sha256"]: raise GuardError("Original geometry index mismatch")
    old_geometries = record(geompath)
    for j in original["jobs"]:
        if j["bands"] != BANDS or j["pixel_size_m"] != 10 or j["crs"] != "EPSG:32612": raise GuardError("Original data specification differs")
        if quarantine and j["id"] == quarantine["job_id"]:
            # Forbidden retry coverage, explicitly NOT a downloaded archive.
            coverage[quarantine["acquisition_key"]].append(shape(quarantine["geometry"]))
            continue
        archived(paths.original / j["id"] / "response.tar", j.get("archive_sha256"))
        if j["status"] == "downloaded":
            image = paths.original / j["id"] / "image.tif"
            if not image.is_file() or not j.get("image_sha256"): raise GuardError("Downloaded image missing")
            # The validated archive is authoritative; image content is checked
            # separately for new extension outputs and source archive provenance.
        coverage[acquisition(j["product_id"])].append(shape(old_geometries[j["id"]]))

    oldpath = paths.base / "data/reports/satellite_history/20261103_history/manifest.json"
    old = record(oldpath)
    if old["bands"] != BANDS or old["pixel_size_m"] != 10: raise GuardError("History data specification differs")
    for j in old["jobs"]:
        if j["status"] not in {"downloaded", "no_data"}: raise GuardError("Historical request outcome is unresolved")
        archived(paths.raw / "history/20261103_history" / j["id"] / j["archive_name"], j.get("sha256"))
        for key in {acquisition(s) for s in j["scene_ids"]}: coverage[key].append(shape(j["geometry"]))

    for folder in sorted((paths.raw / "satellite").iterdir()):
        if not (folder / "process_response.tar").is_file(): continue
        req, ud = record(folder / "process_request.json"), record(folder / "userdata.json")
        bounds = req["input"]["bounds"]
        if not bounds["properties"]["crs"].endswith("/32612"): raise GuardError("Trial CRS mismatch")
        b = bounds["bbox"]
        if (b[2] - b[0]) / req["output"]["width"] != 10 or (b[3] - b[1]) / req["output"]["height"] != 10: raise GuardError("Trial resolution mismatch")
        if not all(band in req["evalscript"] for band in BANDS): raise GuardError("Trial band mismatch")
        products = {x.get("sentinel2ProductId", x.get("productId")) for x in ud.get("tiles", [])}
        if not products: products = {record(folder / "selected_scene.json")["id"]}
        # Trial tar has no common manifest hash: freeze its locally computed hash.
        archived(folder / "process_response.tar", sha_file(folder / "process_response.tar"))
        for key in {acquisition(p) for p in products}: coverage[key].append(box(*b))
    hashes[str(paths.river.relative_to(paths.repo))] = sha_file(paths.river)
    if quarantine: hashes.update(quarantine["evidence_hashes"])
    return {k: unary_union(v) for k, v in coverage.items()}, hashes, archives


def clip_candidate(job, geometry, covered, rivers):
    """Pure geometry deduplication, testable without files or network."""
    missing = geometry.difference(covered)
    if missing.is_empty or missing.area < 0.001: return "skipped_covered", None
    if missing.area < 10000 or rivers.intersection(missing).length < 300: return "skipped_small_fragment", missing
    return "pending", missing


def freeze(paths, original, quarantine=None):
    if paths.output.exists(): raise GuardError("Existing extension directory lacks a complete manifest; inspect it instead of overwriting")
    verified = read(paths.source / "validation.json")
    for name in ["summary.json", "candidate_jobs.json", "geometry_index.json"]:
        if sha_file(paths.source / name) != verified["artifact_sha256"][name]: raise GuardError("Source plan hash mismatch")
    source, candidates, geom = read(paths.source / "summary.json"), read(paths.source / "candidate_jobs.json"), read(paths.source / "geometry_index.json")
    if source["river_sha256"] != sha_file(paths.river): raise GuardError("Source plan river differs")
    coverage, input_hashes, archive_index = source_coverage(paths, original, quarantine)
    for name in ["summary.json", "candidate_jobs.json", "geometry_index.json", "validation.json"]:
        input_hashes[str((paths.source / name).relative_to(paths.repo))] = sha_file(paths.source / name)
    forward = Transformer.from_crs(4326, 32612, always_xy=True).transform
    rivers = unary_union([transform(forward, shape(f["geometry"])) for f in read(paths.river)["features"]])
    by_id = {j["id"]: j for j in candidates["jobs"]}
    if len(by_id) != len(candidates["jobs"]): raise GuardError("Duplicate source job IDs")
    jobs, frozen_geo, states = [], {}, []
    # Reconcile against actually archived requests, then reserve new main-tile
    # samples in stage order. No pending original request is accepted by the gate.
    for number, stage_name in STAGES.items():
        stage = next(x for x in source["proposed_stages"] if x["name"] == stage_name)
        stage_guard = 0.0
        for source_id in stage["job_ids"]:
            candidate = by_id[source_id]
            if candidate["bands"] != BANDS or candidate["pixel_size_m"] != 10 or candidate["crs"] != "EPSG:32612": raise GuardError("Source job specification differs")
            key = acquisition(candidate["product_id"])
            previous = coverage.get(key, box(0, 0, 0, 0))
            status, missing = clip_candidate(candidate, shape(geom[candidate["geometry_id"]]), previous, rivers)
            job = {**candidate, "source_plan_id": source_id, "stage": number, "sampling_policy": "same-pass main-tile spatial sample; not pixel/file equivalence"}
            if missing is not None:
                geo_id = digest(encoded(mapping(missing)))[:24]
                frozen_geo[geo_id] = mapping(missing)
                b = missing.bounds
                bounds = [math.floor(b[0] / 10) * 10, math.floor(b[1] / 10) * 10, math.ceil(b[2] / 10) * 10, math.ceil(b[3] / 10) * 10]
                width, height = (bounds[2] - bounds[0]) // 10, (bounds[3] - bounds[1]) // 10
                if not 0 < width <= 1000 or not 0 < height <= 1000: raise GuardError("Unexpected request dimensions")
                expected = max(0.01, width * height / 262144 * 5 / 3)
                job.update(geometry_id=geo_id, bounds=bounds, width=width, height=height, expected_pu=expected, guarded_pu=4 * expected)
            else:
                job["geometry_id"] = None
            identity = {k: job.get(k) for k in ["product_id", "geometry_id", "bounds", "bands", "pixel_size_m", "crs", "source_plan_id"]}
            job["id"] = digest(encoded(identity))[:24]
            job["status"] = status
            jobs.append(job)
            states.append({"id": job["id"], "status": status, "pixel_visibility": "unknown_not_downloaded", "independent_labels": False})
            if status == "pending":
                stage_guard += job["guarded_pu"]
                coverage[key] = unary_union([previous, missing])
        if stage_guard > stage["guarded_cap_pu"] + 1e-6: raise GuardError("Reconciled stage exceeds its guarded allocation")
    if len({j["id"] for j in jobs}) != len(jobs): raise GuardError("Frozen job ID collision")
    plan = {"created_at": now(), "jobs": jobs, "source_hashes": input_hashes, "source_archives": archive_index,
            "river_sha256": sha_file(paths.river), "policy": "Preserve all archived representations. Main-tile spatial sampling prioritizes novel dates/locations, not identical pixel data.",
            "total_actual_pu_hard_cap": HARD_TOTAL_CAP, "minimum_free_pu_reserve": RESERVE_PU, "accounting_headroom_pu": HEADROOM_PU,
            "bands": BANDS, "pixel_size_m": 10, "source_original_jobs": len(original["jobs"])}
    plan["quarantined_original_requests"] = [quarantine] if quarantine else []
    verify_quarantine_exclusions(plan, frozen_geo)
    paths.output.mkdir()
    write_new(paths.output / "plan.json", plan)
    write_new(paths.output / "geometries.json", frozen_geo)
    if quarantine: write_new(paths.output / "quarantined_original_request.json", quarantine)
    manifest = {"created_at": now(), "jobs": states, "pu_spent_total": 0.0, "plan_sha256": sha_file(paths.output / "plan.json"),
                "geometries_sha256": sha_file(paths.output / "geometries.json"), "network_processing_started": False, "stop_reason": "offline_plan_ready"}
    if quarantine: manifest["quarantine_sha256"] = sha_file(paths.output / "quarantined_original_request.json")
    write_new(paths.output / "manifest.json", manifest)
    return plan, frozen_geo, manifest


def load_frozen(paths, allow_original_quarantine=None):
    manifest = read(paths.output / "manifest.json")
    for name, key in [("plan.json", "plan_sha256"), ("geometries.json", "geometries_sha256")]:
        if sha_file(paths.output / name) != manifest[key]: raise GuardError("Frozen extension plan/geometry hash changed")
    plan, geometries = read(paths.output / "plan.json"), read(paths.output / "geometries.json")
    quarantine_holds(plan, allow_original_quarantine)
    if plan.get("quarantined_original_requests"):
        if sha_file(paths.output / "quarantined_original_request.json") != manifest.get("quarantine_sha256"): raise GuardError("Frozen quarantine audit file changed")
        if read(paths.output / "quarantined_original_request.json") != plan["quarantined_original_requests"][0]: raise GuardError("Quarantine audit file differs from frozen plan")
    verify_quarantine_artifacts(paths, plan)
    verify_quarantine_exclusions(plan, geometries)
    for relative, expected in plan["source_hashes"].items():
        if sha_file(paths.repo / relative) != expected: raise GuardError("Source data/plan changed; review coverage before resuming")
    for item in plan["source_archives"]:
        p = paths.repo / item["path"]
        if not p.is_file(): raise GuardError("Source archive disappeared")
        st = p.stat()
        if st.st_size != item["bytes"] or st.st_mtime_ns != item["mtime_ns"]:
            if sha_file(p) != item["sha256"]: raise GuardError("Source archive changed")
    validate_state(paths, plan, manifest)
    return plan, geometries, manifest


def validate_state(paths, plan, manifest):
    if manifest.get("budget_review_required"): raise GuardError("A previous charge exceeded its guard; budget review is required")
    if {j["id"] for j in plan["jobs"]} != {j["id"] for j in manifest["jobs"]} or len(plan["jobs"]) != len(manifest["jobs"]): raise GuardError("Mutable state no longer matches frozen plan")
    known_spent = 0.0
    for state in manifest["jobs"]:
        if state["status"] in UNCERTAIN or state.get("billed_pu_unknown"):
            raise GuardError("Uncertain/failed request exists; inspect outcome, never retry automatically")
        if state["status"] not in FINISHED | {"pending"}: raise GuardError("Unknown job status")
        folder = paths.output / state["id"]
        if state["status"] == "pending" and folder.exists() and any(folder.iterdir()):
            raise GuardError("Pending job has request/response artifacts; outcome must be inspected")
        if state["status"] in {"downloaded", "no_data"}:
            if not state.get("archive_sha256") or sha_file(folder / "response.tar") != state["archive_sha256"]: raise GuardError("Completed extension archive is missing or changed")
            if not state.get("image_sha256") or sha_file(folder / "image.tif") != state["image_sha256"]: raise GuardError("Completed extension image is missing or changed")
            if state.get("processing_units") is None: raise GuardError("Completed request has no billing receipt")
        if state.get("processing_units") is not None: known_spent += finite_nonnegative(state["processing_units"])
    if not math.isclose(known_spent, finite_nonnegative(manifest["pu_spent_total"]), abs_tol=1e-7): raise GuardError("Cumulative billing ledger mismatch")


@contextmanager
def execution_lock(output):
    path = output / "execution.lock"
    try: fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError: raise GuardError("Execution lock exists; inspect its owner and uncertain outcomes before recovery") from None
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle: json.dump({"pid": os.getpid(), "created_at": now()}, handle)
        yield
    finally:
        path.unlink()


class OfficialClient:
    """Created only after explicit --execute and all local guards pass."""
    def __init__(self, credential_path):
        import requests
        values = {}
        for line in credential_path.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$', line)
            if match: values[match[1].upper()] = match[2].strip().strip('"').strip("'")
        self.client = next((values[k] for k in ["CDSE_CLIENT_ID", "SH_CLIENT_ID", "CLIENT_ID"] if values.get(k)), None)
        self.secret = next((values[k] for k in ["CDSE_CLIENT_SECRET", "SH_CLIENT_SECRET", "CLIENT_SECRET"] if values.get(k)), None)
        if not self.client or not self.secret: raise GuardError("Satellite credentials are missing")
        self.session, self.access, self.expiry = requests.Session(), None, 0

    def headers(self):
        if time.monotonic() >= self.expiry:
            response = self.session.post("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
                                         data={"grant_type": "client_credentials", "client_id": self.client, "client_secret": self.secret}, timeout=30, allow_redirects=False)
            response.raise_for_status()
            data = response.json()
            self.access, self.expiry = data["access_token"], time.monotonic() + max(30, int(data.get("expires_in", 300)) - 30)
        return {"Authorization": "Bearer " + self.access}

    def usage(self):
        r = self.session.get("https://sh.dataspace.copernicus.eu/api/v1/accounting/usage", headers=self.headers(), timeout=30, allow_redirects=False)
        r.raise_for_status()
        u = r.json()
        return validate_usage({k: u[k] for k in ["processingUnitsMonthly", "processingUnitsOverage", "requestsMonthly", "requestsOverage"]})

    def process(self, payload):
        # Exactly one attempt. No automatic redirects or retry adapter.
        return self.session.post("https://sh.dataspace.copernicus.eu/process/v1", json=payload,
                                 headers={**self.headers(), "Accept": "application/tar"}, timeout=(20, 180), allow_redirects=False)


def payload_for(job, geometry):
    t = instant(job["scene_time"])
    allowed = json.dumps([job["product_id"]])
    ev = EVAL + '\nfunction preProcessScenes(c){let allowed=' + allowed + ';c.scenes.tiles=c.scenes.tiles.filter(s=>allowed.indexOf((s.sentinel2ProductId||s.productId||"").replace(/\\.SAFE$/,""))>=0);return c;}\n'
    return {"input": {"bounds": {"bbox": job["bounds"], "geometry": geometry, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/32612"}},
                      "data": [{"type": "sentinel-2-l2a", "dataFilter": {"timeRange": {"from": (t - timedelta(minutes=30)).isoformat(), "to": (t + timedelta(minutes=30)).isoformat()}, "maxCloudCoverage": 100}, "processing": {"upsampling": "NEAREST", "downsampling": "NEAREST"}}]},
            "output": {"width": job["width"], "height": job["height"], "responses": [{"identifier": "image", "format": {"type": "image/tiff"}}, {"identifier": "userdata", "format": {"type": "application/json"}}]}, "evalscript": ev}


def inspect_response(content, job, geometry, core):
    if len(content) > 96 * 1024 * 1024: raise GuardError("Unexpectedly large response")
    with tarfile.open(fileobj=io.BytesIO(content)) as archive:
        members = archive.getmembers()
        if len(members) != 2 or {m.name for m in members} != {"image.tif", "userdata.json"} or not all(m.isfile() for m in members): raise GuardError("Unexpected archive members")
        if any(m.size > (64 * 1024 * 1024 if m.name == "image.tif" else 5 * 1024 * 1024) for m in members): raise GuardError("Unexpected archive member size")
        image, userdata = archive.extractfile("image.tif").read(), json.load(archive.extractfile("userdata.json"))
    tiles = userdata.get("tiles", [])
    for tile in tiles:
        if tile.get("sentinel2ProductId", tile.get("productId", "")).removesuffix(".SAFE") != job["product_id"]: raise GuardError("Response product does not match the requested product")
        if abs((instant(tile["date"]) - instant(job["scene_time"])).total_seconds()) > 1800: raise GuardError("Response sensing time mismatch")
    with MemoryFile(image) as memory, memory.open() as ds:
        if ds.count != 6 or ds.shape != (job["height"], job["width"]) or ds.crs.to_epsg() != 32612 or ds.res != (10, 10) or not np.allclose(ds.bounds, job["bounds"], rtol=0, atol=1e-6) or any(d != "uint16" for d in ds.dtypes): raise GuardError("Response raster specification mismatch")
        if ds.transform.b != 0 or ds.transform.d != 0 or ds.transform.a != 10 or ds.transform.e != -10: raise GuardError("Unexpected raster orientation")
        a = ds.read()
        inside = geometry_mask([geometry], out_shape=ds.shape, transform=ds.transform, invert=True)
        near_shape = core.intersection(shape(geometry))
        near = geometry_mask([mapping(near_shape)], out_shape=ds.shape, transform=ds.transform, invert=True) if not near_shape.is_empty else np.zeros(ds.shape, dtype=bool)
        valid = a[5] == 1
        clear_proxy = valid & np.isin(a[4], [4, 5, 6])
        if np.any(valid & inside) and not tiles: raise GuardError("Valid pixels without source product provenance")
        if np.any(~np.isin(a[5], [0, 1])) or np.any(a[4, inside & valid] > 11): raise GuardError("Invalid mask/SCL values")
        n, k = max(1, int(inside.sum())), max(1, int(near.sum()))
        q = {"valid_fraction": float((inside & valid).sum() / n), "river_valid_fraction": float((near & valid).sum() / k),
             "clear_proxy_fraction": float((inside & clear_proxy).sum() / n), "river_clear_proxy_fraction": float((near & clear_proxy).sum() / k),
             "core_pixels": int(near.sum()), "valid_pixels": int((inside & valid).sum()), "signal": bool(np.any(a[:4, inside & valid] > 0)),
             "core_scl_counts": {str(s): int((near & valid & (a[4] == s)).sum()) for s in range(12)},
             "note": "SCL and a 20 m river-centerline buffer are review proxies, not water/visibility ground truth. Haze and thin cloud are retained."}
    return image, userdata, q


def run_batch(paths, plan, geometries, manifest, client, stage=1, max_requests=24, pu_cap=2000, previous_stage_reviewed=False, sleep_fn=time.sleep, allow_original_quarantine=None):
    """Network boundary is dependency-injected for fully offline mock tests."""
    if stage not in STAGES or max_requests <= 0: raise GuardError("Invalid stage or request limit")
    if not 0 < pu_cap <= HARD_TOTAL_CAP: raise GuardError("Invalid cumulative PU cap")
    quarantine_pu, quarantine_requests = quarantine_holds(plan, allow_original_quarantine)
    verify_quarantine_artifacts(paths, plan)
    verify_quarantine_exclusions(plan, geometries)
    validate_state(paths, plan, manifest)
    states = {j["id"]: j for j in manifest["jobs"]}
    if stage > 1:
        if not previous_stage_reviewed: raise GuardError("Review previous-stage imagery and budget before explicitly releasing another stage")
        if any(states[j["id"]]["status"] not in FINISHED for j in plan["jobs"] if j["stage"] < stage): raise GuardError("Earlier stages are not finished")
    pending = [j for j in plan["jobs"] if j["stage"] == stage and states[j["id"]]["status"] == "pending"]
    if not pending:
        manifest["stop_reason"] = "selected_stage_complete"
        save(paths.output / "manifest.json", manifest)
        return 0
    usage = validate_usage(client.usage())
    base_remaining = min(float(usage["processingUnitsMonthly"]["remaining"]), manifest.get("conservative_remaining_pu", math.inf))
    base_requests = float(usage["requestsMonthly"]["remaining"])
    initial_spent, attempted = manifest["pu_spent_total"], 0
    save(paths.output / "quota_before.json", {"checked_at": now(), "quota": usage, "effective_remaining_pu": base_remaining,
                                               "quarantine_hold_pu_not_actual_spend": quarantine_pu, "quarantine_hold_requests": quarantine_requests})
    manifest.update(network_processing_started=True, last_started_at=now(), selected_stage=stage, cumulative_actual_pu_cap=pu_cap, stop_reason="running")
    save(paths.output / "manifest.json", manifest)
    forward = Transformer.from_crs(4326, 32612, always_xy=True).transform
    core = unary_union([transform(forward, shape(f["geometry"])) for f in read(paths.river)["features"]]).buffer(20)
    finished_coverage = defaultdict(list)
    for j in plan["jobs"]:
        if states[j["id"]]["status"] in {"downloaded", "no_data"}:
            finished_coverage[acquisition(j["product_id"])].append(shape(geometries[j["geometry_id"]]))
    for job in pending:
        if attempted >= max_requests:
            manifest["stop_reason"] = "bounded_batch_finished"
            break
        state, folder = states[job["id"]], paths.output / job["id"]
        geo = geometries[job["geometry_id"]]
        key = acquisition(job["product_id"])
        if finished_coverage[key]:
            g = shape(geo)
            overlap = g.intersection(unary_union(finished_coverage[key])).area
            if g.area - overlap < 0.001:
                state.update(status="skipped_covered", skip_reason="Already archived same-pass spatial coverage; not file/value equivalence")
                save(paths.output / "manifest.json", manifest)
                continue
            if overlap > 0.001: raise GuardError("Frozen candidate now partly overlaps completed work; replan instead of altering frozen geometry")
        if attempted and attempted % 5 == 0: usage = validate_usage(client.usage())
        effective = min(float(usage["processingUnitsMonthly"]["remaining"]), base_remaining - (manifest["pu_spent_total"] - initial_spent))
        requests_left = min(float(usage["requestsMonthly"]["remaining"]), base_requests - attempted)
        reason = budget_stop(manifest["pu_spent_total"], job["guarded_pu"], pu_cap, effective, requests_left, quarantine_pu, quarantine_requests)
        if reason:
            manifest["stop_reason"] = reason
            break
        verify_quarantine_artifacts(paths, plan)
        if folder.exists() and any(folder.iterdir()): raise GuardError("Unrecorded request artifacts; do not repeat request")
        folder.mkdir(exist_ok=True)
        payload = payload_for(job, geo)
        write_new(folder / "request.json", payload)
        state.update(status="in_progress", attempted_at=now())
        save(paths.output / "manifest.json", manifest)
        attempted += 1
        try:
            response = client.process(payload)
            state["http_status"] = response.status_code
            write_new_bytes = folder / "response.tar" if response.status_code == 200 else folder / "http_response.bin"
            with write_new_bytes.open("xb") as handle: handle.write(response.content)
            state["response_sha256"] = digest(response.content)
            receipt = response.headers.get("x-processingunits-spent")
            if receipt is None:
                state["billed_pu_unknown"] = True
                raise GuardError("Missing processing-unit receipt; reconcile before any continuation")
            spent = finite_nonnegative(receipt)
            state["processing_units"] = spent
            manifest["pu_spent_total"] += spent
            manifest["conservative_remaining_pu"] = max(0, min(effective - spent, base_remaining - (manifest["pu_spent_total"] - initial_spent)))
            if spent > job["guarded_pu"] + 1e-7:
                # Persist with the receipt, before validation/success checkpoints,
                # so interruption cannot silently clear the budget-review gate.
                manifest["budget_review_required"] = True
            save(paths.output / "manifest.json", manifest)
            if response.status_code != 200:
                state["status"] = "stopped_http"
                manifest["stop_reason"] = "HTTP response retained; inspect outcome before any retry"
                save(paths.output / "manifest.json", manifest)
                break
            state["archive_sha256"] = state["response_sha256"]
            image, userdata, q = inspect_response(response.content, job, geo, core)
            with (folder / "image.tif").open("xb") as handle: handle.write(image)
            write_new(folder / "userdata.json", userdata)
            state.update(status="downloaded" if q["valid_pixels"] else "no_data", received_at=now(), image_sha256=digest(image), quality=q,
                         pixel_visibility="unknown_review_needed" if q["valid_pixels"] else "no_data", independent_labels=False, training_label_status="unlabeled")
            finished_coverage[key].append(shape(geo))
            save(paths.output / "manifest.json", manifest)
            if spent > job["guarded_pu"] + 1e-7:
                manifest["stop_reason"] = "Actual PU exceeded guarded estimate; stop for budget review"
                manifest["budget_review_required"] = True
                break
            print("Downloaded", job["id"], "stage", stage, "cumulative PU", round(manifest["pu_spent_total"], 4), "visibility", state["pixel_visibility"], flush=True)
            sleep_fn(1)
        except Exception as exc:
            state.update(status="needs_review", error_type=type(exc).__name__)
            if state.get("processing_units") is None: state["billed_pu_unknown"] = True
            manifest["stop_reason"] = "Interrupted or invalid request outcome; retained artifacts require inspection; no automatic retry"
            save(paths.output / "manifest.json", manifest)
            raise GuardError(manifest["stop_reason"]) from None
    else:
        manifest["stop_reason"] = "selected_stage_complete"
    manifest["last_stopped_at"] = now()
    save(paths.output / "manifest.json", manifest)
    try:
        after = validate_usage(client.usage())
        effective = min(float(after["processingUnitsMonthly"]["remaining"]), base_remaining - (manifest["pu_spent_total"] - initial_spent))
        manifest["conservative_remaining_pu"] = max(0, effective)
        save(paths.output / "quota_after.json", {"checked_at": now(), "quota": after, "effective_remaining_pu": effective})
        save(paths.output / "manifest.json", manifest)
    except Exception as exc:
        manifest["accounting_check_failed"] = type(exc).__name__
        save(paths.output / "manifest.json", manifest)
        raise GuardError("Final quota check failed; recorded successful downloads must not be repeated") from None
    return attempted


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Explicitly allow network processing after all guards")
    parser.add_argument("--stage", type=int, choices=STAGES, default=1)
    parser.add_argument("--max-requests", type=int, default=24)
    parser.add_argument("--pu-cap", type=float, default=2000, help="Cumulative actual PU across ALL invocations/stages, maximum 2000")
    parser.add_argument("--previous-stage-reviewed", action="store_true", help="Assert previous-stage imagery and budget were reviewed; required for stages 2 and 3")
    parser.add_argument("--allow-original-quarantine", choices=[QUARANTINE_SPEC["job_id"]], default=None,
                        help="Explicitly isolate only the pinned original disconnect, retaining unknown state, forbidden geometry and extra quota hold")
    args = parser.parse_args(argv)
    if args.max_requests <= 0 or not 0 < args.pu_cap <= HARD_TOTAL_CAP: raise GuardError("Invalid request limit or cumulative cap")
    paths = Paths(Path(__file__).resolve().parents[1])
    original = original_gate(paths, allow_original_quarantine=args.allow_original_quarantine)
    quarantine = validate_original_quarantine(paths, original, args.allow_original_quarantine) if args.allow_original_quarantine else None
    if (paths.output / "execution.lock").exists(): raise GuardError("Another run or unreconciled lock exists")
    if (paths.output / "manifest.json").exists(): plan, geometries, manifest = load_frozen(paths, args.allow_original_quarantine)
    else: plan, geometries, manifest = freeze(paths, original, quarantine)
    print("Extension statuses", dict(Counter(s["status"] for s in manifest["jobs"])), "cumulative actual PU", manifest["pu_spent_total"], flush=True)
    if not args.execute:
        print("OFFLINE ONLY: no authentication, quota query, or Process API call. Plan and geometry hashes are frozen.", flush=True)
        return
    with execution_lock(paths.output):
        # Re-read after winning the lock, closing the gap between preflight and
        # execution if another process finished while this process was checking.
        original_gate(paths, allow_original_quarantine=args.allow_original_quarantine)
        plan, geometries, manifest = load_frozen(paths, args.allow_original_quarantine)
        run_batch(paths, plan, geometries, manifest, OfficialClient(paths.repo / ".env"), args.stage, args.max_requests, args.pu_cap, args.previous_stage_reviewed,
                  allow_original_quarantine=args.allow_original_quarantine)


if __name__ == "__main__":
    try: main()
    except GuardError as exc: raise SystemExit("STOPPED: " + str(exc))
