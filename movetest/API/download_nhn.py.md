# `download_nhn.py`

File: `API/download_nhn.py`

## Purpose

Download all WSC 05C National Hydro Network units once, including SK mouth.

## Defined functions/classes

`main`

## Direct imports

- `API.client: fetch`
- `bs4: BeautifulSoup`
- `concurrent.futures`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json`
- `sys`
- `urllib.parse: urljoin`
- `zipfile`

## Calls

`BeautifulSoup`, `archive_relative`, `concurrent.futures.ThreadPoolExecutor`, `fetch`, `main`, `resolve_runtime_path`, `save_json`, `urljoin`, `zipfile.ZipFile`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L28: save_json(resolve_runtime_path(DATA / 'processed/nhn_inventory.json'), result)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/download_nhn.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
