"""Check package isolation, copied inputs and portable GIS layer references."""
from project_paths import resolve_runtime_path, archive_relative
import ast
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
from project_paths import DATA, ROOT, WORKSPACE, require_local


def main():
    modules = ['API.collector', 'API.snapshot_scope', 'API.validate_satellite_once',
               'rdr.storage', 'rdr.paths', 'rdr_eda.etl', 'rdr_eda.rainfall', 'rdr_eda.hydraulics',
               'rdr_gis.spatial', 'rdr_gis.catalog', 'gis_tools.build_scoped_qgis',
               'gis_tools.build_prediction_points', 'eda_tools.prepare_tributary_history',
               'cv_tools.inspect_archive']
    locations = {}
    for name in modules:
        module = importlib.import_module(name)
        locations[name] = require_local(module.__file__).relative_to(WORKSPACE).as_posix()
        if hasattr(module, 'ROOT'): assert module.ROOT == ROOT, name
        if hasattr(module, 'DATA'): assert module.DATA == DATA, name
    parsed = []
    for folder in ['API', 'shared-resources/src', 'courses']:
        for p in (WORKSPACE/folder).rglob('*.py'):
            ast.parse(p.read_text(encoding='utf-8-sig'), filename=str(p))
            parsed.append(p.relative_to(WORKSPACE).as_posix())
    required = ['processed/station_master.json', 'processed/weather_links.json',
                'processed/etl/profiles.json', 'processed/etl/sections.json',
                'processed/tributary_history_20261012/station_summary.json']
    for rel in required: assert (resolve_runtime_path(DATA/rel)).is_file(), rel
    for p in (resolve_runtime_path(ROOT/'config')).glob('*.json'): json.loads(p.read_text(encoding='utf-8'))
    qgz = resolve_runtime_path(DATA/'processed/qgis_dickson_joffre_20261012/dickson_to_joffre.qgz')
    with zipfile.ZipFile(qgz) as archive:
        xml = ET.fromstring(archive.read(next(n for n in archive.namelist() if n.endswith('.qgs'))))
    layers = []
    for layer in xml.findall('.//projectlayers/maplayer'):
        provider = layer.findtext('provider')
        source = layer.findtext('datasource') or ''
        if provider == 'wms':
            layers.append({'provider': provider, 'source': source, 'network_basemap_not_requested': True})
            continue
        rel = source.split('|')[0]
        resolved = require_local(qgz.parent/rel)
        assert resolved.exists(), str(resolved)
        layers.append({'provider': provider, 'source': source, 'exists': True})
    report = {'checked_at_utc': datetime.now(timezone.utc).isoformat(), 'module_locations': locations,
              'python_files_parsed': len(parsed), 'qgis_layers': layers,
              'qgis_check': 'XML local-source resolution only; GUI rendering not asserted',
              'runtime_root': ROOT.relative_to(WORKSPACE).as_posix(), 'passed': True}
    output = WORKSPACE/'shared-resources/results/path_validation.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
