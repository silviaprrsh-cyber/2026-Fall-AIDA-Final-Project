# `rainfall.py`

File: `courses/AIDA-2156/analysis/rdr_eda/rainfall.py`

## Purpose

Interval-aware precipitation; no averaging of depths or double-counting rolling totals.

## Defined functions/classes

`finite`, `normalize_swob`, `aggregate_precipitation`

## Direct imports

- `API.observations: parse_time`
- `bisect: bisect_right`
- `datetime: timedelta, timezone`
- `math`
- `re`

## Calls

`bisect_right`, `finite`, `math.isfinite`, `parse_time`, `re.fullmatch`, `timedelta`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/rainfall.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
