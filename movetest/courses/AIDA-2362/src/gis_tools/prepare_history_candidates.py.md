# `prepare_history_candidates.py`

File: `courses/AIDA-2362/src/gis_tools/prepare_history_candidates.py`

## Purpose

Select upstream historical stations using fresh WSC inventory and saved topology.

## Defined functions/classes

`main`

## Direct imports

- `csv`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr_gis.catalog: watercourse`
- `sys`

## Calls

`archive_relative`, `csv.DictReader`, `json.dumps`, `json.loads`, `main`, `resolve_runtime_path`, `watercourse`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L57: (folder / 'candidates.json').write_text(json.dumps(candidates, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/prepare_history_candidates.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
