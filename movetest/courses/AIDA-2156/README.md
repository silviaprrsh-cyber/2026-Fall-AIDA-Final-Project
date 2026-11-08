# AIDA 2156 — EDA

The active [unit-value history analysis](data/processed/model_unit_history/20261103T070414Z/README.md) contains 95,053 common screened observation timestamps over the requested 18-month window. The candidate 60/20/20 split is by record count and time order. Daily-history files remain backups and are excluded from this analysis. Source grades, approvals, missingness and provenance are preserved.

The experimental recursive ML entry point is `python -B run.py ml inspect`. Training, evaluation and prediction commands are described in [the ML README](analysis/rdr_ml/README.md). It uses minimum surveyed elevation as experimental section zero and derives velocity from Q/A. 05CC007 supplies independent Q, stage and trend features with a learned lag. All parameters train jointly on the 05CC002 endpoint. The active unit-value dataset is stored in PostgreSQL. Training reads versioned views and reports effective arrival-aligned sample counts for each partition.

Question: are hydrometric and precipitation observations sufficiently complete and temporally compatible to support the selected reach analysis? Observation units are station records and station-specific calculation windows.

The integrated submodel table is `data/processed/project_etl/segment_training.csv`: M01–M06 run from the source inputs (05CB007 + 05CB001 flows, with independent 05CC007 features) through P01–P05 to validation station 05CC002. Sylvan Lake elevation is a separate feature only for P03→P04. Future submodel velocities determine cumulative L/V arrival times and nearest-time endpoint labels; no same-time fallback is used. Missing model states remain null. The data README documents optional `--segment-states` input and PostgreSQL SQL export; local training artifacts are retained separately; credentials and ignored data are not included in a code-only checkout.

Code: `analysis/`; inputs and normalized tables: `data/`. Sources remain separated under `data/sources/`. Run from the project root: `python -B run.py etl`. The current reduced-scope dataset is in [data/processed/project_etl/](data/processed/project_etl/README.md), with CSV and SQLite versions and a build report at `data/reports/project_etl_validation.json`. The final GIS selection and normalized profiles are explicit prerequisites; raw data are retained.

The former 2026-11-02 ETL snapshot is backed up. Current ETL and GIS retain P01-P05, 229 sections and validation endpoint 05CC002, with synchronized PostgreSQL views. Experimental depth assumptions, missing-precipitation handling and EDA reporting work remain; endpoint supervision does not validate intermediate states.

The PostgreSQL importer is `python -B run.py -m eda_tools.import_unit_postgres`. It creates a versioned snapshot with source hashes. Training uses `v_train`, `v_validation` and `v_test`, plus separate lagged input, lake, endpoint and geometry views. Newly acquired data require a new import before training can use them.

The 60/20/20 and 80/20 training experiments both selected the zero-parameter baseline, without demonstrated learned improvement. Reports are `data/reports/segment_ml_training_60_20_20.json` and `data/reports/segment_ml_training_80_20.json`; map updates do not retrain these experiments.

## Scope synchronization — 2026-11-08

API configuration, current GIS and rebuilt ETL now use Dickson Dam outlet → 05CC002: four enabled river gauges, a separate lake reference, one weather station, P01–P05 and 229 sections. The ETL satellite table now indexes 775 overlapping archived rasters; recalculated quality/time checks select 389 candidates. Original images are unchanged. Use the active-scope mask before CV; neither selection nor provider masks are a trained CV model.

The current PostgreSQL snapshot is `rdr_unit_0f36881e431d0966`. Both default 60/20/20 views (57,031 / 19,010 / 19,012 candidates) and 80/20 views (76,042 / 0 / 19,011) were verified. These are candidate counts before travel-time alignment. Training still reads the unit-value dataset, not the 6,572 instantaneous rows in the separate scoped ETL archive.

The previous PostgreSQL snapshot and both trained models remain historical. Changed geometry/graph rejects old model reuse. New default artifacts go to `courses/AIDA-2156/data/processed/segment_ml_05CC002/`; no new model has been trained. Use a separate output directory for an 80/20 run. Previous ETL and configuration are preserved in `courses/AIDA-2156/data/processed/scope_history/before_05CC002_sync_20261108.zip`.

Reproduction from the movetest directory, using its installed Python environment:

```powershell
python -B run.py -m cv_tools.select_scope_history
python -B run.py etl
python -B run.py -m eda_tools.import_unit_postgres
python -B run.py -m eda_tools.import_unit_postgres --split 80-20
python -B run.py ml inspect
```

The first two commands rebuild local derived selections; the import commands write a versioned PostgreSQL schema/configuration. They do not fetch new observations or train a model. The satellite archive, normalized surveys and QGIS layers must accompany the code. For a new machine, create a local Python 3.13 environment and install `requirements.lock.txt`; configure `.env` from the blank `.env.example` using that machine's PostgreSQL account. Satellite credentials are needed only for new acquisition. In this workspace the existing parent `.venv` can be used explicitly; no credentials were copied and no second environment was created. QGIS remains a separately installed dependency. This is reproduction from supplied data, not an automatic reconstruction of every source archive from an empty checkout.
