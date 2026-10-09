# Interfaces and data structures

Acquisition is implemented in `API/`; original responses are separated under `data/sources/<source>/`. Schema validation here is archived evidence, not a new query of every station today.

The public hydrometric and weather interfaces listed below use anonymous HTTPS GET without API keys. Satellite interfaces require the CDSE credentials configured in the root `.env`. Actual station-specific field lists, timestamps and original-response paths are recorded in `data/reports/hydrometric_validation.json` and `data/reports/weather_validation.json`. Validation used bounded, one-time samples; continuous collection has not been started.

| Data | Endpoint and filters | Core structure | Purpose |
|---|---|---|---|
| Hydrometric station metadata | `https://api.weather.gc.ca/collections/hydrometric-stations/items`; `STATION_NUMBER` | GeoJSON `features`, `geometry`, `properties` | Name, coordinates and station status |
| Real-time hydrometric JSON | `https://api.weather.gc.ca/collections/hydrometric-realtime/items`; `STATION_NUMBER`, `sortby=-DATETIME`, `limit=48` | `STATION_NUMBER`, `DATETIME`, discharge/water level and quality fields; actual fields follow station-level validation | Initial schema validation |
| Historical hydrometric data | `https://api.weather.gc.ca/collections/hydrometric-daily-mean/items`; `STATION_NUMBER`, `sortby=-DATE`, `limit=1` | GeoJSON with dates and daily means | One historical sample where real-time data are absent; no scheduled repeated retrieval |
| Hourly hydrometric product | `https://dd.weather.gc.ca/today/hydrometric/csv/AB/hourly/AB_{station_id}_hourly_hydrometric.csv` | Ten columns: station ID, timestamp with time zone, level in m, level grade/symbol/quality flag, discharge in m³/s, discharge grade/symbol/quality flag | Continuous collection; documented file update interval is 3,600 seconds |
| Weather and measured precipitation | `https://api.weather.gc.ca/collections/swob-realtime/items`; `msc_id-value`, `datetime`, `sortby`, `limit` | GeoJSON; `date_tm-value` is observation time and `processed_date_tm` is processing time; measurement fields with `-uom` and `-qa` | Initial validation and continuous collection |

Initial schema validation checks `pcpn_amt_pst1hr` first, followed by `pcpn_amt_pst6hrs` and `pcpn_amt_pst24hrs`. ETL parses recognized minute/hour accumulation fields and selects nonoverlapping periods for each target window, retaining both total depth in mm and mean intensity in mm/h. Accumulation duration, units and quality flags are preserved; missing values are not zero. Different accumulation windows and repeated rolling amounts must not be summed. See [ETL documentation](ETL_REFERENCE.md).

Each hydrometric point is linked to the nearest weather station successfully validated to provide measured precipitation. This is generally not an observation at the hydrometric point itself. Distances and substitute station identifiers are recorded in `data/processed/weather_links.csv`. Provincial station metadata do not guarantee corresponding observations in GeoMet. Additional XML samples from 50 Alberta agricultural stations contained no valid precipitation, so these stations were not enabled as precipitation sources.

## Continuous mode

`config/stations.json` stores `sources` for each monitoring point. Each source's `publication_interval_seconds` and `interval_evidence` drive independent water and weather scheduling. Shared weather sources have one schedule; slower sources do not reduce weather acquisition frequency. `calculation_interval_seconds` separately defines the water station's calculation window. Legacy `interval_seconds` is retained for compatibility and does not drive scheduling.

API configuration loading and ETL use the same calculation-interval rule: preserve an explicitly configured positive finite number; infer the interval from hydrometric sources only when the field is absent or `null`. Reject zero, negative, Boolean, string or nonfinite values. Changing the calculation window does not change source publication schedules. Configuration-generation scripts still rebuild their default intervals from source evidence, so preserve manual overrides before regenerating configuration.

The hydrometric hourly product has a documented interval. Weather intervals are estimated from differences among multiple `processed_date_tm` values in a single response and labelled `observed_estimate`, not an official fixed station-specific publication commitment. A requirement to use only officially confirmed weather publication intervals remains dependent on additional evidence from the provider.

Continuous weather retrieval overlaps the stored cursor by six hours to receive revisions. The initial window is 48 hours, with pagination followed. The cursor advances only after every page succeeds. Original responses are saved first; structured records go to SQLite and are deduplicated by source, station and record ID. Outages exceeding the provider's retention window are logged as gaps.

Start with `.\.venv\Scripts\python.exe -m API watch`. Enter `stop` and press Enter, or press Ctrl+C, to stop. In-flight HTTP requests finish or time out before exit; no background service is installed. Use `watch --dry-run` for offline testing.

## Sources

- [Official hydrometric Datamart documentation](https://eccc-msc.github.io/open-data/msc-data/obs_hydrometric/readme_hydrometric-datamart_en/)
- [Official SWOB directories, naming and partner-station documentation](https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_swobdatamart_en/)
- [Project coverage and data gaps](data/reports/coverage_report.md)

## Timestamp meaning and continuous acquisition status

`DATETIME` and `date_tm-value` are observation times; `processed_date_tm` is provider processing time. None may be presented as actual station transmission time, and local receipt time is not a substitute. Leave the transmission field missing with a reason when selected interfaces do not explicitly expose it.

The implementation uses HTTP retrieval and has not integrated AMQPS. Ongoing Datamart retrieval must follow its [MSC usage policy](https://eccc-msc.github.io/open-data/usage-policy/readme_en/) for AMQPS file notifications and downloads; do not poll directories to detect new data. These notifications are not millisecond sensor telemetry. GeoMet retains its own access rules.

Satellite interfaces use CDSE credentials from the root `.env`; see the [API directory](API/README.md). Key-free public water/weather access does not imply key-free satellite authentication.
