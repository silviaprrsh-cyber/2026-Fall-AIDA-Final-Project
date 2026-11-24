import concurrent.futures
import sys
from pathlib import Path

from API.discover import API, GIS, run

JOBS = {
    'station_index_next.html': 'https://wateroffice.ec.gc.ca/station_metadata/reference_index_e.html?stnIndex=927',
    'station_index_all.csv': 'https://wateroffice.ec.gc.ca/station_metadata/reference_index_download_e.html',
    'stream_layer.json': GIS + '/base_water_feature/MapServer/107?f=pjson',
    'waterbody_layer.json': GIS + '/base_water_feature/MapServer/72?f=pjson',
    'watershed_layer.json': GIS + '/alberta_watersheds/MapServer?f=pjson',
    'tertiary_layer.json': GIS + '/watersheds/MapServer/2?f=pjson',
    'huc4_layer.json': GIS + '/hydrologic_unit_code_watersheds_of_Alberta_v2/MapServer/3?f=pjson',
    'swob_stations.json': API + '/collections/swob-stations/items?bbox=-117.5,50,-109.5,53.5&limit=10000&f=json',
    'swob_partners.json': API + '/collections/swob-partner-stations/items?bbox=-117.5,50,-109.5,53.5&limit=10000&f=json',
    'swob_sample.json': API + '/collections/swob-realtime/items?url=CYQF&sortby=-date_tm-value&limit=5&f=json',
    'swob_queryables.json': API + '/collections/swob-realtime/queryables?f=json',
    'swob_docs.html': 'https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_en/',
    'weather_xml_docs.html': 'https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_xmldatamart_en/',
}
for slug in ['upper-red-deer-river-flood-study', 'red-deer-river-flood-study',
             'red-deer-county-and-markerville-flood-study', 'drumheller-flood-study',
             'didsbury-rosebud-river-flood-hazard-study', 'stettler-flood-study']:
    JOBS[slug + '.html'] = 'https://open.alberta.ca/publications/' + slug

if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for result in pool.map(run, JOBS.items()):
            print(*result, flush=True)
