# `catalog.py`

File: `courses/AIDA-2362/src/rdr_gis/catalog.py`

## Purpose

Normalize station identifiers, names and coordinates into the station master catalogue.

## Defined functions/classes

`watercourse`, `dms`, `build_catalog`

## Direct imports

- `__future__: annotations`
- `collections: OrderedDict`
- `csv`
- `json`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.station_index: normalize_station_index`
- `rdr.storage: DATA, save_json`
- `re`

## Calls

`OrderedDict`, `csv.DictReader`, `dms`, `json.loads`, `normalize_station_index`, `re.findall`, `re.split`, `resolve_runtime_path`, `save_json`, `watercourse`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L65: save_json(resolve_runtime_path(DATA / 'processed/station_master.json'), result)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/catalog.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
