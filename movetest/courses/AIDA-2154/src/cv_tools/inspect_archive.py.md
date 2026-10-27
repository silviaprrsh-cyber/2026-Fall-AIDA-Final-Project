# `inspect_archive.py`

File: `courses/AIDA-2154/src/cv_tools/inspect_archive.py`

## Purpose

Inspect copied Sentinel samples locally without acquisition or model training.

## Defined functions/classes

`summarize`, `main`

## Direct imports

- `json`
- `numpy`
- `project_paths: DATA, WORKSPACE`
- `project_paths: resolve_runtime_path, archive_relative`
- `rasterio`

## Calls

`json.dumps`, `main`, `np.isin`, `rasterio.open`, `resolve_runtime_path`, `summarize`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L28: output.write_text(json.dumps(rows, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
