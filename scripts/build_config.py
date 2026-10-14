"""Build reviewable per-station source configuration from validated evidence."""
import json
import sys
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from rdr.storage import DATA, ROOT, save_json, now
from API.observations import parse_time
from API.collector import station_interval, calculation_interval

def main():
    stations=json.loads((DATA/'processed/station_master.json').read_text())
    hydro={s['station_id']:s for s in json.loads((DATA/'reports/hydrometric_validation.json').read_text())}
    weather={s['weather_id']:s for s in json.loads((DATA/'reports/weather_validation.json').read_text())}
    links={s['station_id']:s for s in json.loads((DATA/'processed/weather_links.json').read_text())}
    selected=set(json.loads((DATA/'processed/monitoring_station_ids.json').read_text()))
    scope_path = ROOT/'config/active_scope.json'
    if scope_path.exists():
        selected = set(json.loads(scope_path.read_text(encoding='utf-8'))['station_ids'])
    result=[]
    for s in stations:
        sid=s['station_id'];h=hydro[sid];link=links[sid];w=weather.get(link['weather_id'],{});sources=[];notes=[]
        product=h.get('scheduled_product',{})
        stamp=h.get('latest_observation_utc')
        age=(datetime.now(timezone.utc)-parse_time(stamp)).total_seconds() if stamp else None
        h['latest_age_seconds_at_config_build']=age
        if age is not None and age>48*3600:
            h['data_status']='stale_realtime';notes.append('Water observation older than 48 hours; not treated as current.')
        if product and age is not None and age<=48*3600:
            sources.append({'kind':'hydrometric_hourly_csv','station_id':sid,'url':product['url'],
                            'publication_interval_seconds':product['publication_cadence']['seconds'],
                            'interval_evidence':product['publication_cadence']})
        else:notes.append('No validated fresh hourly water product; historical/absent water records are not repeatedly polled.')
        rate=w.get('publication_cadence',{})
        if link['weather_id'] and rate.get('seconds'):
            sources.append({'kind':'swob','station_id':link['weather_id'],
                'url':'https://api.weather.gc.ca/collections/swob-realtime/items',
                'publication_interval_seconds':rate['seconds'],'interval_evidence':rate,
                'precipitation_field':link['precipitation_field'],
                'note':'Cadence estimated from processed_date_tm in one snapshot; not an official fixed publishing SLA.'})
        else:notes.append('Weather publishing interval unconfirmed; disabled until evidence or explicit configuration is supplied.')
        config={**s,'enabled':sid in selected and bool(sources),'selected_monitoring_point':sid in selected,
                'sources':sources,'interval_seconds':station_interval(sources) if sources else None,
                'interval_seconds_legacy_note':'Compatibility only; not used for source acquisition scheduling',
                'calculation_interval_seconds':calculation_interval(sources),
                'calculation_window_rule':'trailing water publication interval ending at each water observation time',
                'mode':'water_and_weather' if len(sources)==2 else 'weather_only' if sources and sources[0]['kind']=='swob' else 'unavailable',
                'cadence_confidence':'includes_observed_estimate' if any(x['kind']=='swob' for x in sources) else 'documented',
                'weather_link':link,'water_data_status':h.get('data_status'),'notes':notes}
        result.append(config)
    save_json(DATA/'reports/hydrometric_validation.json',list(hydro.values()))
    save_json(ROOT/'config/stations.json',{'schema_version':2,'generated_at_utc':now(),'max_workers':4,
       'interval_rule':'each unique source polls at its own publication interval; station calculation uses its hydrometric interval',
       'auto_start':False,'stations':result})
    print('configured',len(result),'selected',len(selected),'enabled',sum(x['enabled'] for x in result),flush=True)

if __name__=='__main__':main()
