# `render_qgis_project.py`

File: `courses/AIDA-2362/src/gis_tools/render_qgis_project.py`

## Purpose

Render a simple OSM-backed station/section map using installed QGIS.

Source-separated vectors and display-only weather areas are local. The basemap
connector in API/qgis_basemap.py requests only this overview's visible tiles.

## Defined functions/classes

`sha`, `main`

## Direct imports

- `API.qgis_basemap: create_osm_layer`
- `argparse`
- `hashlib`
- `json`
- `os`
- `pathlib: Path`
- `project_paths: ROOT`
- `project_paths: resolve_runtime_path, archive_relative`
- `qgis.PyQt.QtCore: QSettings`
- `qgis.PyQt.QtGui: QColor, QFont, QFontDatabase`
- `qgis.core: Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsReferencedRectangle, QgsNetworkAccessManager, QgsMarkerSymbol, QgsLineSymbol, QgsFillSymbol, QgsSingleSymbolRenderer, QgsTextFormat, QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel, QgsLayoutPoint, QgsLayoutSize, QgsLayoutExporter, QgsSettingsTree, QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextBufferSettings`
- `sys`

## Calls

`Path`, `QColor`, `QFont`, `QFontDatabase.addApplicationFont`, `QSettings.setDefaultFormat`, `QSettings.setPath`, `QgsApplication`, `QgsApplication.setAuthDatabaseDirPath`, `QgsCoordinateReferenceSystem`, `QgsCoordinateTransform`, `QgsFillSymbol.createSimple`, `QgsLayoutExporter`, `QgsLayoutExporter.ImageExportSettings`, `QgsLayoutItemLabel`, `QgsLayoutItemMap`, `QgsLayoutPoint`, `QgsLayoutSize`, `QgsLineSymbol.createSimple`, `QgsMarkerSymbol.createSimple`, `QgsNetworkAccessManager.removeReplyPreprocessor`, `QgsNetworkAccessManager.removeRequestPreprocessor`, `QgsPalLayerSettings`, `QgsPrintLayout`, `QgsProject.instance`, `QgsReferencedRectangle`, `QgsSettingsTree.treeRoot`, `QgsSettingsTree.treeRoot().childNode`, `QgsSingleSymbolRenderer`, `QgsTextBufferSettings`, `QgsTextFormat`, `QgsVectorLayer`, `QgsVectorLayerSimpleLabeling`, `argparse.ArgumentParser`, `create_osm_layer`, `hashlib.file_digest`, `hashlib.file_digest(stream, 'sha256').hexdigest`, `json.dumps`, `json.loads`, `label`, `main`, `os.environ.get`, `os.environ.setdefault`, `resolve_runtime_path`, `sha`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L214: exporter.exportToImage(str(folder / 'map_overview.png'), settings)`
- `L233: (folder / 'qgis_validation.json').write_text(json.dumps(report, indent=2), encoding='utf-8')`
- `L217: project.write()`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `scripts/render_qgis_project.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
