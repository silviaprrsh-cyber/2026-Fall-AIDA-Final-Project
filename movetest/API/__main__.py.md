# `__main__.py`

File: `API/__main__.py`

## Purpose

Parse API commands and dispatch status inspection, collection and stop operations.

## Defined functions/classes

`main`

## Direct imports

- `API.collector: load_config, run`
- `argparse`
- `json`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, ROOT`

## Calls

`argparse.ArgumentParser`, `json.dumps`, `json.loads`, `load_config`, `main`, `resolve_runtime_path`, `run`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L29: path.write_text('stop\n', encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/__main__.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
