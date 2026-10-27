# `test_collector.py`

File: `shared-resources/tests/test_collector.py`

## Purpose

Offline unit-test module.

## Defined functions/classes

`CollectorTests`

## Direct imports

- `API.collector: station_interval, listen_for_stop, ObservationStore, Collector, load_config, source_schedules, station_calculation_interval`
- `API.observations: precipitation, cadence`
- `io`
- `json`
- `pathlib: Path`
- `rdr_eda.etl: station_windows`
- `subprocess`
- `sys`
- `tempfile`
- `threading`
- `unittest`
- `unittest.mock: patch`

## Calls

`Collector`, `ObservationStore`, `Path`, `cadence`, `feature`, `io.StringIO`, `json.dumps`, `json.loads`, `listen_for_stop`, `load_config`, `patch`, `precipitation`, `self.assertEqual`, `self.assertIsNone`, `self.assertRaises`, `self.assertTrue`, `self.subTest`, `source_schedules`, `station_calculation_interval`, `station_interval`, `station_windows`, `tempfile.TemporaryDirectory`, `threading.Event`, `unittest.main`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L29: path.write_text(original, encoding='utf-8')`
- `L81: store.write('water', 'S', records)`
- `L81: store.write('water', 'S', records)`
- `L82: store.write('water', 'S', [('id1', records[0][1], {'level': 2}, 'raw/revision.json')])`
- `L83: store.write('water', 'S', [('old', '2026-09-27T00:00:00+00:00', {'level': 0}, 'raw/old.json')])`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_collector.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
