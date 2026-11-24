"""One-time official river geometry and survey/report acquisition; resumable."""
from project_paths import resolve_runtime_path, archive_relative
import concurrent.futures
import sys
from pathlib import Path
from urllib.parse import urlparse
from bs4 import BeautifulSoup


from rdr.storage import DATA, save_json
from API.client import fetch, get_json

GIS = 'https://geospatial.alberta.ca/titan/rest/services/environment'

def reports():
    resources = {}
    for p in (resolve_runtime_path(DATA / 'sources/alberta_flood_studies/raw/discovery')).glob('*flood*.html'):
        if p.name == 'flood_studies.html':
            continue
        soup = BeautifulSoup(p.read_bytes(), 'html.parser')
        for a in soup.select('a[href]'):
            url = a['href']
            title = a.get_text(' ', strip=True)
            if '/download/' not in url or not url.startswith('https://open.alberta.ca/'):
                continue
            if url not in resources:
                resources[url] = {'study': p.stem, 'title': title, 'url': url,
                                  'local_path': 'sources/alberta_flood_studies/static/flood_studies/' + p.stem + '/' + Path(urlparse(url).path).name}
    # Survey, hydraulics, channel geometry and revisions are in scope; retain
    # the full resource inventory without downloading unrelated risk inventories.
    def download(item):
        wanted = any(k in (item['title'] + ' ' + item['url']).lower()
                     for k in ['survey', 'hydraulic', 'channel-stability', 'addendum', 'didsbury-rosebud-2006', 'main-report'])
        item['download_selected'] = wanted
        if wanted:
            try:
                path = fetch(item['url'], item['local_path'], timeout=120)
                if path.read_bytes()[:4] != b'%PDF':
                    raise ValueError('Response is not a PDF')
                item['status'] = 'downloaded'
                item['bytes'] = path.stat().st_size
            except Exception as exc:
                item['status'] = 'failed'; item['error'] = str(exc)
        else:
            item['status'] = 'catalogued_not_selected'
        print(item['study'], item['title'], item['status'], flush=True)
        return item
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        result = list(pool.map(download, resources.values()))
    save_json(resolve_runtime_path(DATA / 'processed/flood_resource_inventory.json'), result)


def arc_query(layer, name, params):
    return get_json(GIS + '/' + layer + '/query', 'sources/alberta_geospatial/static/gis/' + name,
                    {'f': 'geojson', 'outFields': '*', 'outSR': 4326, **params}, timeout=120)


def initial_gis():
    jobs = [
        ('hydrologic_unit_code_watersheds_of_Alberta_v2/MapServer/3', 'huc4_red_deer.geojson', {'where': "UPPER(NAME) LIKE '%RED DEER%'"}),
        ('watersheds/MapServer/2', 'tertiary_red_deer.geojson', {'where': "WSC_SUBSUB LIKE '05C%'"}),
        ('base_water_feature/MapServer/107', 'mainstem_ids.json', {'where': "UPPER(NAME) = 'RED DEER RIVER'", 'returnIdsOnly': 'true', 'f': 'json'}),
    ]
    for layer, name, params in jobs:
        try:
            result = arc_query(layer, name, params)
            print(name, len(result.get('features',result.get('objectIds',[]))), flush=True)
        except Exception as exc:
            print(name, str(exc), flush=True)

if __name__ == '__main__':
    initial_gis()
    reports()
