# `test_tributary_history.py`

File: `courses/AIDA-2156/tests/test_tributary_history.py`

## Purpose

Verify daily-data paging, identity checks and missing-value semantics offline.

## Defined functions/classes

`feature`, `HistoryTests`

## Direct imports

- `API: download_tributary_history`
- `csv`
- `eda_tools.prepare_tributary_history: normalize, summarize, write_csv`
- `json`
- `pathlib: Path`
- `tempfile`
- `unittest`
- `unittest.mock: patch`

## Calls

`Path`, `csv.DictReader`, `download.station_history`, `feature`, `json.dumps`, `normalize`, `patch.object`, `self.assertEqual`, `self.assertFalse`, `self.assertIsNone`, `self.assertRaises`, `self.assertTrue`, `self.page_result`, `summarize`, `tempfile.TemporaryDirectory`, `unittest.main`, `write_csv`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L60: path.write_text(json.dumps(page), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `tests/test_tributary_history.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
