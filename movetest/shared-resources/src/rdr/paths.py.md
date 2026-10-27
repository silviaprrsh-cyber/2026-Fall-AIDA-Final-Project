# `paths.py`

File: `shared-resources/src/rdr/paths.py`

## Purpose

Source-specific archive paths and read-only resolution of pre-migration references.

## Defined functions/classes

`source_for_url`, `source_relative_path`, `_relocations`, `resolve_archived_path`

## Direct imports

- `functools: lru_cache`
- `json`
- `pathlib: Path`
- `project_paths: ROOT, WORKSPACE`
- `project_paths: resolve_runtime_path, archive_relative`
- `urllib.parse: urlsplit`

## Calls

`Path`, `_relocations`, `archive_relative`, `json.loads`, `lru_cache`, `resolve_runtime_path`, `source_for_url`, `urlsplit`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/paths.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
