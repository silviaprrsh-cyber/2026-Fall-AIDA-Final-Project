"""Bounded first discovery: public metadata and one sample, cached under data/."""
import concurrent.futures
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from API.client import fetch

API = 'https://api.weather.gc.ca'
GIS = 'https://geospatial.alberta.ca/titan/rest/services/environment'
JOBS = {
    'collections.json': API + '/collections?f=json',
    'hydrometric_stations.json': API + '/collections/hydrometric-stations/items?bbox=-117.5,50,-109.5,53.5&limit=10000&f=json',
    'hydrometric_sample.json': API + '/collections/hydrometric-realtime/items?STATION_NUMBER=05CC002&sortby=-DATETIME&limit=12&f=json',
    'climate_stations.json': API + '/collections/climate-stations/items?bbox=-117.5,50,-109.5,53.5&limit=10000&f=json',
    'climate_sample.json': API + '/collections/climate-hourly/items?CLIMATE_IDENTIFIER=3025484&sortby=-LOCAL_DATE&limit=12&f=json',
    'water_network.json': GIS + '/base_water_feature/MapServer?f=pjson',
    'watersheds.json': GIS + '/watersheds/MapServer?f=pjson',
    'huc_watersheds.json': GIS + '/hydrologic_unit_code_watersheds_of_Alberta_v2/MapServer?f=pjson',
    'flood_hazard.json': GIS + '/flood_hazard/MapServer?f=pjson',
    'station_index.html': 'https://wateroffice.ec.gc.ca/station_metadata/reference_index_e.html?stnIndex=820',
    'flood_studies.html': 'https://www.alberta.ca/final-flood-maps',
    'hydrometric_docs.html': 'https://eccc-msc.github.io/open-data/msc-data/obs_hydrometric/readme_hydrometric-datamart_en/',
    'environment_services.json': GIS + '?f=pjson',
}

def run(item):
    name, url = item
    try:
        p = fetch(url, 'raw/discovery/' + name)
        return name, p.stat().st_size, 'OK'
    except Exception as exc:
        return name, 0, str(exc)

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(run, JOBS.items()):
            print(*result, flush=True)
