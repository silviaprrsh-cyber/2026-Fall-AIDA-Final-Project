"""Bounded, cached inspection of alternative partner weather feeds.

Inspect only AB-MAI candidates encountered in the original nearest-station
search, and one latest XML per station. Never schedule this discovery script.
"""
import concurrent.futures
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urljoin
from bs4 import BeautifulSoup
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rdr.storage import DATA, save_json, now
from API.client import fetch
from API.observations import precipitation

BASE='https://dd.weather.gc.ca/today/observations/swob-ml/partners/ab_agriculture/'

def links(path):
    return [a['href'] for a in BeautifulSoup(path.read_text(encoding='utf-8'),'html.parser').select('a[href]')]

def inspect_xml(path, expected_id):
    root=ET.parse(path).getroot();props={};fields=[]
    for element in root.iter():
        if element.tag.rsplit('}',1)[-1]!='element':continue
        name=element.get('name');value=element.get('value');fields.append(name)
        if name=='msc_id' and value!=expected_id:raise ValueError('Partner station mismatch')
        try:value=float(value)
        except (TypeError,ValueError):pass
        props[name]=value;props[name+'-uom']=element.get('uom')
        for q in element:
            if q.get('name')=='qa_summary':props[name+'-qa']=int(q.get('value'))
    if props.get('msc_id')!=expected_id:raise ValueError('Missing partner identity')
    return {'fields':sorted(fields),'latest_observation_utc':props.get('date_tm'),
            'precipitation':precipitation(props),'attribution':props.get('data_attrib_not')}

def main():
    index=fetch(BASE,'sources/eccc_weather_datamart/raw/discovery/ab_agriculture_directory.html')
    days=sorted(x for x in links(index) if x.rstrip('/').isdigit())
    if not days:raise ValueError('No partner day directory')
    day=days[-1];daily=fetch(urljoin(BASE,day),'sources/eccc_weather_datamart/raw/discovery/ab_agriculture_day.html')
    available=set(links(daily))
    candidates=[s for s in json.loads((DATA/'reports/weather_validation.json').read_text()) if s['weather_id'].startswith('AB-MAI_')]
    def check(station):
        sid=station['weather_id'];code=sid.split('_',1)[1].lower()
        result={'weather_id':sid,'name':station['name'],'directory_day':day.rstrip('/')}
        if code+'/' not in available:return {**result,'status':'no_station_directory'}
        try:
            base=urljoin(BASE,day+code+'/')
            p=fetch(base,f'sources/eccc_weather_datamart/raw/discovery/partners/{code}_directory.html')
            xmls=sorted(x for x in links(p) if x.endswith('.xml') and '/' not in x)
            if not xmls:return {**result,'status':'no_xml'}
            p=fetch(urljoin(base,xmls[-1]),f'sources/eccc_weather_datamart/raw/validation/partners/{code}.xml')
            parsed=inspect_xml(p,sid)
            return {**result,**parsed,'status':'precipitation_available' if parsed['precipitation'] else 'no_valid_precipitation_in_sample','raw_path':str(p.relative_to(DATA))}
        except Exception as exc:return {**result,'status':'error','error':str(exc)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(check,candidates))
    report={'checked_at_utc':now(),'mode':'one cached latest XML per candidate; no polling',
            'source':BASE,'stations':results,'valid_precipitation_count':sum(bool(r.get('precipitation')) for r in results),
            'limitation':'Absence in these samples does not prove that a station never measures precipitation.'}
    save_json(DATA/'reports/partner_precipitation_check.json',report)
    print('Partner samples',len(results),'with valid precipitation',report['valid_precipitation_count'])

if __name__=='__main__':main()
