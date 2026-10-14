"""Source-specific archive paths and read-only resolution of pre-migration references."""
from functools import lru_cache
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def source_for_url(url):
    parsed = urlsplit(url)
    host, path = parsed.hostname or '', parsed.path.lower()
    if host == 'api.weather.gc.ca':
        if '/hydrometric-' in path:
            return 'eccc_hydrometric_geomet'
        if '/swob-' in path or '/climate-' in path:
            return 'eccc_weather_geomet'
        return 'eccc_geomet_catalog'
    if host == 'dd.weather.gc.ca':
        if '/hydrometric/' in path:
            return 'eccc_hydrometric_datamart'
        if '/observations/' in path:
            return 'eccc_weather_datamart'
    if host == 'wateroffice.ec.gc.ca':
        return 'eccc_wateroffice'
    if host == 'eccc-msc.github.io':
        return 'eccc_documentation'
    if host == 'geospatial.alberta.ca':
        return 'alberta_geospatial'
    if host in {'open.alberta.ca', 'www.alberta.ca', 'alberta.ca'}:
        return 'alberta_flood_studies'
    if host == 'ftp.maps.canada.ca':
        return 'nrcan_nhn'
    if host == 'overpass-api.de':
        return 'openstreetmap'
    if host.endswith('.dataspace.copernicus.eu'):
        return 'copernicus_sentinel2'
    raise ValueError(f'Unregistered data source host: {host}')


def source_relative_path(url, relative_path):
    """Reject mixed-source writes, absolute paths and traversal outside data/."""
    relative = Path(relative_path)
    if relative.is_absolute() or relative.drive or relative.root or '..' in relative.parts:
        raise ValueError('Archive path must be relative and remain inside data/')
    source = source_for_url(url)
    if relative.parts and relative.parts[0] == 'sources':
        if len(relative.parts) < 3 or relative.parts[1] != source:
            raise ValueError('Archive path does not match the URL source')
        return relative.as_posix()
    return (Path('sources') / source / relative).as_posix()


@lru_cache(maxsize=1)
def _relocations():
    path = DATA / 'reports/layout_migration/manifest.json'
    if not path.exists():
        return {}
    records = json.loads(path.read_text(encoding='utf-8'))['files']
    return {r['old_path']: r['new_path'] for r in records}


def resolve_archived_path(value):
    """Resolve original provenance paths without changing archived response bytes."""
    path = Path(value)
    if path.is_absolute():
        relative = path.resolve().relative_to(ROOT).as_posix()
    else:
        relative = path.as_posix()
        if relative not in _relocations() and not relative.startswith('data/'):
            relative = 'data/' + relative
    if '..' in Path(relative).parts:
        raise ValueError('Reference must remain inside the project')
    resolved = (ROOT / _relocations().get(relative, relative)).resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError('Reference must remain inside the project')
    return resolved
