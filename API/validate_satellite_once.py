"""Run one bounded CDSE discovery and image retrieval check; never schedule polling."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
from pathlib import Path
import re
import struct
import tarfile
from datetime import datetime, timedelta, timezone

import requests
import numpy as np
import rasterio
from PIL import Image
from pyproj import Transformer
from shapely.geometry import box, shape

ROOT = Path(__file__).resolve().parents[1]
STAC = "https://stac.dataspace.copernicus.eu/v1/search"
TOKEN = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
PROCESS = "https://sh.dataspace.copernicus.eu/process/v1"

EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{bands: ["B04", "B03", "B02", "B08", "SCL", "dataMask"]}],
    mosaicking: "TILE",
    output: [
      {id: "rgb", bands: 4, sampleType: "AUTO"},
      {id: "reflectance", bands: 4, sampleType: "FLOAT32"},
      {id: "quality", bands: 2, sampleType: "UINT8"}
    ]
  };
}
function evaluatePixel(samples) {
  let s = samples.find(x => x.dataMask === 1);
  if (!s) return {rgb: [0,0,0,0], reflectance: [0,0,0,0], quality: [0,0]};
  return {
    rgb: [2.5*s.B04, 2.5*s.B03, 2.5*s.B02, s.dataMask],
    reflectance: [s.B04, s.B03, s.B02, s.B08],
    quality: [s.SCL, s.dataMask]
  };
}
function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = {tiles: scenes.tiles};
}
"""


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def credentials():
    """Read explicit key/value entries without executing or expanding their contents."""
    source = ROOT / ".env"
    values = {}
    if source.exists():
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$", line)
            if not match:
                continue
            key, value = match.groups()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values[key.upper()] = value
    values.update({k.upper(): v for k, v in os.environ.items()})
    client = next((values[k] for k in ("CDSE_CLIENT_ID", "SH_CLIENT_ID", "CLIENT_ID") if values.get(k)), None)
    secret = next((values[k] for k in ("CDSE_CLIENT_SECRET", "SH_CLIENT_SECRET", "CLIENT_SECRET") if values.get(k)), None)
    if not client or not secret:
        raise RuntimeError("Missing CDSE client ID or client secret; values were not logged.")
    return client, secret


def checked(response, label):
    if response.status_code != 200:
        # Do not echo server bodies, request headers or authentication responses.
        raise RuntimeError(f"{label} returned HTTP {response.status_code}.")
    return response


def inspect_pixels(folder, bounds):
    """Reject empty imagery even when the provider reports HTTP 200."""
    metadata = json.loads((folder / "userdata.json").read_text(encoding="utf-8"))
    if not metadata.get("tiles"):
        raise RuntimeError("Process API returned no source tiles (empty image).")
    times = sorted(datetime.fromisoformat(t["date"].replace("Z", "+00:00")) for t in metadata["tiles"])
    selected = json.loads((folder / "selected_scene.json").read_text(encoding="utf-8"))
    selected_day = datetime.fromisoformat(selected["properties"]["datetime"].replace("Z", "+00:00")).date()
    if any(t.date() != selected_day for t in times) or (times[-1] - times[0]).total_seconds() > 300:
        raise RuntimeError("Source tiles are not from a consistent observation window.")
    with rasterio.open(folder / "reflectance.tif") as src:
        if src.crs.to_epsg() != 32612 or src.count != 4 or src.shape != (512, 512):
            raise RuntimeError("Reflectance raster has an unexpected CRS, band count or shape.")
        if not np.allclose(src.bounds, bounds) or src.res != (10, 10):
            raise RuntimeError("Reflectance raster has unexpected spatial bounds or pixel spacing.")
        reflectance = src.read()
    with rasterio.open(folder / "quality.tif") as src:
        if src.count != 2 or src.shape != (512, 512) or src.crs.to_epsg() != 32612 or not np.allclose(src.bounds, bounds):
            raise RuntimeError("Quality raster is inconsistent with the reflectance raster.")
        scl, mask = src.read()
    with Image.open(folder / "rgb.png") as image:
        rgba = np.asarray(image.convert("RGBA"))
    valid = mask == 1
    if valid.mean() < 0.95 or not np.isfinite(reflectance[:, valid]).all():
        raise RuntimeError("Raster has insufficient valid coverage or nonfinite reflectance.")
    if not np.any(reflectance[:, valid] > 0) or not np.any(rgba[:, :, :3][valid] > 0):
        raise RuntimeError("Downloaded image contains no nonzero valid image values.")
    if not np.array_equal(rgba[:, :, 3] > 0, valid):
        raise RuntimeError("PNG alpha and raster validity mask disagree.")
    labels, counts = np.unique(scl[valid], return_counts=True)
    return {"valid_pixel_fraction": float(valid.mean()),
            "cloud_pixel_fraction": float(np.isin(scl[valid], [8, 9, 10]).mean()),
            "cloud_shadow_fraction": float((scl[valid] == 3).mean()),
            "scl_counts": {str(int(k)): int(v) for k, v in zip(labels, counts)},
            "source_tile_count": len(metadata["tiles"]), "georeferencing_check": "passed",
            "tile_sensing_time_min": times[0].isoformat(), "tile_sensing_time_max": times[-1].isoformat(),
            "png_alpha_check": "passed"}


def main():
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    folder = ROOT / "data/sources/copernicus_sentinel2/raw/satellite" / run_id
    folder.mkdir(parents=True, exist_ok=False)
    report = {
        "run_id": run_id, "started_at": now.isoformat(), "status": "started",
        "mode": "one_shot", "project_scope": "Full basin scope unchanged",
        "trial_station": "05CC002", "continuous_collection_started": False,
        "cv_training_started": False, "endpoints": {"stac": STAC, "process": PROCESS},
        "raw_directory": str(folder.relative_to(ROOT)),
    }
    try:
        with (ROOT / "data/processed/station_master.csv").open(encoding="utf-8-sig", newline="") as handle:
            station = next(r for r in csv.DictReader(handle) if r["station_id"] == "05CC002")
        lon, lat = float(station["longitude"]), float(station["latitude"])
        forward = Transformer.from_crs(4326, 32612, always_xy=True)
        reverse = Transformer.from_crs(32612, 4326, always_xy=True)
        x, y = forward.transform(lon, lat)
        bounds = [round(x / 10) * 10 - 2560, round(y / 10) * 10 - 2560,
                  round(x / 10) * 10 + 2560, round(y / 10) * 10 + 2560]
        search_bounds = list(reverse.transform_bounds(*bounds))
        search = {
            "collections": ["sentinel-2-l2a"], "bbox": search_bounds,
            "datetime": (now - timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ") + "/" + now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "limit": 100, "sortby": [{"field": "datetime", "direction": "desc"}],
            "filter-lang": "cql2-json",
            "filter": {"op": "<=", "args": [{"property": "eo:cloud_cover"}, 20]},
        }
        write_json(folder / "stac_request.json", search)
        session = requests.Session()
        response = checked(session.post(STAC, json=search, timeout=60, allow_redirects=False), "STAC")
        (folder / "stac_response.json").write_bytes(response.content)
        catalog = response.json()
        features = catalog.get("features", [])
        aoi = box(*search_bounds)
        candidates = [f for f in features if f.get("geometry") and shape(f["geometry"]).covers(aoi)
                      and f["properties"].get("eo:cloud_cover", 101) <= 20]
        candidates.sort(key=lambda f: f["properties"]["datetime"], reverse=True)
        report.update({"stac_http": 200, "returned_scene_count": len(features),
                       "fully_covering_candidate_count": len(candidates),
                       "catalog_has_next_page": any(l.get("rel") == "next" for l in catalog.get("links", []))})
        if not candidates:
            raise RuntimeError("No <=20% cloud scene fully covers the trial AOI in the returned catalogue page.")
        selected = candidates[0]
        write_json(folder / "selected_scene.json", selected)
        instant = datetime.fromisoformat(selected["properties"]["datetime"].replace("Z", "+00:00"))
        report.update({"selected_scene_id": selected["id"], "scene_datetime": instant.isoformat(),
                       "tile_cloud_cover_percent": selected["properties"]["eo:cloud_cover"],
                       "output_crs": "EPSG:32612", "output_bounds": bounds,
                       "pixel_size_m": 10, "width": 512, "height": 512})
        print("STAC: selected", selected["id"], flush=True)
        client, secret = credentials()
        auth = checked(session.post(TOKEN, data={"grant_type": "client_credentials", "client_id": client,
                                                "client_secret": secret}, timeout=40, allow_redirects=False), "OAuth")
        token = auth.json().get("access_token")
        if not token:
            raise RuntimeError("OAuth returned no access token.")
        report["oauth_http"] = 200
        # STAC product timestamps can differ from tile sensing timestamps.
        # Restrict the request to the selected UTC day, retaining actual tile metadata.
        day_start = instant.replace(hour=0, minute=0, second=0, microsecond=0)
        process = {
            "input": {
                "bounds": {"bbox": bounds, "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/32612"}},
                "data": [{"type": "sentinel-2-l2a", "dataFilter": {
                    "timeRange": {"from": day_start.isoformat().replace("+00:00", "Z"),
                                  "to": (day_start + timedelta(days=1) - timedelta(milliseconds=1)).isoformat().replace("+00:00", "Z")},
                    "maxCloudCoverage": 20, "mosaickingOrder": "mostRecent"},
                    "processing": {"upsampling": "NEAREST", "downsampling": "NEAREST"}}]},
            "output": {"width": 512, "height": 512, "responses": [
                {"identifier": "rgb", "format": {"type": "image/png"}},
                {"identifier": "reflectance", "format": {"type": "image/tiff"}},
                {"identifier": "quality", "format": {"type": "image/tiff"}},
                {"identifier": "userdata", "format": {"type": "application/json"}}]},
            "evalscript": EVALSCRIPT,
        }
        write_json(folder / "process_request.json", process)
        print("Process API: requesting one 5.12 km square image at 10 m output spacing", flush=True)
        response = checked(session.post(PROCESS, json=process, headers={"Authorization": "Bearer " + token,
                                   "Accept": "application/tar"}, timeout=120, allow_redirects=False), "Process API")
        (folder / "process_response.tar").write_bytes(response.content)
        allowed = {"rgb.png", "reflectance.tif", "quality.tif", "userdata.json"}
        with tarfile.open(fileobj=io.BytesIO(response.content)) as archive:
            for member in archive.getmembers():
                if not member.isfile() or member.name not in allowed:
                    raise RuntimeError("Unexpected Process API archive member.")
                with archive.extractfile(member) as src:
                    (folder / member.name).write_bytes(src.read())
        for name in allowed:
            if not (folder / name).is_file():
                raise RuntimeError("Process API response is missing an expected output.")
        png = (folder / "rgb.png").read_bytes()
        if png[:8] != b"\x89PNG\r\n\x1a\n" or struct.unpack(">II", png[16:24]) != (512, 512):
            raise RuntimeError("Unexpected PNG dimensions or signature.")
        report.update({"status": "downloaded_pending_pixel_review", "process_http": 200,
                       "processing_units": response.headers.get("x-processingunits-spent"),
                       "reflectance_bands": ["B04", "B03", "B02", "B08"],
                       "quality_bands": ["SCL", "dataMask"],
                       "quality_note": "SCL is resampled onto the 10 m output grid, not native 10 m classification; it is not a trained CV mask.",
                       "artifacts": [{"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size,
                                      "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                                     for p in sorted(folder.iterdir()) if p.is_file()]})
        report["pixel_validation"] = inspect_pixels(folder, bounds)
        report["status"] = "passed"
        print("Downloaded:", folder.relative_to(ROOT), flush=True)
    except Exception as exc:
        report["status"] = "failed"
        # Only our own deliberately sanitized error messages are exposed.
        report["error"] = str(exc) if type(exc) is RuntimeError else type(exc).__name__
        print("Trial failed:", report["error"], flush=True)
    finally:
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        write_json(folder / "validation.json", report)
        write_json(ROOT / "data/reports/satellite_validation_once.json", report)
    return 1 if report["status"] == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
