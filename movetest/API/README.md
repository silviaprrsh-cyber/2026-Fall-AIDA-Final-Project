# API

Shared acquisition code. Launched through root `run.py -m API`. Course-owned data destinations are configured in `shared-resources/config/data_layout.json`. Continuous collection requires an explicit task; no collection is launched by offline processing.

Historical satellite acquisition uses `run.py -m API.download_satellite_history`; see the AIDA-2154 README for scope, finite downloads, resume and indexing commands.
