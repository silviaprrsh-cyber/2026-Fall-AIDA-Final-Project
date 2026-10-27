# `update_scoped_stations.py`

File: `courses/AIDA-2362/src/gis_tools/update_scoped_stations.py`

## Purpose

Apply reviewed station exclusions and mutually exclusive recency map layers.

## Defined functions/classes

`read`, `write`, `window_start`, `recent`, `partition`, `coordinate_review`, `update_map`

## Direct imports

- `calendar`
- `copy: deepcopy`
- `datetime: date, datetime, time, timezone`
- `hashlib`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer`
- `shapely.geometry: LineString, Point`
- `shapely.ops: transform`
- `zoneinfo: ZoneInfo`

## Calls

`LineString`, `Point`, `Transformer.from_crs`, `ZoneInfo`, `calendar.monthrange`, `coordinate_review`, `date`, `date.fromisoformat`, `datetime.combine`, `datetime.fromisoformat`, `datetime.strptime`, `datetime.strptime(source['run'], '%Y%m%dT%H%M%SZ').replace`, `deepcopy`, `hashlib.sha256`, `hashlib.sha256(path.read_bytes()).hexdigest`, `json.dumps`, `json.loads`, `partition`, `read`, `recent`, `resolve_runtime_path`, `transform`, `update_map`, `window_start`, `write`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L23: path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')`
- `L162: write(folder / 'manifest.json', manifest)`
- `L163: write(folder / 'station_display_review.json', report)`
- `L149: write(path, {'type': 'FeatureCollection', 'features': features})`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/update_scoped_stations.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
