from __future__ import annotations
from project_paths import resolve_runtime_path, archive_relative

import json
import threading
from datetime import datetime, timezone
from pathlib import Path


from project_paths import ROOT
DATA = ROOT / 'data'
_LOCK = threading.Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(path)


def log(event):
    path = resolve_runtime_path(DATA / 'logs' / 'requests.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, path.open('a', encoding='utf-8') as out:
        out.write(json.dumps(event, ensure_ascii=False) + '\n')
