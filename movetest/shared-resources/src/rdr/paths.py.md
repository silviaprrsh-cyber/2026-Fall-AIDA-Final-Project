# `paths.py`

`shared-resources/src/rdr/paths.py`

Validate source archive names and resolve legacy references using config/archive_paths.json.

## Imports

- `from project_paths import resolve_runtime_path, archive_relative`
- `from functools import lru_cache`
- `import json`
- `from pathlib import Path`
- `from urllib.parse import urlsplit`
- `from project_paths import ROOT, WORKSPACE`

## Calls

`Path`, `ValueError`, `_relocations`, `archive_relative`, `json.loads`, `len`, `lru_cache`, `resolve_runtime_path`, `source_for_url`, `urlsplit`

## File outputs

No direct file writes; invoked modules own their outputs.
