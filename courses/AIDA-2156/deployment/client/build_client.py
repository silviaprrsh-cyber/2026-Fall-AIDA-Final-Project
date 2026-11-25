"""Build the single-file RedDeerRiver.exe (v2.1 Hydro-GIS WebView2 desktop client) and Windows client ZIP.

Embeds:
  - 8 active AIDA 2362 56 km GIS layers (gis_bundle.json.gz)
  - Official NRCan OGL-Canada CBMT offline basemap (nrcan_cbmt_basemap.jpg + metadata)
  - Full 18-month matched historical ECCC + V4 replay dataset (replay_history.json.gz)
  - Modern Hydro-GIS WebView2 UI (ui.html.gz) + Microsoft WebView2 runtime bridges

Usage (from repository root):
  python -B courses/AIDA-2156/deployment/client/build_client.py --wv2-dir <path-to-wv2-dlls>
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import subprocess
import tempfile
import zipfile
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
CLIENT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = CLIENT_DIR / "assets"
DIST_DIR = CLIENT_DIR.parent / "dist"
GIS_PROJECT = WORKSPACE / "courses" / "AIDA-2362" / "project"
CSC_EXE = Path(r"C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe")


def round_coords(coords, decimals: int = 5):
    if isinstance(coords[0], (int, float)):
        return [round(float(coords[0]), decimals), round(float(coords[1]), decimals)]
    return [round_coords(c, decimals) for c in coords]


def simplify_line(pts, stride: int = 1):
    if stride <= 1 or len(pts) <= 4:
        return pts
    out = pts[::stride]
    if out[-1] != pts[-1]:
        out.append(pts[-1])
    return out


def build_gis_bundle() -> bytes:
    """Compact all 8 active AIDA 2362 56 km GIS layers into a lean JSON payload."""
    def load(rel: str) -> list[dict]:
        return json.loads((GIS_PROJECT / rel).read_text(encoding="utf-8"))["features"]

    rivers = []
    for f in load("nrcan_nhn/selected_rivers.geojson"):
        p = f["properties"]
        g = f["geometry"]
        coords = round_coords(g["coordinates"], 5)
        if g["type"] == "LineString":
            coords = simplify_line(coords, stride=2 if len(coords) > 200 else 1)
        rivers.append({
            "t": g["type"],
            "g": coords,
            "p": {"river": p.get("river"), "role": p.get("role"), "length_m": round(float(p.get("length_m") or 0), 1)},
        })

    def load_sections(rel: str, surveyed: bool) -> list[dict]:
        out = []
        for f in load(rel):
            p = f["properties"]
            coords = round_coords(f["geometry"]["coordinates"], 5)
            coords = simplify_line(coords, stride=2 if len(coords) > 40 else 1)
            out.append({
                "t": "LineString",
                "g": coords,
                "p": {
                    "id": p.get("section_id"),
                    "src": p.get("source_section_id"),
                    "river": p.get("river"),
                    "surveyed": surveyed,
                },
            })
        return out

    sections_surveyed = load_sections("alberta_flood_surveys/red_deer/cross_section_lines.geojson", True)
    sections_planned = load_sections("alberta_flood_surveys/county_markerville/cross_section_lines.geojson", False)

    targets = []
    for f in load("derived_prediction_targets/prediction_points.geojson"):
        p = f["properties"]
        sec_id = str(p.get("nearest_section_id") or "")
        targets.append({
            "t": "Point",
            "g": round_coords(f["geometry"]["coordinates"], 5),
            "p": {
                "id": p.get("target_id"),
                "name": p.get("name"),
                "chainage_m": round(float(p.get("chainage_from_dickson_m") or 0), 1),
                "offset_m": round(float(p.get("nearest_section_along_river_offset_m") or 0), 2),
                "section_id": sec_id,
                "surveyed": sec_id.startswith("red_deer:"),
            },
        })

    stations = []
    for f in load("eccc_hydrometric_geomet/stations.geojson"):
        p = f["properties"]
        stations.append({
            "t": "Point",
            "g": round_coords(f["geometry"]["coordinates"], 5),
            "p": {
                "id": p.get("station_id"),
                "name": p.get("name"),
                "river": p.get("river"),
                "role": p.get("role", "water_observation"),
            },
        })

    hist_stations = []
    for f in load("eccc_hydrometric_geomet/historical_tributary_stations.geojson"):
        p = f["properties"]
        hist_stations.append({
            "t": "Point",
            "g": round_coords(f["geometry"]["coordinates"], 5),
            "p": {
                "id": p.get("station_id"),
                "name": p.get("name"),
                "river": p.get("river"),
                "role": p.get("role"),
            },
        })

    weather_station = []
    for f in load("eccc_weather_geomet/stations.geojson"):
        p = f["properties"]
        weather_station.append({
            "t": "Point",
            "g": round_coords(f["geometry"]["coordinates"], 5),
            "p": {"id": p.get("station_id") or p.get("msc_id"), "name": p.get("name")},
        })

    weather_area = []
    for f in load("derived_weather_associations/areas.geojson"):
        g = f["geometry"]
        coords = round_coords(g["coordinates"], 4)
        if g["type"] == "Polygon":
            coords = [simplify_line(ring, stride=3 if len(ring) > 100 else 1) for ring in coords]
        elif g["type"] == "MultiPolygon":
            coords = [[simplify_line(ring, stride=3 if len(ring) > 100 else 1) for ring in poly] for poly in coords]
        weather_area.append({"t": g["type"], "g": coords, "p": {"id": f["properties"].get("weather_id")}})

    bundle = {
        "rivers": rivers,
        "sections_surveyed": sections_surveyed,
        "sections_planned": sections_planned,
        "targets": targets,
        "stations": stations,
        "hist_stations": hist_stations,
        "weather_station": weather_station,
        "weather_area": weather_area,
    }
    return json.dumps(bundle, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def gz_write(dest: Path, raw: bytes) -> int:
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    dest.write_bytes(compressed)
    return len(compressed)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wv2-dir", type=Path, required=True, help="Directory with WebView2 Core/WinForms/Loader DLLs.")
    args = parser.parse_args()

    assert CSC_EXE.is_file(), f"Missing C# compiler: {CSC_EXE}"
    core_dll = args.wv2_dir / "Microsoft.Web.WebView2.Core.dll"
    wf_dll = args.wv2_dir / "Microsoft.Web.WebView2.WinForms.dll"
    loader_dll = args.wv2_dir / "WebView2Loader.dll"
    bm_jpg = ASSETS_DIR / "nrcan_cbmt_basemap.jpg"
    bm_json = ASSETS_DIR / "nrcan_cbmt_basemap.json"
    ab_jpg = ASSETS_DIR / "nrcan_ab_wide.jpg"
    ab_json = ASSETS_DIR / "nrcan_ab_wide.json"
    replay_gz = ASSETS_DIR / "replay_history.json.gz"
    for p in (core_dll, wf_dll, loader_dll, bm_jpg, bm_json, ab_jpg, ab_json, replay_gz):
        assert p.is_file(), f"Missing required build asset: {p}"

    gis_json = build_gis_bundle()
    ui_html = (CLIENT_DIR / "ui.html").read_bytes()

    with tempfile.TemporaryDirectory(prefix="rdr_build_") as tmp_str:
        tmp = Path(tmp_str)
        r_gis = tmp / "gis_bundle.json.gz"
        r_ui = tmp / "ui.html.gz"
        r_bm_json = tmp / "nrcan_cbmt_basemap.json.gz"
        r_ab_json = tmp / "nrcan_ab_wide.json.gz"
        r_core = tmp / "wv2_core.dll.gz"
        r_wf = tmp / "wv2_winforms.dll.gz"
        r_loader = tmp / "wv2_loader.dll.gz"

        sizes = {
            "gis_json_gz": gz_write(r_gis, gis_json),
            "ui_html_gz": gz_write(r_ui, ui_html),
            "nrcan_bm_jpg": bm_jpg.stat().st_size,
            "nrcan_bm_json_gz": gz_write(r_bm_json, bm_json.read_bytes()),
            "nrcan_ab_jpg": ab_jpg.stat().st_size,
            "nrcan_ab_json_gz": gz_write(r_ab_json, ab_json.read_bytes()),
            "replay_history_gz": replay_gz.stat().st_size,
            "wv2_core_gz": gz_write(r_core, core_dll.read_bytes()),
            "wv2_wf_gz": gz_write(r_wf, wf_dll.read_bytes()),
            "wv2_loader_gz": gz_write(r_loader, loader_dll.read_bytes()),
        }
        print("Embedded asset sizes:", json.dumps(sizes))

        DIST_DIR.mkdir(parents=True, exist_ok=True)
        out_exe = DIST_DIR / "RedDeerRiver.exe"
        cmd = [
            str(CSC_EXE),
            "/nologo",
            "/target:winexe",
            "/platform:x64",
            "/optimize+",
            f"/out:{out_exe}",
            "/r:System.dll",
            "/r:System.Core.dll",
            "/r:System.Drawing.dll",
            "/r:System.Net.Http.dll",
            "/r:System.Web.Extensions.dll",
            "/r:System.Windows.Forms.dll",
            f"/r:{core_dll}",
            f"/r:{wf_dll}",
            f"/resource:{r_gis},gis_bundle.json.gz",
            f"/resource:{r_ui},ui.html.gz",
            f"/resource:{replay_gz},replay_history.json.gz",
            f"/resource:{r_bm_json},nrcan_cbmt_basemap.json.gz",
            f"/resource:{bm_jpg},nrcan_cbmt_basemap.jpg",
            f"/resource:{r_ab_json},nrcan_ab_wide.json.gz",
            f"/resource:{ab_jpg},nrcan_ab_wide.jpg",
            f"/resource:{r_core},wv2_core.dll.gz",
            f"/resource:{r_wf},wv2_winforms.dll.gz",
            f"/resource:{r_loader},wv2_loader.dll.gz",
            str(CLIENT_DIR / "RedDeerRiver.cs"),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            print(res.stdout)
            print(res.stderr)
            raise SystemExit(res.returncode)

        # Rebuild RedDeerRiver-Client-Windows.zip (single EXE + English guide)
        out_zip = DIST_DIR / "RedDeerRiver-Client-Windows.zip"
        with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            zf.write(out_exe, arcname="RedDeerRiver.exe")
            zf.write(CLIENT_DIR / "README.md", arcname="README.md")

        print(f"Built {out_exe.name}: {out_exe.stat().st_size:,} B ({out_exe.stat().st_size/1024/1024:.2f} MB) | sha256={sha256(out_exe)[:16]}")
        print(f"Built {out_zip.name}: {out_zip.stat().st_size:,} B ({out_zip.stat().st_size/1024/1024:.2f} MB) | sha256={sha256(out_zip)[:16]}")


if __name__ == "__main__":
    main()
