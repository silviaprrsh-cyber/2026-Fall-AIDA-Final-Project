# filter_model_history.py

Run from movetest with `python -B run.py -m eda_tools.filter_model_history --manifest courses/AIDA-2156/data/reports/tributary_history/RUN/download_manifest.json`.

Reads only a complete five-station download manifest and its raw GeoMet daily pages. Checks station/date uniqueness, HTTP status, file SHA-256 and manifest counts. Calls project path resolution and the bilingual companion writer. Saves source-separated normalized records, wide common numeric dates, a conservative unflagged positive-value subset, per-date exclusion reasons, chronological 60/20/20 candidate assignments and a coverage/provenance report in course data/processed/model_daily_history/RUN.

Required fields are Q and level for 05CB007, 05CB001, 05CC007 and 05CC002, and level alone for 05CC003. The strict subset excludes any required source symbol, including ice, estimated and partial-day values. Original and flagged records remain available. Dates keep day precision. This command prepares daily candidates and invokes no training or acquisition.
