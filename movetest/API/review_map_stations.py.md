# `review_map_stations.py`

File: `API/review_map_stations.py`

## Purpose

Fetch bounded station samples and official metadata for a map review.

## Defined functions/classes

`main`

## Direct imports

- `API.client: fetch`
- `API.observations: numeric`
- `API.snapshot_scope: sample`
- `argparse`
- `concurrent.futures: ThreadPoolExecutor`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`

## Calls

`ThreadPoolExecutor`, `archive_relative`, `argparse.ArgumentParser`, `datetime.now`, `datetime.now(timezone.utc).strftime`, `fetch`, `json.dumps`, `json.loads`, `main`, `numeric`, `resolve_runtime_path`, `sample`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L50: path.write_text(json.dumps(report, indent=2), encoding='utf-8')`
- `L64: path.write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/review_map_stations.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
