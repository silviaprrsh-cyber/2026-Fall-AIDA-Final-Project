# `build_config.py`

File: `shared-resources/src/project_tools/build_config.py`

## Purpose

Build reviewable per-station source configuration from validated evidence.

## Defined functions/classes

`main`

## Direct imports

- `API.collector: station_interval, calculation_interval`
- `API.observations: parse_time`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, ROOT, save_json, now`
- `sys`

## Calls

`calculation_interval`, `datetime.now`, `json.loads`, `main`, `now`, `parse_time`, `resolve_runtime_path`, `save_json`, `station_interval`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L52: save_json(resolve_runtime_path(DATA / 'reports/hydrometric_validation.json'), list(hydro.values()))`
- `L53: save_json(resolve_runtime_path(ROOT / 'config/stations.json'), {'schema_version': 2, 'generated_at_utc': now(), 'max_workers': 4, 'interval_rule': 'each unique source polls at its own publication interval; station calculation uses its hydrometric interval', 'auto_start': False, 'stations': result})`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/build_config.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
