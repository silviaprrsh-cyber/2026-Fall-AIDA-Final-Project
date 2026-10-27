# `download_static.py`

File: `API/download_static.py`

## Purpose

One-time official river geometry and survey/report acquisition; resumable.

## Defined functions/classes

`reports`, `arc_query`, `initial_gis`

## Direct imports

- `API.client: fetch, get_json`
- `bs4: BeautifulSoup`
- `concurrent.futures`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json`
- `sys`
- `urllib.parse: urlparse`

## Calls

`BeautifulSoup`, `Path`, `arc_query`, `concurrent.futures.ThreadPoolExecutor`, `fetch`, `get_json`, `initial_gis`, `reports`, `resolve_runtime_path`, `save_json`, `urlparse`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L50: save_json(resolve_runtime_path(DATA / 'processed/flood_resource_inventory.json'), result)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/download_static.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
