# `build_prediction_points.py`

File: `courses/AIDA-2362/src/gis_tools/build_prediction_points.py`

## Purpose

Build reviewable prediction locations from archived river, survey and OSM geometry.

This offline tool creates cartographic targets only; it does not estimate flows.

## Defined functions/classes

`read`, `write`, `first_downstream`, `bridge_position`, `build`

## Direct imports

- `hashlib`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer`
- `shapely.geometry: LineString, Point, shape, mapping`
- `shapely.ops: nearest_points, transform, unary_union`

## Calls

`LineString`, `Point`, `Transformer.from_crs`, `archive_relative`, `bridge_position`, `build`, `first_downstream`, `hashlib.sha256`, `hashlib.sha256(output.read_bytes()).hexdigest`, `hashlib.sha256(p.read_bytes()).hexdigest`, `json.dumps`, `json.loads`, `mapping`, `nearest_points`, `read`, `resolve_runtime_path`, `shape`, `transform`, `unary_union`, `write`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L22: path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')`
- `L148: write(output, {'type': 'FeatureCollection', 'features': features})`
- `L150: write(folder / 'prediction_points_review.json', {'target_count': 11, 'ordered_upstream_to_downstream': True, 'all_points_on_selected_mainstem': True, 'all_prediction_values_null': True, 'inputs': provenance, 'targets': [{**f['properties'], 'coordinates': f['geometry']['coordinates']} for f in features]})`
- `L160: write(folder / 'manifest.json', manifest)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/build_prediction_points.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
