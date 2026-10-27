# `inspect_reports.py`

File: `shared-resources/src/project_tools/inspect_reports.py`

## Purpose

Index PDF contents; do not equate figures/reports with raw survey/model files.

## Defined functions/classes

`main`

## Direct imports

- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `pymupdf`
- `rdr.storage: DATA, save_json`
- `re`
- `sys`

## Calls

`archive_relative`, `json.loads`, `main`, `pymupdf.open`, `resolve_runtime_path`, `save_json`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L29: save_json(resolve_runtime_path(DATA / 'reports/pdf_content_inventory.json'), result)`
- `L24: target.write_text('\n'.join(pages), encoding='utf-8')`
- `L27: save_json(index_path, entry)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/inspect_reports.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
