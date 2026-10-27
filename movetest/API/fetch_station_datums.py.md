# `fetch_station_datums.py`

File: `API/fetch_station_datums.py`

## Purpose

Cache official station-specific vertical-datum evidence once, without polling.

## Defined functions/classes

`inspect`, `main`

## Direct imports

- `API.client: fetch`
- `bs4: BeautifulSoup`
- `concurrent.futures: ThreadPoolExecutor`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json, now`
- `re`
- `sys`

## Calls

`BeautifulSoup`, `ThreadPoolExecutor`, `archive_relative`, `fetch`, `json.loads`, `main`, `now`, `re.finditer`, `resolve_runtime_path`, `save_json`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L50: save_json(resolve_runtime_path(DATA / 'processed/station_datums.json'), {'checked_at': now(), 'stations': records})`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/fetch_station_datums.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
