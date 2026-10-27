# `discover.py`

File: `API/discover.py`

## Purpose

Bounded first discovery: public metadata and one sample, cached under data/.

## Defined functions/classes

`run`

## Direct imports

- `API.client: fetch`
- `concurrent.futures`
- `pathlib: Path`
- `sys`

## Calls

`concurrent.futures.ThreadPoolExecutor`, `fetch`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/discover.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
