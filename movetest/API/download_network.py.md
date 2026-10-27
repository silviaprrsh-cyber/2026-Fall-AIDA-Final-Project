# `download_network.py`

File: `API/download_network.py`

## Purpose

Download every 20K river segment intersecting the Red Deer watershed.

Uses returnIdsOnly + explicit ID chunks: no silent ArcGIS transfer-limit truncation.

## Defined functions/classes

`main`

## Direct imports

- `API.client: get_json`
- `concurrent.futures`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json`
- `shapely.geometry: shape, mapping`
- `shapely.ops: unary_union`
- `sys`

## Calls

`concurrent.futures.ThreadPoolExecutor`, `get_json`, `json.loads`, `main`, `mapping`, `resolve_runtime_path`, `save_json`, `shape`, `unary_union`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L23: save_json(resolve_runtime_path(DATA / 'processed/basin_boundary.geojson'), {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'properties': {'source': 'Union of Alberta HUC4 and WSC 05C tertiary units, including internally drained areas'}, 'geometry': mapping(basin)}]})`
- `L50: save_json(resolve_runtime_path(DATA / f'processed/{label}.geojson'), {'type': 'FeatureCollection', 'features': actual})`
- `L51: save_json(resolve_runtime_path(DATA / f'reports/{label}_coverage.json'), {'requested_feature_count': len(ids), 'received_feature_count': len(all_features), 'basin_intersecting_count': len(actual), 'complete_id_download': len(all_features) == len(ids), 'note': 'Full intersecting features retained; geometry not clipped. Provincial service extent is A`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/download_network.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
