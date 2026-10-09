"""Cache official station-specific vertical-datum evidence once, without polling."""
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rdr.storage import DATA, save_json, now
from API.client import fetch


def inspect(station):
    sid = station['station_id']
    url = 'https://wateroffice.ec.gc.ca/report/datum_e.html'
    result = {'station_id': sid, 'metadata_datum': station.get('vertical_datum'),
              'source_url': url+'?stn='+sid, 'conversions': [], 'status': 'unavailable'}
    try:
        path = fetch(url, f'sources/eccc_wateroffice/raw/datums/{sid}.html', {'stn': sid}, timeout=25)
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        main = soup.find('main') or soup
        text = main.get_text(' ', strip=True)
        result['raw_path'] = str(path.relative_to(DATA))
        if f'Vertical datum information for {sid}' not in text:
            result['status'] = 'station_page_not_confirmed'
            return result
        result['status'] = 'no_published_conversion'
        for match in re.finditer(r'To convert to (.*?),\s*add\s+(-?\d+(?:\.\d+)?)\s*m\.', text):
            label, offset = match.groups()
            result['conversions'].append({'target_label': label, 'add_m': float(offset),
                'target_datum': 'CGVD28_conventional' if label == 'GEODETIC SURVEY OF CANADA DATUM' else
                    'CGVD2013' if '2013' in label else 'other_or_local_adjustment',
                'evidence_text': match.group(0), 'status': 'official_published_conversion'})
        if result['conversions']: result['status'] = 'published_conversions_found'
        result['datum_caution'] = 'GSC datum is conventionally CGVD28; absolute accuracy, epoch and section transfer still require review.'
    except Exception as exc:
        result['error'] = type(exc).__name__
    return result


def main():
    stations = json.loads((DATA/'processed/station_master.json').read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = []
        for record in pool.map(inspect, stations):
            records.append(record)
            print(record['station_id'], record['status'], flush=True)
    save_json(DATA/'processed/station_datums.json', {'checked_at': now(), 'stations': records})


if __name__ == '__main__': main()
