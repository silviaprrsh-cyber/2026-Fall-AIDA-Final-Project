# `download_tributary_history.py`

The model-history station list also covers mainstem and lake stations. Download all five with `python -B run.py -m API.download_tributary_history --candidates config/model_history_stations.json`. Intermediate numberMatched values are recorded because the provider can report page-dependent counts. Completion requires terminal pagination, unique ordered station records and a final total equal to the first-page count. Original pages and response metadata are retained under the source's raw/tributary_history/run directory.

File: `API/download_tributary_history.py`

## Purpose

Archive HYDAT station metadata and complete paged daily records once.

## Defined functions/classes

`acquire`, `station_history`, `main`

## Direct imports

- `API.client: fetch`
- `argparse`
- `concurrent.futures: ThreadPoolExecutor`
- `datetime: datetime, timezone`
- `json`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `time`
- `urllib.parse: urlsplit`

## Calls

`Path`, `ThreadPoolExecutor`, `acquire`, `archive_relative`, `argparse.ArgumentParser`, `datetime.now`, `datetime.now(timezone.utc).strftime`, `fetch`, `json.dumps`, `json.loads`, `main`, `resolve_runtime_path`, `station_history`, `time.sleep`, `urlsplit`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L112: (directory / 'download_manifest.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/download_tributary_history.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
