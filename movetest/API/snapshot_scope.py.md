# `snapshot_scope.py`

File: `API/snapshot_scope.py`

## Purpose

Fetch one bounded latest-observation sample for a specified station set.

## Defined functions/classes

`sample`, `main`

## Direct imports

- `API.client: fetch`
- `API.observations: numeric, precipitation`
- `argparse`
- `concurrent.futures: ThreadPoolExecutor`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`

## Calls

`ThreadPoolExecutor`, `archive_relative`, `argparse.ArgumentParser`, `datetime.now`, `datetime.now(timezone.utc).strftime`, `fetch`, `json.dumps`, `json.loads`, `main`, `numeric`, `precipitation`, `resolve_runtime_path`, `sample`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L73: (folder / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/snapshot_scope.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
