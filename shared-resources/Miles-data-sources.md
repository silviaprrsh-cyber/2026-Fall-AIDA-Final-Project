# Data Sources, Permissions, APIs, and Databases — Miles Zhang

**Last Updated:** 2026-11-23  
**Related Inventories:** [`data-inventory.md`](data-inventory.md) · [`provenance-and-permissions.md`](provenance-and-permissions.md) · [`courses/AIDA-2154/docs/data-permission-selection.md`](../courses/AIDA-2154/docs/data-permission-selection.md) · [`courses/AIDA-2156/data/provenance.txt`](../courses/AIDA-2156/data/provenance.txt) · [`courses/AIDA-2362/data/layer-inventory.md`](../courses/AIDA-2362/data/layer-inventory.md)

---

## 1. Master Data Sources and Authority

| Source & Owner | Courses | Authority / Permission | Grain / Period / Preparation | Known Limitations & Packaging Rule |
|---|---|---|---|---|
| **ECCC Wateroffice Real-Time & Unit-Value Hydrometry** (Environment and Climate Change Canada) | 2156, 2154 (indirect check) | Public open government data (Open Government Licence — Canada). On **2026-11-17**, ECCC Hydrological Services responded to a datum inquiry confirming most stations operate in an **assumed datum**. | 5-minute unit-value CSVs (`2025-05-03` to `2026-11-03 UTC`), `1,350,764` records across 5 stations (`05CB007`, `05CB001`, `05CC007`, `05CC002`, `05CC003`), UTC-normalized, missing/rejected/off-grid classified. | `05CB001` & `05CC007` are 100% Provisional; `05CC003` has a 6-month winter gap; assumed datum means stage ≠ physical depth. Frozen CSVs & SHA-256 ledger bundled in 2156; ECCC emailed benchmark PDFs excluded from Git. |
| **ECCC MSC GeoMet Hourly Climate** (Station `3025484`, Red Deer Regional A) | 2156 (contextual V4 only) | Public open government API (`api.weather.gc.ca`). | Monthly JSON pulls (`2025-05-01` to `2026-11-04 UTC`, `13,208` in-window hourly rows); 1/6/24 h rain & temperature; missing/flagged rain never zero-filled. | Single nearby point gauge (not catchment average); strictly excluded from the formal AIDA 2156 EDA study. |
| **Copernicus Sentinel-2 L2A** (via Copernicus Data Space Ecosystem — CDSE) | 2154 | Open Copernicus data; retrieved with personal CDSE credentials kept strictly in Git-ignored `.env`. | `1,442` source scenes (`2016-05-02` to `2026-11-04`), cropped to native 10 m `61 × 61` pixels at 9 GIS points (`2,322` weak masks; `1,009` unique retained samples split `708/169/132`). | 10 m mixed bank/water pixels, cloud/shadow/bridge occlusion; automatic masks are weak labels, not physical ground truth. No credentials or raw bulk archives committed to Git. |
| **NRCan Hydrography / National Hydro Network** (Natural Resources Canada) | 2362 | Public open government geospatial data. | Clipped mainstem & tributary vector lines for Dickson Dam → `05CC002` (`56.0 km`), reprojected to `EPSG:3400` for metric along-river calculations. | Map polyline centerline; does not represent seasonal wetted channel width. |
| **Alberta Flood Hazard Survey Cross-Sections** (Government of Alberta — EPA) | 2362 | Provided `2026-09-30` for academic use; on **2026-11-23**, Alberta EPA confirmed in writing that the Red Deer River survey data is publicly available information and may be used in the course submission **provided EPA is credited**. | `229` active reach cross-sections (`38` surveyed, `191` planned/interpolated) clipped to Dickson → `05CC002`; preserved in portable GIS package with EPA attribution. | Original vertical datum (`CGVD28`, `EPSG:3780`) is not universally tied to ECCC assumed gauge zeros. Raw full GDBs and `Protected A` correspondence are strictly excluded from Git and ZIPs. |

---

## 2. API Documentation (No Secrets Included)

| API | Provider & Purpose | Endpoint (No Secrets) & Auth | Key Fields Retrieved | Retrieval Date / Error Handling / Reproduction |
|---|---|---|---|---|
| **ECCC MSC GeoMet Climate Hourly** | ECCC; contextual airport hourly weather for V4 experiments. | `https://api.weather.gc.ca/collections/climate-hourly/items` (anonymous public HTTP GET; no key). | `LOCAL_DATE`, `UTC_DATE`, `PRECIP_AMOUNT`, `PRECIP_AMOUNT_FLAG`, `TEMP`, `CLIMATE_IDENTIFIER`. | Retrieved monthly `2026-11-09` via `python -B run.py -m API.download_weather_history`. Long-range truncated responses were detected and rejected in favor of chunked monthly requests with raw byte hashes. |
| **ECCC Wateroffice Real-Time / Unit History** | ECCC; 5-minute river discharge (`Q`) and water level (`stage`) observations. | Official public Wateroffice / MSC GeoMet hydrometric collection endpoints (anonymous public GET; no key). | `station_id`, `timestamp_utc`, `parameter`, `value`, `grade`, `approval`. | Retrieved `2026-11-03` (`95` monthly station requests covering `2025-05-03` to `2026-11-03 UTC`). Formal AIDA 2156 EDA replays offline from the frozen CSVs in `courses/AIDA-2156/data/`; no live API call is required to reproduce results. |
| **Copernicus CDSE Sentinel-2 API** | ESA / Copernicus; 10 m multispectral reflectance (`B02`, `B03`, `B04`, `B08`) & `SCL` quality bands. | CDSE OAuth2 + Sentinel Hub / Catalog endpoints (authenticated via local Git-ignored `.env` variables `CDSE_CLIENT_ID` / `CDSE_CLIENT_SECRET`). | `B02` (Blue), `B03` (Green), `B04` (Red), `B08` (NIR), `SCL` (Scene Classification). | Retrieved `2026-11-03`–`2026-11-04`; `34` no-data responses and `1` zero-reflectance image were automatically flagged and excluded. Frozen 132-image CPU replay and 9-site blind manual scoring run 100% offline with zero credentials. |

---

## 3. Database Documentation (No Secrets Included)

| Engine & Version | Database / Schema | Tables, Views & Keys | Setup, Checks & Security Boundary |
|---|---|---|---|
| **PostgreSQL 18.6** (`psycopg 3.3.7`) | `red_deer_river` — Hydrological schemas `rdr_unit_0f36881e431d0966` & `rdr_segments_989fed53a9ba` | `v_train`, `v_validation`, `v_test` (chronological 60/20/20 & 80/20 candidate partitions), `v_input_history`, `v_lake_history`, `v_endpoint_observations`. Keyed by `(station_id, timestamp_utc, parameter)`. | Used by contextual V4 ML experiments only — **not required** for the formal AIDA 2156 EDA replay. Reproducible import: `python -B run.py -m eda_tools.import_unit_postgres`. Verified in `courses/AIDA-2156/data/reports/postgresql_unit_import.json`. |
| **PostgreSQL 18.6** (`psycopg 3.3.7`) | `red_deer_river` — CV engineering schema `cv_pipeline` | Tables: `scenes`, `samples`, `masks`, `runs`, `audit` (SQL trigger-logged; `6,094` committed events). Views: `v_raw_images`, `v_training_pairs`. Raster files stay on disk referenced by relative path + SHA-256. | Additive engineering workflow (`courses/AIDA-2154/docs/postgres-cv-pipeline.md`). Reproducible commands: `python -B run.py cv init/register/masks/train/verify`. **Not required** for the frozen 132-image CPU replay or 9-site blind manual audit. |
| **SQLite 3** (Python stdlib) | Local scoped ETL snapshot (`courses/AIDA-2156/data/processed/project_etl/`) | Scoped tables for 4 river gauges, 1 lake reference, 1 weather station, 229 sections, 5 targets, and 775 satellite index entries. | Rebuilt via `python -B run.py etl`. Kept separate from frozen formal EDA inputs. |

**Security rule (verified across repository):** Zero passwords, API tokens, private host strings, personal emails, or `Protected A` correspondence are committed to Git or bundled into D2L ZIPs. Local credentials follow the blank template in [`.env.example`](../.env.example).
