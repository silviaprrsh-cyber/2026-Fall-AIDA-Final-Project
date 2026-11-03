# `render_qgis_project.py`

`courses/AIDA-2362/src/gis_tools/render_qgis_project.py`

Render GIS layers into a project and map; may fetch OSM tiles and overwrite generated layouts. The final project is an allowed output location.

## Imports

- `from project_paths import resolve_runtime_path, archive_relative`
- `import argparse`
- `import hashlib`
- `import json`
- `import os`
- `from pathlib import Path`
- `import sys`
- `from qgis.core import Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsReferencedRectangle, QgsNetworkAccessManager, QgsMarkerSymbol, QgsLineSymbol, QgsFillSymbol, QgsSingleSymbolRenderer, QgsTextFormat, QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel, QgsLayoutPoint, QgsLayoutSize, QgsLayoutExporter, QgsSettingsTree, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextBufferSettings`
- `from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase`
- `from qgis.PyQt.QtCore import QSettings`
- `from project_paths import ROOT, is_gis_output_path`
- `from API.qgis_basemap import create_osm_layer`

## Calls

`Path`, `QColor`, `QFont`, `QgsApplication`, `QgsCoordinateReferenceSystem`, `QgsCoordinateTransform`, `QgsLayoutExporter`, `QgsLayoutItemLabel`, `QgsLayoutItemMap`, `QgsLayoutPoint`, `QgsLayoutSize`, `QgsPalLayerSettings`, `QgsPrintLayout`, `QgsReferencedRectangle`, `QgsSingleSymbolRenderer`, `QgsTextBufferSettings`, `QgsTextFormat`, `QgsVectorLayer`, `QgsVectorLayerSimpleLabeling`, `RuntimeError`, `ValueError`, `all`, `any`, `create_osm_layer`, `exporter.exportToImage`, `is_gis_output_path`, `json.dumps`, `json.loads`, `label`, `len`, `main`, `next`, `print`, `project.addMapLayer`, `project.clear`, `project.layerTreeRoot`, `project.layoutManager`, `project.layoutManager().addLayout`, `project.mapLayers`, `project.mapLayers().values`, `project.read`, `project.setBackgroundColor`, `project.setCrs`, `project.setFileName`, `project.setFilePathStorage`, `project.setTitle`, `project.viewSettings`, `project.viewSettings().setDefaultViewExtent`, `project.write`, `project.writeEntry`, `resolve_runtime_path`, `sha`, `sorted`, `str`

## File outputs

- `exporter.exportToImage(str(folder / 'map_overview.png'), settings)`
- `(folder / 'qgis_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`
- `project.write()`
