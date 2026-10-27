# `test_archive_inspection.py`

File: `courses/AIDA-2154/tests/test_archive_inspection.py`

## Purpose

Check that empty imagery cannot be reported as a usable CV input.

## Defined functions/classes

`ArchiveInspectionTests`

## Direct imports

- `cv_tools.inspect_archive: summarize`
- `numpy`
- `pathlib: Path`
- `rasterio`
- `rasterio.transform: from_origin`
- `tempfile`
- `unittest`
- `unittest.mock: patch`

## Calls

`Path`, `from_origin`, `np.array`, `patch`, `rasterio.open`, `self.assertEqual`, `summarize`, `tempfile.TemporaryDirectory`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L19: rasterio.open(path, 'w', driver='GTiff', width=2, height=2, count=2, dtype='uint8', crs='EPSG:32612', transform=from_origin(300000, 5800000, 10, 10))`
- `L21: dst.write(bands)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
