# `test_migration_isolation.py`

File: `shared-resources/tests/test_migration_isolation.py`

## Purpose

Catch accidental imports and path writes into the original project.

## Defined functions/classes

`MigrationIsolationTests`

## Direct imports

- `importlib`
- `pathlib: Path`
- `project_paths: WORKSPACE, ROOT, DATA, require_local, resolve_runtime_path, archive_relative`
- `unittest`

## Calls

`Path`, `archive_relative`, `importlib.import_module`, `require_local`, `resolve_runtime_path`, `self.assertEqual`, `self.assertRaises`, `self.assertTrue`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
