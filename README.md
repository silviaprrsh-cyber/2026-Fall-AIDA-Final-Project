# Red Deer River near-real-time monitoring and potential overbank-risk project

The final goal is to combine mainstem gauges, available tributary inflows, river-network relationships and surveyed sections to continually estimate discharge Q, water level, travel time and potential overbank risk at key sections. Historical analysis supports development, calibration and validation; existing code does not establish verified basin-wide conditions.

## Active development directory — updated 2026-11-05

Continue development from [movetest/README.md](movetest/README.md). Its active reach is **Dickson Dam outlet → 05CC002**, retaining **P01–P05**. The current [QGIS project](movetest/courses/AIDA-2362/project/dickson_to_joffre.qgz) keeps its legacy filename. Root-level code, configuration, data and the older Joffre map remain the original implementation/archive; the commands below describe that root implementation and do not automatically use the reduced movetest configuration. See the movetest README for current ETL, PostgreSQL, ML and satellite status.

The archived root implementation covers the reach from the Gleniffer Lake outlet / Dickson Dam downstream to the **Joffre Bridge / Highway 11**, approximately 96.3 km along the selected mapped centerline. It includes the Blindman River input-to-mouth segment and stops at Joffre Bridge. Tributaries are retained from their nearest usable same-river station to their confluence with this reach. Available river geometry remains visible where no usable station exists.

## Stage deliverables

Current reduced-scope map (2026-11-08): [PDF](movetest/courses/AIDA-2362/outputs/Overhead%20view.pdf) ? [PNG](movetest/courses/AIDA-2362/project/map_overview.png). Endpoint: 05CC002; targets: P01?P05. The root Joffre PDF listed below remains historical.

Reviewed and confirmed stage deliverables for presentation or submission are stored in the root [`outputs/`](outputs/) folder. This folder is not excluded from Git.

- **GIS mapping stage:** [Monitoring stations and prediction targets - Dickson Dam to Joffre Bridge](outputs/Overhead%20view.pdf). This map presents the selected reach, monitoring locations, surveyed cross-sections and requested prediction locations; it does not represent completed hydraulic predictions or model validation.

Only selected stage deliverables belong here. Working QGIS projects and derived datasets remain in `data/processed/`, original data in `data/sources/`, and validation records in `data/reports/`. Temporary exports, intermediate results, logs and caches do not belong in `outputs/`.

## Archived root implementation and data-processing status

Historical tributary data remain in [the daily archive](data/processed/tributary_history_20261012/README.md): 12 river stations and 3 lake-level references from the 2026-10-12 download. The 2026-10-13 map shows 6 blue stations with observations since 2026-07-13 and 2 yellow historical/reference stations, each ID once. Sylvan Creek 05CC004 is removed from display and replaced by Sylvan Lake 05CC003 as a yellow lake-level reference; recent lake availability is unverified. A separate red layer contains **11 prediction targets**, ordered upstream to downstream, including the footbridge beside Discovery Canyon. See the [map and point inventory](data/processed/qgis_dickson_joffre_20261012/README.md). Red points are locations for future estimation, with no calculated discharge, level or risk. Source archives and live acquisition configuration remain unchanged.

The 2026-10-12 snapshot selected **05CB007, 05CC002, 05CB001, 05CC007, 05CC011 and 05CC001**, with precipitation stations **3025484 and 3023722**. Dickson tunnel outlet discharge is not confirmed to include every dam release path. Do not add serial gauge flows. Configuration retains the broader catalogue with other stations disabled; `config/active_scope.json` records the active selection, and configuration rebuilding respects this selection.

Open [the archived Joffre QGIS project](data/processed/qgis_dickson_joffre_20261012/dickson_to_joffre.qgz), or view [the map preview](data/processed/qgis_dickson_joffre_20261012/map_overview.png). It contains 6 recent water stations, 2 historical/lake references, 11 prediction targets, 2 precipitation stations and 366 section lines with survey points, separated by source, over OpenStreetMap. Green shading is a schematic 2 km corridor showing existing weather associations, not official coverage or a catchment. See [scope verification](data/processed/qgis_dickson_joffre_20261012/scope_validation.json) for the initial selection and routing limitations, and the map README for current display counts. The pre-existing full-basin map and original archives remain available; the superseded 67 Street endpoint draft has been removed. These local data links require the corresponding local files.

The user has received the government reply, data-use permission and download links. Four survey packages are saved. The ETL snapshot dated 2026-09-30 UTC contains 1,607 section lines, 91,967 points and 1,596 candidate profiles; the 2026-10-08 migration checks confirmed unchanged normalized data and section identifiers. All section risks in that snapshot are indeterminate pending verified datums, gauge-to-section transfers and effective bank elevations. These are archived results, not a fresh online availability check.

Completed migration and obsolete document-editing utilities were deleted. `scripts/` contains reusable configuration, network, ETL, report and QGIS tools, including `build_scoped_qgis.py` and `render_qgis_project.py`. One-shot API acquisition scripts remain. `rdr/` provides local cataloguing, spatial associations, precipitation ETL, hydraulics and storage utilities.

As of 2026-10-10, `watch` subscribes to anonymous Datamart AMQPS file notifications before hydrometric collection. After an optional initial snapshot, water retrieval requires a notification (or a pending failed retrieval) and respects each source interval. GeoMet weather sources retain independent schedules. No directory listing is polled. See the [MSC usage policy](https://eccc-msc.github.io/open-data/usage-policy/readme_en/). Acquisition and ETL still run separately.

English Markdown keeps the original filename; Chinese copies use `*CN.md`, such as `READMECN.md`, and remain local through `.gitignore`. Documentation links use the corresponding language.

See [AI use declaration](AI_DECLARATION.md) for the disclosed assistance with documentation, code and technical design. Code comments and docstrings use English only; Chinese report content is retained. `.gitignore` also covers credentials, source and derived data, runtime files, the English Scope Proposal DOCX/PDF and the English detailed project DOCX, as well as the existing Chinese document patterns. It does not exclude every Word or PDF file automatically.

A dedicated Python environment, `.venv`, has been created in this folder. Public hydrometric and weather endpoints use anonymous HTTPS; satellite services use credentials from the root `.env`.
The project includes data interfaces, one-time validation, static downloads, stoppable independent source scheduling, survey normalization, spatial links, observation-time ETL and basic hydraulic calculation code. See [ETL and calculations](ETL_REFERENCE.md) for current results and validation limits.
**The 2026-10-08 migration verification records that continuous network collection was not started; this README is not a live process-status monitor. Complete numerical riverbed data and some tributary locations still have public-data gaps.**

Read the [Initial acquisition and coverage report](data/reports/coverage_report.md), which distinguishes acquired, stale, historical, provisional and missing material.
Endpoint addresses, fields, precipitation accumulation windows and scheduling evidence are described in the [API reference](API_REFERENCE.md).

## Current layout

All remote acquisition code lives in [API](API/README.md). `rdr/` contains local storage, spatial processing, ETL and hydraulics; `scripts/` contains local processing and document tools. Original data are separated by source under `data/sources/`; see [data/README.md](data/README.md). `.venv`, `.env` and `config/` remain in the root.

Use `python -m API` as the main entry point; `python -m rdr` remains a compatibility forwarder. The root station timestamp CSV moved to `data/processed/station_timestamps/`. Original bytes and provenance remain unchanged; trace old paths through `data/reports/layout_migration/manifest.json`.

## Usage

For one latest sample of the active scope only, run `.\.venv\Scripts\python.exe -m API.snapshot_scope`. It fetches at most 48 recent records per unique water/weather source, saves source-separated originals and a timestamped report under `data/reports/scope_snapshot/`, and exits. It does not run ETL or automatically refresh a saved QGIS snapshot. Observation timestamps are not actual station transmission timestamps.

Run the appropriate command in PowerShell from the project folder; environment activation is not required. `status` displays saved configuration, not current station availability. Start `watch` only when continuous acquisition is intended. `--dry-run` makes no network requests, but runs until stopped or its optional deadline; it prints progress and writes run state.

For a three-hour run, use `python -m API watch --duration-seconds 10800`. Terminal `stop` and Ctrl+C remain available. Background launches use `--detached`, which requires a finite duration; stop such a run with `python -m API stop`. At the deadline, new requests stop and in-flight requests finish or time out. `data/state/active_run.json` records the PID, UTC deadline, counters and stop-control path; `last_run.json` records completion. Keep the computer running and online.

```powershell
# Show saved station configuration and intervals without network access.
.\.venv\Scripts\python.exe -m API status

# Start continuous collection. Each water or weather source uses its own publication interval.
.\.venv\Scripts\python.exe -m API watch

# Test scheduling and stop without retrieving observations.
.\.venv\Scripts\python.exe -m API watch --dry-run

# Run one specified monitoring point.
.\.venv\Scripts\python.exe -m API watch --station 05CC002
```

Enter `stop` and press Enter while the program runs, or press `Ctrl+C`.
No new requests start after stopping; in-flight requests finish or time out, and saved raw data remain available.
The program installs no scheduled task, background service or startup entry.

## Data locations

- `data/sources/<source>/raw/discovery/`: initial responses containing API metadata, station indexes and official documentation.
- `data/sources/<source>/raw/validation/`: initial station-level hydrometric and weather responses, plus historical samples.
- `data/sources/<source>/static/`: one-time downloads of channel GIS, NHN ZIP files and survey, cross-section or hydraulic PDFs.
- `data/processed/station_master.csv`: 102 public station records in the catalogue checked during the 2026-10-08 migration; validation status is archived.
- `data/processed/tributary_outlets.csv`: named confluences, nearest same-river gauge matches, methods and uncertainty.
- `data/processed/weather_links.csv`: precipitation stations associated with each hydrometric point and their distances.
- `data/processed/observations.sqlite3`: continuous-mode observations, deduplicated by source, station and record ID, retaining revised values.
- `data/sources/<source>/raw/live/`: original response bytes from continuous mode, created when that mode is first started.
- `data/reports/`: schema validation, coverage, gaps and stop-test results.
- `data/logs/requests.jsonl`: source URLs, retrieval times, checksums and failures.
- `config/stations.json`: enabled status, sources, publication intervals and evidence for each station.

## Frequency and coverage

Continuous hydrometric collection uses Datamart CSV files with a documented hourly update schedule. The GeoMet hydrometric JSON interface has also been validated station by station.
SWOB weather publication intervals are estimated from processing timestamps in the initial response; **they are not official fixed station-specific publication commitments**.
Observation intervals and publication intervals are recorded separately; observation-time differences are not presented as official publication frequencies.
Each water or weather source uses its own publication interval. Shared weather sources have one deduplicated schedule. Calculation windows use each hydrometric station's interval and observation timestamps. See [ETL and calculations](ETL_REFERENCE.md) for the normalized surveys, spatial links, rainfall aggregation and screening calculations.

Gauge selection preferably uses distance along the same river network. Where connectivity cannot be verified, straight-line distance is used provisionally and explicitly labelled as such.
A same-name gauge more than 500 m from all mapped same-name river geometry is not selected automatically; candidates and offsets remain in the gap report.
Existing saved matches do not automatically replace an inactive nearest gauge with a farther station. Revisions require verified same-river connectivity and availability. Some archived points have weather but only historical hydrometry.
Ungauged tributaries, unresolved topology and missing original bathymetry, cross-sections or model files remain documented in the report.

## Rebuilding and adding libraries

The following sequence rebuilds acquisition/catalogue products; it does not run survey ETL or an automatic forecasting workflow. API scripts can access the network and write archives; local scripts overwrite derived products or configuration. Run only the steps needed for the task. Reused cached responses are historical evidence, not a fresh online validation. `build_config.py` evaluates freshness against the current clock and can remove water sources older than 48 hours; back up manual configuration and review evidence before rebuilding.

```powershell
# Create the environment only when it is absent.
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt

# Rebuild when needed; matching successful responses at the same archive path may be reused.
.\.venv\Scripts\python.exe API/discover.py
.\.venv\Scripts\python.exe API/discover_details.py
.\.venv\Scripts\python.exe API/download_static.py
.\.venv\Scripts\python.exe API/download_network.py
.\.venv\Scripts\python.exe API/download_nhn.py
.\.venv\Scripts\python.exe API/validate_once.py
.\.venv\Scripts\python.exe API/check_partner_precipitation.py
.\.venv\Scripts\python.exe scripts/build_network.py
.\.venv\Scripts\python.exe scripts/refine_outlets.py
.\.venv\Scripts\python.exe scripts/build_config.py
.\.venv\Scripts\python.exe scripts/inspect_reports.py
.\.venv\Scripts\python.exe scripts/write_report.py

# Replace PACKAGE_NAME with the actual library name.
.\.venv\Scripts\python.exe -m pip install PACKAGE_NAME

# Run local tests.
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`requirements.txt` specifies direct dependency ranges; `requirements.lock.txt` records exact versions from the validated environment.
When adding libraries, update both dependency files to reflect the validated project environment.
Configuration-generation scripts rebuild `config/stations.json`; back up manual edits before rebuilding.
Public API responses have `.meta.json` sidecars containing provenance and SHA-256; satellite runs and manual survey packages use their respective manifests or inventories. Raw material is separate from code; source data and derived datasets under `data` are excluded from Git.

Run survey normalization and observation-time ETL separately with `.\.venv\Scripts\python.exe scripts/run_etl.py`. Use `--reuse-spatial` only when the survey inputs and spatial processing logic are unchanged. ETL runs offline and replaces the derived snapshot; it is not automatically triggered by `watch`. Incomplete precipitation windows retain partial data and coverage, with whole-window totals and mean intensities set to `null`. See [ETL and calculations](ETL_REFERENCE.md).

## One-shot satellite image validation

This root-level satellite validation belongs to the archived Dickson outlet to Joffre Bridge implementation. The command below validates CDSE STAC, OAuth and the Sentinel Hub Process API using only a 5.12 × 5.12 km test area around `05CC002`; it does not establish imagery coverage of the whole selected reach or start scheduled collection or CV training.

Credentials are read from the project-root `.env`. Supported keys include `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET` and the existing `Client_ID` / `Client_secret`. Environment variables override file values with the same name. Credentials and access tokens are never written to reports.

The script searches the preceding 90 days for Sentinel-2 L2A products with tile cloud cover at most 20%, then selects the newest fully covering scene from the returned results. Processing uses that UTC day, checks that source-tile sensing times differ by no more than five minutes, and retains product and tile timestamps separately. Valid pixels, coordinates, bands and PNG alpha are checked after download; empty imagery fails validation.

Outputs are saved under `data/sources/copernicus_sentinel2/raw/satellite/<run_id>/`: original API responses, RGB PNG, four-band reflectance GeoTIFF (B04/B03/B02/B08), SCL/dataMask quality GeoTIFF, source-tile metadata and per-file SHA-256 hashes. Satellite provenance and checksums use a run manifest. The latest result is `data/reports/satellite_validation_once.json`. SCL is a provider classification resampled to the output grid, not this project's trained CV segmentation.

```powershell
.\.venv\Scripts\python.exe API/validate_satellite_once.py
```

Official documentation: [CDSE authentication](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html), [STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), [Process API examples](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S2L2A.html).

## Refresh coverage documentation only

Use `.\.venv\Scripts\python.exe scripts/write_report.py --docs-only` to generate separate English and Chinese Markdown without rebuilding CSV indexes or accessing the network.


## Project Change History

### 2026-10-13 Scope reduction based on data coverage

The active project area is reduced from the approximately 724 km Red Deer River mainstem and its basin to the reach from the Gleniffer Lake outlet downstream of Dickson Dam to Joffre Bridge on Highway 11, approximately 96.3 km along the selected river network. Relevant tributary inflows entering this reach remain part of the analysis.

The original full-basin data are incomplete. Available, relatively reliable observations cannot support every relevant tributary inflow point. Filling these widespread gaps would require extensive estimation, increasing accumulated uncertainty and weakening model reliability. The project therefore focuses subsequent development on this reach, where hydrometric observations, tributary information and surveyed cross-sections are relatively more complete.

The goal remains a near-real-time monitoring system that uses available mainstem and tributary observations, river-network relationships and surveyed sections to estimate discharge, water level, travel time and potential overbank risk at selected locations. The smaller scope does not establish complete coverage or validated predictions; remaining gaps, assumptions and uncertainty must still be recorded and assessed.

Earlier text is retained as the original project record. This entry defines the revised geographic scope for subsequent work and supersedes earlier full-basin scope statements. It records a scope decision, not completion or validation of the model.

## Project modification history — 2026-11-04 (verified 2026-11-05)

The active movetest reach now ends at Red Deer station 05CC002. Retain P01–P05; remove P06–P11 and downstream Blindman/Waskasoo map inputs. The selected project data provide no comparable downstream observation constraint to validate the continuation to P11. This reduction limits unsupported extrapolation; it does not establish accuracy at retained targets. The filename `dickson_to_joffre.qgz` is retained for compatibility, but its layers and displayed endpoint now use 05CC002.

Source archives, previous model results and satellite acquisitions are retained. Existing `Overhead view.pdf`, `map_overview.png` and earlier validation reports are historical Joffre snapshots, not updated exports. Current GIS checks are `movetest/courses/AIDA-2362/data/reports/scope_05CC002.json` and `movetest/courses/AIDA-2362/data/reports/qgis_scope_05CC002.json`. The model already ends at 05CC002: its M06 link from P05 to the validation station remains; M06 is not prediction point P06. This map update does not retrain the model or replace PostgreSQL snapshots.

Per-file explanatory companions (for example `client.py.md`, `active_scope.json.md` and their Chinese copies) remain local and are ignored through `*.*.md` and `*CN.md`. Previously tracked companions have been removed from the Git index, not from local storage, except companions archived with retired tools. README and standalone English project documents remain eligible for Git tracking.
