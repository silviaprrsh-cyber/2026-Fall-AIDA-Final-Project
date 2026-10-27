# `prepare_tributary_history.py`

File: `courses/AIDA-2156/analysis/eda_tools/prepare_tributary_history.py`

## Purpose

Validate archived daily records and export historical station GIS metadata.

## Defined functions/classes

`read`, `write`, `write_csv`, `numeric`, `normalize`, `summarize`, `main`

## Direct imports

- `argparse`
- `csv`
- `datetime: date`
- `gis_tools.update_scoped_stations: update_map`
- `hashlib`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `sys`

## Calls

`argparse.ArgumentParser`, `csv.DictWriter`, `date.fromisoformat`, `date.fromisoformat(day).isoformat`, `hashlib.sha256`, `hashlib.sha256(layer.read_bytes()).hexdigest`, `hashlib.sha256(path.read_bytes()).hexdigest`, `json.dumps`, `json.loads`, `main`, `math.isfinite`, `normalize`, `numeric`, `read`, `resolve_runtime_path`, `summarize`, `update_map`, `write`, `write_csv`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L21: path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')`
- `L109: write(folder / 'station_summary.json', summaries)`
- `L123: write(layer, {'type': 'FeatureCollection', 'features': features})`
- `L131: write(map_folder / 'manifest.json', manifest)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/prepare_tributary_history.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
