# `run.py`

File: `run.py`

## Purpose

Bootstrap the split course packages without importing the original project.

## Defined functions/classes

`bootstrap`, `main`

## Direct imports

- `os`
- `pathlib: Path`
- `runpy`
- `sys`

## Calls

`Path`, `bootstrap`, `main`, `os.chdir`, `os.environ.pop`, `runpy.run_module`, `sys.path.insert`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
