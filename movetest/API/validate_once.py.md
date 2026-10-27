# `validate_once.py`

File: `API/validate_once.py`

## Purpose

One bounded validation run per endpoint, resumed from cached raw responses.

## Defined functions/classes

`distance`, `main`

## Direct imports

- `API.observations: hydrometric, hydro_csv, swob, parse_time`
- `concurrent.futures`
- `datetime: datetime, timezone`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json, now`
- `rdr_gis.catalog: build_catalog`
- `sys`

## Calls

`build_catalog`, `concurrent.futures.ThreadPoolExecutor`, `datetime.now`, `distance`, `hydro_csv`, `hydrometric`, `json.loads`, `main`, `math.asin`, `math.cos`, `math.sin`, `math.sqrt`, `now`, `parse_time`, `resolve_runtime_path`, `save_json`, `swob`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L36: save_json(resolve_runtime_path(DATA / 'reports/hydrometric_validation.json'), waters)`
- `L65: save_json(resolve_runtime_path(DATA / 'reports/weather_validation.json'), list(validation.values()))`
- `L66: save_json(resolve_runtime_path(DATA / 'processed/weather_links.json'), links)`
- `L67: save_json(resolve_runtime_path(DATA / 'reports/validation_run.json'), {'completed_at_utc': now(), 'hydrometric_stations': len(stations), 'weather_endpoints': len(validation), 'linked_with_precipitation': sum((bool(x['weather_id']) for x in links)), 'mode': 'single cached snapshot, no continuous polling'})`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/validate_once.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
