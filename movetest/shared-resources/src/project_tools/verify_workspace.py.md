# `verify_workspace.py`

File: `shared-resources/src/project_tools/verify_workspace.py`

## Purpose

Check package isolation, copied inputs and portable GIS layer references.

## Defined functions/classes

`main`

## Direct imports

- `ast`
- `datetime: datetime, timezone`
- `importlib`
- `json`
- `pathlib: Path`
- `project_paths: DATA, ROOT, WORKSPACE, require_local`
- `project_paths: resolve_runtime_path, archive_relative`
- `xml.etree.ElementTree`
- `zipfile`

## Calls

`ET.fromstring`, `ROOT.relative_to`, `ROOT.relative_to(WORKSPACE).as_posix`, `ast.parse`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `importlib.import_module`, `json.dumps`, `json.loads`, `main`, `require_local`, `resolve_runtime_path`, `zipfile.ZipFile`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L55: output.write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
