from __future__ import annotations
import csv
import io
import math
from collections import Counter
from datetime import datetime, timezone
from rdr.storage import DATA
from API.client import fetch, get_json
from rdr.paths import source_relative_path

API = 'https://api.weather.gc.ca/collections'
HYDRO_DOC = 'https://eccc-msc.github.io/open-data/msc-data/obs_hydrometric/readme_hydrometric-datamart_en/'
SWOB_DOC = 'https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_swobdatamart_en/'


def parse_time(value):
    dt = datetime.fromisoformat(value.replace('Z','+00:00'))
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def cadence(times):
    """One-response timestamp evidence, never claim a publication SLA from this."""
    times=sorted({parse_time(t).timestamp() for t in times if t})
    gaps=[b-a for a,b in zip(times,times[1:]) if b>a]
    if len(gaps)<3: return {'seconds':None,'samples':len(gaps),'status':'unconfirmed'}
    buckets=Counter(max(60,round(x/60)*60) for x in gaps)
    typical=buckets.most_common(1)[0][0]
    return {'seconds':typical,'min_seconds':min(gaps),'max_seconds':max(gaps),
            'samples':len(gaps),'status':'observed_estimate'}


def numeric(v):
    return isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v)


def precipitation(properties):
    """Prefer one-hour measured accumulation. Never replace missing with zero."""
    for field, period in [('pcpn_amt_pst1hr',3600),('pcpn_amt_pst6hrs',21600),('pcpn_amt_pst24hrs',86400)]:
        value=properties.get(field)
        qa=properties.get(field+'-qa')
        if numeric(value) and value>=0 and qa not in (-1,0):
            return {'value':value,'unit':properties.get(field+'-uom'),'period_seconds':period,
                    'field':field,'qa':qa}
    return None


def swob(station, folder='sources/eccc_weather_geomet/raw/validation/weather', *, reuse=True, limit=48):
    folder = source_relative_path(API+'/swob-realtime/items', folder)
    identifier=station['weather_id']
    obj=get_json(API+'/swob-realtime/items',f'{folder}/{identifier}.json',
        {'msc_id-value':identifier,'sortby':'-date_tm-value','limit':limit,'f':'json'},reuse=reuse)
    features=obj.get('features',[])
    # Reject ignored filters or ambiguous mixed-station results.
    for f in features:
        actual=str(f['properties'].get('msc_id-value',''))
        if actual!=identifier: raise ValueError(f'Weather filter mismatch: {identifier} != {actual}')
    props=[f['properties'] for f in features]
    valid=[(p,precipitation(p)) for p in props if precipitation(p)]
    latest=props[0] if props else {}
    result={'weather_id':identifier,'record_count':len(props),'fields':sorted({k for p in props for k in p}),
            'latest_observation_utc':latest.get('date_tm-value'),
            'latest_processed_utc':latest.get('processed_date_tm'),
            'observation_cadence':cadence([p.get('date_tm-value') for p in props]),
            'publication_cadence':cadence([p.get('processed_date_tm') for p in props]),
            'precipitation_valid_records':len(valid),'latest_precipitation':valid[0][1] if valid else None,
            'latest_precipitation_utc':valid[0][0].get('date_tm-value') if valid else None,
            'source':SWOB_DOC,'raw_path':f'{folder}/{identifier}.json'}
    return result


def hydrometric(station, folder='sources/eccc_hydrometric_geomet/raw/validation/hydrometric', *, reuse=True):
    folder = source_relative_path(API+'/hydrometric-realtime/items', folder)
    sid=station['station_id']
    obj=get_json(API+'/hydrometric-realtime/items',f'{folder}/{sid}.json',
                 {'STATION_NUMBER':sid,'sortby':'-DATETIME','limit':48,'f':'json'},reuse=reuse)
    fs=obj.get('features',[])
    if any(f['properties']['STATION_NUMBER']!=sid for f in fs): raise ValueError('Water station filter mismatch')
    result={'station_id':sid,'record_count':len(fs),'fields':sorted({k for f in fs for k in f['properties']}),
            'latest_observation_utc':fs[0]['properties']['DATETIME'] if fs else None,
            'observation_cadence':cadence([f['properties']['DATETIME'] for f in fs]),
            'geomet_publication_cadence':{'seconds':None,'status':'unconfirmed',
                'note':'DATETIME describes observation time, not API publication time.'},
            'raw_path':f'{folder}/{sid}.json'}
    if not fs:
        # One historical sample, explicitly not current monitoring.
        hist=get_json(API+'/hydrometric-daily-mean/items',f'{folder}/{sid}_historical.json',
                      {'STATION_NUMBER':sid,'sortby':'-DATE','limit':1,'f':'json'},reuse=reuse)
        hfs=hist.get('features',[])
        result['historical_record_count']=len(hfs)
        result['historical_latest_date']=hfs[0]['properties'].get('DATE') if hfs else None
        result['data_status']='historical_only' if hfs else 'no_observations'
    else:
        result['data_status']='realtime_available'
    return result


def hydro_csv(station, folder='sources/eccc_hydrometric_datamart/raw/validation/hydrometric_hourly', *, reuse=True):
    sid=station['station_id']; province=station.get('province','AB')
    url=f'https://dd.weather.gc.ca/today/hydrometric/csv/{province}/hourly/{province}_{sid}_hourly_hydrometric.csv'
    folder = source_relative_path(url, folder)
    path=fetch(url,f'{folder}/{sid}.csv',reuse=reuse)
    rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
    if len(rows)<2 or not any(r and r[0]==sid for r in rows[1:]): raise ValueError('Empty/invalid station CSV')
    return {'station_id':sid,'url':url,'record_count':len(rows)-1,'columns':rows[0],
            'publication_cadence':{'seconds':3600,'status':'documented_product_schedule','source':HYDRO_DOC},
            'raw_path':f'{folder}/{sid}.csv'}
