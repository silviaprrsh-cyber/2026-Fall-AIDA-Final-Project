"""Offline-only extension plan. Never authenticates or calls a network API.

Reads preserved catalogs, archived coverage and all current reservations. Writes
new planning artifacts only. Does not change the running download manifest.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
import csv
import hashlib
import json
import math
from pathlib import Path

from pyproj import Transformer
from shapely.geometry import box, mapping, shape
from shapely.ops import transform, unary_union


BANDS = ["B04", "B03", "B02", "B08", "SCL", "dataMask"]
REPO = Path(__file__).resolve().parents[1]
BASE = REPO / "courses/AIDA-2154"
RAW = BASE / "data/sources/copernicus_sentinel2/raw"
DEFAULT_OUT = BASE / "data/reports/cv_extended_plan_20261111"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    raw = path.read_bytes()
    return json.loads(raw), digest(raw)


def keys(product):
    a = product.removesuffix(".SAFE").split("_")
    if len(a) != 7:
        raise ValueError("Unrecognized Sentinel product: " + product)
    return "_".join([a[0], a[2], a[4], a[5]]), "_".join([a[0], a[2], a[4]])


def cloud_bin(value):
    return "00_20" if value <= 20 else "20_60" if value <= 60 else "60_90" if value <= 90 else "90_100"


def write_json(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def summary(jobs):
    return {
        "jobs": len(jobs),
        "products": len({j["observation_key"] for j in jobs}),
        "acquisitions": len({j["acquisition_key"] for j in jobs}),
        "dates": len({j["scene_time"][:10] for j in jobs}),
        "year_months": len({j["scene_time"][:7] for j in jobs}),
        "expected_pu": round(sum(j["expected_pu"] for j in jobs), 3),
        "guarded_pu_4x": round(sum(j["guarded_pu"] for j in jobs), 3),
    }


def diversify(jobs, existing_month, existing_dates):
    """Round-robin year-months, and dates before repeated cells of one date."""
    per_month = defaultdict(lambda: defaultdict(list))
    for j in jobs:
        per_month[j["scene_time"][:7]][j["scene_time"][:10]].append(j)
    month_queues = {}
    for month, date_groups in per_month.items():
        for group in date_groups.values():
            group.sort(key=lambda j: (j["cloud_cover"], -j["river_length_m"] / max(j["guarded_pu"], 0.01), j["id"]))
        date_order = sorted(date_groups, key=lambda d: (d in existing_dates, d))
        queue = []
        while any(date_groups.values()):
            for date in date_order:
                if date_groups[date]:
                    queue.append(date_groups[date].pop(0))
        month_queues[month] = deque(queue)
    ordered = []
    month_order = sorted(month_queues, key=lambda m: (existing_month[m], m))
    while any(month_queues.values()):
        for month in month_order:
            if month_queues[month]:
                ordered.append(month_queues[month].popleft())
    return ordered


def select_budget(ordered, cap, excluded_ids=None):
    selected, spent = [], 0.0
    excluded_ids = excluded_ids or set()
    for job in ordered:
        if job["id"] in excluded_ids:
            continue
        if spent + job["guarded_pu"] <= cap:
            selected.append(job)
            spent += job["guarded_pu"]
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to((BASE / "data/reports").resolve()):
        raise ValueError("Output must be a new directory under data/reports")
    if out.exists():
        raise FileExistsError("Refusing to replace an existing plan: " + str(out))

    forward = Transformer.from_crs(4326, 32612, always_xy=True).transform
    river_path = REPO / "courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson"
    river_doc, river_hash = read(river_path)
    rivers = unary_union([transform(forward, shape(f["geometry"])) for f in river_doc["features"]])
    corridor = rivers.buffer(500)
    source_hashes = {str(river_path.relative_to(REPO)): river_hash}
    reservations = defaultdict(list)
    existing_dates, existing_month = set(), Counter()
    source_counts = {}

    old_path = BASE / "data/reports/satellite_history/20261103_history/manifest.json"
    old, sha = read(old_path)
    source_hashes[str(old_path.relative_to(REPO))] = sha
    assert old["bands"] == BANDS and old["pixel_size_m"] == 10
    for job in old["jobs"]:
        if job["status"] not in ["downloaded", "no_data"]:
            continue
        assert (RAW / "history/20261103_history" / job["id"] / job["archive_name"]).is_file()
        geometry = shape(job["geometry"])
        # Allowed scene lists over-approximate source coverage, deliberately
        # conservative: never re-request a billed geometry from that acquisition.
        for acquisition in {keys(s)[1] for s in job["scene_ids"]}:
            reservations[acquisition].append(geometry)
        existing_dates.add(job["scene_time"][:10])
        existing_month[job["scene_time"][:7]] += 1
    source_counts["history_statuses"] = dict(Counter(j["status"] for j in old["jobs"]))

    current_path = RAW / "cv_gap_fill_20261111/manifest.json"
    current, sha = read(current_path)
    source_hashes[str(current_path.relative_to(REPO))] = sha
    assert current["river_sha256"] == river_hash
    geometry_path = current_path.parent / current["geometry_index"]
    geometries, sha = read(geometry_path)
    assert sha == current["geometry_index_sha256"]
    source_hashes[str(geometry_path.relative_to(REPO))] = sha
    for job in current["jobs"]:
        assert job["bands"] == BANDS and job["pixel_size_m"] == 10 and job["crs"] == "EPSG:32612"
        reservations[keys(job["product_id"])[1]].append(shape(geometries[job["id"]]))
        existing_dates.add(job["scene_time"][:10])
        existing_month[job["scene_time"][:7]] += 1
    source_counts["current_jobs_reserved"] = len(current["jobs"])
    source_counts["current_statuses_at_snapshot"] = dict(Counter(j["status"] for j in current["jobs"]))
    pending = [j for j in current["jobs"] if j["status"] != "downloaded"]
    pending_guard = sum(j["estimated_pu"] for j in pending)
    receipts = [j for j in current["jobs"] if j.get("processing_units") is not None]
    calibration = {
        "receipts": len(receipts),
        "actual_pu": sum(j["processing_units"] for j in receipts),
        "guarded_estimate_pu": sum(j["estimated_pu"] for j in receipts),
        "maximum_actual_to_guard_ratio": max((j["processing_units"] / j["estimated_pu"] for j in receipts), default=None),
        "remaining_current_guarded_pu_at_snapshot": pending_guard,
        "remaining_current_expected_pu_at_snapshot": pending_guard / 4,
    }
    del geometries

    for folder in sorted((RAW / "satellite").iterdir()):
        if not (folder / "process_response.tar").exists():
            continue
        req, sha = read(folder / "process_request.json")
        source_hashes[str((folder / "process_request.json").relative_to(REPO))] = sha
        assert req["input"]["bounds"]["properties"]["crs"].endswith("/32612")
        assert all(b in req["evalscript"] for b in BANDS)
        bounds = req["input"]["bounds"]["bbox"]
        assert (bounds[2] - bounds[0]) / req["output"]["width"] == 10
        assert (bounds[3] - bounds[1]) / req["output"]["height"] == 10
        ud, sha = read(folder / "userdata.json")
        source_hashes[str((folder / "userdata.json").relative_to(REPO))] = sha
        products = {x.get("sentinel2ProductId", x.get("productId")) for x in ud.get("tiles", [])}
        if not products:
            selected, sha = read(folder / "selected_scene.json")
            source_hashes[str((folder / "selected_scene.json").relative_to(REPO))] = sha
            products.add(selected["id"])
        for acquisition in {keys(p)[1] for p in products}:
            reservations[acquisition].append(box(*bounds))
    coverage = {k: unary_union(v) for k, v in reservations.items()}
    del reservations

    catalog_dir = RAW / "catalog_history/20261111_full_catalog"
    catalog, sha = read(catalog_dir / "resume_manifest.json")
    source_hashes[str((catalog_dir / "resume_manifest.json").relative_to(REPO))] = sha
    assert catalog["complete"] and catalog["river_sha256"] == river_hash
    products, raw_count = {}, 0
    for page in catalog["pages"]:
        data, sha = read(catalog_dir / page["path"])
        assert sha == page["sha256"], page["path"]
        for f in data["features"]:
            raw_count += 1
            key, acquisition = keys(f["id"])
            if key not in products or f["id"] > products[key]["id"]:
                # Save only relevant catalog fields, never service credentials.
                products[key] = {"id": f["id"], "geometry": f["geometry"], "properties": f["properties"], "acquisition": acquisition}
    assert raw_count == catalog["raw_feature_count"]
    print("Catalog verified:", raw_count, "products;", len(products), "canonical products", flush=True)

    cells = []
    for x in range(math.floor(corridor.bounds[0] / 10000) * 10000, math.ceil(corridor.bounds[2] / 10000) * 10000, 10000):
        for y in range(math.floor(corridor.bounds[1] / 10000) * 10000, math.ceil(corridor.bounds[3] / 10000) * 10000, 10000):
            clip = corridor.intersection(box(x, y, x + 10000, y + 10000))
            if not clip.is_empty:
                cells.append((f"{x}_{y}", clip))
    by_acquisition = defaultdict(list)
    counts = Counter()
    for f in products.values():
        footprint = transform(forward, shape(f["geometry"]))
        overlap = corridor.intersection(footprint)
        if overlap.is_empty:
            counts["canonical_products_outside_corridor"] += 1
            continue
        f["overlap"] = overlap
        f["river_length"] = rivers.intersection(overlap).length
        by_acquisition[f["acquisition"]].append(f)
    counts["canonical_intersecting_products"] = sum(map(len, by_acquisition.values()))

    jobs, unique_geometries = [], {}
    for acquisition, features in sorted(by_acquisition.items()):
        # Prefer the tile covering more of this actual river, not its scene-wide
        # cloud percentage. Same-pass tile overlap is not a new time/location
        # sample, although L2A processing and resampling values can differ.
        features.sort(key=lambda f: (-f["river_length"], f["properties"].get("eo:cloud_cover", 100), f["id"]))
        covered = coverage.get(acquisition, box(0, 0, 0, 0))
        before_count = len(jobs)
        for f in features:
            missing = f["overlap"].difference(covered)
            if missing.is_empty:
                counts["covered_or_duplicate_product_footprints"] += 1
                continue
            additions = []
            for grid, cell in cells:
                clip = missing.intersection(cell)
                river_length = rivers.intersection(clip).length
                if clip.is_empty or clip.area < 10000 or river_length < 300:
                    if not clip.is_empty:
                        counts["small_or_no_river_fragments_deferred"] += 1
                    continue
                assert clip.intersection(covered).area < 0.001
                bounds = [math.floor(clip.bounds[0] / 10) * 10, math.floor(clip.bounds[1] / 10) * 10,
                          math.ceil(clip.bounds[2] / 10) * 10, math.ceil(clip.bounds[3] / 10) * 10]
                width, height = int((bounds[2] - bounds[0]) / 10), int((bounds[3] - bounds[1]) / 10)
                geo = mapping(clip)
                geo_id = digest(json.dumps(geo, sort_keys=True, separators=(",", ":")).encode())[:24]
                unique_geometries.setdefault(geo_id, geo)
                props = f["properties"]
                cloud = props.get("eo:cloud_cover", 100)
                winter = int(props["datetime"][5:7]) in [12, 1, 2, 3]
                strata = ("winter_" if winter else "apr_nov_") + cloud_bin(cloud)
                identity = {"acquisition_key": acquisition, "observation_key": keys(f["id"])[0], "product_id": f["id"],
                            "geometry_id": geo_id, "bounds": bounds, "bands": BANDS, "pixel_size_m": 10, "crs": "EPSG:32612"}
                job_id = digest(json.dumps(identity, sort_keys=True).encode())[:24]
                expected = max(0.01, width * height / 262144 * 5 / 3)
                stats = props.get("statistics", {})
                jobs.append({**identity, "id": job_id, "scene_time": props["datetime"], "grid": grid,
                             "width": width, "height": height, "cloud_cover": cloud,
                             "snow_cover": props.get("eo:snow_cover"), "scene_thin_cirrus_percent": stats.get("thin_cirrus"),
                             "scene_high_cloud_percent": stats.get("high_proba_clouds"),
                             "sun_elevation_degrees": props.get("view:sun_elevation"),
                             "river_length_m": round(river_length, 3), "geometry_area_m2": round(clip.area, 3),
                             "season": "dec_mar" if winter else "apr_nov", "stratum": strata,
                             "expected_pu": expected, "guarded_pu": 4 * expected,
                             "status": "planned_not_downloaded", "pixel_visibility": "unknown_not_downloaded",
                             "independent_labels": False, "actual_pu": None})
                additions.append(clip)
            if additions:
                covered = unary_union([covered, *additions])
        if len(jobs) == before_count:
            counts["acquisitions_with_no_new_eligible_area"] += 1
    assert len({j["id"] for j in jobs}) == len(jobs)

    ordered_groups = {}
    for name, condition in {
        "winter_low_moderate": lambda j: j["season"] == "dec_mar" and j["cloud_cover"] <= 60,
        "apr_nov_low_moderate": lambda j: j["season"] == "apr_nov" and j["cloud_cover"] <= 60,
        "higher_cloud_60_90": lambda j: 60 < j["cloud_cover"] <= 90,
        "extreme_cloud_over_90": lambda j: j["cloud_cover"] > 90,
    }.items():
        ordered_groups[name] = diversify([j for j in jobs if condition(j)], existing_month, existing_dates)
    stages, selected_ids = [], set()
    for name, allocation in [
        ("stage_1_seasonal_and_thin_cloud", [("winter_low_moderate", 1000), ("apr_nov_low_moderate", 1000)]),
        ("stage_2_higher_cloud_pilot", [("higher_cloud_60_90", 2000)]),
        ("stage_3_optional_extension", [("winter_low_moderate", 750), ("apr_nov_low_moderate", 750), ("extreme_cloud_over_90", 500)]),
    ]:
        batch = []
        for group, cap in allocation:
            chosen = select_budget(ordered_groups[group], cap, selected_ids)
            batch.extend(chosen)
            selected_ids.update(j["id"] for j in chosen)
        for j in batch:
            j["proposed_stage"] = name
        stages.append({"name": name, "guarded_cap_pu": sum(x[1] for x in allocation), "allocations": dict(allocation),
                       **summary(batch), "job_ids": [j["id"] for j in batch],
                       "execution_gate": "No automatic execution. Finish current run, refresh dedup and live quota, validate previous batch river visibility before release."})
    for j in jobs:
        j.setdefault("proposed_stage", "backlog_not_budgeted")

    quality_jobs = [j for j in current["jobs"] if j.get("quality")]
    offline_quality = {
        "downloaded_jobs_with_quality": len(quality_jobs),
        "strict_existing_cv_candidate_true": sum(bool(j.get("cv_candidate")) for j in quality_jobs),
        "strict_existing_cv_candidate_false": sum(not j.get("cv_candidate", False) for j in quality_jobs),
        "strict_false_but_signal_and_valid_95_percent": sum(not j.get("cv_candidate", False) and j["quality"]["signal"] and j["quality"]["valid_fraction"] >= 0.95 for j in quality_jobs),
        "note": "Counts are screening flags only, not visibility labels. Recovering difficult examples from these preserved pixels consumes zero PU.",
    }
    quota_path = current_path.parent / "quota_after.json"
    quota, sha = read(quota_path)
    source_hashes[str(quota_path.relative_to(REPO))] = sha
    cached_remaining = float(quota["quota"]["processingUnitsMonthly"]["remaining"])
    reserve_after_pending = max(0.0, cached_remaining - pending_guard - 5000 - 250)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(), "planning_only": True, "network_requests": 0,
        "process_api_calls": 0, "credentials_read": False, "output_crs": "EPSG:32612", "bands": BANDS,
        "pixel_size_m": 10, "corridor_buffer_m": 500, "river_core_buffer_m_for_review": 20,
        "river_sha256": river_hash, "catalog_raw_products": raw_count, "catalog_canonical_products": len(products),
        "catalog_acquisitions_intersecting_corridor": len(by_acquisition), "grid_cells": len(cells),
        "source_counts": source_counts, "dedup_counts": dict(counts), "all_candidates": summary(jobs),
        "strata": {s: summary([j for j in jobs if j["stratum"] == s]) for s in sorted({j["stratum"] for j in jobs})},
        "proposed_stages": stages, "cost_calibration": calibration, "offline_reclassification": offline_quality,
        "cached_quota_checked_at": quota["checked_at"], "cached_remaining_pu_not_live": cached_remaining,
        "planning_only_allowance_after_current_guard_5000_reserve_250_headroom": reserve_after_pending,
        "source_hashes": source_hashes, "unique_geometries": len(unique_geometries),
        "dedup_policy": [
            "Canonical product observation = platform + sensing timestamp + orbit + MGRS tile; processing versions are not new observations.",
            "Spatial reservation = platform + sensing timestamp + orbit, union across overlapping MGRS tiles, at the same bands and 10 m resolution.",
            "Subtract archived history including no-data, both validation requests, and every current job including pending or uncertain before creating new candidates.",
            "Different timestamps on one calendar date remain distinct observations, but date diversity ranks first.",
            "Older multi-product mosaics reserve their entire requested geometry for each listed acquisition conservatively; this may defer gaps rather than repeat a billed request.",
            "Every stage must refresh coverage from current manifests before execution. A changed reservation or uncertain response stops that candidate until reconciled.",
        ],
        "limitations": [
            "Cross-tile union is a diversity/budget sampling policy, not proof that product files, reflectance or SCL values are identical. Preserve downloaded alternatives.",
            "Scene cloud/snow/cirrus percentages are ranking metadata, never measured river visibility or pixel labels.",
            "Catalog footprint does not guarantee Process API availability or usable pixels. All new pixel_visibility values remain unknown.",
            "All >90 percent cloud observations remain in backlog; their optional 500-PU guarded pilot is last and can be skipped after earlier visibility results.",
            "Fragments under 1 hectare or with less than 300 m river intersection are deferred, not declared downloaded or irrelevant.",
            "4x is a conservative guard calibrated against current receipts, not a contractual maximum. Live free quota, overage=0, bounded requests and billed receipts are still mandatory.",
            "Quota file is cached and can lag ongoing work. Planning allowance is illustrative, not live authority to spend.",
            "This plan does not repair or alter duplicates already present in the old or currently running plan.",
        ],
    }
    out.mkdir(parents=False)
    write_json(out / "summary.json", report)
    write_json(out / "candidate_jobs.json", {"jobs": jobs})
    write_json(out / "geometry_index.json", unique_geometries)
    fields = ["id", "product_id", "acquisition_key", "scene_time", "grid", "stratum", "cloud_cover", "snow_cover", "scene_thin_cirrus_percent", "width", "height", "river_length_m", "expected_pu", "guarded_pu", "proposed_stage", "pixel_visibility"]
    with (out / "candidate_jobs.csv").open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(jobs)
    print(json.dumps({k: report[k] for k in ["all_candidates", "strata", "dedup_counts", "offline_reclassification", "cost_calibration", "planning_only_allowance_after_current_guard_5000_reserve_250_headroom"]}, indent=2), flush=True)
    print("Wrote offline plan only:", out, flush=True)


if __name__ == "__main__":
    main()
