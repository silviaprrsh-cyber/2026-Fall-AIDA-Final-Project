# API acquisition code

This directory contains the project's remote data acquisition code. It uses `.venv`, `.env` and `config/` in the project root. Original data are written to `data/sources/<source>/`, not to the code directory. Paths resolve from the project location rather than the terminal's working directory.

| File | Purpose |
| --- | --- |
| `client.py` | HTTP retrieval, source-specific archives, caching and provenance |
| `observations.py` | Hydrometric and weather interfaces and observation parsing |
| `collector.py`, `__main__.py` | Independent scheduling, status and terminal stop |
| `datamart_notifications.py` | Anonymous AMQPS hydrometric file notifications |
| `discover.py`, `discover_details.py` | Bounded endpoint and metadata discovery |
| `validate_once.py` | One-shot hydrometric and weather validation |
| `download_static.py`, `download_network.py`, `download_nhn.py` | Government reports and river-network downloads |
| `fetch_station_datums.py` | Station datum evidence |
| `backfill_weather_for_etl.py` | Bounded weather backfill |
| `check_partner_precipitation.py` | Partner precipitation checks |
| `validate_satellite_once.py` | One-shot satellite API and image validation |
| `query_station_timestamps.py` | One-shot source timestamp query |
| `snapshot_scope.py` | One latest sample per active water/weather source; original responses and timestamped report, then exit |
| `query_scope_boundary.py` | One OSM bridge geometry query for the selected downstream boundary |
| `query_prediction_landmarks.py` | Bounded OSM bridge query, or `--details-only` for 76 Street, Discovery Canyon and Sylvan confluence geometry; archives original responses |
| `qgis_basemap.py` | QGIS OpenStreetMap basemap access and request diagnostics |
| `download_tributary_history.py` | Bounded, paginated download of all available official historical daily values for a reviewed candidate list |

Historical archive command: `.\.venv\Scripts\python.exe -m API.download_tributary_history --candidates data/processed/tributary_history_20261012/candidates.json`. It makes new network requests and saves original pages under `data/sources/eccc_hydrometric_geomet/raw/tributary_history/<UTC-run>/<station>/`, with a download manifest under `data/reports/tributary_history/<UTC-run>/`. It does not start continuous collection, train a model or refresh the QGIS layer. `--discover` retrieves station metadata, the collection description and the WSC stream-order index; candidate selection still requires geographic review. The current candidate-preparation tool uses the archived discovery paths recorded in its source.

Use `python -m API.snapshot_scope` for the station IDs in `config/active_scope.json`, or repeat `--station ID` to check explicit candidates. Each unique source is queried once for at most 48 recent records; no historical fallback, continuous loop or ETL is started. Reports are saved under `data/reports/scope_snapshot/<UTC-run>/`. A saved QGIS map remains a dated snapshot until explicitly rebuilt.

Inspect configuration and run offline tests from the project root. `status` reads saved configuration; it does not query current station availability:

```powershell
.\.venv\Scripts\python.exe -m API status
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Run one-shot scripts with `python API/<script>.py` or `python -m API.<module>`, using the project virtual environment. Confirm the task scope and network/file-write effects before execution. Timestamp queries write `data/reports/station_timestamp_export/results.json`. The existing summary CSV lives in `data/processed/station_timestamps/`; rerunning the query does not regenerate that separately exported CSV.

Use `.\.venv\Scripts\python.exe -m API watch --dry-run` from the project root for an offline scheduler exercise; enter `stop` followed by Enter to exit. It makes no network requests, but prints progress, writes `data/state/last_run.json` on exit and does not terminate automatically while terminal input remains open. Ctrl+C or input EOF also stops it. The old `python -m rdr` command remains a forwarding compatibility entry point; acquisition is implemented here.

`watch` subscribes to Datamart AMQPS notifications before the optional initial water snapshot. Later water retrieval requires a notification or pending failed retrieval and respects source cadence; weather sources are scheduled independently. `--duration-seconds 10800` bounds a run to three hours of new requests. `--detached` requires a duration and disables stdin control; use `python -m API stop` for a graceful external stop. Foreground runs still accept `stop` and Ctrl+C. UTC start/deadline, PID and progress are in `data/state/active_run.json`; the final state is also in `last_run.json`. Run only with task authorization. `watch` stores observations; ETL and hydraulic calculations remain separate.

`python -m API.review_map_stations` performs a bounded map review using the selected station IDs, latest samples and official location references. It does not collect continuously. The local `scripts/update_scoped_stations.py` uses the saved review named in `config/map_station_selection.json`; changing the review date requires matching source evidence before rebuilding the map.
