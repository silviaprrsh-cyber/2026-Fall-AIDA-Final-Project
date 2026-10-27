# AIDA 2156 — EDA

Question: are hydrometric and precipitation observations sufficiently complete and temporally compatible to support the selected reach analysis? Observation units are station records and station-specific calculation windows.

Code: `analysis/`; inputs and normalized tables: `data/`. Sources are separated under `data/sources/`; copied provenance and validation records remain with the data. Survey inputs are read explicitly from AIDA 2362 through the shared path resolver. Run from the workspace root: `python -B run.py -m eda_tools.run_etl --reuse-spatial`. Results include `data/processed/etl/`, `data/reports/etl_validation.json` and `output/`.

Existing ETL still uses the historical full catalogue, not a completed P01–P03 model. Missing precipitation is not zero; all section risk results remain indeterminate. Still required: bounded analysis plan, dictionary/provenance, quality and claim-evidence tables, exploratory figures, uncertainty, two consequential sensitivity comparisons, accessible report, governance and final package. AI assisted migration; no causal or validated hydraulic claims are made.
