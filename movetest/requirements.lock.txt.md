# `requirements.lock.txt`

File: `requirements.lock.txt`

Purpose: Python dependency specification; consumed by pip. Installation creates packages in the selected environment, not project data. A fresh installation has not been validated.

Declared entries: `ï»¿affine==3.0.1`, `attrs==26.1.0`, `beautifulsoup4==4.15.0`, `certifi==2026.7.22`, `cffi==2.1.1`, `charset-normalizer==3.5.1`, `click==8.5.0`, `cryptography==50.0.1`, `idna==3.20`, `numpy==2.5.3`, `packaging==26.3`, `pillow==12.3.0`, `pika==1.4.4`, `pycparser==3.0`, `pymupdf==1.28.2`, `pyogrio==0.13.0`, `pyparsing==3.3.3`, `pypdf==6.19.0`, `pyproj==3.8.0`, `pyshp==3.1.6`, `rasterio==1.5.1`, `requests==2.34.2`, `shapely==2.1.2`, `soupsieve==2.10`, `typing_extensions==4.16.0`, `tzdata==2026.5`, `urllib3==2.8.0`

## Copy provenance

Manifest source: `template` / `requirements.lock.txt`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

No exact static code reference was identified; this does not mean the file is unused. QGIS/GDAL and dynamic directory scans may consume it.

This note describes existing files only; it does not run collection, processing or training.

PostgreSQL import and training views use psycopg with its binary wheel. The lock records psycopg and psycopg-binary 3.3.7.
