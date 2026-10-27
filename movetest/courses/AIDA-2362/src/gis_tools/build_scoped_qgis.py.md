# `build_scoped_qgis.py`

File: `courses/AIDA-2362/src/gis_tools/build_scoped_qgis.py`

## Purpose

Build a Dickson outlet to the selected bridge map from saved data.

Routing uses connected NHN geometry with named-river constraints. Its orientation
is set by the verified endpoints, not an assertion of hydraulic calibration.

## Defined functions/classes

`read`, `sha`, `metric`, `Network`, `feature`, `main`

## Direct imports

- `argparse`
- `collections: defaultdict`
- `datetime: datetime, timezone`
- `hashlib`
- `heapq`
- `io`
- `json`
- `math`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer`
- `shapefile`
- `shapely.geometry: LineString, MultiPoint, Point, mapping, shape`
- `shapely.ops: transform, substring, unary_union`
- `shapely.strtree: STRtree`
- `shapely: voronoi_polygons`
- `zipfile`

## Calls

`LineString`, `MultiPoint`, `Network`, `Point`, `STRtree`, `Transformer.from_crs`, `archive_relative`, `argparse.ArgumentParser`, `contact_points`, `datetime.fromisoformat`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `defaultdict`, `feature`, `hashlib.sha256`, `hashlib.sha256(path.read_bytes()).hexdigest`, `heapq.heappop`, `heapq.heappush`, `io.BytesIO`, `json.dumps`, `json.loads`, `main`, `mapping`, `metric`, `read`, `resolve_runtime_path`, `save`, `self.edges.append`, `self.inputs.append`, `sha`, `shape`, `shapefile.Reader`, `substring`, `transform`, `unary_union`, `voronoi_polygons`, `zipfile.ZipFile`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L338: (output / 'scope_validation.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')`
- `L339: (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')`
- `L255: path.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/build_scoped_qgis.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
