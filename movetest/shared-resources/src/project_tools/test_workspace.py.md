# `test_workspace.py`

File: `shared-resources/src/project_tools/test_workspace.py`

## Purpose

Run migrated unit tests with outbound sockets disabled.

## Defined functions/classes

`main`

## Direct imports

- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `project_paths: WORKSPACE`
- `socket`
- `sys`
- `unittest`
- `unittest.mock: patch`

## Calls

`datetime.now`, `datetime.now(timezone.utc).isoformat`, `json.dumps`, `main`, `patch.object`, `sys.exit`, `unittest.TestLoader`, `unittest.TestLoader().discover`, `unittest.TestSuite`, `unittest.TextTestRunner`, `unittest.TextTestRunner(verbosity=2).run`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L27: path.write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
