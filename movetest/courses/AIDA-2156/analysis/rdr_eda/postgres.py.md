# postgres.py

Loads PostgreSQL connection settings from the project .env and allowed PG environment variables. Uses psycopg with explicit keyword arguments, a connection timeout and password-redacted connection errors. Reads a consistent, read-only repeatable-read snapshot through the configured views. Returns observation histories, section geometry, six model segments, the database dataset identifier and the train/validation/test origin lists to rdr_ml.Dataset. Datetimes are normalized to UTC ISO strings. This module creates no files and performs no acquisition.

Optional partition_views in the dataset configuration selects alternate partition views while retaining the same observation and geometry snapshot.
