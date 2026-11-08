# AIDA 2362 — GIS

Purpose: map monitoring coverage and requested estimation locations from Dickson Dam to validation station 05CC002. QGIS is the core tool.

Code: `src/`; survey, river-network and derived spatial inputs: `data/`. The portable project is `project/dickson_to_joffre.qgz`; the reviewed map is `outputs/Overhead view.pdf`. Hydrometric/weather inputs owned by AIDA 2156 are referenced through the shared resolver. Source metadata and CRS checks remain in data records; permissions do not imply unrestricted redistribution.

Open the project in QGIS. Blue/yellow indicate archived observation availability, red indicates prediction targets, and green areas are schematic weather associations, not watershed boundaries. Still required: decision baseline, changed-setting sensitivity, exact text/table equivalent, complete geometry/CRS/ID checks, governance and portable final submission. AI assisted code organization; the map alone does not establish valid flood estimates.

## Current map inventory and use

The 2026-11-05 check confirms 5 prediction points (P01–P05), 4 river gauges (05CB007, 05CB001, 05CC007, 05CC002), 2 historical/lake references (05CC003, 05CC012), 1 weather station, 229 section lines and 4 river features. Blue/yellow status refers to the archived availability review, not a fresh station query. The centerline endpoint is projected from the official 05CC002 coordinate, about 69 m away; the station coordinate itself is unchanged.

Open [the working project](project/dickson_to_joffre.qgz) in QGIS 3.44.14. Both `Simple OSM overview` and `Overhead view` layouts remain. OSM tiles need network access. The [presentation PDF](outputs/Overhead%20view.pdf) and [PNG preview](project/map_overview.png) were updated and visually checked on 2026-11-08, showing P01–P05 and endpoint 05CC002. The prior Joffre PDF remains in data/processed/scope_history/Overhead_view_Joffre.pdf.

Reproduce the current map by opening `project/dickson_to_joffre.qgz` in QGIS, or run `src/gis_tools/export_scope_layout.py` with QGIS python-qgis-ltr.bat to export the saved layout. `build_prediction_points.py` regenerates P01-P05 from current configuration. Five retired legacy builders, one-time clipping and layout-refresh scripts and their notes are archived in `data/processed/scope_history/retired_gis_tools_20261108.zip`. Current reproduction requires the supplied QGIS project and layers; this is not a new one-command GIS rebuild from raw sources. Previous scope backups and validation reports remain available.

## Project modification history — 2026-11-04 (verified 2026-11-05)

The active movetest reach now ends at Red Deer station 05CC002. Retain P01–P05; remove P06–P11 and downstream Blindman/Waskasoo map inputs. The selected project data provide no comparable downstream observation constraint to validate the continuation to P11. This reduction limits unsupported extrapolation; it does not establish accuracy at retained targets. The filename `dickson_to_joffre.qgz` is retained for compatibility, but its layers and displayed endpoint now use 05CC002.

Source archives, previous model results and satellite acquisitions are retained. Existing `Overhead view.pdf`, `map_overview.png` and earlier validation reports are historical Joffre snapshots, not updated exports. Current GIS checks are `courses/AIDA-2362/data/reports/scope_05CC002.json` and `qgis_scope_05CC002.json`. The model already ends at 05CC002: its M06 link from P05 to the validation station remains; M06 is not prediction point P06. This map update does not retrain the model or replace PostgreSQL snapshots.
