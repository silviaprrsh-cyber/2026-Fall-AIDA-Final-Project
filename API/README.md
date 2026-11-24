# API

Shared acquisition code. Launched through root `run.py -m API`. Course-owned data destinations are configured in `shared-resources/config/data_layout.json`. The legacy collector and validation commands here serve archive workflows. They are not how to start the deployed snapshot server. Offline processing does not launch collection.

For deployment, use the separate [AIDA-2156 research snapshot server](../courses/AIDA-2156/deployment/server/README.md). Once started in live mode with its dedicated PostgreSQL database, it polls automatically every 600 seconds by default, even without clients. Local demo checks use synthetic observations and do not certify live cloud readiness. Research only; do not use for flood alerts or emergency decisions.

Historical satellite acquisition uses `run.py -m API.download_satellite_history`; see the AIDA-2154 README for scope, finite downloads, resume and indexing commands.

Weather update (2026-11-09): the finite `API.download_weather_history` module archives official station 3025484 hourly records by month. `rdr_ml.weather_experiment` trains and tests paired weather/control joint chains using the existing PostgreSQL hydrometric views and a local weather join. Full commands, metrics, missingness rules and limitations are in the root README weather section; comparison: courses/AIDA-2156/data/reports/segment_ml_weather_comparison_60_20_20.json.
