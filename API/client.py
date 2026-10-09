"""HTTP acquisition with source-separated archives and original provenance."""
import hashlib
import json
import requests
from rdr.storage import DATA, now, save_json, log
from rdr.paths import source_relative_path


def fetch(url, relative_path, params=None, *, reuse=True, timeout=45):
    """Save original bytes and provenance. Static/snapshot reads are cached by path.

    Failed HTTP responses are also retained. No credentials or API keys are used.
    """
    path = DATA / source_relative_path(url, relative_path)
    meta_path = path.with_suffix(path.suffix + '.meta.json')
    requested_url = requests.Request('GET', url, params=params).prepare().url
    if reuse and path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding='utf-8'))
        if meta.get('status') == 200 and meta.get('url') == requested_url:
            return path
    path.parent.mkdir(parents=True, exist_ok=True)
    started = now()
    try:
        response = requests.get(url, params=params, timeout=(15, timeout),
                                headers={'User-Agent': 'RedDeerRiverAcademicProject/0.1'})
        body = response.content
        path.write_bytes(body)
        meta = {'url': response.url, 'requested_at_utc': started, 'received_at_utc': now(),
                'status': response.status_code, 'content_type': response.headers.get('Content-Type'),
                'last_modified': response.headers.get('Last-Modified'),
                'etag': response.headers.get('ETag'), 'bytes': len(body),
                'sha256': hashlib.sha256(body).hexdigest(), 'path': str(path.relative_to(DATA))}
        save_json(meta_path, meta)
        log(meta)
        response.raise_for_status()
        return path
    except Exception as exc:
        log({'url': url, 'requested_at_utc': started, 'error': str(exc), 'path': str(path)})
        raise


def get_json(url, relative_path, params=None, **kwargs):
    path = fetch(url, relative_path, params, **kwargs)
    obj = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(obj, dict) and 'error' in obj:
        raise ValueError(f'{url}: {obj["error"]}')
    return obj
