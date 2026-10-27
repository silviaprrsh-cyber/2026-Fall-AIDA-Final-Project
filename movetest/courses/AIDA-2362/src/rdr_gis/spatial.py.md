# `spatial.py`

File: `courses/AIDA-2362/src/rdr_gis/spatial.py`

## Purpose

Survey normalization and evidence-labelled links to the existing named river graph.

## Defined functions/classes

`canonical`, `clean`, `features`, `normalize_surveys`, `RiverGraph`, `build_links`

## Direct imports

- `collections: defaultdict, Counter`
- `heapq`
- `json`
- `math`
- `numpy`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyogrio.raw: read`
- `pyproj: Transformer`
- `rdr.storage: DATA, save_json`
- `rdr_eda.rainfall: finite`
- `re`
- `shapely.geometry: Point, shape, mapping`
- `shapely.ops: linemerge, transform`
- `shapely.strtree: STRtree`
- `shapely: from_wkb, force_2d`
- `statistics: median`

## Calls

`Point`, `RiverGraph`, `STRtree`, `Transformer.from_crs`, `archive_relative`, `canonical`, `clean`, `defaultdict`, `features`, `finite`, `force_2d`, `from_wkb`, `heapq.heapify`, `heapq.heappop`, `heapq.heappush`, `json.loads`, `linemerge`, `mapping`, `math.isfinite`, `median`, `read`, `resolve_runtime_path`, `self.adj[a].append`, `self.adj[b].append`, `self.backward[b].append`, `self.directions.append`, `self.forward[a].append`, `self.ids.append`, `self.key`, `self.lines.append`, `self.tree.nearest`, `shape`, `transform`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/spatial.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
