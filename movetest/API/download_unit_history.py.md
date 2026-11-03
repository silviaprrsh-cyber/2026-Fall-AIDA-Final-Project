# download_unit_history.py

Downloads Wateroffice unit values for the five model stations using parameter 46 for water level and 47 for river discharge. Lake 05CC003 requests level alone. The default window is the preceding 18 calendar months, frozen when the run begins. Monthly intervals share their endpoints, which the local analyzer deduplicates.

Run from movetest with `python -B run.py -m API.download_unit_history`. Resume unfinished requests using `--run-id RUN`. Optional `--start` and `--end` require explicit UTC offsets. Two concurrent requests, three attempts per interval, HTTP timeouts and finite jobs bound the run. Complete requests can still contain provider gaps or empty responses.

Calls API.client.fetch for source-separated original CSVs and HTTP metadata in course data/sources/eccc_wateroffice/raw/unit_values/RUN. Writes a resumable manifest under data/reports/unit_history/RUN. Checks CSV structure, station IDs, parameters, observation bounds and checksums. Keeps observation and receipt times separate. Downloads only unit values. Official service documentation is https://wateroffice.ec.gc.ca/services/index_e.html.
