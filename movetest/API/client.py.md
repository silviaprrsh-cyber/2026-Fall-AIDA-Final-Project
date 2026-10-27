# `client.py`

File: `API/client.py`

## Purpose

HTTP acquisition with source-separated archives and original provenance.

## Defined functions/classes

`fetch`, `get_json`

## Direct imports

- `hashlib`
- `json`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.paths: source_relative_path`
- `rdr.storage: DATA, now, save_json, log`
- `requests`

## Calls

`archive_relative`, `fetch`, `hashlib.sha256`, `hashlib.sha256(body).hexdigest`, `json.loads`, `log`, `now`, `requests.Request`, `requests.Request('GET', url, params=params).prepare`, `requests.get`, `resolve_runtime_path`, `save_json`, `source_relative_path`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L28: path.write_bytes(body)`
- `L34: save_json(meta_path, meta)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/client.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
