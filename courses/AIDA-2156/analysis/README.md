# analysis

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

---

## Project implementation and reproduction

The course requirements above are preserved. The following section describes the implemented Red Deer River project and its current limitations.

## analysis

Course code or run results for courses/AIDA-2156/analysis. See the course README for purpose, inputs, commands and limitations.

## Existing workflow and EDA boundary

From the repository root, `python -B run.py etl` runs `eda_tools.run_etl` and rebuilds scoped derived data. `python -B run.py -m eda_tools.analyze_unit_history --manifest <local-unit-acquisition-manifest>` normalizes the frozen source run, audits quality/gaps/cohorts and writes derived SQLite, CSV and `analysis_report.json`. Use the real archived manifest; the angle-bracket value is a placeholder. These commands write outputs and were not rerun during the documentation review.

`rdr_eda` contains reusable ETL/coverage/geometry checks; `rdr_ml` contains experimental modelling. These are historical supporting workflows. The formal EDA is separate: run `python -B analysis/analysis.py` from the course directory with the frozen normalized files (see [input provenance](../data/provenance.txt)). To generate the four colourblind-safe SVG figures from those verified CSV/JSON outputs, run `python -B -E -S analysis/make_eda_figures.py` (standard library only, writes `output/final_eda/figures/fig1_monthly_coverage.svg` through `fig4_sensitivity_rules.svg`). To choose another authorized archive path, use `--input-dir`; use `--output-dir` for an independent replay. The formal EDA and figure generator were verified with CPython 3.13 on Windows x64 (standard library only). They do not need the project virtual environment, GIS software, a database, model weights or network access. See the [decision report](../app-or-report/final-eda-report.md) for interpretation and output descriptions.

## Deployment pipeline is separate

The frozen reference checkpoint and the different source-only deployment adapter are documented in the [course README](../README.md). Analysis runs in this folder do not start the service, and their metrics do not validate the deployment adapter.

## Raw data EDA

Run `raw_data_eda.py` for the independent raw hydrometric/weather, satellite and survey audits. See the [output evidence and run command](../output/raw_data_eda/README.md). This is separate from the ETL pipeline and model training.
