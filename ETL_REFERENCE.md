# Surveys, ETL and calculations (stages 1–4)

Statistics come from the archived trial in `data/reports/etl_validation.json` dated 2026-09-30T05:52:25.088102+00:00. The 2026-10-08 migration checks confirmed unchanged water/precipitation content and section identifiers. This update performs no online query or hydraulic calibration. The user has confirmed government permission and download links.

The original scope of the approximately 724 km mainstem and the entire Red Deer River basin is retained. These implementation and trial results use archived observations and four manual survey packages; they do not establish complete surveyed basin coverage. Original ZIP files, geodatabases and API responses remain under `data`.

## Current results

| Item | Result |
|---|---|
| Station catalogue | 102 stations; 42 monitoring points enabled by default |
| Acquisition configuration | 26 water sources and 8 shared weather sources, giving 34 independent schedules |
| Four survey packages | 1,607 section lines, 91,967 points and 1,596 candidate elevation profiles |
| Section–gauge links | 1,143 same-river network candidates, 310 provisional same-river straight-distance links, 154 without a same-river gauge |
| Official datum pages | 45 stations with published conversions; 57 without; not all 45 provide CGVD28 conversions |
| Normalized observations | 31,438 water records and 25,086 precipitation interval records |
| Trial calculation windows | 670 complete, 1,964 without usable complete precipitation intervals; another 59 stations lack instantaneous water or a calculation interval |
| Historical geometry | 128 previews using survey water-surface elevations |
| Actual risk output | All 1,607 sections are `indeterminate` pending verified inputs |

Counts describe this archived sample, not current online availability. Only 42 points are enabled for acquisition; offline ETL examines all 102 catalogue stations, including archived observations at disabled stations. Continuous acquisition had not started when this snapshot was built. The separately authorized three-hour run on 2026-10-10 writes new raw batches and the observation store; it does not refresh these ETL results. Offline scheduling and terminal `stop` have been exercised.

## Time and precipitation rules

API loading and ETL share `station_calculation_interval()`: explicit positive finite `calculation_interval_seconds` values are preserved; missing or `null` values fall back to the hydrometric source cadence. Invalid explicit values raise an error rather than silently reverting to a source interval. Acquisition schedules remain independent of this analysis setting.

1. Each water or weather source uses its own `publication_interval_seconds`; shared weather sources are fetched once. The current water product interval is 3,600 seconds. Weather interval estimates remain in source configuration and are not official fixed publication commitments.
2. Each water station has its own `calculation_interval_seconds`. This offline snapshot anchors windows at that station's latest water observation and steps backward by its interval. Calculation requires a water record at the window end. Level and discharge are endpoint observations, not window means. The endpoint may change in a new snapshot; overlapping rainfall totals across snapshots must not be summed again.
3. Precipitation enters a window according to its measurement period, not fetch time. Both `precipitation_total_mm` and `mean_precipitation_intensity_mm_h` are retained. Four quarter-hour depths of 1, 2, 0 and 3 mm produce 6 mm total and 6 mm/h mean intensity. Interval intensities are integrated over their durations and divided by the target duration.
4. A past-hour amount updated every minute is an overlapping rolling accumulation. Select a nonoverlapping set covering the target; an exactly matching hourly total is used once. Do not sum 60 rolling values or prorate a cumulative amount crossing a target boundary.
5. Missing is not zero. Totals and mean intensities require full coverage; otherwise they are `null`, with coverage, covered duration and partial amount retained separately. For a 20:10–21:10 target with only a 20:00–21:00 accumulation, preserve the gap instead of assuming uniform rain. More frequent API requests cannot fix incompatible source measurement periods.
6. Revisions are ordered using available provider-processing/local-receipt timestamps; processing time is not assumed to be actual publication time. Newer revisions supersede duplicates, including invalid revisions. Failed quality checks, unquantified traces and incomplete amounts are excluded. Raw paths, record identifiers, fields, periods and quality flags remain traceable. `derived_complete` means a complete provider-derived accumulation, not a passed individual QA test.
7. This is retrospective ETL. Later downloads do not prove observations were known at a historical forecast time. The aggregation function supports an `as_of` receipt-time cutoff; unknown receipt times cannot support strict historical replay.

## Spatial links, datums and calculations

Section keys use `study:river:source_section_id`; points retain source database, layer, FID and original attributes. Red Deer and Upper Red Deer use source section identifiers. Drumheller and County planned lines without equivalent identifiers use a spatial candidate within 20 m only when clearly closer than the alternative; these remain unverified. Profiles are ordered by projected section distance. Points sharing a rounded 0.01 m offset use median elevation, with duplicate counts and elevation spread retained. Insufficient points, mixed survey years, offsets from section lines and profile gaps remain auditable.

Section–gauge matching prefers the same named river network; disconnected cases are labelled straight-distance candidates. Direction requires known NHN flow direction. Confluence links are also candidates: nearest does not establish the same hydraulic location. Weather links are nearby point observations, not catchment-average rainfall.

The four surveys are registered as CGVD28 according to accompanying reports. Gauge levels are generally relative to station zero. Conversion requires a documented gauge zero, compatible vertical datum and valid period. CGVD2013 offsets cannot be directly applied to CGVD28 profiles. A documented datum conversion still does not establish the gauge-to-section water-surface transfer, representative discharge or bank crests.

`rdr/hydraulics.py` implements wet area and perimeter, surface width, hydraulic radius, `V=Q/A`, minimum two-bank freeboard, trapezoidal reach storage, `L/V` travel time, explicitly lag-aligned contributions and local Q–H interpolation. Partial wet segments use triangular integration. Open profile edges or disconnected pools without a verified main-channel seed suppress reliable mean velocity. `L/V` is a simplified water travel time, not calibrated flood-wave propagation. Nested upstream/downstream catchment flows cannot be summed; routing requires explicit disjoint contributing areas and aligned arrival times. Rating-curve extrapolation is prohibited.

Risk colours are project demonstration screening thresholds: minimum freeboard ≤0, ≤0.5, ≤1 and >1 m gives red, orange, yellow and green, respectively, not official warning levels. Actual section calculations require evidence, station identity, validity dates, verified datum/transfer/profile/banks and two bank elevations in `config/section_calibration.json`. No verification has been invented, so actual risks remain indeterminate. Rainfall is retained as calculation context; validated incremental-catchment runoff parameters are absent, and mm cannot be added directly to m³/s. Routing and Q–H functions are implemented and tested with known inputs, but full-river forecasts are not calibrated.

## Running and outputs

Use these commands for a full local rebuild, a rebuild reusing unchanged spatial results, or unit tests. They do not download data.

```powershell
# Full local rebuild; no network access
.\.venv\Scripts\python.exe scripts/run_etl.py

# Reuse spatial results when survey inputs are unchanged
.\.venv\Scripts\python.exe scripts/run_etl.py --reuse-spatial

# Unit tests
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

`data/processed/etl/` contains `sections`, `survey_points`, `profiles`, `section_station_links`, `confluence_links`, `station_section_coverage`, `water_observations`, `precipitation_intervals`, `station_windows`, `section_calculations` and `survey_geometry`. JSON preserves full fields; key tables also have CSV exports. `project.sqlite3` stores derived tables as primary keys plus JSON payloads; query fields with `json_extract(payload, '$.station_id')`. ETL replaces the derived snapshot and preserves original responses.

See `data/reports/etl_validation.json` for counts and blockers, and `data/reports/etl_weather_backfill.json` for bounded weather retrieval. Original backfill responses are in `data/sources/eccc_weather_geomet/raw/validation/etl_weather/`; official datum pages are in `data/sources/eccc_wateroffice/raw/datums/`. `API/fetch_station_datums.py` and `API/backfill_weather_for_etl.py` are separate bounded network scripts, not automatically called by ETL or the scheduler.

`watch` acquires raw data; `run_etl.py` separately performs retrospective transformation and calculations. The acquisition thread does not automatically produce forecasts. CV training and joint feedback in stages 5 and 6 remain unchanged.
