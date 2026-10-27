# `export_qgis_layers.py`

File: `courses/AIDA-2362/src/gis_tools/export_qgis_layers.py`

## Purpose

Export archived spatial data into source-separated WGS84 GeoJSON layers.

Run with the project virtual environment. This performs no acquisition or ETL
rebuild. The separate render_qgis_project.py uses the installed QGIS runtime.

## Defined functions/classes

`sha`, `main`

## Direct imports

- `argparse`
- `collections: Counter, defaultdict`
- `datetime: datetime, timezone`
- `hashlib`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj.transformer: AreaOfInterest, TransformerGroup`
- `pyproj: datadir`
- `shapely.geometry: box, mapping, shape`
- `shapely.ops: transform`
- `shapely: make_valid, is_valid_reason`
- `xml.etree.ElementTree`

## Calls

`AreaOfInterest`, `Counter`, `ET.parse`, `ET.parse(path).getroot`, `TransformerGroup`, `archive_relative`, `argparse.ArgumentParser`, `box`, `datadir.append_data_dir`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `defaultdict`, `export`, `feature`, `hashlib.file_digest`, `hashlib.file_digest(stream, 'sha256').hexdigest`, `is_valid_reason`, `json.dumps`, `json.loads`, `main`, `make_valid`, `mapping`, `math.isfinite`, `point`, `project_geometry`, `read`, `resolve_runtime_path`, `sha`, `shape`, `transform`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L300: (output / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')`
- `L120: path.write_text(json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/export_qgis_layers.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
