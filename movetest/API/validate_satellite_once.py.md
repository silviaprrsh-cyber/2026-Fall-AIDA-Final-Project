# `validate_satellite_once.py`

File: `API/validate_satellite_once.py`

## Purpose

Run one bounded CDSE discovery and image retrieval check; never schedule polling.

## Defined functions/classes

`write_json`, `credentials`, `checked`, `inspect_pixels`, `main`

## Direct imports

- `PIL: Image`
- `__future__: annotations`
- `csv`
- `datetime: datetime, timedelta, timezone`
- `hashlib`
- `io`
- `json`
- `numpy`
- `os`
- `pathlib: Path`
- `project_paths: ROOT, WORKSPACE`
- `project_paths: resolve_runtime_path, archive_relative`
- `pyproj: Transformer`
- `rasterio`
- `re`
- `requests`
- `shapely.geometry: box, shape`
- `struct`
- `tarfile`

## Calls

`Image.open`, `Transformer.from_crs`, `archive_relative`, `box`, `checked`, `credentials`, `csv.DictReader`, `datetime.fromisoformat`, `datetime.fromisoformat(selected['properties']['datetime'].replace('Z', '+00:00')).date`, `datetime.now`, `datetime.now(timezone.utc).isoformat`, `hashlib.sha256`, `hashlib.sha256(p.read_bytes()).hexdigest`, `inspect_pixels`, `io.BytesIO`, `json.dumps`, `json.loads`, `main`, `np.allclose`, `np.any`, `np.array_equal`, `np.asarray`, `np.isfinite`, `np.isfinite(reflectance[:, valid]).all`, `np.isin`, `np.isin(scl[valid], [8, 9, 10]).mean`, `np.unique`, `os.environ.items`, `rasterio.open`, `re.match`, `requests.Session`, `resolve_runtime_path`, `shape`, `struct.unpack`, `tarfile.open`, `timedelta`, `write_json`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L57: path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')`
- `L156: write_json(folder / 'stac_request.json', search)`
- `L159: (folder / 'stac_response.json').write_bytes(response.content)`
- `L172: write_json(folder / 'selected_scene.json', selected)`
- `L204: write_json(folder / 'process_request.json', process)`
- `L208: (folder / 'process_response.tar').write_bytes(response.content)`
- `L240: write_json(folder / 'validation.json', report)`
- `L241: write_json(resolve_runtime_path(ROOT / 'data/reports/satellite_validation_once.json'), report)`
- `L215: (folder / member.name).write_bytes(src.read())`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/validate_satellite_once.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
