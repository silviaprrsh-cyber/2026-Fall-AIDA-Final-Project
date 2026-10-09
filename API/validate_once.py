"""One bounded validation run per endpoint, resumed from cached raw responses."""
import concurrent.futures
import json
import math
import sys
from pathlib import Path
from datetime import datetime, timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rdr.catalog import build_catalog
from API.observations import hydrometric, hydro_csv, swob, parse_time
from rdr.storage import DATA, save_json, now


def distance(a,b):
    lon1,lat1=map(math.radians,a);lon2,lat2=map(math.radians,b)
    h=math.sin((lat2-lat1)/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin((lon2-lon1)/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(h)))


def main():
    stations=build_catalog()
    def water(s):
        try:
            r=hydrometric(s)
            if r['record_count']:
                try:r['scheduled_product']=hydro_csv(s)
                except Exception as exc:r['scheduled_product_error']=str(exc)
            print(s['station_id'],r['data_status'],flush=True)
            return r
        except Exception as exc:
            print(s['station_id'],'ERROR',str(exc),flush=True)
            return {'station_id':s['station_id'],'error':str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        waters=list(pool.map(water,stations))
    save_json(DATA/'reports/hydrometric_validation.json',waters)
    candidates={}
    for name in ['swob_stations','swob_partners']:
        for f in json.loads((DATA/f'sources/eccc_weather_geomet/raw/discovery/{name}.json').read_text())['features']:
            p=f['properties'];c=f['geometry']['coordinates']
            candidates[str(p['msc_id'])]={'weather_id':str(p['msc_id']),'name':p.get('name',p.get('name_en')),
               'longitude':c[0],'latitude':c[1],'provider':p.get('data_provider',p.get('data_provider_en'))}
    validation={};links=[]
    for s in stations:
        ranked=sorted(candidates.values(),key=lambda c:distance((s['longitude'],s['latitude']),(c['longitude'],c['latitude'])))
        link={'station_id':s['station_id'],'weather_id':None,'status':'no_verified_precipitation','attempts':[]}
        for c in ranked:
            dist=distance((s['longitude'],s['latitude']),(c['longitude'],c['latitude']))
            if dist>150:break
            wid=c['weather_id']
            if wid not in validation:
                try:validation[wid]={**c,**swob(c)}
                except Exception as exc:validation[wid]={**c,'error':str(exc)}
                print('WEATHER',wid,validation[wid].get('precipitation_valid_records',validation[wid].get('error')),flush=True)
            result=validation[wid];link['attempts'].append(wid)
            stamp=result.get('latest_precipitation_utc')
            fresh=stamp and (datetime.now(timezone.utc)-parse_time(stamp)).total_seconds()<48*3600
            if result.get('precipitation_valid_records',0)>0 and fresh:
                link.update({'weather_id':wid,'weather_name':c['name'],'distance_km':round(dist,3),
                             'status':'nearest_verified_precipitation_station','collocated':dist<0.1,
                             'precipitation_field':result['latest_precipitation']['field'],
                             'precipitation_period_seconds':result['latest_precipitation']['period_seconds']})
                break
        links.append(link)
    save_json(DATA/'reports/weather_validation.json',list(validation.values()))
    save_json(DATA/'processed/weather_links.json',links)
    save_json(DATA/'reports/validation_run.json',{'completed_at_utc':now(),'hydrometric_stations':len(stations),
               'weather_endpoints':len(validation),'linked_with_precipitation':sum(bool(x['weather_id']) for x in links),
               'mode':'single cached snapshot, no continuous polling'})

if __name__=='__main__':main()
