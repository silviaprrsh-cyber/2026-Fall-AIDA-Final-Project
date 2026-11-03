"""Source-specific archive paths and read-only resolution of pre-migration references."""
from project_paths import resolve_runtime_path, archive_relative
from functools import lru_cache
import json
from pathlib import Path
from urllib.parse import urlsplit

from project_paths import ROOT, WORKSPACE
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
    path = ROOT / 'config/archive_paths.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def resolve_archived_path(value):
    """Resolve original provenance paths without changing archived response bytes."""
    path = Path(value)
    if path.is_absolute():
        relative = archive_relative(path.resolve(), ROOT).as_posix()
    else:
        relative = path.as_posix()
        if relative not in _relocations() and not relative.startswith('data/'):
            relative = 'data/' + relative
    if '..' in Path(relative).parts:
        raise ValueError('Reference must remain inside the project')
    resolved = (resolve_runtime_path(ROOT / _relocations().get(relative, relative))).resolve()
    if not resolved.is_relative_to(WORKSPACE):
        raise ValueError('Reference must remain inside the project')
    return resolved
