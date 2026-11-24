"""Run the three independent, offline AIDA 2156 raw-data audits."""
from __future__ import annotations

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import sys

ANALYSIS = Path(__file__).resolve().parent
COURSE = ANALYSIS.parent
DEFAULT = COURSE / "output" / "raw_data_eda"
SCRIPTS = {
    "hydro": "raw_hydro_audit.py",
    "cv": "raw_cv_audit.py",
    "gis": "raw_gis_audit.py",
}


def resolve_gis_python(override):
    if override:
        if not override.is_file():
            raise FileNotFoundError(f"GIS Python launcher not found: {override}")
        return override.resolve()
    if importlib.util.find_spec("osgeo"):
        return Path(sys.executable)
    if os.name == "nt":
        base = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        candidates = sorted(base.glob("QGIS */bin/python-qgis-ltr.bat"), reverse=True)
        candidates += sorted(base.glob("QGIS */bin/python-qgis.bat"), reverse=True)
        if candidates:
            return candidates[0]
    raise RuntimeError("GIS audit needs GDAL with OpenFileGDB support. "
                       "Use GDAL-enabled Python or pass --gis-python with the QGIS Python launcher.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT)
    parser.add_argument("--only", choices=SCRIPTS, action="append", help="Repeat to run selected audits.")
    parser.add_argument("--gis-python", type=Path, help="GDAL-enabled Python executable or QGIS Python launcher.")
    parser.add_argument("--no-raster-spot-check", action="store_true", help="Omit CV raster metadata sampling.")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    selected = set(args.only or SCRIPTS)
    gis_python = resolve_gis_python(args.gis_python) if "gis" in selected else None
    for name, script in SCRIPTS.items():
        if name not in selected:
            continue
        python = gis_python if name == "gis" else sys.executable
        command = [str(python), "-B", str(ANALYSIS / script), "--output-dir", str(output)]
        if name == "cv" and args.no_raster_spot_check:
            command.append("--no-raster-spot-check")
        subprocess.run(command, check=True)
    print(f"Completed {', '.join(name for name in SCRIPTS if name in selected)}: {output}")


if __name__ == "__main__":
    main()

