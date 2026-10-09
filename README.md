# Red Deer River near-real-time monitoring and potential overbank-risk project

## Current status and next data-processing work

The final goal is to combine mainstem gauges, available tributary inflows, river-network relationships and surveyed sections to continually estimate discharge Q, water level, travel time and potential overbank risk at key sections. Historical analysis supports development, calibration and validation; existing code does not establish verified basin-wide conditions.

The four selected mainstem inputs are 05CA009, 05CC002, 05CE001 and 05CK004. Incorporate additional valid mainstem inputs according to coordinates, connectivity, flow direction, river distance and upstream-to-downstream order. Do not simply sum serial gauge flows.

The user has received the government reply, data-use permission and download links. Four survey packages are saved. The ETL snapshot dated 2026-09-30 UTC contains 1,607 section lines, 91,967 points and 1,596 candidate profiles; the 2026-10-08 migration checks confirmed unchanged normalized data and section identifiers. All section risks in that snapshot are indeterminate pending verified datums, gauge-to-section transfers and effective bank elevations. These are archived results, not a fresh online availability check.

Eight completed migration and old document-editing utilities were deleted. `scripts/` now retains `build_config.py`, `build_network.py`, `refine_outlets.py`, `run_etl.py`, `inspect_reports.py` and `write_report.py`. All one-shot API acquisition scripts remain. `rdr/` provides local cataloguing, spatial associations, precipitation ETL, hydraulics and storage utilities.

Acquisition still uses HTTP retrieval; AMQPS notifications have not been integrated. Before ongoing Datamart retrieval, address AMQPS notifications and downloads under the [MSC usage policy](https://eccc-msc.github.io/open-data/usage-policy/readme_en/); do not poll directory listings for new files. `watch` and ETL run separately, and this update starts no acquisition.

English Markdown keeps the original filename; Chinese copies use `*CN.md`, such as `READMECN.md`, and remain local through `.gitignore`. Documentation links use the corresponding language.

See [AI use declaration](AI_DECLARATION.md) for the disclosed assistance with documentation, code and technical design. Code comments and docstrings use English only; Chinese report content is retained. `.gitignore` also covers credentials, source and derived data, runtime files, the English Scope Proposal DOCX/PDF and the English detailed project DOCX, as well as the existing Chinese document patterns. It does not exclude every Word or PDF file automatically.

A dedicated Python environment, `.venv`, has been created in this folder. Public hydrometric and weather endpoints use anonymous HTTPS; satellite services use credentials from the root `.env`.
The project includes data interfaces, one-time validation, static downloads, stoppable independent source scheduling, survey normalization, spatial links, observation-time ETL and basic hydraulic calculation code. See [ETL and calculations](ETL_REFERENCE.md) for current results and validation limits.
**The 2026-10-08 migration verification records that continuous network collection was not started; this README is not a live process-status monitor. Complete numerical riverbed data and some tributary locations still have public-data gaps.**

Read the [Initial acquisition and coverage report](data/reports/coverage_report.md), which distinguishes acquired, stale, historical, provisional and missing material.
Endpoint addresses, fields, precipitation accumulation windows and scheduling evidence are described in the [API reference](API_REFERENCE.md).

## Current layout

All remote acquisition code lives in [API](API/README.md). `rdr/` contains local storage, spatial processing, ETL and hydraulics; `scripts/` contains local processing and document tools. Original data are separated into 12 source directories under `data/sources/`; see [data/README.md](data/README.md). `.venv`, `.env` and `config/` remain in the root.

Use `python -m API` as the main entry point; `python -m rdr` remains a compatibility forwarder. The root station timestamp CSV moved to `data/processed/station_timestamps/`. Original bytes and provenance remain unchanged; trace old paths through `data/reports/layout_migration/manifest.json`.

## Usage

Run the appropriate command in PowerShell from the project folder; environment activation is not required. `status` displays saved configuration, not current station availability. Start `watch` only when continuous acquisition is intended and the Datamart requirement above has been addressed. `--dry-run` makes no network requests, but runs until stopped, prints progress and writes `data/state/last_run.json` on exit.

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

The original full-basin project scope is retained. The command below validates CDSE STAC, OAuth and the Sentinel Hub Process API using only a 5.12 × 5.12 km test area around `05CC002`; it does not start scheduled collection or CV training.

Credentials are read from the project-root `.env`. Supported keys include `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET` and the existing `Client_ID` / `Client_secret`. Environment variables override file values with the same name. Credentials and access tokens are never written to reports.

The script searches the preceding 90 days for Sentinel-2 L2A products with tile cloud cover at most 20%, then selects the newest fully covering scene from the returned results. Processing uses that UTC day, checks that source-tile sensing times differ by no more than five minutes, and retains product and tile timestamps separately. Valid pixels, coordinates, bands and PNG alpha are checked after download; empty imagery fails validation.

Outputs are saved under `data/sources/copernicus_sentinel2/raw/satellite/<run_id>/`: original API responses, RGB PNG, four-band reflectance GeoTIFF (B04/B03/B02/B08), SCL/dataMask quality GeoTIFF, source-tile metadata and per-file SHA-256 hashes. Satellite provenance and checksums use a run manifest. The latest result is `data/reports/satellite_validation_once.json`. SCL is a provider classification resampled to the output grid, not this project's trained CV segmentation.

```powershell
.\.venv\Scripts\python.exe API/validate_satellite_once.py
```

Official documentation: [CDSE authentication](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html), [STAC](https://documentation.dataspace.copernicus.eu/APIs/STAC.html), [Process API examples](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Process/Examples/S2L2A.html).

## Refresh coverage documentation only

Use `.\.venv\Scripts\python.exe scripts/write_report.py --docs-only` to generate separate English and Chinese Markdown without rebuilding CSV indexes or accessing the network.
#   2 0 2 6 - F a l l - A I D A - F i n a l - P r o j e c t  
 