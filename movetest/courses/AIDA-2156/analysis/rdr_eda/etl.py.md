# `etl.py`

File: `courses/AIDA-2156/analysis/rdr_eda/etl.py`

## Purpose

Reproducible local ETL from archived source observations and survey files.

## Defined functions/classes

`metadata`, `normalize_archives`, `station_windows`, `calculate_sections`, `export_csv`, `write_database`, `run_pipeline`

## Direct imports

- `.hydraulics: section_geometry, screen_section`
- `.rainfall: finite, normalize_swob, aggregate_precipitation`
- `API.collector: station_calculation_interval`
- `API.observations: parse_time`
- `collections: defaultdict, Counter`
- `contextlib: closing`
- `csv`
- `datetime: timedelta, timezone`
- `json`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, ROOT, save_json, now`
- `rdr_gis.spatial: normalize_surveys, build_links`
- `sqlite3`

## Calls

`Counter`, `add_water`, `aggregate_precipitation`, `archive_relative`, `build_links`, `calculate_sections`, `closing`, `csv.DictWriter`, `csv.reader`, `defaultdict`, `export_csv`, `finite`, `json.dumps`, `json.loads`, `json.loads(path.read_text(encoding='utf-8')).get`, `metadata`, `normalize_archives`, `normalize_surveys`, `normalize_swob`, `now`, `parse_time`, `resolve_runtime_path`, `save_json`, `screen_section`, `section_geometry`, `sqlite3.connect`, `station_calculation_interval`, `station_windows`, `timedelta`, `write_database`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L230: write_database(folder, {'sections': (sections, lambda r, i: r['section_id']), 'survey_points': (points, lambda r, i: r['point_key']), 'section_station_links': (links, lambda r, i: r['section_id']), 'confluences': (mouths, lambda r, i: r['confluence_id']), 'station_datums': (datums['stations'], lambda r, i: r['station_id']), 'water_observations': (w`
- `L254: save_json(resolve_runtime_path(DATA / 'reports/etl_validation.json'), report)`
- `L219: save_json(folder / (name + '.json'), obj)`
- `L229: export_csv(folder / (name + '.csv'), rows, fields)`
- `L189: sqlite3.connect(temporary)`
- `L206: save_json(folder / (name + '.json'), obj)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/etl.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
