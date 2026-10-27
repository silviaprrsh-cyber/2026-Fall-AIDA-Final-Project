# `test_scope_snapshot.py`

File: `shared-resources/tests/test_scope_snapshot.py`

## Purpose

Check availability classification for bounded source snapshots offline.

## Defined functions/classes

`SnapshotTests`

## Direct imports

- `API: snapshot_scope`
- `json`
- `pathlib: Path`
- `tempfile: TemporaryDirectory`
- `unittest`
- `unittest.mock: patch`

## Calls

`Path`, `TemporaryDirectory`, `json.dumps`, `patch.object`, `self.assertEqual`, `self.assertIsNone`, `self.sample`, `snapshot_scope.sample`, `unittest.main`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L17: path.write_text(json.dumps({'features': [{'properties': p, 'geometry': None} for p in properties]}), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_scope_snapshot.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
