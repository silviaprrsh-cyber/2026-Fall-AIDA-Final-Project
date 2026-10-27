# `project_paths.py`

File: `shared-resources/src/project_paths.py`

## Purpose

Resolve all runtime data/config paths inside this independent workspace.

## Defined functions/classes

`data_routes`, `resolve_runtime_path`, `archive_relative`, `require_local`

## Direct imports

- `functools: lru_cache`
- `json`
- `pathlib: Path`

## Calls

`Path`, `data_routes`, `json.loads`, `lru_cache`, `require_local`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
