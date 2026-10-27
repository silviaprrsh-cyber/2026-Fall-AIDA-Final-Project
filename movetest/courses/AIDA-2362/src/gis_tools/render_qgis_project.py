"""Render a simple OSM-backed station/section map using installed QGIS.

Source-separated vectors and display-only weather areas are local. The basemap
connector in API/qgis_basemap.py requests only this overview's visible tiles.
"""

from project_paths import resolve_runtime_path, archive_relative
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from qgis.core import (
    Qgis, QgsApplication, QgsProject, QgsVectorLayer, QgsCoordinateReferenceSystem,
    QgsCoordinateTransform, QgsReferencedRectangle, QgsNetworkAccessManager,
    QgsMarkerSymbol, QgsLineSymbol, QgsFillSymbol, QgsSingleSymbolRenderer,
    QgsTextFormat, QgsPrintLayout, QgsLayoutItemMap, QgsLayoutItemLabel,
    QgsLayoutPoint, QgsLayoutSize, QgsLayoutExporter, QgsSettingsTree,
    QgsPalLayerSettings, QgsVectorLayerSimpleLabeling, QgsTextBufferSettings,
)
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase
from qgis.PyQt.QtCore import QSettings

from project_paths import ROOT

from API.qgis_basemap import create_osm_layer


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", default="data/processed/qgis_dickson_joffre_20261012")
    args = parser.parse_args()
    folder = (resolve_runtime_path(ROOT / args.folder)).resolve()
    if not folder.is_relative_to((resolve_runtime_path(ROOT / "data/processed")).resolve()):
        raise ValueError("Folder must be inside data/processed")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    profile = resolve_runtime_path(ROOT / "data/state/qgis_map_render_profile")
    profile.mkdir(parents=True, exist_ok=True)
    cache = resolve_runtime_path(ROOT / "data/sources/openstreetmap/raw/qgis_cache")
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["QGIS_AUTH_DB_DIR_PATH"] = str(profile)
    QSettings.setDefaultFormat(QSettings.IniFormat)
    QSettings.setPath(QSettings.IniFormat, QSettings.UserScope, str(profile))
    app = QgsApplication([], False, str(profile), "external")
    QgsApplication.setAuthDatabaseDirPath(str(profile))
    app.initQgis()
    cache_settings = QgsSettingsTree.treeRoot().childNode("cache")
    cache_settings.childSetting("directory").setValue(str(cache))
    for name in ("arial.ttf", "arialbd.ttf", "seguisym.ttf"):
        font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name
        if font_path.exists():
            QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Arial", 10))
    project = QgsProject.instance()
    project_file = folder / manifest.get("project_filename", "red_deer_sources.qgz")
    project.setFileName(str(project_file))
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    project.setTitle(manifest.get("project_title", "Red Deer River — stations and cross-sections"))
    display_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    project.setCrs(display_crs)
    project.setBackgroundColor(QColor("white"))
    root = project.layerTreeRoot()
    groups = {}
    loaded, checks = [], []
    order = {"prediction": -1, "weather": 0, "hydro": 1, "uncertain": 1, "historical": 1.5, "sections": 2, "weather_areas": 4}
    if "project_filename" in manifest:
        order["network"] = 3
    for entry in manifest["layers"]:
        path = folder / entry["path"]
        if sha(path) != entry["sha256"]:
            raise ValueError(f"Layer changed after export: {path}")
        style = entry["style"]
        if style not in order or entry["source"] == "eccc_hydrometric_datamart":
            continue
        layer = QgsVectorLayer(str(path), entry["title"], "ogr")
        if not layer.isValid() or layer.featureCount() != entry["count"]:
            raise ValueError(f"QGIS loading/count failure: {path}")
        assert layer.crs().authid() in {"EPSG:4326", "OGC:CRS84"}
        if style in {"hydro", "uncertain", "weather"}:
            symbol = QgsMarkerSymbol.createSimple({
                "name": "triangle" if style == "weather" else "circle",
                "color": "#147b54" if style == "weather" else "#1267ab",
                "outline_color": "white", "outline_width": "0.3",
                "size": "3.8" if style == "weather" else "2.4",
            })
        elif style == "prediction":
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle", "color": "#e31922", "outline_color": "#ffffff",
                "outline_width": "0.35", "size": "3.2",
            })
        elif style == "historical":
            symbol = QgsMarkerSymbol.createSimple({
                "name": "circle", "color": "#ffdf00", "outline_color": "#252525",
                "outline_width": "0.3", "size": "2.4",
            })
        elif style == "sections":
            symbol = QgsLineSymbol.createSimple({"line_color": "#d65039", "line_width": "0.42"})
        elif style == "network":
            symbol = QgsLineSymbol.createSimple({"line_color": "#368cba", "line_width": "0.35"})
        else:
            symbol = QgsFillSymbol.createSimple({"color": "40,160,75,60", "outline_color": "0,0,0,255",
                                                  "outline_width": "0.6", "outline_width_unit": "MM",
                                                  "joinstyle": "round"})
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setLabelsEnabled(False)
        if layer.fields().indexFromName("map_label") >= 0:
            label_settings = QgsPalLayerSettings()
            label_settings.fieldName = "map_label"
            label_format = QgsTextFormat()
            label_format.setFont(QFont("Arial", 8))
            label_format.setSize(8)
            label_format.setColor(QColor("#3b3420"))
            buffer = QgsTextBufferSettings()
            buffer.setEnabled(True)
            buffer.setSize(0.8)
            buffer.setColor(QColor("white"))
            label_format.setBuffer(buffer)
            label_settings.setFormat(label_format)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
            layer.setLabelsEnabled(True)
        metadata = layer.metadata()
        metadata.setTitle(entry["title"])
        metadata.setAbstract("Source: " + entry["source"] + ". See feature attributes for provenance and datum status. "
                             "Weather areas are association schematics, not physical coverage. No flood risk is shown.")
        layer.setMetadata(metadata)
        project.addMapLayer(layer, False)
        group_key = entry["source"]
        if group_key not in groups:
            groups[group_key] = root.addGroup(group_key)
        groups[group_key].addLayer(layer).setExpanded(False)
        loaded.append((entry, layer))
        checks.append({"path": entry["path"], "qgis_valid": True, "qgis_count": layer.featureCount(),
                       "qgis_crs": layer.crs().authid(), "symbol": style})
    assert loaded
    osm, network, hooks = create_osm_layer()
    project.addMapLayer(osm, False)
    root.addLayer(osm).setExpanded(False)
    layers = [layer for entry, layer in sorted(loaded, key=lambda item: order[item[0]["style"]])] + [osm]
    root.setHasCustomLayerOrder(True)
    root.setCustomLayerOrder(layers)
    for group in groups.values():
        group.setExpanded(False)
    areas = next(layer for entry, layer in loaded if entry["style"] == "weather_areas")
    weather = next(layer for entry, layer in loaded if entry["style"] == "weather")
    conversion = QgsCoordinateTransform(areas.crs(), display_crs, project)
    extent = conversion.transformBoundingBox(areas.extent())
    extent.combineExtentWith(conversion.transformBoundingBox(weather.extent()))
    for entry, layer in loaded:
        if entry["style"] == "historical":
            extent.combineExtentWith(conversion.transformBoundingBox(layer.extent()))
    extent.scale(1.06)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent, display_crs))
    project.writeEntry("CopyrightLabel", "/Enabled", True)
    project.writeEntry("CopyrightLabel", "/Label", '© OpenStreetMap contributors')
    project.writeEntry("CopyrightLabel", "/Placement", 3)
    layout = QgsPrintLayout(project)
    layout.initializeDefaults()
    layout.setName("Simple OSM overview")
    layout.pageCollection().pages()[0].setPageSize(QgsLayoutSize(300, 210))
    project.layoutManager().addLayout(layout)

    def label(text, x, y, width, height, size=9, color="#233847", bold=False):
        item = QgsLayoutItemLabel(layout)
        item.setText(text)
        font = QFont("Arial", size)
        font.setBold(bold)
        fmt = QgsTextFormat()
        fmt.setFont(font)
        fmt.setSize(size)
        fmt.setColor(QColor(color))
        item.setTextFormat(fmt)
        item.setMargin(0)
        layout.addLayoutItem(item)
        item.attemptMove(QgsLayoutPoint(x, y))
        item.attemptResize(QgsLayoutSize(width, height))

    label("RED DEER RIVER", 7, 4, 150, 10, 17, bold=True)
    label(manifest.get("map_subtitle", "Stations and cross-sections"), 190, 6, 100, 7, 10)
    canvas = QgsLayoutItemMap(layout)
    layout.addLayoutItem(canvas)
    canvas.attemptMove(QgsLayoutPoint(7, 19))
    canvas.attemptResize(QgsLayoutSize(286, 170))
    canvas.setCrs(display_crs)
    canvas.setLayers(layers)
    canvas.setKeepLayerSet(True)
    canvas.zoomToExtent(extent)
    label("●  Recent water station" if "recency_legend" in manifest else "●  Water station", 8, 191, 47, 7, 8, "#1267ab")
    label("▲  Weather station", 57, 191, 48, 7, 9, "#147b54")
    label("—  Cross-section", 111, 191, 48, 7, 9, "#d65039")
    label("▧  Weather association area (schematic)", 162, 191, 126, 7, 9, "#387963")
    if any(entry["style"] == "prediction" for entry, _ in loaded):
        label("●  Prediction target", 8, 199, 51, 7, 8, "#e31922")
        label("●  Historical / lake reference", 62, 199, 72, 7, 8, "#6b5900")
        label("Blue: last 3 months; red: no estimates yet", 135, 199, 86, 7, 7, "#46525b")
    elif "recency_legend" in manifest:
        label("●  " + manifest["recency_legend"], 8, 199, 209, 7, 7, "#6b5900")
    elif any(entry["style"] == "historical" for entry, _ in loaded):
        label("●  Historical daily station (yellow)", 8, 199, 204, 7, 8, "#6b5900")
    else:
        label("Shading follows existing station links; it is not official weather coverage.", 8, 199, 194, 7, 8, "#596773")
    label("© OpenStreetMap contributors", 222, 199, 72, 7, 8, "#46525b")
    exporter = QgsLayoutExporter(layout)
    settings = QgsLayoutExporter.ImageExportSettings()
    settings.dpi = 150
    settings.exportMetadata = False
    result = exporter.exportToImage(str(folder / "map_overview.png"), settings)
    if result != QgsLayoutExporter.Success:
        raise RuntimeError(f"Map render failed: {result}")
    if not project.write():
        raise RuntimeError("Could not save QGIS project")
    project.clear()
    assert project.read(str(project_file))
    assert len(project.mapLayers()) == len(checks) + 1
    assert all(layer.isValid() for layer in project.mapLayers().values())
    report = {"qgis_version": Qgis.QGIS_VERSION, "layer_count": len(checks) + 1, "local_vector_layers": len(checks),
              "retained_geojson_files": len(manifest["layers"]), "project_reopened_successfully": True,
              "all_layers_valid_after_reopen": True, "project_display_crs": "EPSG:3857",
              "geojson_crs": "EPSG:4326", "relative_local_paths": True,
              "saved_print_layouts": 1, "checks": checks,
              "basemap": "OpenStreetMap standard XYZ; Internet required",
              "osm_requested_tiles_for_this_view": len(network["requested_urls"]),
              "osm_response_diagnostics": network["responses"],
              "project_sha256": sha(project_file),
              "overview_sha256": sha(folder / "map_overview.png")}
    (folder / "qgis_validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in {"checks", "osm_response_diagnostics"}}, indent=2))
    print("OSM response statuses:", sorted({str(r['status']) for r in network['responses']}))
    QgsNetworkAccessManager.removeRequestPreprocessor(hooks[0])
    QgsNetworkAccessManager.removeReplyPreprocessor(hooks[1])
    project.clear()
    app.exitQgis()


if __name__ == "__main__":
    main()
