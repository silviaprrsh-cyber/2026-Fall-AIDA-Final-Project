# `test_api_layout.py`

File: `shared-resources/tests/test_api_layout.py`

## Purpose

Verify source separation, cache reuse and safe paths without contacting providers.

## Defined functions/classes

`SourceLayoutTests`

## Direct imports

- `API.client: fetch`
- `API.observations: swob`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path`
- `rdr.paths: ROOT, resolve_archived_path, source_for_url, source_relative_path`
- `requests`
- `tempfile`
- `unittest`
- `unittest.mock: patch`

## Calls

`Path`, `fetch`, `json.loads`, `patch`, `requests.Response`, `resolve_archived_path`, `resolve_runtime_path`, `self.assertEqual`, `self.assertRaises`, `source_for_url`, `source_relative_path`, `swob`, `tempfile.TemporaryDirectory`, `unittest.main`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_api_layout.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
