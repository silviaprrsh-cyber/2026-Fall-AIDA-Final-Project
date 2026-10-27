# `test_timed_collection.py`

File: `shared-resources/tests/test_timed_collection.py`

## Purpose

Offline unit-test module.

## Defined functions/classes

`TimedCollectionTests`

## Direct imports

- `API.__main__: main`
- `API.collector: run`
- `API.datamart_notifications: DatamartNotifications`
- `json`
- `pathlib: Path`
- `tempfile`
- `threading`
- `time`
- `unittest`
- `unittest.mock: patch`

## Calls

`DatamartNotifications`, `Path`, `json.dumps`, `json.loads`, `main`, `patch`, `run`, `self.assertEqual`, `self.assertFalse`, `self.assertGreater`, `self.assertLess`, `self.assertRaises`, `self.assertTrue`, `self.config`, `tempfile.TemporaryDirectory`, `threading.Event`, `threading.Thread`, `time.monotonic`, `time.sleep`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L20: (state / 'active_run.json').write_text(json.dumps(active))`
- `L29: (state / 'active_run.json').write_text(json.dumps({'status': 'running', 'stop_file': 'outside.stop'}))`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_timed_collection.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
