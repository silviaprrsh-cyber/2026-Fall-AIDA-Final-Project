# Data sources and formats

[中文](DATA_SOURCESCN.md) · [Data pipeline](DATA_PIPELINE.md) · [Documentation index](README.md)

> **Course research only. Do not use V4 for real floods, warnings or response decisions.** See [Model experiments](MODEL_EXPERIMENTS.md) for the final test and release decision.

## 1. River observations

The Water Survey of Canada (WSC), within Environment and Climate Change Canada (ECCC), is the authority for the hydrometric measurements used here. The local Water Office archive was collected from the [unit-value CSV endpoint](https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline), not from the daily summaries. The working grain after deduplication is one station, parameter and observation time. One unit-value bin nominally spans five minutes; missing bins were not fabricated in the archived data.

| Source and role | WSC ID | Discharge observations in the audited archive | Last discharge observation (UTC) |
|---|---|---:|---|
| Dickson Dam Tunnel Outlet: regulated upstream flow | 05CB007 | 156,057 | 2026-11-11 02:25 |
| Little Red Deer River near the Mouth: tributary flow | 05CB001 | 157,682 | 2026-11-03 06:25 |
| Medicine River near Eckville: independent tributary flow | 05CC007 | 156,388 | 2026-11-03 06:20 |
| Red Deer River at Red Deer: terminal flow for the arrival grid and event audit, not a network prediction feature | 05CC002 | 158,574 | 2026-11-11 02:50 |

All four discharge series in this audit start at 2025-05-03 07:05 UTC. These are **raw station-level observation counts**, not the V4 training or test counts. The source summary's longest between-observation gaps in the corresponding order are 141h15, 2h15, 30h55 and 1h. The reported instantaneous gauge stage at 05CC002, a separate measurement from its discharge, provides the label after a datum adjustment. Upstream gauge-stage series are not V4 input features.

| Unit-value CSV field | Meaning |
|---|---|
| `ID`, `Date` | WSC station identifier; observation timestamp stored in UTC with a time-zone marker. The observation clock is not the clock of first publication. |
| `Parameter/Paramètre`, `Value/Valeur` | 47 = discharge (m³/s); 46 = reported gauge stage (m relative to that gauge's local datum). A blank value does not mean measured zero. |
| `Qualifier`, `Symbol`, `Approval`, `Grade`, `Qualifiers` | Provider quality and status information; retain with the raw response. Do not infer that every value is final or unqualified. |
| CSV sidecar and manifest | Query window, archive receipt, HTTP/checksum evidence and attribution. These are retrieval receipts, not per-observation availability records. |

Local evidence: `data/sources/eccc_wateroffice/raw/unit_values/{20261103T070414Z,20261111T030808Z}/<station>/` (CSV and companion `.csv.meta.json`), and `data/processed/wave_time_alignment_full_history_v2_20261117/{source_manifest.csv,summary.json}` for the inventory and coverage audit. The station configuration is `shared-resources/config/stations.json` at repository level. Read [the course provenance notes](../data/provenance.md) and [the data dictionary](../data/data-dictionary.md) for companion normalized inputs and packaging restrictions.

## 2. Weather observations

Only **Red Deer Regional A**, climate station **3025484**, supplies V4 precipitation. It is a single airport point record from the ECCC [GeoMet climate-hourly collection](https://api.weather.gc.ca/collections/climate-hourly), not three rain gauges, basin-average rain, radar rain or a weather forecast. Each routing branch references that record on its own matched source clock. The three branch histories are separate neural inputs, not added together as precipitation.

| Field in monthly GeoJSON | Role and units |
|---|---|
| `CLIMATE_IDENTIFIER`, `ID` | Climate station ID and provider feature ID; checked against the requested records. |
| `UTC_DATE` | Hourly observation time in UTC; do not reinterpret the provider's local-standard-clock fields as Red Deer civil daylight time. |
| `PRECIP_AMOUNT`, `PRECIP_AMOUNT_FLAG` | Hourly precipitation in mm and its provider flag. The V4 parser keeps finite, nonnegative, unflagged values. Unknown/flagged remains null before routing's explicitly audited zero fill. |
| `TEMP`, `RELATIVE_HUMIDITY` | Air temperature (°C) and relative humidity (%); available for later ablations but **not** V4 model inputs, nor a direct measure of evapotranspiration. |

The two archived monthly manifests are under `data/sources/eccc_climate_hourly/raw/`: `20250501_20261104_3025484_monthly` (13,334 source rows) and `20260601_20261111_3025484_monthly` (3,880 source rows). Counts overlap and are not additive; on an overlapping hour the newer documented archive receipt wins, including a null or flagged result. Local sources retain JSON pages, metadata sidecars and a manifest. See [the staging implementation](../analysis/eda_tools/stage_forward_weather.py), [the provider parser](../analysis/rdr_ml/weather.py) and `station_metadata_20261111/station.json` under the same raw directory.

## 3. Spatial and datum evidence

The surveyed cross sections and selected GIS reach come from the shared AIDA 2362 project inputs; check the [course data README](../data/README.md) and [the PostgreSQL importer](../analysis/eda_tools/import_unit_postgres.py) for the references and datum controls. The V4 chain maps **P01 → P02 → P03 → P04 → P05 → 05CC002**; surveyed geometry informs segment definitions and the terminal bed proxy, not independently measured intermediate model states. The Red Deer bed proxy uses a 2017 point near the gauge, not a contemporaneous survey of the exact gauge position. The target is a **stage-derived depth proxy**. See [Data pipeline](DATA_PIPELINE.md) for the calculation. Satellite imagery and Sylvan Lake occur in other project work but are not among V4's twelve variable inputs.

The geometry archive is the Alberta Flood Survey geodatabase: `courses/AIDA-2362/data/sources/alberta_flood_surveys/manual/Red Deer/SURVEY_DATA.gdb` with supporting reach material in `Red Deer County and Markerville/A_FieldSurvey.gdb`. The terminal point is `Survey_Points` feature 15173 (MD201709230317, R38), originally 849.522 m in CGVD28. The model preparation converted that elevation to 849.5955450123237 m in CGVD2013_e2010 before combining it with the WSC gauge adjustment. Local WSC datum pages and metadata are under `data/sources/eccc_wateroffice/raw/datums/`. The checkpoint also carries fixed per-block distances in metres; it does not ingest raster imagery as data.

## 4. Availability and traceability

Data acquisition, archived bytes, database staging and the model-ready view are different layers. A source receipt or checksum establishes what was archived, not what a forecaster knew at a past time. A public endpoint does not by itself authorize redistributing every underlying archive, local survey or credential-bearing configuration. Use permitted archives, retain attribution and source flags, and keep machine-specific secrets and restricted sources out of the submission.

## Relation to the current package

The formulas, units and counts above refer to the frozen training archive. [See the documentation index for release files and guides.](README.md) Live mode separately reads instantaneous ECCC GeoMet discharge and airport hourly precipitation, keeping the observation and receipt times. It does not substitute daily means for instantaneous flow.

## Current final EDA evidence

The frozen V4 archive described above is distinct from the formal observational EDA. The latter reads only five existing Water Office station-observation CSVs from `20261103T070414Z` (or the field-minimized course-package copies), without model predictions, rain or GIS inputs. An independent offline raw audit uses the two Water Office snapshots, four monthly climate snapshots, Sentinel-2 metadata/pixel samples and Alberta survey material to characterize source coverage. See [exact inputs and checksums](../data/provenance.md) and [scope and release restrictions](../governance-and-release.md).
