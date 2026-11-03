# `build_weather_map_areas.py`

`courses/AIDA-2362/src/gis_tools/build_weather_map_areas.py`

Build schematic weather areas in permitted GIS output locations.

## Imports

- `from project_paths import resolve_runtime_path, archive_relative`
- `import argparse`
- `from collections import defaultdict`
- `from datetime import datetime, timezone`
- `import hashlib`
- `import json`
- `from pathlib import Path`
- `from pyproj import Transformer`
- `from shapely import voronoi_polygons, make_valid`
- `from shapely.geometry import MultiPoint, Point, mapping, shape`
- `from shapely.ops import transform, unary_union`
- `from project_paths import ROOT, is_gis_output_path`

## Calls

`MultiPoint`, `Point`, `ValueError`, `abs`, `archive_relative`, `defaultdict`, `is_gis_output_path`, `json.dumps`, `json.loads`, `len`, `list`, `main`, `make_valid`, `mapping`, `print`, `read`, `resolve_runtime_path`, `sha`, `shape`, `sorted`, `sum`, `transform`, `tuple`, `unary_union`, `voronoi_polygons`, `zip`

## File outputs

- `destination.write_text(json.dumps({'type': 'FeatureCollection', 'name': 'weather_association_areas', 'bbox': bounds, 'features': features}, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf-8')`
- `(folder / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')`
- `(folder / 'weather_area_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`
