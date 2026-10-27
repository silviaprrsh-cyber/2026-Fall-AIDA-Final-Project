# `backfill_weather_for_etl.py`

File: `API/backfill_weather_for_etl.py`

## Purpose

One bounded weather backfill matching saved hydrometric samples, no live scheduler.

## Defined functions/classes

`main`

## Direct imports

- `API.client: get_json`
- `API.observations: parse_time, API`
- `collections: defaultdict`
- `concurrent.futures: ThreadPoolExecutor`
- `csv`
- `datetime: timedelta, timezone`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json, now`
- `sys`

## Calls

`ThreadPoolExecutor`, `csv.reader`, `defaultdict`, `get_json`, `json.dumps`, `json.loads`, `main`, `now`, `parse_time`, `resolve_runtime_path`, `save_json`, `timedelta`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L47: save_json(resolve_runtime_path(DATA / 'reports/etl_weather_backfill.json'), {'completed_at': now(), 'continuous': False, 'sources': results})`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/backfill_weather_for_etl.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
