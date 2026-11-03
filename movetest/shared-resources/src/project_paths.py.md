# `project_paths.py`

`shared-resources/src/project_paths.py`

Resolve course data locations and restrict GIS output paths to derived data or the single final project.

## Imports

- `from pathlib import Path`
- `from functools import lru_cache`
- `import json`

## Calls

`Path`, `ValueError`, `data_routes`, `json.loads`, `len`, `lru_cache`, `require_local`, `sorted`

## File outputs

No direct file writes; invoked modules own their outputs.
