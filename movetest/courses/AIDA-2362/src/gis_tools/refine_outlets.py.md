# `refine_outlets.py`

File: `courses/AIDA-2362/src/gis_tools/refine_outlets.py`

## Purpose

Cross-check NHN name transitions against provincial river geometry.

An unnamed reach on the mainstem must not shift a tributary mouth downstream.
Distances use EPSG:3400 metres. All geometric mouths remain mapped estimates.

## Defined functions/classes

`select_gauge`, `main`

## Direct imports

- `collections: defaultdict`
- `gis_tools.build_network: canonical`
- `heapq`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer`
- `rdr.storage: DATA, save_json`
- `shapely.geometry: Point, shape`
- `shapely.ops: transform, unary_union, nearest_points`
- `sys`

## Calls

`Point`, `Transformer.from_crs`, `canonical`, `defaultdict`, `heapq.heapify`, `heapq.heappop`, `heapq.heappush`, `json.loads`, `key`, `main`, `math.isfinite`, `nearest_points`, `resolve_runtime_path`, `save_json`, `select_gauge`, `shape`, `transform`, `unary_union`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L113: save_json(resolve_runtime_path(DATA / 'processed/tributary_outlets.json'), rows)`
- `L124: save_json(resolve_runtime_path(DATA / 'reports/tributary_geometry_gaps.json'), gaps)`
- `L127: save_json(resolve_runtime_path(DATA / 'processed/monitoring_station_ids.json'), sorted(selected))`
- `L128: save_json(resolve_runtime_path(DATA / 'reports/confluence_summary.json'), {'named_mouths': len(rows), 'direct_mainstem_named_mouths': sum((r['direct_to_mainstem'] for r in rows)), 'with_same_river_gauge': sum((bool(r['selected_station_id']) for r in rows)), 'selected_station_count': len(selected), 'gap_records': len(gaps), 'selection_requires_revie`
- `L62: save_json(original, topology)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/refine_outlets.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
