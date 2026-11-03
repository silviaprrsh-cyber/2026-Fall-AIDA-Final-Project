# `requirements.txt`

File: `requirements.txt`

Purpose: Python dependency specification; consumed by pip. Installation creates packages in the selected environment, not project data. A fresh installation has not been validated.

Declared entries: `requests>=2.32,<3`, `pika>=1.3,<2`, `beautifulsoup4>=4.12,<5`, `shapely>=2.1,<3`, `pyproj>=3.7,<4`, `pypdf>=6,<7`, `pyshp>=3,<4`, `cryptography>=46,<51`, `pymupdf>=1.26,<2`, `pyogrio>=0.11,<1`, `numpy>=2,<3`, `rasterio>=1.4,<2`, `Pillow>=11,<13`, `tzdata>=2026.5`

## Copy provenance

Manifest source: `template` / `requirements.txt`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

No exact static code reference was identified; this does not mean the file is unused. QGIS/GDAL and dynamic directory scans may consume it.

This note describes existing files only; it does not run collection, processing or training.

PostgreSQL import and training views use psycopg with its binary wheel. The lock records psycopg and psycopg-binary 3.3.7.
