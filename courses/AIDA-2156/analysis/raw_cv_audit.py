"""Audit acquisition dates, pixel availability and quality of local Sentinel-2 inputs."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from statistics import median


ROOT = Path(__file__).resolve().parents[3]
CV = ROOT / "courses" / "AIDA-2154"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "output" / "raw_data_eda"
HISTORY = CV / "data/processed/satellite_history/20261103_history/image_index.json"
GAP_DOWNLOADS = CV / "outputs/cv_gap_fill_20261111/all_downloaded_images.csv"
GAP_STATUS = CV / "outputs/cv_gap_fill_20261111/request_status_inventory.csv"
SCOPED_QUALITY = CV / "outputs/cv_material_screening_20261111/all_image_screening.csv"
CATALOGUE = CV / "outputs/cv_material_screening_20261111/catalog_pixel_availability.csv"
POINTS = CV / "data/processed/point_water_masks_20261113/full_manifest.json"
SEASONS = ("winter", "spring", "summer", "autumn")
SOURCES = ("historical", "gap_fill")
SPECTRAL_BANDS = ("b04", "b03", "b02", "b08")
SPECTRAL_STATS = ("p05", "p50", "p95")
QUALITY_REASONS = (
    "valid_coverage_below_95pct",
    "clear_corridor_below_80pct",
    "clear_river_core_below_90pct",
    "snow_ice_above_1pct",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def read_csv(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows, columns):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def safe_key(value: str) -> str:
    path = PurePosixPath(value.replace(chr(92), "/"))
    if not path.parts or path.is_absolute() or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError(f"Expected a repository-relative raster reference: {value}")
    return path.as_posix()


def times(values):
    parsed = set()
    for value in values:
        if not value:
            continue
        timestamp = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            raise ValueError(f"Expected a sensing timestamp with a UTC offset: {value}")
        parsed.add(timestamp.astimezone(timezone.utc))
    return sorted(parsed)


def season(day: str) -> str:
    return SEASONS[(int(day[5:7]) % 12) // 3] if day else "unknown"


def truth(value: str) -> bool:
    return value.strip().lower() == "true"


def source_row(path, source, timestamps, *, product="", grid="", archive="", candidate=""):
    day = timestamps[0].date().isoformat() if timestamps else ""
    return {
        "path": path,
        "source_batch": source,
        "response_archive_reference": archive,
        "catalogue_product_id": product,
        "grid": grid,
        "earliest_sensing_utc": timestamps[0].isoformat() if timestamps else "",
        "latest_sensing_utc": timestamps[-1].isoformat() if timestamps else "",
        "sensing_timestamp_count": len(timestamps),
        "sensing_utc_day": day,
        "season": season(day),
        "raster_file_present": (ROOT / path).is_file(),
        "gap_fill_candidate": candidate,
    }


def inventory_rows(history, gap):
    combined = {}
    for row in history:
        path = safe_key(row["image"])
        source_times = times(t["sensing_at"] for t in row.get("time_matches", []))
        if path in combined:
            raise ValueError(f"Duplicate historical raster reference: {path}")
        combined[path] = source_row(
            path, "historical", source_times, grid="_".join(Path(path).stem.split("_")[-2:]),
            archive=safe_key(row["source_archive"]),
        )
    for row in gap:
        path = safe_key(row["image"])
        # The request inventory serializes the sensing times from the response's userdata.
        actual = row.get("actual_sensing_times", "").replace(";", "|").replace(",", "|")
        source_times = times(t for t in actual.split("|") if t.strip())
        if path in combined:
            raise ValueError(f"Duplicate gap-fill raster reference: {path}")
        combined[path] = source_row(
            path, "gap_fill", source_times, product=row["product_id"], grid=row["grid"],
            archive=PurePosixPath(path).with_name("response.tar").as_posix(),
            candidate=truth(row["cv_candidate"]),
        )
    return [combined[key] for key in sorted(combined)]


def distribution(dates):
    dated = sorted({day for day in dates if day})
    gaps = [(datetime.fromisoformat(b) - datetime.fromisoformat(a)).days
            for a, b in zip(dated, dated[1:])]
    return {
        "records": len(dates),
        "undated_records": sum(not d for d in dates),
        "first_sensing_utc_day": dated[0] if dated else None,
        "last_sensing_utc_day": dated[-1] if dated else None,
        "unique_sensing_utc_days": len(dated),
        "records_by_season": {
            name: sum(season(day) == name for day in dates) for name in (*SEASONS, "unknown")
        },
        "median_gap_between_observed_days": median(gaps) if gaps else None,
        "max_gap_between_observed_days": max(gaps) if gaps else None,
    }


def coverage_rows(rows):
    all_dates = [r["sensing_utc_day"] for r in rows]
    years = sorted({t[:4] for t in all_dates if t})
    for group in ("all", *SOURCES):
        cohort = [r for r in rows if group == "all" or r["source_batch"] == group]
        for period in ("all", *years, "undated"):
            for name in ("all", *SEASONS, "unknown"):
                chosen = [
                    r for r in cohort if
                    (period == "all" or
                     (period == "undated" and not r["sensing_utc_day"]) or
                     r["sensing_utc_day"][:4] == period) and
                    (name == "all" or r["season"] == name)
                ]
                # Keep missing-season zeroes in the all-years table.
                if not chosen and period != "all":
                    continue
                dates = [r["sensing_utc_day"] for r in chosen]
                verified = [r for r in chosen if r["raster_file_present"]]
                yield {
                    "source_batch": group, "year": period, "season": name,
                    "inventory_rasters": len(chosen), "local_rasters": len(verified),
                    "utc_days": len({t for t in dates if t}),
                    "local_utc_days": len({r["sensing_utc_day"] for r in verified
                                          if r["sensing_utc_day"]}),
                }


def quality_rows(rows):
    for name in ("all", *SEASONS, "unknown"):
        subset = [r for r in rows if name == "all" or r["season"] == name]
        accepted = [r for r in subset if truth(r["eligible_for_label_review"])]
        rejection_reasons = Counter(
            reason for r in subset for reason in r["rejection_reasons"].split(";") if reason
        )
        yield {
            "season": name,
            "scoped_rasters": len(subset),
            "overpass_groups": len({r["event_group"] for r in subset if r["event_group"]}),
            "eligible_for_label_review": len(accepted),
            "eligible_overpass_groups": len({r["event_group"] for r in accepted if r["event_group"]}),
            "eligible_share": len(accepted) / len(subset) if subset else None,
            "median_clear_corridor_fraction": median(
                float(r["clear_corridor_fraction"]) for r in subset
            ) if subset else None,
            "median_clear_river_core_fraction": median(
                float(r["clear_river_core_fraction"]) for r in subset
            ) if subset else None,
            **{reason: rejection_reasons[reason] for reason in QUALITY_REASONS},
            "hash_check_failed_in_saved_screen": sum(not truth(r["hash_verified"]) for r in subset),
        }


def point_coverage(records, indexed_points):
    for point in indexed_points:
        samples = [r for r in records if r["point_id"] == point["id"]]
        sample_dates = [times([r["date"]])[0].date().isoformat() for r in samples]
        counts = distribution(sample_dates)
        yield {
            "point_id": point["id"],
            "kind": point["kind"],
            "derived_crops": len(samples),
            "unique_source_rasters": len({safe_key(r["source"]) for r in samples}),
            "unique_sensing_utc_days": counts["unique_sensing_utc_days"],
            "first_sensing_utc_day": counts["first_sensing_utc_day"],
            "last_sensing_utc_day": counts["last_sensing_utc_day"],
            **{f"{name}_crops": counts["records_by_season"][name] for name in SEASONS},
        }


def raster_checks(rows, *, enabled):
    """Optional whole-tile spot checks; these are not corridor or point quality metrics."""
    if not enabled:
        return "disabled", []
    try:
        import numpy as np
        import rasterio
    except (ImportError, OSError):
        return "optional rasterio/numpy unavailable", []
    checked = []
    for name in SEASONS:
        candidates = sorted(
            (r for r in rows if r["raster_file_present"] and r["season"] == name),
            key=lambda r: (r["earliest_sensing_utc"], r["path"]),
        )
        if not candidates:
            continue
        selected = candidates[len(candidates) // 2]
        checked_row = {"season": name, "path": selected["path"],
                       "sensing_utc_day": selected["sensing_utc_day"]}
        try:
            with rasterio.open(ROOT / selected["path"]) as dataset:
                epsg = dataset.crs.to_epsg() if dataset.crs else None
                checked_row.update(
                    {"status": "read", "pixel_width_m": abs(dataset.res[0]),
                     "pixel_height_m": abs(dataset.res[1]), "width": dataset.width,
                     "height": dataset.height, "bands": dataset.count,
                     "crs": f"EPSG:{epsg}" if epsg else (
                         dataset.crs.to_string() if dataset.crs else ""
                     ),
                     "dtypes": "|".join(dataset.dtypes)}
                )
                if dataset.count == 6:
                    bands = dataset.read()
                    scl, data_mask = bands[-2:]
                    valid = data_mask == 1
                    checked_row.update(
                        {"whole_tile_valid_fraction": float(valid.mean()),
                         "whole_tile_clear_fraction": float((valid & np.isin(scl, [4, 5, 6])).mean()),
                         "whole_tile_snow_ice_fraction": float((valid & (scl == 11)).mean()),
                         "scl_codes": "|".join(str(x) for x in np.unique(scl)),
                         "data_mask_codes": "|".join(str(x) for x in np.unique(data_mask))}
                    )
                    if valid.any():
                        for band_name, band in zip(SPECTRAL_BANDS, bands[:4]):
                            for stat, value in zip(SPECTRAL_STATS, np.percentile(band[valid], [5, 50, 95])):
                                checked_row[f"{band_name}_{stat}_valid_dn"] = float(value)
                else:
                    checked_row["status"] = "unexpected_band_count"
        except (rasterio.errors.RasterioError, OSError, ValueError) as exc:
            checked_row["status"] = "read_failed"
            checked_row["error_type"] = type(exc).__name__
        checked.append(checked_row)
    return "attempted" if checked else "no local seasonal raster available", checked


def run(output_dir: Path, *, raster_spot_check: bool = True) -> dict:
    history = read_json(HISTORY)
    gap = read_csv(GAP_DOWNLOADS)
    status = Counter(r["status"] for r in read_csv(GAP_STATUS))
    scoped_rows = read_csv(SCOPED_QUALITY)
    catalogue = read_csv(CATALOGUE)
    point_manifest = read_json(POINTS)
    records = point_manifest["records"]
    registered = {safe_key(r["source"]): r["source_sha256"] for r in records}
    crops = Counter(safe_key(r["source"]) for r in records)
    rows = inventory_rows(history["images"], gap)
    for row in rows:
        row["registered_for_point_analysis"] = row["path"] in registered
        row["derived_point_crops"] = crops[row["path"]]
    local = [r for r in rows if r["raster_file_present"]]
    verified = [r for r in local if r["registered_for_point_analysis"]]
    quality = list(quality_rows(scoped_rows))
    spot_status, spot = raster_checks(rows, enabled=raster_spot_check)
    point_rows = list(point_coverage(records, point_manifest["points"]))
    outlet = {
        "source": {
            "product": "Copernicus Data Space Ecosystem Sentinel-2 L2A",
            "grain": "Local downloaded raster references, not independent overpasses or widths",
            "stored_bands_in_order": ["B04 red", "B03 green", "B02 blue", "B08 NIR",
                                      "SCL scene classification", "dataMask"],
            "raster_grid": "WGS 84 / UTM zone 12N; 10-m grid; SCL originates at 20 m",
            "point_crop": "Derived 61 × 61 pixels; not the source raster size",
            "regions": ["Red Deer River project corridor", "Nine CV target points"],
            "local_inventory_inputs": [relative(p) for p in
                                       (HISTORY, GAP_DOWNLOADS, GAP_STATUS, SCOPED_QUALITY,
                                        CATALOGUE, POINTS)],
        },
        "download_inventory": {
            "recorded_raster_paths": len(rows),
            "raster_paths_found_locally": len(local),
            "missing_local_raster_paths": len(rows) - len(local),
            "local_raster_date_coverage": distribution([r["sensing_utc_day"] for r in local]),
            "historical": {
                "catalogue_records_in_original_batch": history["catalog_scene_count"],
                "grid_requests": history["expected_grid_requests"],
                "saved_request_statuses": history["statuses"],
                "local_raster_date_coverage": distribution(
                    [r["sensing_utc_day"] for r in local if r["source_batch"] == "historical"]
                ),
            },
            "gap_fill": {
                "saved_request_statuses": dict(status),
                "catalogue_product_ids_in_downloaded_records": len({r["product_id"] for r in gap
                                                                  if r["product_id"]}),
                "grids_in_downloaded_records": len({r["grid"] for r in gap if r["grid"]}),
                "candidate_rasters_in_downloaded_records": sum(truth(r["cv_candidate"]) for r in gap),
                "local_raster_date_coverage": distribution(
                    [r["sensing_utc_day"] for r in local if r["source_batch"] == "gap_fill"]
                ),
            },
        },
        "catalogue_index": {
            "intersection_product_records": len(catalogue),
            "interpretation": "Metadata intersection records; separate from the pixel inventory.",
        },
        "saved_historical_corridor_quality_screen": {
            "scope": "Dickson Dam to 05CC002 along the selected river network",
            "all_seasons": quality[0],
            "eligible_by_season": {
                r["season"]: r["eligible_for_label_review"] for r in quality if r["season"] != "all"
            },
            "independent_manual_labels_provided": False,
            "interpretation": "Saved pixel-derived screening; eligibility is not label approval.",
            "rejection_reasons_overlap": True,
        },
        "derived_point_analysis": {
            "registered_source_paths": len(registered),
            "distinct_registered_source_hashes_in_saved_manifest": len(set(registered.values())),
            "registered_source_paths_found_locally": len(verified),
            "registered_source_paths_absent_from_acquisition_inventory": len(
                set(registered) - {r["path"] for r in rows}
            ),
            "local_registered_sources_date_coverage": distribution([r["sensing_utc_day"] for r in verified]),
            "point_crops": len(records),
            "points": len(point_rows),
        },
        "raster_spot_check": {
            "status": spot_status,
            "opened": sum(r["status"] == "read" for r in spot),
            "selection": "Temporal middle raster per season, ties broken by path",
            "quality_denominator": "Whole tile; distinct from the corridor and river-core screen",
            "band_statistics_denominator": "dataMask = 1, digital numbers without normalization",
        },
        "limitations": [
            "This is the input pool for the point-mask analysis, not all project experiments or catalogue scenes.",
            "TARs and their extracted GeoTIFFs are the same acquisitions; only the raster paths are counted.",
            "Multiple grids may share a sensing day and are not independent river observations.",
            "Irregular acquisition and quality-dependent missingness prevent continuous seasonal coverage.",
            "Catalogue or clear-pixel records do not establish an independently measured river width.",
        ],
    }
    base_fields = ("path", "source_batch", "response_archive_reference", "catalogue_product_id",
                   "grid", "earliest_sensing_utc", "latest_sensing_utc", "sensing_timestamp_count",
                   "sensing_utc_day", "season", "raster_file_present", "gap_fill_candidate",
                   "registered_for_point_analysis", "derived_point_crops")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "cv_input_inventory.csv", rows, base_fields)
    write_csv(output_dir / "cv_acquisition_coverage.csv", coverage_rows(rows),
              ("source_batch", "year", "season", "inventory_rasters", "local_rasters",
               "utc_days", "local_utc_days"))
    write_csv(output_dir / "cv_scoped_quality.csv", quality, tuple(quality[0]))
    write_csv(output_dir / "cv_point_coverage.csv", point_rows,
              ("point_id", "kind", "derived_crops", "unique_source_rasters",
               "unique_sensing_utc_days", "first_sensing_utc_day", "last_sensing_utc_day",
               "winter_crops", "spring_crops", "summer_crops", "autumn_crops"))
    write_csv(output_dir / "cv_raster_spot_checks.csv", spot,
              ("season", "path", "sensing_utc_day", "status", "pixel_width_m", "pixel_height_m",
               "width", "height", "bands", "crs", "dtypes", "whole_tile_valid_fraction",
               "whole_tile_clear_fraction", "whole_tile_snow_ice_fraction", "scl_codes",
               "data_mask_codes", "error_type",
               *(f"{name}_{stat}_valid_dn" for name in SPECTRAL_BANDS for stat in SPECTRAL_STATS)))
    (output_dir / "cv_summary.json").write_text(
        json.dumps(outlet, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return outlet


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--no-raster-spot-check", action="store_true")
    args = parser.parse_args()
    result = run(args.output_dir, raster_spot_check=not args.no_raster_spot_check)
    acquisition = result["download_inventory"]
    print(f"CV: {acquisition['raster_paths_found_locally']:,}/"
          f"{acquisition['recorded_raster_paths']:,} raster paths present; "
          f"{acquisition['local_raster_date_coverage']['unique_sensing_utc_days']:,} sensing days.")


if __name__ == "__main__":
    main()
