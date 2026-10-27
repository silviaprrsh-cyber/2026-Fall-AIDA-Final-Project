# `storage.py`

File: `shared-resources/src/rdr/storage.py`

## Purpose

Provide atomic JSON writes, UTC timestamps and request-log storage.

## Defined functions/classes

`now`, `save_json`, `log`

## Direct imports

- `__future__: annotations`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `threading`

## Calls

`Path`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `json.dumps`, `resolve_runtime_path`, `threading.Lock`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L23: tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')`
- `L31: out.write(json.dumps(event, ensure_ascii=False) + '\n')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/storage.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
