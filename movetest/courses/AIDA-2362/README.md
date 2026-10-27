# AIDA 2362 — GIS

Purpose: map monitoring coverage and requested estimation locations from Dickson Dam to Joffre Bridge. QGIS is the core tool.

Code: `src/`; survey, river-network and derived spatial inputs: `data/`. The portable project is `project/dickson_to_joffre.qgz`; the reviewed map is `outputs/Overhead view.pdf`. Hydrometric/weather inputs owned by AIDA 2156 are referenced through the shared resolver. Source metadata and CRS checks remain in data records; permissions do not imply unrestricted redistribution.

Open the project in QGIS. From the root, `python -B run.py verify` checks local paths; QGIS Python can run `run.py -m gis_tools.check_project` to validate loading. Blue/yellow indicate archived observation availability, red indicates prediction targets, and green areas are schematic weather associations, not watershed boundaries. Still required: decision baseline, changed-setting sensitivity, exact text/table equivalent, complete geometry/CRS/ID checks, governance and portable final submission. AI assisted code organization; the map alone does not establish valid flood estimates.
