# `collector.py`

File: `API/collector.py`

## Purpose

Independent source schedules, persisted cursors, raw provenance and stop input.

## Defined functions/classes

`station_interval`, `calculation_interval`, `station_calculation_interval`, `source_schedules`, `ObservationStore`, `Collector`, `listen_for_stop`, `load_config`, `run`

## Direct imports

- `API.client: fetch, get_json`
- `API.datamart_notifications: DatamartNotifications`
- `API.observations: API, parse_time`
- `__future__: annotations`
- `concurrent.futures: ThreadPoolExecutor`
- `contextlib: contextmanager`
- `csv`
- `datetime: datetime, timedelta, timezone`
- `io`
- `json`
- `math`
- `os`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.paths: source_relative_path`
- `rdr.storage: DATA, ROOT, save_json, now, log`
- `signal`
- `sqlite3`
- `sys`
- `threading`
- `time`
- `uuid: uuid4`

## Calls

`Collector`, `DatamartNotifications`, `ObservationStore`, `Path`, `ThreadPoolExecutor`, `archive_relative`, `calculation_interval`, `csv.reader`, `datetime.now`, `fetch`, `get_json`, `io.StringIO`, `json.dumps`, `json.loads`, `log`, `math.isfinite`, `now`, `os.getpid`, `parse_time`, `resolve_runtime_path`, `save_json`, `self._fetch`, `self.connect`, `self.last_success.get`, `self.locks.setdefault`, `self.path.parent.mkdir`, `self.stop.is_set`, `self.store.cursor`, `self.store.write`, `signal.getsignal`, `signal.signal`, `source_relative_path`, `source_schedules`, `sqlite3.connect`, `station_calculation_interval`, `station_interval`, `threading.Event`, `threading.Lock`, `threading.Thread`, `threading.Thread(target=listen_for_stop, args=(stop,), daemon=True).start`, `time.monotonic`, `timedelta`, `uuid4`, `write_state`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L77: sqlite3.connect(self.path, timeout=30)`
- `L251: save_json(state_path, state)`
- `L252: save_json(resolve_runtime_path(DATA / 'state/active_run.json'), state)`
- `L253: save_json(resolve_runtime_path(DATA / 'state/last_run.json'), state)`
- `L118: self.store.write(*key, records)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/collector.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
