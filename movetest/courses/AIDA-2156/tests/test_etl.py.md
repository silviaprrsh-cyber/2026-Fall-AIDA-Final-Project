# `test_etl.py`

File: `courses/AIDA-2156/tests/test_etl.py`

## Purpose

Offline unit-test module.

## Defined functions/classes

`stamp`, `rain`, `RainfallTests`, `HydraulicTests`, `PipelineTests`

## Direct imports

- `API.collector: calculation_interval, source_schedules`
- `json`
- `math`
- `pathlib: Path`
- `rdr_eda.etl: station_windows, write_database, calculate_sections`
- `rdr_eda.hydraulics: section_geometry, screen_section, reach_storage, travel_time_seconds, routed_discharge, rating_level`
- `rdr_eda.rainfall: aggregate_precipitation, normalize_swob`
- `sqlite3`
- `tempfile`
- `unittest`

## Calls

`Path`, `aggregate_precipitation`, `calculation_interval`, `json.loads`, `math.sqrt`, `normalize_swob`, `rain`, `rating_level`, `reach_storage`, `routed_discharge`, `screen_section`, `section_geometry`, `self.assertAlmostEqual`, `self.assertEqual`, `self.assertFalse`, `self.assertIsNone`, `self.assertRaises`, `self.assertTrue`, `source_schedules`, `sqlite3.connect`, `stamp`, `station_windows`, `tempfile.TemporaryDirectory`, `travel_time_seconds`, `unittest.main`, `write_database`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L144: sqlite3.connect(path / 'project.sqlite3')`
- `L143: write_database(path, {'sample': ([{'value': value}], lambda row, index: 'one')})`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_etl.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
