# Red Deer River — reproducible course code

Code and inputs for the Dickson Dam–Joffre Bridge project, separated into CV (2154), EDA (2156) and GIS (2362). This folder contains the current implemented workflow; it does not claim completed ML/CV training or validated flood prediction.


## Field observation and winter observation scope

On 2026-11-03, the project author personally visited the Red Deer River within the City of Red Deer. The riverbed was visible in the visited reach, and the water appeared very shallow. This qualitative field note records the conditions seen at that location on that date.

Considering winter conditions that may include extremely low water, locally almost dry areas or freezing, the project will temporarily suspend observation work under winter low-water or frozen conditions. The current observation focus is on unfrozen periods with observable river flow.

## Segment ML entry point

PostgreSQL storage is active in database `red_deer_river`, schema `rdr_unit_c85b2cab1263ea01`. `v_train`, `v_validation` and `v_test` expose the 60/20/20 candidate partitions. `v_input_history`, `v_lake_history` and `v_endpoint_observations` support arrival-time matching, while geometry and routing have their own views. Run `python -B run.py ml inspect` to check loading or `python -B run.py ml train --iterations 3` for a bounded trial. The reproducible import is `python -B run.py -m eda_tools.import_unit_postgres`. Credentials stay in the project `.env`. Import verification is in `courses/AIDA-2156/data/reports/postgresql_unit_import.json`.

The active analysis source is the [18-month Wateroffice unit-value dataset](courses/AIDA-2156/data/processed/model_unit_history/20261103T070414Z/README.md). All 95 monthly station requests completed for 2025-05-03 through 2026-11-03 UTC. The files contain 1,350,764 unique parameter records and 95,053 screened, common observation timestamps, typically spaced five minutes apart. Chronological 60/20/20 candidate counts are 57,031/19,010/19,012 before propagation alignment and target-boundary checks. Numeric grades and provisional approvals are retained. The lake has a long winter gap. Daily means remain backup material and are excluded from the active analysis. The ML entry point now reads PostgreSQL views by default.

The backup [historical daily data](courses/AIDA-2156/data/processed/model_daily_history/20261102T233101Z/README.md) contains 118,655 records and its earlier screening audit. Those files are retained separately from the active unit-value analysis.

The offline main program supports `python -B run.py ml inspect`, `train`, `evaluate` and `predict`. It applies the minimum surveyed elevation as experimental section zero, computes A(h) and V = Q/A, and calibrates six recursive parameter blocks with arrival-aligned endpoint supervision. 05CC007 supplies independent Q, stage and trend features with a learned lag. All segment and feature parameters train jointly on the 05CC002 endpoint. The active PostgreSQL unit-value snapshot supports arrival-aligned training, validation and testing. Effective counts and model selection are recorded in each training report. Commands, outputs, equations and limitations are documented in [ML README](courses/AIDA-2156/analysis/rdr_ml/README.md).

The integrated model dataset is [segment_training.csv](courses/AIDA-2156/data/processed/project_etl/segment_training.csv). Each row represents one trajectory and independent submodel. The first chain is three source gauges → P01 → P02 → P03 → P04 → P05 → 05CC002, which lies before P06 in the selected GIS. Lake 05CC003 elevation is an ML feature only for P03→P04, never an added discharge. Transit times use along-river distance and future submodel-predicted velocity; endpoint labels are matched to the nearest downstream observation time at predicted arrival, not to simultaneous records. Missing velocity leaves labels pending. [ETL usage and state format](courses/AIDA-2156/data/processed/project_etl/README.md) describe the feature allowlist, configurable match tolerance and optional PostgreSQL import. CSV/SQLite are populated locally. The segment snapshot has also been imported and verified in PostgreSQL database `red_deer_river`, schema `rdr_segments_989fed53a9ba`; see `courses/AIDA-2156/data/reports/postgresql_import.json`.

| Location | Contents |
|---|---|
| `API/` | Remote acquisition, one-time downloads and independent source scheduling |
| `shared-resources/src/` and `config/` | Shared storage, path resolution and configuration |
| `courses/AIDA-2154/src/`, `data/`, `outputs/` | Satellite input inspection and its data/results |
| `courses/AIDA-2156/analysis/`, `data/`, `output/` | Observation-time ETL and preliminary hydraulic calculations |
| `courses/AIDA-2362/src/`, `data/` | Survey/river processing and required spatial inputs |
| `courses/AIDA-2362/project/dickson_to_joffre.qgz` | The single final QGIS project and its local layers |
| `courses/AIDA-2362/outputs/` | Reviewed GIS presentation output |

## Experimental water-depth assumption and limitations

The local archived observations checked for the six river stations (05CB001, 05CB007, 05CC001, 05CC002, 05CC007 and 05CC011) contain no valid zero or negative water levels; each station's observed minimum is above zero. This finding applies only to the checked archives, which have different time coverage and gaps, not to each station's entire history.

For this experiment, the reported river water level will be used as the variable depth input. Any depth below the station's zero-water-level reference will be treated as an unknown constant and excluded from the calculation; only the component above that reference will be modelled. This is a simplifying experimental assumption, not a verified equivalence between gauge level and actual water depth. Sylvan Lake station 05CC003 will be handled separately as a lake-level elevation reference.

The supplied cross-section data have not been verified to identify the corresponding gauge zero on each profile. Consequently, the omitted depth and the alignment between gauge levels and section elevations remain unresolved. Predicted water depth, wetted area, velocity and potential overbank risk may therefore differ from actual conditions. Treating the omitted depth as constant does not establish that its effects on area or flow are constant. ETL now preserves the original `level_m` and supplies a separate `experimental_variable_depth_m` under this assumption. It does not calculate or validate area, velocity or risk predictions.

## Environment

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

The commands above read local archives without acquisition. Default ETL now builds the reduced Dickson–Joffre dataset in [`courses/AIDA-2156/data/processed/project_etl/`](courses/AIDA-2156/data/processed/project_etl/README.md): CSV tables plus `project.sqlite3`. It includes six river gauges, the separate Sylvan Lake reference, two linked weather stations, selected section profiles, P01–P11, candidate inflow/validation links and an index of existing satellite rasters. Historical daily values remain separate from instantaneous observations. Only necessary analytical fields, quality, missingness and provenance are retained; acquired originals are not removed. The build report is `courses/AIDA-2156/data/reports/project_etl_validation.json`.

This build reuses normalized profiles in `courses/AIDA-2156/data/processed/etl/` and the final GIS selections in `courses/AIDA-2362/project/`. If those prerequisite profiles must be rebuilt from the supplied geodatabases, explicitly run `run.py etl --legacy-full-basin` first, then `run.py etl`. The older full-basin output is a prerequisite archive, not the current analysis dataset. `--reuse-spatial` affects only the legacy command; the default scoped build always reuses the reviewed spatial selection. Image inspection separately writes `courses/AIDA-2154/outputs/archive_inspection.json`.

Open the final `.qgz` in QGIS to inspect its saved layers/layouts and export the selected layout. Its OSM basemap requires network access. The older `qgis_layers_20261011` directory contains prerequisite vector layers for reconstruction, not another retained QGIS project. Rendering/rebuilding tools can change layouts; use the supplied final project to reproduce the reviewed map.

Additional executable modules use `python -B run.py -m PACKAGE [ARGS]`. Running API acquisition is a separate operation and may need network access; satellite acquisition also needs root `.env` credentials. No credentials are supplied. Module-specific companion notes describe calls and outputs.

There are no shipped unit-test directories, migration-check tools or test reports. Runtime data checks and the source evidence required by acquisition/ETL remain. AI assisted code organization and documentation; scientific validity is not established by a successful run. Data-use terms govern redistribution. Course submission must include the permitted inputs needed for the intended reproduction route.
