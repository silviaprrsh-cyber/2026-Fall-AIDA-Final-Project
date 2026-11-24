"""Download all WSC 05C National Hydro Network units once, including SK mouth."""
from project_paths import resolve_runtime_path, archive_relative
import concurrent.futures
import sys
import zipfile
from pathlib import Path
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from rdr.storage import DATA, save_json
from API.client import fetch

BASE='https://ftp.maps.canada.ca/pub/nrcan_rncan/vector/geobase_nhn_rhn/shp_en/05/'

def main():
    p=fetch(BASE,'sources/nrcan_nhn/raw/discovery/nhn_05.html')
    links=[a['href'] for a in BeautifulSoup(p.read_bytes(),'html.parser').select('a[href]')
           if a['href'].startswith('nhn_rhn_05c') and a['href'].endswith('.zip')]
    def job(link):
        path=fetch(urljoin(BASE,link),'sources/nrcan_nhn/static/nhn/'+link,timeout=120)
        with zipfile.ZipFile(path) as z:
            bad=z.testzip()
            if bad:raise ValueError(f'ZIP CRC failure: {bad}')
            layers=[n for n in z.namelist() if n.endswith('.shp')]
        print(link,path.stat().st_size,flush=True)
        return {'url':urljoin(BASE,link),'path':str(archive_relative(path, DATA)),'bytes':path.stat().st_size,'layers':layers,'crc_verified':True}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool: result=list(pool.map(job,links))
    save_json(resolve_runtime_path(DATA/'processed/nhn_inventory.json'),result)

if __name__=='__main__':main()
