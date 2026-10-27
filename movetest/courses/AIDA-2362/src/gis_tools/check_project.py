"""Open copied GIS projects in QGIS without rendering or fetching map tiles."""
from project_paths import resolve_runtime_path, archive_relative
import json
import os
from pathlib import Path
import tempfile
from project_paths import WORKSPACE, DATA


def main():
    with tempfile.TemporaryDirectory(prefix='rdr_qgis_check_') as folder:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        os.environ['QGIS_CUSTOM_CONFIG_PATH'] = folder
        os.environ['QGIS_AUTH_DB_DIR_PATH'] = folder
        from qgis.core import QgsApplication, QgsProject
        app = QgsApplication([], False)
        app.initQgis()
        results = []
        try:
            for path in [resolve_runtime_path(DATA/'processed/qgis_dickson_joffre_20261012/dickson_to_joffre.qgz'),
                         WORKSPACE/'courses/AIDA-2362/project/dickson_to_joffre.qgz']:
                project = QgsProject()
                assert project.read(str(path)), path
                layers = [{'name': layer.name(), 'valid': layer.isValid(), 'provider': layer.providerType()}
                          for layer in project.mapLayers().values()]
                assert layers and all(row['valid'] for row in layers), layers
                results.append({'project': path.relative_to(WORKSPACE).as_posix(), 'layers': layers,
                                'layouts': len(project.layoutManager().layouts())})
                project.clear()
                del project
            output = WORKSPACE/'shared-resources/results/qgis_runtime_validation.json'
            output.write_text(json.dumps({'projects': results, 'passed': True,
                              'note': 'Projects opened without map rendering or basemap requests.'}, indent=2), encoding='utf-8')
            print('Both copied QGIS projects opened; all layers valid.')
        finally:
            app.exitQgis()


if __name__ == '__main__':
    main()
