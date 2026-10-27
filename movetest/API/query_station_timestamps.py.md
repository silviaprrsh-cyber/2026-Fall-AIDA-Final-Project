# `query_station_timestamps.py`

File: `API/query_station_timestamps.py`

## Purpose

Read public source timestamps once; do not start the project collector.

## Defined functions/classes

`now`, `load_csv`, `query`, `numeric`, `parse_time`, `newest`, `base`, `hydro`, `weather_valid`, `meteo`, `main`

## Direct imports

- `concurrent.futures`
- `csv`
- `datetime: datetime, timezone`
- `hashlib`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.paths: source_relative_path`
- `sys`
- `urllib.error`
- `urllib.parse`
- `urllib.request`

## Calls

`Path`, `base`, `concurrent.futures.ThreadPoolExecutor`, `concurrent.futures.as_completed`, `csv.DictReader`, `datetime.fromisoformat`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `datetime.now(timezone.utc).isoformat().replace`, `datetime.now(timezone.utc).strftime`, `hashlib.sha256`, `hashlib.sha256(body).hexdigest`, `json.dumps`, `json.loads`, `load_csv`, `main`, `math.isfinite`, `newest`, `now`, `numeric`, `parse_time`, `query`, `resolve_runtime_path`, `source_relative_path`, `urllib.parse.urlencode`, `urllib.request.Request`, `urllib.request.urlopen`, `weather_valid`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L171: (OUT / 'results.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')`
- `L43: (folder / (stem + '.json')).write_bytes(body)`
- `L51: (folder / (stem + '.meta.json')).write_text(json.dumps(meta, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/query_station_timestamps.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
