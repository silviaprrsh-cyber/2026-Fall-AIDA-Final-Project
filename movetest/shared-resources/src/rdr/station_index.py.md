# `station_index.py`

File: `shared-resources/src/rdr/station_index.py`

## Purpose

Normalize the provider's station-index CSV without changing its original bytes.

## Defined functions/classes

`parse_provider_line`, `normalize_station_index`

## Direct imports

- `csv`
- `hashlib`
- `io`
- `pathlib: Path`
- `rdr.storage: save_json`

## Calls

`Path`, `csv.reader`, `csv.writer`, `hashlib.sha256`, `hashlib.sha256(body).hexdigest`, `hashlib.sha256(raw).hexdigest`, `io.StringIO`, `parse_provider_line`, `save_json`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L97: temporary.write_bytes(body)`
- `L99: save_json(destination.with_suffix(destination.suffix + '.meta.json'), {'normalization_version': 1, 'source_path': source.as_posix(), 'source_sha256': hashlib.sha256(raw).hexdigest(), 'normalized_sha256': hashlib.sha256(body).hexdigest(), 'rows': len(rows), 'columns': len(HEADER), 'rule': 'Preserve literal name quotes, remove empty surplus columns, `

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/station_index.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
