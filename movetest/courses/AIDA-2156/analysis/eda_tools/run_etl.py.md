# `run_etl.py`

File: `courses/AIDA-2156/analysis/eda_tools/run_etl.py`

## Purpose

`--segment-states PATH` optionally passes model predictions to the scoped builder for arrival-time labels. It cannot be combined with the legacy branch. The builder also writes the four segment tables, feature contract and PostgreSQL SQL export.

Default: build the current Dickson–Joffre dataset with `rdr_eda.project_etl.run_project_pipeline`, writing `data/processed/project_etl/` and `data/reports/project_etl_validation.json` in AIDA-2156. Only `--legacy-full-basin` invokes the older `run_pipeline`; `--reuse-spatial` applies to that older branch. No network or continuous collection.

## Defined functions/classes

None / 无

## Direct imports

- `argparse`
- `pathlib: Path`
- `rdr_eda.etl: run_pipeline`
- `rdr_eda.project_etl: run_project_pipeline`

## Calls

`argparse.ArgumentParser`, `run_project_pipeline` or `run_pipeline`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/run_etl.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
