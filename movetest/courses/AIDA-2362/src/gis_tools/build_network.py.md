# `build_network.py`

File: `courses/AIDA-2362/src/gis_tools/build_network.py`

## Purpose

Derive tributary outlets and nearest SAME-river gauges from NHN topology.

Unknown flow directions and absent gauges remain explicit coverage gaps.
This is a catalog builder, not a hydraulic model.

## Defined functions/classes

`canonical`, `node`, `main`

## Direct imports

- `collections: defaultdict, Counter`
- `csv`
- `heapq`
- `io`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer, CRS`
- `rdr.storage: DATA, save_json`
- `shapefile`
- `shapely.geometry: LineString, Point, mapping`
- `shapely.ops: transform`
- `sys`
- `zipfile`

## Calls

`Counter`, `LineString`, `Point`, `Transformer.from_crs`, `canonical`, `defaultdict`, `downstream_parent`, `heapq.heappop`, `heapq.heappush`, `io.BytesIO`, `json.dumps`, `json.loads`, `main`, `mapping`, `node`, `resolve_runtime_path`, `save_json`, `shapefile.Reader`, `transform`, `zipfile.ZipFile`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L71: save_json(resolve_runtime_path(DATA / 'processed/nhn_named_rivers.geojson'), {'type': 'FeatureCollection', 'name': 'NHN named drainage network; coordinates NAD83(CSRS), EPSG:4617', 'crs': {'type': 'name', 'properties': {'name': 'urn:ogc:def:crs:EPSG::4617'}}, 'features': features})`
- `L148: save_json(resolve_runtime_path(DATA / 'processed/tributary_outlets.json'), outlets)`
- `L149: save_json(resolve_runtime_path(DATA / 'processed/unnamed_mainstem_inflows.json'), unnamed)`
- `L150: save_json(resolve_runtime_path(DATA / 'reports/tributary_topology_gaps.json'), unresolved)`
- `L153: save_json(resolve_runtime_path(DATA / 'processed/monitoring_station_ids.json'), sorted(selected))`
- `L163: save_json(resolve_runtime_path(DATA / 'reports/network_summary.json'), summary)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/build_network.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
