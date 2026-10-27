# `test_station_index.py`

File: `shared-resources/tests/test_station_index.py`

## Purpose

Verify lossless normalization of the provider-specific station index.

## Defined functions/classes

`StationIndexTests`

## Direct imports

- `csv`
- `hashlib`
- `io`
- `json`
- `pathlib: Path`
- `rdr.station_index: HEADER, normalize_station_index, parse_provider_line`
- `tempfile`
- `unittest`

## Calls

`Path`, `csv.reader`, `csv.writer`, `csv.writer(buffer).writerow`, `hashlib.sha256`, `hashlib.sha256(body).hexdigest`, `hashlib.sha256(target.read_bytes()).hexdigest`, `io.StringIO`, `json.loads`, `normalize_station_index`, `parse_provider_line`, `self.assertEqual`, `self.assertFalse`, `self.assertRaises`, `self.assertTrue`, `tempfile.TemporaryDirectory`, `unittest.main`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L28: source.write_bytes(body)`
- `L46: source.write_text(','.join(HEADER) + '\n' + ','.join(['05CA009'] + [''] * 17 + ['unexpected']), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_station_index.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
