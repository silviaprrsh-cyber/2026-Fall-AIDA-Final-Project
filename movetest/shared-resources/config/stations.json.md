# `stations.json`

File: `shared-resources/config/stations.json`

## Content, source and use

Station configuration or point records

Source/use: local project configuration used by acquisition, data routing or analysis; not observed measurements.

Top-level fields: `generated_at_utc`, `max_workers`, `interval_rule`, `auto_start`, `stations`, `schema_version`, `active_scope`, `scope_updated_at_utc`

Calls/outputs: this file does not execute code or generate other files by itself. Its consumers and provenance are listed below where identifiable.

## Copy provenance

Manifest source: `original` / `config/stations.json`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

## Identified code references

- `shared-resources/tests/test_collector.py`

Matched literal paths/names; directory scans or dynamic references may have additional consumers.

This note describes existing files only; it does not run collection, processing or training.

## Directory/path consumers

These modules reference this file or a containing archive directory; the exact runtime selection depends on filters.

- `shared-resources/tests/test_collector.py`
