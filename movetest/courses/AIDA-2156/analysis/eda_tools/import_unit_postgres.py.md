# import_unit_postgres.py

Run `python -B run.py -m eda_tools.import_unit_postgres` from movetest. Reads the deduplicated unit-value SQLite and scoped geometry SQLite snapshots. Hashes both files and creates a versioned rdr_unit schema in the .env database inside one transaction. Uses psycopg COPY for 1,350,764 parameter records, candidate origins, segment routing and survey profiles. Builds a materialized station/time pairing and ordinary training views. Existing matching snapshots are verified and reused.

The feature views v_train, v_validation and v_test contain the 60/20/20 origin partitions and upstream/lake input fields. v_input_history and v_lake_history support lagged input lookup. v_endpoint_observations supplies the downstream observations used for arrival-time labels. Geometry comes through v_model_segments, v_model_segment_legs, v_sections and v_section_profile_points. v_dataset_metadata provides source hashes and provenance. Daily backups are excluded.

Writes shared-resources/config/postgres_dataset.json and data/reports/postgresql_unit_import.json with bilingual notes. Credentials remain in .env. Imports run within a transaction with a schema-specific advisory lock. Partial failures roll back. The Python entry point is the reproducible view definition and import procedure.

--split 80-20 creates named 80/20 chronological views and postgres_dataset_8020.json. Existing source tables and default views remain available. The validation view is empty.
