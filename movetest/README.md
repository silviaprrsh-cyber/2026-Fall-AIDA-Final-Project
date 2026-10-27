# Red Deer River — split-code test workspace

This test copy separates the Dickson Dam–Joffre Bridge project into three courses. The original project and formal course repository remain separate.

| Course | Code | Data | Results |
|---|---|---|---|
| AIDA 2154 — CV | `courses/AIDA-2154/src/` | `courses/AIDA-2154/data/` — satellite images | `courses/AIDA-2154/outputs/` |
| AIDA 2156 — EDA | `courses/AIDA-2156/analysis/` | `courses/AIDA-2156/data/` — water, weather and historical series | `courses/AIDA-2156/output/` |
| AIDA 2362 — GIS | `courses/AIDA-2362/src/` | `courses/AIDA-2362/data/` — surveys, river networks and layers | `courses/AIDA-2362/project/` and `outputs/` |

`API/` contains acquisition code; `shared-resources/` contains shared code, configuration, tests and run-check results. Data are physically stored by course and source. Cross-course readers use `shared-resources/config/data_layout.json`; old provenance paths are resolved without rewriting raw responses.

From this folder, use the existing parent environment: `..\.venv\Scripts\python.exe -B run.py verify`, `run.py test`, `run.py status`, or `run.py cv-check` (same interpreter). Offline ETL: `..\.venv\Scripts\python.exe -B run.py -m eda_tools.run_etl --reuse-spatial`. QGIS tools require the QGIS Python environment. Fresh installation uses `requirements.lock.txt` but has not been verified.

This is code/data organization, not completed course analysis. Course READMEs list current evidence and missing required work. No acquisition or model training is started by these checks. AI assisted code restructuring and documentation; runnable checks support technical claims, not scientific validation. Inputs remain local and ignored; permission to use government data does not automatically permit redistribution. Submit each course separately through D2L according to its approved proposal and final brief.
