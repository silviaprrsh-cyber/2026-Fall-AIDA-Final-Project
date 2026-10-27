# `query_prediction_landmarks.py`

File: `API/query_prediction_landmarks.py`

## Purpose

Archive road and footbridge geometry for the selected prediction reach once.

## Defined functions/classes

`main`

## Direct imports

- `API.client: fetch`
- `argparse`
- `datetime: datetime, timezone`

## Calls

`argparse.ArgumentParser`, `datetime.now`, `datetime.now(timezone.utc).strftime`, `fetch`, `main`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/query_prediction_landmarks.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
