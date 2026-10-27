# `hydraulics.py`

File: `courses/AIDA-2156/analysis/rdr_eda/hydraulics.py`

## Purpose

Explicit-input screening calculations; no implicit datum, bank or runoff assumptions.

## Defined functions/classes

`section_geometry`, `screen_section`, `reach_storage`, `travel_time_seconds`, `routed_discharge`, `rating_level`

## Direct imports

- `API.observations: parse_time`
- `math: isfinite, hypot`

## Calls

`hypot`, `isfinite`, `parse_time`, `section_geometry`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `rdr/hydraulics.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
