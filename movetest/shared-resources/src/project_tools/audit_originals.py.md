# `audit_originals.py`

File: `shared-resources/src/project_tools/audit_originals.py`

## Purpose

Read-only optional audit of migration inputs; never needed to run the project.

## Defined functions/classes

`digest`, `main`

## Direct imports

- `argparse`
- `datetime: datetime, timezone`
- `hashlib`
- `json`
- `pathlib: Path`
- `project_paths: WORKSPACE`

## Calls

`argparse.ArgumentParser`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `digest`, `hashlib.file_digest`, `hashlib.file_digest(stream, 'sha256').hexdigest`, `json.dumps`, `json.loads`, `main`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L31: (WORKSPACE / 'shared-resources/results/source_preservation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

This note describes existing files only; it does not run collection, processing or training.
