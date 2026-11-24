"""Export the saved Overhead view layout without rebuilding its map layers."""
import json
import os
from pathlib import Path
import shutil

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from qgis.core import (QgsApplication, QgsProject, QgsLayoutExporter, QgsLayoutItemLabel,
                       QgsSettingsTree, QgsLayoutItemScaleBar, QgsLayoutPoint)
from qgis.PyQt.QtGui import QFont, QFontDatabase


def main():
    workspace = Path(__file__).resolve().parents[4]
    course = workspace / 'courses/AIDA-2362'
    profile = course / 'data/state/qgis_scope_profile'
    os.environ['QGIS_AUTH_DB_DIR_PATH'] = str(profile)
    app = QgsApplication([], False, str(profile), 'external')
    QgsApplication.setAuthDatabaseDirPath(str(profile))
    app.initQgis()
    cache = course / 'data/sources/openstreetmap/raw/qgis_cache'
    cache.mkdir(parents=True, exist_ok=True)
    QgsSettingsTree.treeRoot().childNode('cache').childSetting('directory').setValue(str(cache))
    for name in ('arial.ttf', 'arialbd.ttf', 'seguisym.ttf'):
        font = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / name
        if font.exists():
            QFontDatabase.addApplicationFont(str(font))
    app.setFont(QFont('Arial', 10))
    project = QgsProject.instance()
    assert project.read(str(course / 'project/dickson_to_joffre.qgz'))
    assert all(layer.isValid() for layer in project.mapLayers().values())
    layout = project.layoutManager().layoutByName('Overhead view')
    assert layout is not None
    for item in layout.items():
        if isinstance(item, QgsLayoutItemLabel):
            item.setText(item.text().replace('Map date: 2026-11-04', 'Map date: 2026-11-08'))
        elif isinstance(item, QgsLayoutItemScaleBar):
            page_width = layout.pageCollection().page(0).sizeWithUnits().width()
            item.attemptMove(QgsLayoutPoint(page_width - item.rect().width() - 18, item.pos().y()))
    layout.refresh()
    assert project.write()
    pdf = course / 'outputs/Overhead view.pdf'
    backup = course / 'data/processed/scope_history/Overhead_view_Joffre.pdf'
    if pdf.exists() and not backup.exists():
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf, backup)
    png = course / 'project/map_overview.png'
    exporter = QgsLayoutExporter(layout)
    image_settings = QgsLayoutExporter.ImageExportSettings()
    image_settings.dpi = 200
    result = exporter.exportToImage(str(png), image_settings)
    assert result == QgsLayoutExporter.Success, ('PNG export failed', result)
    pdf_settings = QgsLayoutExporter.PdfExportSettings()
    pdf_settings.dpi = 300
    result = exporter.exportToPdf(str(pdf), pdf_settings)
    assert result == QgsLayoutExporter.Success, ('PDF export failed', result)
    print(json.dumps({'png': str(png), 'pdf': str(pdf), 'layout': layout.name()}), flush=True)
    project.clear()
    app.exitQgis()


if __name__ == '__main__':
    main()
