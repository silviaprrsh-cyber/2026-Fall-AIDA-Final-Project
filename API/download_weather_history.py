"""Fetch a bounded, resumable ECCC hourly weather archive for the linked station."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import time

import requests
from project_paths import WORKSPACE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', default='2025-05-01T00:00:00Z')
    parser.add_argument('--end', default='2026-11-04T00:00:00Z')
    args = parser.parse_args()
    start = datetime.fromisoformat(args.start.replace('Z', '+00:00'))
    end = datetime.fromisoformat(args.end.replace('Z', '+00:00'))
    if not start.tzinfo or not end.tzinfo or not start < end:
        raise ValueError('Explicit UTC-aware ordered bounds required')
    run = start.strftime('%Y%m%d') + '_' + end.strftime('%Y%m%d') + '_3025484_monthly'
    folder = WORKSPACE / 'courses/AIDA-2156/data/sources/eccc_climate_hourly/raw' / run
    folder.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    pages, total, expected = [], 0, 0
    months = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append((year, month))
        year, month = (year+1, 1) if month == 12 else (year, month+1)
    if len(months) > 36:
        raise ValueError('History request must be bounded to 36 months')
    for year, month in months:
        params = {'f': 'json', 'limit': 1000, 'LOCAL_YEAR': year, 'LOCAL_MONTH': month,
                  'CLIMATE_IDENTIFIER': '3025484'}
        path = folder / f'{year}_{month:02d}.json'
        meta = path.with_suffix('.meta.json')
        if path.exists() and meta.exists():
            raw = path.read_bytes()
            record = json.loads(meta.read_text())
            if hashlib.sha256(raw).hexdigest() != record['sha256'] or record['params'] != params:
                raise ValueError('Archive cache identity mismatch')
        else:
            for attempt in range(3):
                try:
                    response = session.get('https://api.weather.gc.ca/collections/climate-hourly/items',
                                           params=params, timeout=60)
                    response.raise_for_status()
                    raw = response.content
                    json.loads(raw)
                    break
                except (requests.RequestException, ValueError):
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
            record = {'url': response.url, 'params': params,
                      'received_at': datetime.now(timezone.utc).isoformat(),
                      'sha256': hashlib.sha256(raw).hexdigest()}
            path.write_bytes(raw)
            meta.write_text(json.dumps(record, indent=2) + '\n')
            time.sleep(.3)
        obj = json.loads(raw)
        rows = obj['features']
        matched = obj.get('numberMatched')
        if matched != len(rows) or len({r['id'] for r in rows}) != len(rows):
            raise ValueError('Monthly query is truncated or duplicated')
        expected += matched
        for row in rows:
            props = row['properties']
            if (props['CLIMATE_IDENTIFIER'] != '3025484' or
                    props['LOCAL_YEAR'] != year or props['LOCAL_MONTH'] != month):
                raise ValueError('Provider did not honor requested station/time filter')
        pages.append({'path': str(path.relative_to(WORKSPACE)).replace('\\', '/'), **record,
                      'rows': len(rows)})
        total += len(rows)
        print('Weather records archived:', total, flush=True)
    manifest = {'station_id': '3025484', 'station_name': 'RED DEER REGIONAL A',
                'start': args.start, 'end': args.end, 'rows': total, 'number_matched': expected,
                'pages': pages, 'complete': expected is not None and total == expected,
                'source': 'ECCC climate-hourly OGC API', 'transmission_time_available': False,
                'selection': 'Full local calendar months archived; UTC start/end applied by feature loader.'}
    if not manifest['complete']:
        raise ValueError('Incomplete provider count')
    (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Complete:', str(folder.relative_to(WORKSPACE)))


if __name__ == '__main__':
    main()
