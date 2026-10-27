# `check_project.py`

File: `courses/AIDA-2362/src/gis_tools/check_project.py`

## Purpose

Open copied GIS projects in QGIS without rendering or fetching map tiles.

## Defined functions/classes

`main`

## Direct imports

- `json`
- `os`
- `pathlib: Path`
- `project_paths: WORKSPACE, DATA`
- `project_paths: resolve_runtime_path, archive_relative`
- `qgis.core: QgsApplication, QgsProject`
- `tempfile`

## Calls

`QgsApplication`, `QgsProject`, `json.dumps`, `main`, `resolve_runtime_path`, `tempfile.TemporaryDirectory`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L32: output.write_text(json.dumps({'projects': results, 'passed': True, 'note': 'Projects opened without map rendering or basemap requests.'}, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
