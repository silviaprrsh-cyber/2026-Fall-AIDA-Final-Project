"""Resolve all runtime data/config paths inside this independent workspace."""
from pathlib import Path
from functools import lru_cache
import json

WORKSPACE = Path(__file__).resolve().parents[2]
ROOT = WORKSPACE / 'shared-resources'
DATA = ROOT / 'data'


@lru_cache(maxsize=1)
def data_routes():
    """Map archived logical prefixes to their single course-owned location."""
    rows = json.loads((ROOT/'config/data_layout.json').read_text(encoding='utf-8'))
    return sorted(((Path(k), WORKSPACE/v) for k, v in rows.items()),
                  key=lambda item: -len(item[0].parts))


def resolve_runtime_path(path):
    """Route old archive references without modifying original response bytes."""
    path = Path(path)
    if path.is_relative_to(ROOT/'courses'):
        return require_local(WORKSPACE/path.relative_to(ROOT))
    if path.is_relative_to(DATA/'courses'):
        return require_local(WORKSPACE/path.relative_to(DATA))
    if not path.is_relative_to(DATA):
        return path
    relative = path.relative_to(DATA)
    for prefix, target in data_routes():
        if relative.is_relative_to(prefix):
            return require_local(target/relative.relative_to(prefix))
    return require_local(path)


@lru_cache(maxsize=8192)
def archive_relative(path, base):
    """Preserve portable logical provenance for archives across course roots."""
    path, base = Path(path), Path(base)
    if path.is_relative_to(base):
        return path.relative_to(base)
    for prefix, target in data_routes():
        if path.is_relative_to(target):
            return (DATA/prefix/path.relative_to(target)).relative_to(base)
    return path.relative_to(base)


def require_local(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(WORKSPACE):
        raise ValueError('Runtime path must stay inside this project')
    return resolved


def is_gis_output_path(path):
    """Allow GIS work products and the single final handoff directory only."""
    resolved = require_local(path)
    return (resolved.is_relative_to(WORKSPACE/'courses/AIDA-2362/data/processed')
            or resolved == WORKSPACE/'courses/AIDA-2362/project')
