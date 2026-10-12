"""Render a simple OSM-backed station/section map using installed QGIS.

Source-separated vectors and display-only weather areas are local. The basemap
connector in API/qgis_basemap.py requests only this overview's visible tiles.
"""

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
)
from qgis.PyQt.QtGui import QColor, QFont, QFontDatabase
from qgis.PyQt.QtCore import QSettings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from API.qgis_basemap import create_osm_layer


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", default="data/processed/qgis_layers_20261011")
    args = parser.parse_args()
    folder = (ROOT / args.folder).resolve()
    if not folder.is_relative_to((ROOT / "data/processed").resolve()):
        raise ValueError("Folder must be inside data/processed")
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    profile = ROOT / "data/state/qgis_map_render_profile"
    profile.mkdir(parents=True, exist_ok=True)
    cache = ROOT / "data/sources/openstreetmap/raw/qgis_cache"
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
    project.setFileName(str(folder / "red_deer_sources.qgz"))
    project.setFilePathStorage(Qgis.FilePathType.Relative)
    project.setTitle("Red Deer River — stations and cross-sections")
    display_crs = QgsCoordinateReferenceSystem("EPSG:3857")
    project.setCrs(display_crs)
    project.setBackgroundColor(QColor("white"))
    root = project.layerTreeRoot()
    groups = {}
    loaded, checks = [], []
    order = {"weather": 0, "hydro": 1, "uncertain": 1, "sections": 2, "weather_areas": 3}
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
        elif style == "sections":
            symbol = QgsLineSymbol.createSimple({"line_color": "#d65039", "line_width": "0.42"})
        else:
            symbol = QgsFillSymbol.createSimple({"color": "66,157,130,40", "outline_color": "48,120,104,105",
                                                  "outline_width": "0.3", "joinstyle": "round"})
        layer.setRenderer(QgsSingleSymbolRenderer(symbol))
        layer.setLabelsEnabled(False)
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
    assert len(loaded) == 8
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
    extent.scale(1.06)
    project.viewSettings().setDefaultViewExtent(QgsReferencedRectangle(extent, display_crs))
    project.writeEntry("CopyrightLabel", "/Enabled", True)
    project.writeEntry("CopyrightLabel", "/Label", '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>')
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
    label("Stations and cross-sections", 190, 6, 100, 7, 10)
    canvas = QgsLayoutItemMap(layout)
    layout.addLayoutItem(canvas)
    canvas.attemptMove(QgsLayoutPoint(7, 19))
    canvas.attemptResize(QgsLayoutSize(286, 170))
    canvas.setCrs(display_crs)
    canvas.setLayers(layers)
    canvas.setKeepLayerSet(True)
    canvas.zoomToExtent(extent)
    label("●  Water station", 8, 191, 47, 7, 9, "#1267ab")
    label("▲  Weather station", 57, 191, 48, 7, 9, "#147b54")
    label("—  Cross-section", 111, 191, 48, 7, 9, "#d65039")
    label("▧  Weather association area (schematic)", 162, 191, 126, 7, 9, "#387963")
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
    assert project.read(str(folder / "red_deer_sources.qgz"))
    assert len(project.mapLayers()) == 9
    assert all(layer.isValid() for layer in project.mapLayers().values())
    report = {"qgis_version": Qgis.QGIS_VERSION, "layer_count": 9, "local_vector_layers": 8,
              "retained_geojson_files": len(manifest["layers"]), "project_reopened_successfully": True,
              "all_layers_valid_after_reopen": True, "project_display_crs": "EPSG:3857",
              "geojson_crs": "EPSG:4326", "relative_local_paths": True,
              "saved_print_layouts": 1, "checks": checks,
              "basemap": "OpenStreetMap standard XYZ; Internet required",
              "osm_requested_tiles_for_this_view": len(network["requested_urls"]),
              "osm_response_diagnostics": network["responses"],
              "project_sha256": sha(folder / "red_deer_sources.qgz"),
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
