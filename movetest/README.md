# Red Deer River — reproducible course code

Code and inputs for the Dickson Dam–05CC002 project, separated into CV (2154), EDA (2156) and GIS (2362). The goal is a near-real-time monitoring system combining API inputs, recursive predictions and a dashboard. GIS, ETL and experimental ML are implemented to different extents; CV training and end-to-end deployment remain pending.

## Current scope and stage deliverables

Active development is in this folder. The reach ends at **05CC002**, about 56.0 km along the mapped mainstem from Dickson Dam outlet. The working map retains **P01–P05**, four river gauges (05CB007, 05CB001, 05CC007 and 05CC002), two historical/lake references, one weather station and 229 section lines. Marker availability remains the dated archived review, not a live availability check.

Reviewed presentation deliverables belong in the respective course deliverable folders, including [GIS outputs](courses/AIDA-2362/outputs/). These are not general destinations for logs, intermediate data or temporary exports. The [current GIS PDF](courses/AIDA-2362/outputs/Overhead%20view.pdf) and [PNG map](courses/AIDA-2362/project/map_overview.png) were exported and visually checked on 2026-11-08 from the reduced-scope [QGIS project](courses/AIDA-2362/project/dickson_to_joffre.qgz). The former Joffre PDF is preserved in the course data/processed/scope_history archive.

| Component | Verified state and remaining work |
|---|---|
| GIS | Reduced map reopened in QGIS 3.44.14 with all layers valid and both layouts retained; see [verification](courses/AIDA-2362/data/reports/qgis_scope_05CC002.json). |
| ETL / PostgreSQL | Rebuilt for 05CC002 with 229 sections and five targets; new versioned PostgreSQL snapshot and both partition-view sets verified. |
| ML | 60/20/20 and 80/20 experiments ran. Both selected the zero-parameter baseline; this is not evidence of useful learned improvement or validated intermediate predictions. |
| CV | Historical imagery is downloaded and indexed. Segmentation training and independent validation remain pending. |
| Final integration | Automatic acquisition → model inference → dashboard remains the final goal, not an implemented end-to-end service. |

Next work is retraining and evaluation on the new snapshot, investigating depth bias, and preparing CV with the active-scope mask. Old models and results remain historical comparisons.


## Field observation and winter observation scope

On 2026-11-03, the project author personally visited the Red Deer River within the City of Red Deer. The riverbed was visible in the visited reach, and the water appeared very shallow. This qualitative field note records the conditions seen at that location on that date.

Considering winter conditions that may include extremely low water, locally almost dry areas or freezing, the project will temporarily suspend observation work under winter low-water or frozen conditions. The current observation focus is on unfrozen periods with observable river flow.

## Segment ML entry point

PostgreSQL storage is active in database `red_deer_river`, schema `rdr_unit_0f36881e431d0966`. `v_train`, `v_validation` and `v_test` expose the 60/20/20 candidate partitions. `v_input_history`, `v_lake_history` and `v_endpoint_observations` support arrival-time matching, while geometry and routing have their own views. Run `python -B run.py ml inspect` to check loading or `python -B run.py ml train --iterations 3` for a bounded trial. The reproducible import is `python -B run.py -m eda_tools.import_unit_postgres`. Credentials stay in the project `.env`. Import verification is in `courses/AIDA-2156/data/reports/postgresql_unit_import.json`.

The active analysis source is the [18-month Wateroffice unit-value dataset](courses/AIDA-2156/data/processed/model_unit_history/20261103T070414Z/README.md). All 95 monthly station requests completed for 2025-05-03 through 2026-11-03 UTC. The files contain 1,350,764 unique parameter records and 95,053 screened, common observation timestamps, typically spaced five minutes apart. Chronological 60/20/20 candidate counts are 57,031/19,010/19,012 before propagation alignment and target-boundary checks. Numeric grades and provisional approvals are retained. The lake has a long winter gap. Daily means remain backup material and are excluded from the active analysis. The ML entry point now reads PostgreSQL views by default.

The backup [historical daily data](courses/AIDA-2156/data/processed/model_daily_history/20261102T233101Z/README.md) contains 118,655 records and its earlier screening audit. Those files are retained separately from the active unit-value analysis.

The offline main program supports `python -B run.py ml inspect`, `train`, `evaluate` and `predict`. It applies the minimum surveyed elevation as experimental section zero, computes A(h) and V = Q/A, and calibrates six recursive parameter blocks with arrival-aligned endpoint supervision. 05CC007 supplies independent Q, stage and trend features with a learned lag. All segment and feature parameters train jointly on the 05CC002 endpoint. The active PostgreSQL unit-value snapshot supports arrival-aligned training, validation and testing. Effective counts and model selection are recorded in each training report. Commands, outputs, equations and limitations are documented in [ML README](courses/AIDA-2156/analysis/rdr_ml/README.md).

The integrated model dataset is [segment_training.csv](courses/AIDA-2156/data/processed/project_etl/segment_training.csv). Each row represents one trajectory and independent submodel. The first chain is 05CB007 + 05CB001 flows and independent 05CC007 features → P01 → P02 → P03 → P04 → P05 → 05CC002 (current downstream endpoint). Lake 05CC003 elevation is an ML feature only for P03→P04, never an added discharge. Transit times use along-river distance and future submodel-predicted velocity; endpoint labels are matched to the nearest downstream observation time at predicted arrival, not to simultaneous records. Missing velocity leaves labels pending. [ETL usage and state format](courses/AIDA-2156/data/processed/project_etl/README.md) describe the feature allowlist, configurable match tolerance and optional PostgreSQL import. CSV/SQLite are populated locally. The segment snapshot has also been imported and verified in PostgreSQL database `red_deer_river`, schema `rdr_segments_989fed53a9ba`; see `courses/AIDA-2156/data/reports/postgresql_import.json`.

| Location | Contents |
|---|---|
| `API/` | Remote acquisition, one-time downloads and independent source scheduling |
| `shared-resources/src/` and `shared-resources/config/` | Shared storage, path resolution and configuration |
| `courses/AIDA-2154/src/`, `data/`, `outputs/` | Satellite input inspection and its data/results |
| `courses/AIDA-2156/analysis/`, `data/`, `output/` | Observation-time ETL and preliminary hydraulic calculations |
| `courses/AIDA-2362/src/`, `data/` | Survey/river processing and required spatial inputs |
| `courses/AIDA-2362/project/dickson_to_joffre.qgz` | Current working QGIS project and its local layers |
| `courses/AIDA-2362/outputs/` | Reviewed GIS presentation output |

## Experimental water-depth assumption and limitations

The local archived observations checked for the six river stations (05CB001, 05CB007, 05CC001, 05CC002, 05CC007 and 05CC011) contain no valid zero or negative water levels; each station's observed minimum is above zero. This finding applies only to the checked archives, which have different time coverage and gaps, not to each station's entire history.

For this experiment, the reported river water level will be used as the variable depth input. Any depth below the station's zero-water-level reference will be treated as an unknown constant and excluded from the calculation; only the component above that reference will be modelled. This is a simplifying experimental assumption, not a verified equivalence between gauge level and actual water depth. Sylvan Lake station 05CC003 will be handled separately as a lake-level elevation reference.

The supplied cross-section data have not been verified to identify the corresponding gauge zero on each profile. Consequently, the omitted depth and the alignment between gauge levels and section elevations remain unresolved. Predicted water depth, wetted area, velocity and potential overbank risk may therefore differ from actual conditions. Treating the omitted depth as constant does not establish that its effects on area or flow are constant. ETL now preserves the original `level_m` and supplies a separate `experimental_variable_depth_m` under this assumption. It does not calculate or validate area, velocity or risk predictions.

## Training experiment records

The [60/20/20 report](courses/AIDA-2156/data/reports/segment_ml_training_60_20_20.json) and [80/20 report](courses/AIDA-2156/data/reports/segment_ml_training_80_20.json) are retained separately. Both selected iteration 0. In the 80/20 test, experimental-depth Bias = -1.227800 m, MAE = 1.227800 m and RMSE = 1.228352 m, indicating persistent underestimation with little error spread. The 80/20 comparison reuses a previously inspected period and is not a new untouched test. See the ML README for assumptions and effective sample counts.

## Environment

For the existing workspace, run from `movetest` using `..\.venv\Scripts\python.exe -B run.py status` or `..\.venv\Scripts\python.exe -B run.py ml inspect`. The latter checks configured database inputs and needs PostgreSQL access. The setup below is for a separate new environment; do not recreate the existing parent environment. `etl` writes derived products and is not a read-only status check.

Use 64-bit Python 3.13. The existing workflow was checked with Python 3.13.11 on Windows. From this folder:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -B run.py status
.\.venv\Scripts\python.exe -B run.py inspect-imagery
.\.venv\Scripts\python.exe -B run.py etl
```

`requirements.txt` records dependency ranges; `requirements.lock.txt` records exact versions. A fresh dependency installation has not been checked here. QGIS-specific rendering requires QGIS 3.44.14 and its Python environment, not just pip packages.

## Inputs and reproduction

Keep the course `data/` folders and the GIS `project/` together with the code. A code-only Git checkout cannot reproduce archived results unless these ignored inputs are supplied separately with permission. Do not copy an environment or credentials from another machine. Source responses and metadata remain under each course's `data/sources/`; `shared-resources/config/data_layout.json` routes shared reads and writes. `archive_paths.json` resolves legacy provenance references.

`run.py etl` now rebuilds CSV/SQLite for the current map: four river stations, a lake reference, one weather station, 229 sections, five targets and 775 satellite index entries. Unit-value training history is separate from scoped ETL observations; current training views use the unit-value history. Source originals and previous snapshots are retained.

This build reuses normalized profiles in `courses/AIDA-2156/data/processed/etl/` and the final GIS selections in `courses/AIDA-2362/project/`. If those prerequisite profiles must be rebuilt from the supplied geodatabases, explicitly run `run.py etl --legacy-full-basin` first, then `run.py etl`. The older full-basin output is a prerequisite archive, not the current analysis dataset. `--reuse-spatial` affects only the legacy command; the default scoped build always reuses the reviewed spatial selection. Image inspection separately writes `courses/AIDA-2154/outputs/archive_inspection.json`.

Open the final `.qgz` in QGIS to inspect its saved layers/layouts and export the selected layout. Its OSM basemap requires network access. The older `qgis_layers_20261011` directory contains prerequisite vector layers for reconstruction, not another retained QGIS project. Rendering/rebuilding tools can change layouts; use the supplied final project to reproduce the reviewed map.

Additional executable modules use `python -B run.py -m PACKAGE [ARGS]`. Running API acquisition is a separate operation and may need network access; satellite acquisition also needs root `.env` credentials. No credentials are supplied. Module-specific companion notes describe calls and outputs.

Standalone test suites are not part of the submission package; runtime validation and experiment reports remain with their data. Runtime data checks and the source evidence required by acquisition/ETL remain. AI assisted code organization and documentation; scientific validity is not established by a successful run. Data-use terms govern redistribution. Course submission must include the permitted inputs needed for the intended reproduction route.

## Historical satellite inputs

The 2026-11-04 verification completed all 989 river-grid requests for 2025-05-03 through 2026-11-01 UTC. [Historical imagery](courses/AIDA-2154/data/processed/satellite_history/20261103_history/README.md) contains 955 extracted 10 m GeoTIFFs from 104 acquisition groups. The index flags 34 no-data responses and one image without reflectance signal. Of the downloaded images, 658 match common hydrometric observations within 150 seconds for all source tiles, and 485 also meet the >=80% clear-corridor criterion. These are automated CV input candidates, not trained segmentation results. Original TAR responses and acquisition provenance are retained in the AIDA-2154 source archive.

## Project modification history — 2026-11-04 (verified 2026-11-05)

The active movetest reach now ends at Red Deer station 05CC002. Retain P01–P05; remove P06–P11 and downstream Blindman/Waskasoo map inputs. The selected project data provide no comparable downstream observation constraint to validate the continuation to P11. This reduction limits unsupported extrapolation; it does not establish accuracy at retained targets. The filename `dickson_to_joffre.qgz` is retained for compatibility, but its layers and displayed endpoint now use 05CC002.

Source archives, previous model results and satellite acquisitions are retained. Existing `Overhead view.pdf`, `map_overview.png` and earlier validation reports are historical Joffre snapshots, not updated exports. Current GIS checks are `courses/AIDA-2362/data/reports/scope_05CC002.json` and `qgis_scope_05CC002.json`. The model already ends at 05CC002: its M06 link from P05 to the validation station remains; M06 is not prediction point P06. This map update does not retrain the model or replace PostgreSQL snapshots.

Per-file explanatory companions (for example `client.py.md`, `active_scope.json.md` and their Chinese copies) remain local and are ignored through `*.*.md` and `*CN.md`. Previously tracked companions have been removed from the Git index, not from local storage, except companions archived with retired tools. README and standalone English project documents remain eligible for Git tracking.

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
