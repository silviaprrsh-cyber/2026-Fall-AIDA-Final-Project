# `check_partner_precipitation.py`

File: `API/check_partner_precipitation.py`

## Purpose

Bounded, cached inspection of alternative partner weather feeds.

Inspect only AB-MAI candidates encountered in the original nearest-station
search, and one latest XML per station. Never schedule this discovery script.

## Defined functions/classes

`links`, `inspect_xml`, `main`

## Direct imports

- `API.client: fetch`
- `API.observations: precipitation`
- `bs4: BeautifulSoup`
- `concurrent.futures`
- `json`
- `pathlib: Path`
- `project_paths: resolve_runtime_path, archive_relative`
- `rdr.storage: DATA, save_json, now`
- `sys`
- `urllib.parse: urljoin`
- `xml.etree.ElementTree`

## Calls

`BeautifulSoup`, `ET.parse`, `ET.parse(path).getroot`, `archive_relative`, `concurrent.futures.ThreadPoolExecutor`, `fetch`, `inspect_xml`, `json.loads`, `links`, `main`, `now`, `precipitation`, `resolve_runtime_path`, `save_json`, `urljoin`

Static syntax evidence, not proof that every branch runs. Dynamic launcher dispatch depends on command arguments.

## Generated files / writes

- `L63: save_json(resolve_runtime_path(DATA / 'reports/partner_precipitation_check.json'), report)`

The write expressions show output names or variables. Variables, loops and caller-supplied paths are not fixed filenames. `DATA`/`ROOT` archive paths are routed by `project_paths.py` and `data_layout.json`.

## Copy provenance

Manifest source: `original` / `API/check_partner_precipitation.py`. The recorded input hash is not a guarantee that derived outputs still equal the initial copy.

This note describes existing files only; it does not run collection, processing or training.
