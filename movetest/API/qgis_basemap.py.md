# `qgis_basemap.py`

File: `API/qgis_basemap.py`

## Purpose

Provide standard OpenStreetMap XYZ tiles for a requested QGIS view.

QGIS handles viewport requests and its normal HTTP cache. This module provides
no tile enumeration, prefetch, offline archive or acquisition scheduler.

## Defined functions/classes

`create_osm_layer`

## Direct imports

- `qgis.PyQt.QtNetwork: QNetworkRequest`
- `qgis.core: QgsNetworkAccessManager, QgsRasterLayer`
- `urllib.parse: quote`

## Calls

`QgsNetworkAccessManager.setReplyPreprocessor`, `QgsNetworkAccessManager.setRequestPreprocessor`, `QgsNetworkAccessManager.setTimeout`, `QgsRasterLayer`, `quote`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

No direct file-write call identified here. Imported functions may produce files; see their companion notes.

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/qgis_basemap.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
