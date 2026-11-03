# `segments.py`

Builds the independent submodel chain and integrated `segment_training` table. Called by `rdr_eda.project_etl.run_project_pipeline`; uses the existing timestamp parser, standard CSV/JSON tools and selected GIS distances. Reads `shared-resources/config/segment_etl.json`, normalized project tables and optional CSV submodel states. No network, training or prediction is performed.

Returns `model_segments`, `model_segment_legs`, `segment_training` and `segment_arrivals` to the main exporter. `postgres_export` creates `segments_postgresql.sql`; `feature_contract` supplies the JSON predictor allowlist. Per-segment travel time is distance / upstream model-predicted velocity. The initial three branches require separate source-velocity predictions. Missing velocity leaves arrival and labels pending. The endpoint observation nearest the cumulative arrival is matched by observation time within the configured tolerance; receipt time is retained independently. Lake elevation is an input only for P03 to P04.

See the output README for the state CSV contract and commands. Existing database schemas are not overwritten by the PostgreSQL export.
