# `project_etl.py`

Also calls `rdr_eda.segments` to build six independent submodel stages through 05CC002, the integrated master table, arrival audit, predictor contract and transactional PostgreSQL SQL export. Optional `segment_state_path` supplies model predictions; missing velocities keep endpoint labels null. Database credentials are neither read nor exported.

Builds the current Dickson–Joffre ETL dataset offline. Called by `python -B run.py etl` through `eda_tools.run_etl`. Uses the existing precipitation normalizer/aggregator, API timestamp parser, configured station intervals, Shapely/PyProj geometry and Rasterio metadata. Reads archived CSV/GeoJSON responses, `active_scope.json`, station configuration, final GIS layers and normalized survey profiles. Does not call the network, train models or alter source data.

Writes CSV tables, a typed SQLite database and bilingual per-file descriptions to `courses/AIDA-2156/data/processed/project_etl/`; writes the build counts, input hashes and limitations to `courses/AIDA-2156/data/reports/project_etl_validation.json` and its descriptions. Temporary SQLite staging is replaced after integrity validation. See the output README for field meanings and assumptions.
