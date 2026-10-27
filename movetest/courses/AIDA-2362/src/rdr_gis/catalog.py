from __future__ import annotations
from project_paths import resolve_runtime_path, archive_relative
import csv
import json
import re
from collections import OrderedDict
from rdr.storage import DATA, save_json
from rdr.station_index import normalize_station_index


def watercourse(name):
    name = name.lstrip('.').strip().upper().replace('(MAIN STEM)', '').replace('(M1)', '')
    name = re.split(r'\s+(?:NEAR|AT|ABOVE|BELOW|ON)\s+', name)[0]
    return ' '.join(name.split())


def dms(value, west=False):
    numbers = re.findall(r'\d+(?:\.\d+)?', value)
    if len(numbers) < 3: return None
    value = float(numbers[0]) + float(numbers[1])/60 + float(numbers[2])/3600
    return -value if west else value


def build_catalog():
    index_path = normalize_station_index(
        resolve_runtime_path(DATA/'sources/eccc_wateroffice/raw/discovery/station_index_all.csv'),
        resolve_runtime_path(DATA/'processed/source_normalized/eccc_wateroffice/station_index_all.csv'))
    with index_path.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle, strict=True))
    metadata = json.loads((resolve_runtime_path(DATA/'sources/eccc_hydrometric_geomet/raw/discovery/hydrometric_stations.json')).read_text())['features']
    meta = {f['id']: f for f in metadata}
    entries = OrderedDict()
    active = False
    for row in rows:
        sid = row['Station Number']
        if sid == '05CA004': active = True
        if active and sid and not sid.startswith('05C'): break
        if not active or not sid: continue
        name = row['Water Course'].lstrip('.')
        if sid not in entries:
            f = meta.get(sid, {})
            prop = f.get('properties', {})
            coords = f.get('geometry', {}).get('coordinates') or [dms(row['Longitude'], True), dms(row['Latitude'])]
            kind = ('MAINSTEM' if name.startswith('RED DEER RIVER ') else
                    'CONTROL' if sid in {'05CB006','05CB007'} else 'TRIBUTARY_NETWORK')
            entries[sid] = {'station_id': sid, 'name': name, 'watercourse': watercourse(name),
                'kind': kind, 'longitude': coords[0], 'latitude': coords[1],
                'status': prop.get('STATUS_EN', 'not_in_geomet_metadata'),
                'realtime_metadata': prop.get('REAL_TIME'),
                'index_depth': len(row['Water Course'])-len(name),
                'source': 'WSC complete stream-order reference index', 'operation_periods': [],
                'vertical_datum': prop.get('VERTICAL_DATUM'), 'province': prop.get('PROV_TERR_STATE_LOC','AB')}
        entries[sid]['operation_periods'].append({k:row[k] for k in ['Year From','Year To','Data Type','Gauge Type','Operation Schedule']})
    # Keep additional 05C inventory records (including internally drained lakes
    # and newer stations absent from the stream-order tree) explicitly separate.
    for sid, f in meta.items():
        if not sid.startswith('05C') or sid in entries: continue
        p = f['properties']; c=f['geometry']['coordinates']
        entries[sid]={'station_id':sid,'name':p['STATION_NAME'],'watercourse':watercourse(p['STATION_NAME']),
                     'kind':'ADDITIONAL_BASIN_RECORD','longitude':c[0],'latitude':c[1],
                     'status':p['STATUS_EN'],'realtime_metadata':p['REAL_TIME'],'index_depth':None,
                     'source':'GeoMet 05C drainage-area station metadata','operation_periods':[],
                     'vertical_datum':p.get('VERTICAL_DATUM'),'province':p['PROV_TERR_STATE_LOC']}
    result=list(entries.values())
    save_json(resolve_runtime_path(DATA/'processed/station_master.json'),result)
    return result
