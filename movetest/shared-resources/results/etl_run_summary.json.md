# `etl_run_summary.json`

File: `shared-resources/results/etl_run_summary.json`

## Content, source and use

Structured response, configuration or derived records; fields below identify its contents.

Source/use: local migration and validation tools; technical evidence, not hydraulic/model validation.

Top-level fields: `generated_at`, `scope`, `sections`, `survey_points`, `profiles`, `stations`, `section_profile_status`, `point_assignment_status`, `section_station_link_methods`, `stations_with_section_within_1km`, `water_observations`, `precipitation_intervals`, `precipitation_quality`, `window_status`, `latest_window_status`, `section_calculation_status`, `calculation_blockers`, `historical_survey_geometry_previews`, `live_collection_started`, `datum_status`, `normalization_issues`

Calls/outputs: this file does not execute code or generate other files by itself. Its consumers and provenance are listed below where identifiable.

No exact static code reference was identified; this does not mean the file is unused. QGIS/GDAL and dynamic directory scans may consume it.

This note describes existing files only; it does not run collection, processing or training.
