"""Independent source schedules, persisted cursors, raw provenance and stop input."""
from __future__ import annotations
from project_paths import resolve_runtime_path, archive_relative
import csv
import io
import json
import math
import os
import signal
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from rdr.storage import DATA, ROOT, save_json, now, log
from API.client import fetch, get_json
from rdr.paths import source_relative_path
from API.observations import API, parse_time


def station_interval(sources):
    """Validate source intervals; retained for older callers, not scheduler timing."""
    intervals=[s.get('publication_interval_seconds') for s in sources]
    if not intervals or any(not isinstance(x,(int,float)) or isinstance(x,bool) or not math.isfinite(x) or x<=0 for x in intervals):
        raise ValueError('Every enabled source needs a positive evidenced publication interval')
    return max(intervals)


def calculation_interval(sources):
    """A hydrometric station defines its own trailing analysis window."""
    water=[s for s in sources if s['kind']=='hydrometric_hourly_csv']
    return station_interval(water) if water else None


def station_calculation_interval(station):
    """Preserve an explicit analysis interval; infer it only when missing or null."""
    interval = station.get('calculation_interval_seconds')
    if interval is None:
        return calculation_interval(station.get('sources', []))
    if (isinstance(interval, bool) or not isinstance(interval, (int, float))
            or not math.isfinite(interval) or interval <= 0):
        raise ValueError('calculation_interval_seconds must be a positive finite number')
    return interval


def source_schedules(stations):
    """Deduplicate shared providers without slowing weather to the water cadence."""
    jobs={}
    for station in stations:
        for source in station['sources']:
            station_interval([source])
            key=(source['kind'],source['station_id'])
            if key in jobs:
                previous=jobs[key]['source']
                if any(previous.get(k)!=source.get(k) for k in ['url','publication_interval_seconds']):
                    raise ValueError(f'Conflicting source settings for {key}')
                jobs[key]['monitoring_stations'].append(station['station_id'])
            else:jobs[key]={'source':source,'monitoring_stations':[station['station_id']]}
    return jobs


class ObservationStore:
    def __init__(self,path=None):
        self.path=Path(path or resolve_runtime_path(DATA/'processed/observations.sqlite3'))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS observations (source TEXT, station TEXT, record_id TEXT, observed_at TEXT, payload TEXT, raw_path TEXT, updated_at TEXT, PRIMARY KEY(source,station,record_id))')
            db.execute('CREATE TABLE IF NOT EXISTS cursors (source TEXT, station TEXT, observed_at TEXT, PRIMARY KEY(source,station))')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            db.execute('PRAGMA journal_mode=WAL')
            with db:yield db
        finally:
            db.close()

    def cursor(self,source,station):
        with self.connect() as db:
            row=db.execute('SELECT observed_at FROM cursors WHERE source=? AND station=?',(source,station)).fetchone()
        return row[0] if row else None

    def write(self,source,station,records):
        if not records:return 0
        with self.connect() as db:
            for rid,stamp,payload,raw in records:
                db.execute('INSERT INTO observations VALUES (?,?,?,?,?,?,?) ON CONFLICT(source,station,record_id) DO UPDATE SET payload=excluded.payload, raw_path=excluded.raw_path, updated_at=excluded.updated_at WHERE payload!=excluded.payload',
                           (source,station,rid,stamp,json.dumps(payload,sort_keys=True),raw,now()))
            latest=max(r[1] for r in records)
            db.execute('INSERT INTO cursors VALUES (?,?,?) ON CONFLICT(source,station) DO UPDATE SET observed_at=MAX(observed_at,excluded.observed_at)',(source,station,latest))
        return len(records)


class Collector:
    def __init__(self,stop,store=None):
        self.stop=stop;self.store=store or ObservationStore()
        self.locks={};self.locks_guard=threading.Lock();self.last_success={}

    def collect(self,source):
        key=(source['kind'],source['station_id'])
        with self.locks_guard:lock=self.locks.setdefault(key,threading.Lock())
        # Shared weather sources fetched once per provider cadence, even when
        # several independent monitoring stations are due at the same instant.
        with lock:
            if self.stop.is_set():return {'status':'stopped'}
            if time.monotonic()-self.last_success.get(key,-float('inf')) < source['publication_interval_seconds']:
                return {'status':'shared_source_cached'}
            folder=source_relative_path(source['url'], f'raw/live/{datetime.now(timezone.utc):%Y%m%dT%H%M%S}_{uuid4().hex[:8]}/{key[0]}')
            try:
                records=self._fetch(source,folder)
                if records is None:return {'status':'stopped'}
                count=self.store.write(*key,records)
                self.last_success[key]=time.monotonic()
                return {'status':'ok','records':count,'source':key}
            except Exception as exc:
                log({'event':'collection_error','source':key,'error':str(exc),'at':now()})
                return {'status':'error','source':key,'error':str(exc)}

    def _fetch(self,source,folder):
        kind=source['kind'];sid=source['station_id'];records=[]
        if kind=='hydrometric_hourly_csv':
            path=fetch(source['url'],f'{folder}/{sid}.csv',reuse=False,timeout=20)
            rows=list(csv.reader(io.StringIO(path.read_text(encoding='utf-8-sig'))))
            if len(rows)<2:raise ValueError('Empty hydrometric CSV')
            for row in rows[1:]:
                if not row:continue
                if row[0]!=sid:raise ValueError('Wrong station in hydrometric CSV')
                if len(row)<10:raise ValueError('Hydrometric schema changed: expected 10 columns')
                stamp=parse_time(row[1]).astimezone(timezone.utc).isoformat()
                payload={'station_id':sid,'water_level_m':row[2] or None,'level_grade':row[3],
                         'level_symbol':row[4],'level_qa':row[5],'discharge_m3_s':row[6] or None,
                         'discharge_grade':row[7],'discharge_symbol':row[8],'discharge_qa':row[9]}
                records.append((stamp,stamp,payload,str(archive_relative(path, DATA))))
            previous=self.store.cursor(kind,sid)
            if previous and records and parse_time(previous)<min(parse_time(r[1]) for r in records):
                log({'event':'water_retrieval_window_gap','station':sid,'previous':previous,'earliest_returned':min(r[1] for r in records),'at':now()})
            return records
        if kind!='swob':raise ValueError(f'Unsupported source: {kind}')
        current=datetime.now(timezone.utc)
        previous=self.store.cursor(kind,sid)
        start=parse_time(previous)-timedelta(hours=6) if previous else current-timedelta(hours=48)
        if start<current-timedelta(days=29):
            log({'event':'weather_retention_gap','station':sid,'previous':previous,'at':now()})
            start=current-timedelta(days=29)
        url=API+'/swob-realtime/items'
        params={'msc_id-value':sid,'datetime':f'{start.isoformat()}/{current.isoformat()}',
                'sortby':'date_tm-value','limit':1000,'f':'json'}
        visited=set()
        for page in range(200):
            if self.stop.is_set():return None
            obj=get_json(url,f'{folder}/{sid}_{page:03}.json',params,reuse=False,timeout=20)
            fs=obj.get('features')
            if not isinstance(fs,list):raise ValueError('SWOB schema changed: missing features')
            for f in fs:
                p=f['properties']
                if str(p.get('msc_id-value'))!=sid:raise ValueError('Wrong weather station returned')
                stamp=parse_time(p['date_tm-value']).astimezone(timezone.utc).isoformat()
                records.append((f['id'],stamp,p,f'{folder}/{sid}_{page:03}.json'))
            next_url=next((x['href'] for x in obj.get('links',[]) if x.get('rel')=='next'),None)
            if not next_url: return records
            if next_url in visited or not next_url.startswith('https://api.weather.gc.ca/'):
                raise ValueError('Invalid/repeated pagination URL')
            visited.add(next_url);url=next_url;params=None
        raise ValueError('SWOB pagination limit exceeded; cursor not advanced')


def listen_for_stop(stop,stream=None):
    stream=stream or sys.stdin
    for line in stream:
        if line.strip().lower()=='stop':
            print('Stop requested. Finishing in-flight requests and saving data.',flush=True)
            stop.set();return
    # An EOF is not permission to leave an uncontrolled background collector.
    stop.set()


def load_config(path=None):
    cfg=json.loads(Path(path or resolve_runtime_path(ROOT/'config/stations.json')).read_text(encoding='utf-8'))
    for station in cfg['stations']:
        if station.get('enabled'):
            station_interval(station['sources'])
        station['calculation_interval_seconds']=station_calculation_interval(station)
    return cfg


def run(config, *, collect_immediately=True, dry_run=False, selected=None,
        duration_seconds=None, detached=False):
    if duration_seconds is not None and (isinstance(duration_seconds,bool) or
            not isinstance(duration_seconds,(int,float)) or not math.isfinite(duration_seconds) or duration_seconds<=0):
        raise ValueError('duration_seconds must be a positive finite number')
    if detached and duration_seconds is None:
        raise ValueError('Detached collection requires a finite duration')
    stations=[s for s in config['stations'] if s.get('enabled') and (not selected or s['station_id'] in selected)]
    if not stations:raise ValueError('No enabled monitoring stations selected')
    stop=threading.Event()
    old=signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT,lambda *args:stop.set())
    schedules=source_schedules(stations)
    notifications=None
    water_ids=[sid for kind,sid in schedules if kind=='hydrometric_hourly_csv']
    try:
        if water_ids and not dry_run:
            from API.datamart_notifications import DatamartNotifications
            notifications=DatamartNotifications(water_ids,stop)
            notifications.start()
        collector=Collector(stop) if not dry_run else None
    except Exception:
        stop.set()
        if notifications:notifications.close()
        signal.signal(signal.SIGINT,old)
        raise
    if not detached:
        threading.Thread(target=listen_for_stop,args=(stop,),daemon=True).start()
    started=time.monotonic()
    started_utc=datetime.now(timezone.utc)
    deadline=started+duration_seconds if duration_seconds is not None else None
    deadline_utc=(started_utc+timedelta(seconds=duration_seconds)).isoformat() if duration_seconds is not None else None
    run_id=started_utc.strftime('%Y%m%dT%H%M%S')+'_'+uuid4().hex[:8]
    stop_file=resolve_runtime_path(DATA/'state'/f'{run_id}.stop')
    stop_reason=['stop_or_keyboard_interrupt_or_stdin_closed']
    def deadline_watch():
        while not stop.wait(0.2):
            if stop_file.exists():
                stop_reason[0]='stop_file';stop.set()
            elif deadline is not None and time.monotonic()>=deadline:
                stop_reason[0]='duration_elapsed';stop.set()
    controller=threading.Thread(target=deadline_watch,daemon=True)
    controller.start()
    due={key:started+(0 if collect_immediately else job['source']['publication_interval_seconds'])
         for key,job in schedules.items()}
    pending={};jobs=0;completed=0;errors=0
    initial_water=set(water_ids) if collect_immediately else set()
    state_path=resolve_runtime_path(DATA/'state'/f'{run_id}.json')
    def write_state(status):
        state={'run_id':run_id,'pid':os.getpid(),'status':status,
               'started_at_utc':started_utc.isoformat(),'deadline_utc':deadline_utc,
               'duration_seconds':duration_seconds,'jobs_submitted':jobs,
               'jobs_completed':completed,'jobs_with_errors':errors,'dry_run':dry_run,
               'station_count':len(stations),'source_schedule_count':len(schedules),
               'stop_file':str(archive_relative(stop_file, ROOT)),
               'datamart_mode':'initial_snapshot_then_amqps_notifications',
               'datamart_notifications':notifications.status() if notifications else None}
        if status=='stopped':
            state.update(stopped_at_utc=now(),reason=stop_reason[0])
        save_json(state_path,state)
        save_json(resolve_runtime_path(DATA/'state/active_run.json'),state)
        if status=='stopped':save_json(resolve_runtime_path(DATA/'state/last_run.json'),state)
        return state
    control='Run python -m API stop to stop.' if detached else 'Type stop then Enter to stop.'
    print(f'{len(stations)} monitoring points; {len(schedules)} independent source schedules. {control} Dry run={dry_run}',flush=True)
    def source_job(source):
        if stop.is_set():return {'status':'stopped'}
        return {'status':'dry_run'} if dry_run else collector.collect(source)
    try:
        write_state('running')
        print(json.dumps({'run_id':run_id,'started_at_utc':started_utc.isoformat(),
                          'deadline_utc':deadline_utc,'stop_file':str(stop_file)},ensure_ascii=True),flush=True)
        last_state=started
        with ThreadPoolExecutor(max_workers=config.get('max_workers',4)) as pool:
            while not stop.is_set():
                current=time.monotonic()
                if deadline is not None and current>=deadline:
                    stop_reason[0]='duration_elapsed';stop.set();break
                for key,job in schedules.items():
                    if stop.is_set():break
                    source=job['source']
                    future=pending.get(key)
                    if future and future.done():
                        result=future.result();print(':'.join(key),json.dumps(result),flush=True)
                        completed+=1
                        if result.get('status')=='error':
                            errors+=1
                            if notifications and key[0]=='hydrometric_hourly_csv':notifications.restore(key[1])
                        del pending[key]
                        due[key]=current+source['publication_interval_seconds']
                    if key not in pending and current>=due[key]:
                        if notifications and key[0]=='hydrometric_hourly_csv':
                            if key[1] in initial_water:initial_water.remove(key[1])
                            elif not notifications.take(key[1]):continue
                        pending[key]=pool.submit(source_job,source);jobs+=1
                if current-last_state>=10:
                    write_state('running');last_state=current
                stop.wait(0.2)
            for future in pending.values():future.cancel()
            # Executor finishes only requests already in flight; stop blocks
            # every subsequent source and pagination request.
        for key,future in pending.items():
            if not future.cancelled():
                result=future.result();completed+=1
                if result.get('status')=='error':errors+=1
                print(':'.join(key),json.dumps(result),flush=True)
    finally:
        stop.set()
        if notifications:notifications.close()
        controller.join(timeout=1)
        signal.signal(signal.SIGINT,old)
        write_state('stopped')
        if stop_file.exists():stop_file.unlink()
        print('Stopped; no background acquisition remains.',flush=True)
