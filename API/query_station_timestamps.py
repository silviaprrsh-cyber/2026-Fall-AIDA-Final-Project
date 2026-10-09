"""Read public source timestamps once; do not start the project collector."""
import concurrent.futures
import csv
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.parse
import urllib.error
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rdr.paths import source_relative_path
OUT = ROOT / 'data/reports/station_timestamp_export'
RUN = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
RAW = Path('raw/station_timestamp_check') / RUN
API = 'https://api.weather.gc.ca/collections/'

def now():
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def load_csv(name):
    with (ROOT/name).open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))

def query(collection, params, stem):
    params = {**params, 'f':'json'}
    url = API + collection + '/items?' + urllib.parse.urlencode(params)
    folder = ROOT / 'data' / source_relative_path(url, RAW)
    folder.mkdir(parents=True, exist_ok=True)
    meta = {'url':url,'query_started_at_utc':now()}
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'RedDeerRiverAcademicProject/0.1'})
        with urllib.request.urlopen(req, timeout=30) as response:
            body=response.read()
            meta.update(status=response.status, received_at_utc=now(),
                        http_last_modified=response.headers.get('Last-Modified'),
                        sha256=hashlib.sha256(body).hexdigest())
        (folder/(stem+'.json')).write_bytes(body)
        obj=json.loads(body)
        if 'features' not in obj: raise ValueError('No features array')
        return obj['features'], url, None
    except Exception as exc:
        meta.update(error=str(exc),failed_at_utc=now())
        return [], url, str(exc)
    finally:
        (folder/(stem+'.meta.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')

def numeric(x):
    return isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x)

def parse_time(s):
    dt=datetime.fromisoformat(s.replace('Z','+00:00'))
    if dt.tzinfo is None: raise ValueError('Timestamp lacks timezone')
    return dt.astimezone(timezone.utc)

def newest(features, field):
    candidates=[f for f in features if f['properties'].get(field)]
    return max(candidates,key=lambda f:parse_time(f['properties'][field]),default=None)

HEADERS = ['station_id','station_name','station_type','river_role',
           'latest_source_observation_time_utc','latest_source_processing_time_utc',
           'observation_time_of_latest_processed_record_utc',
           'actual_station_transmission_time_utc','transmission_time_status',
           'latest_historical_daily_date','query_data_status','enabled_collection_source',
           'associated_weather_station_id','latest_record_id','latest_processed_record_id',
           'observation_source_url','processing_source_url','historical_source_url',
           'snapshot_date_utc','notes']

stations=load_csv('data/processed/station_master.csv')
links=load_csv('data/processed/weather_links.csv')
link_map={s['station_id']:s for s in links}
config=json.loads((ROOT/'config/stations.json').read_text(encoding='utf-8'))
enabled_sources={(s['kind'],str(s['station_id'])) for st in config['stations'] if st.get('enabled')
                 for s in st.get('sources',[])}
weather={s['weather_id']:s for s in links if s.get('weather_id')}

def base(sid,name,kind):
    row={h:'' for h in HEADERS}
    row.update(station_id=sid,station_name=name,station_type=kind,
               transmission_time_status='not_exposed_by_selected_public_API',
               snapshot_date_utc=RUN[:4]+'-'+RUN[4:6]+'-'+RUN[6:8])
    return row

def hydro(station):
    sid=station['station_id']
    row=base(sid,station['name'],'hydrometric')
    row.update(river_role=station['kind'],
               associated_weather_station_id=link_map.get(sid,{}).get('weather_id',''),
               enabled_collection_source=str(('hydrometric_hourly_csv',sid) in enabled_sources).lower())
    features,url,error=query('hydrometric-realtime',{'STATION_NUMBER':sid,'sortby':'-DATETIME','limit':48},'water_'+sid)
    row['observation_source_url']=url
    row['notes']='DATETIME is source observation time, not station transmission, publication, or local receipt time. Actual transmission time is not exposed.'
    if error:
        row.update(query_data_status='query_failed',notes=row['notes']+' Query error: '+error)
        return row
    if any(f['properties'].get('STATION_NUMBER')!=sid for f in features):
        raise ValueError('Hydrometric station filter mismatch: '+sid)
    usable=[f for f in features if any(numeric(f['properties'].get(k)) for k in ('LEVEL','DISCHARGE'))]
    latest=newest(usable,'DATETIME')
    if latest:
        props=latest['properties']
        row.update(latest_source_observation_time_utc=props['DATETIME'],
                   latest_record_id=str(latest.get('id',props.get('IDENTIFIER',''))),
                   query_data_status='realtime_record_returned')
        if (datetime.now(timezone.utc)-parse_time(props['DATETIME'])).total_seconds()>48*3600:
            row['query_data_status']='realtime_record_older_than_48h'
    else:
        row['query_data_status']='no_numeric_record_in_latest_48' if features else 'no_realtime_record_returned'
        hist,hurl,herr=query('hydrometric-daily-mean',{'STATION_NUMBER':sid,'sortby':'-DATE','limit':1},'historical_'+sid)
        row['historical_source_url']=hurl
        if herr: row['notes']+=' Historical query failed: '+herr
        elif hist:
            if any(f['properties'].get('STATION_NUMBER')!=sid for f in hist): raise ValueError('Historical station mismatch')
            row['latest_historical_daily_date']=hist[0]['properties'].get('DATE','')
            row['query_data_status']='historical_daily_only' if not features else row['query_data_status']
            row['notes']+=' Historical date is a daily aggregate, not an exact transmission time; no midnight timestamp has been invented.'
    return row

def weather_valid(f):
    p=f['properties']
    # At least one numerical measured variable with a documented unit; station
    # coordinates/metadata do not count as a measurement.
    return any(numeric(v) and k+'-uom' in p and k+'-qa' in p and p.get(k+'-qa') not in (-1,0)
               for k,v in p.items() if not k.endswith(('-qa','-uom')))

def meteo(sid):
    row=base(sid,weather[sid]['weather_name'],'weather')
    row['enabled_collection_source']=str(('swob',sid) in enabled_sources).lower()
    obs,url,error=query('swob-realtime',{'msc_id-value':sid,'sortby':'-date_tm-value','limit':48},'weather_obs_'+sid)
    proc,purl,perror=query('swob-realtime',{'msc_id-value':sid,'sortby':'-processed_date_tm','limit':48},'weather_processed_'+sid)
    row.update(observation_source_url=url,processing_source_url=purl,
               notes='date_tm-value is observation time. processed_date_tm is provider processing time, not proven station transmission or publication time. The two maxima are selected independently; their record IDs and associated observation time are retained. No local receipt time is used.')
    if any(str(f['properties'].get('msc_id-value',''))!=sid for f in obs+proc):
        raise ValueError('Weather station filter mismatch: '+sid)
    latest=newest([f for f in obs if weather_valid(f)],'date_tm-value')
    latest_proc=newest([f for f in proc if weather_valid(f)],'processed_date_tm')
    if latest:
        p=latest['properties']
        row.update(latest_source_observation_time_utc=p['date_tm-value'],latest_record_id=str(latest.get('id','')))
    if latest_proc:
        p=latest_proc['properties']
        row.update(latest_source_processing_time_utc=p['processed_date_tm'],
                   observation_time_of_latest_processed_record_utc=p.get('date_tm-value',''),
                   latest_processed_record_id=str(latest_proc.get('id','')))
    row['query_data_status']='realtime_record_returned' if latest else 'no_valid_numeric_record_in_latest_48'
    if error or perror:
        row['query_data_status']='query_failed_or_partial'
        row['notes']+=' Query error: '+str(error or perror)
    return row

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    jobs=[('hydrometric',s) for s in stations]+[('weather',s) for s in sorted(weather)]
    rows=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures=[pool.submit(hydro if kind=='hydrometric' else meteo,item) for kind,item in jobs]
        for n,future in enumerate(concurrent.futures.as_completed(futures),1):
            rows.append(future.result())
            if n%20==0: print('Completed',n,'of',len(jobs),flush=True)
    rows.sort(key=lambda r:(r['station_type']!='hydrometric',r['station_id']))
    assert len(rows)==len(stations)+len(weather)
    assert len({(r['station_type'],r['station_id']) for r in rows})==len(rows)
    assert all(r['actual_station_transmission_time_utc']=='' for r in rows)
    payload={'headers':HEADERS,'rows':rows,'raw_directories':[str(ROOT / 'data/sources' / source / RAW) for source in ('eccc_hydrometric_geomet','eccc_weather_geomet')],'run':RUN,
             'notes':'Finite one-shot source queries. No continuous collection started. Local receipt times are retained only in raw audit metadata, not used as source timestamps.'}
    (OUT/'results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
    counts={status:sum(r['query_data_status']==status for r in rows) for status in sorted({r['query_data_status'] for r in rows})}
    print(json.dumps({'rows':len(rows),'water':len(stations),'weather':len(weather),'statuses':counts,
                     'actual_transmission_times_exposed':0,'run':RUN},indent=2),flush=True)

if __name__=='__main__': main()
