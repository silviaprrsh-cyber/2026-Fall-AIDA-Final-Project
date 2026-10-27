# `observations.py`

File: `API/observations.py`

## Purpose

Parse hydrometric and weather observations, precipitation fields, timestamps and observed cadence evidence.

## Defined functions/classes

`parse_time`, `cadence`, `numeric`, `precipitation`, `swob`, `hydrometric`, `hydro_csv`

## Direct imports

- `API.client: fetch, get_json`
- `__future__: annotations`
- `collections: Counter`
- `csv`
- `datetime: datetime, timezone`
- `io`
- `math`
- `rdr.paths: source_relative_path`
- `rdr.storage: DATA`

## Calls

`Counter`, `cadence`, `csv.reader`, `datetime.fromisoformat`, `fetch`, `get_json`, `io.StringIO`, `math.isfinite`, `numeric`, `parse_time`, `precipitation`, `source_relative_path`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/observations.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
