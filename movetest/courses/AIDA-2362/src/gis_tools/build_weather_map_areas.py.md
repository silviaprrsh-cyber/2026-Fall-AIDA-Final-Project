# `build_weather_map_areas.py`

File: `courses/AIDA-2362/src/gis_tools/build_weather_map_areas.py`

## Purpose

Create display-only weather association areas from existing station links.

Voronoi cells belong to hydrometric sites, inherit their already assigned weather
station, and are dissolved by weather ID and clipped to the archived basin.
This is not a meteorological footprint, catchment delineation or new linkage.

## Defined functions/classes

`sha`, `main`

## Direct imports

- `argparse`
- `collections: defaultdict`
- `datetime: datetime, timezone`
- `hashlib`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer`
- `shapely.geometry: MultiPoint, Point, mapping, shape`
- `shapely.ops: transform, unary_union`
- `shapely: voronoi_polygons, make_valid`

## Calls

`MultiPoint`, `Point`, `Transformer.from_crs`, `archive_relative`, `argparse.ArgumentParser`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `defaultdict`, `hashlib.file_digest`, `hashlib.file_digest(stream, 'sha256').hexdigest`, `json.dumps`, `json.loads`, `main`, `make_valid`, `mapping`, `read`, `resolve_runtime_path`, `sha`, `shape`, `transform`, `unary_union`, `voronoi_polygons`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L108: destination.write_text(json.dumps({'type': 'FeatureCollection', 'name': 'weather_association_areas', 'bbox': bounds, 'features': features}, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')`
- `L122: (folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')`
- `L135: (folder / 'weather_area_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/build_weather_map_areas.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
