# `build_scoped_qgis.py`

`courses/AIDA-2362/src/gis_tools/build_scoped_qgis.py`

Build scoped GIS layers from archived observations, river networks and survey vectors; an existing destination is not overwritten.

## Imports

- `from project_paths import resolve_runtime_path, archive_relative`
- `import argparse`
- `from collections import defaultdict`
- `from datetime import datetime, timezone`
- `import hashlib`
- `import heapq`
- `import io`
- `import json`
- `import math`
- `from pathlib import Path`
- `import zipfile`
- `import shapefile`
- `from pyproj import Transformer`
- `from shapely import voronoi_polygons`
- `from shapely.geometry import LineString, MultiPoint, Point, mapping, shape`
- `from shapely.ops import transform, substring, unary_union`
- `from shapely.strtree import STRtree`
- `from project_paths import ROOT, is_gis_output_path`

## Calls

`LineString`, `MultiPoint`, `Network`, `Point`, `STRtree`, `TO_M`, `ValueError`, `any`, `archive_relative`, `contact_points`, `defaultdict`, `enumerate`, `feature`, `int`, `is_gis_output_path`, `json.dumps`, `json.loads`, `len`, `list`, `main`, `mapping`, `max`, `metric`, `min`, `print`, `read`, `resolve_runtime_path`, `round`, `save`, `set`, `sha`, `shape`, `sorted`, `str`, `substring`, `transform`, `tuple`, `unary_union`, `voronoi_polygons`, `zip`

## File outputs

- `(output / 'scope_validation.json').write_text(json.dumps(audit, indent=2), encoding='utf-8')`
- `(output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')`
- `path.write_text(json.dumps({'type': 'FeatureCollection', 'features': features}), encoding='utf-8')`
