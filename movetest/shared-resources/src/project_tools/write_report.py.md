# `write_report.py`

File: `shared-resources/src/project_tools/write_report.py`

## Purpose

Summarize data-coverage evidence and write bilingual reports and tables.

## Defined functions/classes

`read`, `export`, `write_language_reports`, `main`

## Direct imports

- `argparse`
- `collections: Counter`
- `csv`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, ROOT`
- `sys`

## Calls

`Counter`, `argparse.ArgumentParser`, `csv.DictWriter`, `export`, `insert`, `json.loads`, `main`, `read`, `resolve_runtime_path`, `write_language_reports`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L53: resolve_runtime_path(DATA / 'reports/coverage_reportCN.md').write_text(insert(zh, notes_zh), encoding='utf-8')`
- `L54: resolve_runtime_path(DATA / 'reports/coverage_report.md').write_text(insert(en, notes_en), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/write_report.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
