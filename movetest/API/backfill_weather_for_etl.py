"""One bounded weather backfill matching saved hydrometric samples, no live scheduler."""
from project_paths import resolve_runtime_path, archive_relative
import csv
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, timezone
from pathlib import Path


from API.observations import parse_time, API
from rdr.storage import DATA, save_json, now
from API.client import get_json


def main():
    links={s['station_id']:s for s in json.loads((resolve_runtime_path(DATA/'processed/weather_links.json')).read_text())}
    spans=defaultdict(list)
    for path in (resolve_runtime_path(DATA/'sources/eccc_hydrometric_datamart/raw/validation/hydrometric_hourly')).glob('*.csv'):
        sid=path.stem;link=links.get(sid)
        if not link or not link.get('weather_id'):continue
        with path.open(encoding='utf-8-sig') as handle:
            rows=list(csv.reader(handle))[1:]
        stamps=[parse_time(row[1]).astimezone(timezone.utc) for row in rows if len(row)>=10 and row[0]==sid]
        if stamps:spans[link['weather_id']].extend([min(stamps)-timedelta(hours=1),max(stamps)])
    def retrieve(item):
        sid,times=item;start,end=min(times),max(times)
        url=API+'/swob-realtime/items'
        params={'msc_id-value':sid,'datetime':start.isoformat()+'/'+end.isoformat(),
                'sortby':'date_tm-value','limit':1000,'f':'json'}
        visited=set();count=0
        for page in range(30):
            obj=get_json(url,f'sources/eccc_weather_geomet/raw/validation/etl_weather/{sid}_{page:03d}.json',params,timeout=40)
            features=obj.get('features')
            if not isinstance(features,list):raise ValueError('Missing weather features')
            if any(str(f['properties'].get('msc_id-value'))!=sid for f in features):raise ValueError('Wrong weather station')
            count+=len(features)
            nxt=next((link['href'] for link in obj.get('links',[]) if link.get('rel')=='next'),None)
            if not nxt:break
            if nxt in visited or not nxt.startswith('https://api.weather.gc.ca/'):raise ValueError('Invalid pagination URL')
            visited.add(nxt);url=nxt;params=None
        else:raise ValueError('Backfill exceeds bounded 30-page limit')
        result={'weather_id':sid,'start':start.isoformat(),'end':end.isoformat(),'records':count,'pages':page+1}
        print(json.dumps(result),flush=True);return result
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(retrieve,sorted(spans.items())))
    save_json(resolve_runtime_path(DATA/'reports/etl_weather_backfill.json'),{'completed_at':now(),'continuous':False,'sources':results})


if __name__=='__main__':main()
