"""Reproducible local ETL from archived source observations and survey files."""
from project_paths import resolve_runtime_path, archive_relative
from collections import defaultdict, Counter
from contextlib import closing
import csv
from datetime import timedelta, timezone
import json
import sqlite3

from rdr.storage import DATA, ROOT, save_json, now
from API.observations import parse_time
from .rainfall import finite,normalize_swob,aggregate_precipitation
from .hydraulics import section_geometry,screen_section
from API.collector import station_calculation_interval


def metadata(path):
    sidecar=path.with_suffix(path.suffix+'.meta.json')
    return json.loads(sidecar.read_text(encoding='utf-8')) if sidecar.exists() else {}


def normalize_archives():
    water={};rain={};issues=[]
    def add_water(row):
        key=(row['station_id'],row['observed_at'],row['resolution'])
        rank=(row.get('available_at') or '',row['source']=='hydrometric_hourly_csv')
        old=water.get(key)
        if old is None or rank>(old.get('available_at') or '',old['source']=='hydrometric_hourly_csv'):water[key]=row
    csv_paths=list((resolve_runtime_path(DATA/'sources/eccc_hydrometric_datamart/raw/validation/hydrometric_hourly')).glob('*.csv'))+list((resolve_runtime_path(DATA/'sources/eccc_hydrometric_datamart/raw/live')).rglob('*.csv'))
    for path in csv_paths:
        sid=path.stem;meta=metadata(path)
        if meta.get('status',200)!=200:
            issues.append({'file':str(archive_relative(path, DATA)),'reason':'source_http_error','http_status':meta['status']})
            continue
        with path.open(encoding='utf-8-sig',newline='') as handle:
            rows=csv.reader(handle);next(rows,None)
            for row in rows:
                if len(row)<10 or row[0]!=sid:
                    issues.append({'file':str(archive_relative(path, DATA)),'reason':'invalid_hydrometric_row'});continue
                stamp=parse_time(row[1]).astimezone(timezone.utc).isoformat()
                level,q=finite(row[2]),finite(row[6])
                add_water({'station_id':sid,'observed_at':stamp,'level_m':level,
                    'discharge_m3_s':q if q is not None and q>=0 else None,
                    'level_quality':row[5],'discharge_quality':row[9],'level_symbol':row[4],
                    'discharge_symbol':row[8],'resolution':'instantaneous','source':'hydrometric_hourly_csv',
                    'raw_path':str(archive_relative(path, DATA)),'available_at':meta.get('received_at_utc'),
                    'qa_status':'provisional_source_values_preserved',
                    'ice_flag':row[4]=='B' or row[8]=='B'})
    for path in (resolve_runtime_path(DATA/'sources/eccc_hydrometric_geomet/raw/validation/hydrometric')).glob('*.json'):
        if path.name.endswith('.meta.json'):continue
        meta=metadata(path)
        try:features=json.loads(path.read_text(encoding='utf-8')).get('features',[])
        except (ValueError,AttributeError):continue
        daily='_historical' in path.stem
        for f in features:
            p=f['properties'];stamp=p.get('DATE') if daily else p.get('DATETIME')
            if not stamp:continue
            sid=p.get('STATION_NUMBER')
            if sid!=path.stem.replace('_historical',''):raise ValueError('Water station identity mismatch')
            q=finite(p.get('DISCHARGE'))
            add_water({'station_id':sid,'observed_at':parse_time(stamp).astimezone(timezone.utc).isoformat(),
                'level_m':finite(p.get('LEVEL')),'discharge_m3_s':q if q is not None and q>=0 else None,
                'resolution':'daily_mean' if daily else 'instantaneous','source':'geomet',
                'raw_path':str(archive_relative(path, DATA)),'available_at':meta.get('received_at_utc'),
                'source_quality':{k:v for k,v in p.items() if any(s in k for s in ['SYMBOL','FLAG','APPROVAL'])},
                'ice_flag':any(v=='B' for k,v in p.items() if 'SYMBOL' in k)})
    paths=[]
    for folder in [resolve_runtime_path(DATA/'sources/eccc_weather_geomet/raw/validation/weather'),resolve_runtime_path(DATA/'sources/eccc_weather_geomet/raw/validation/etl_weather'),resolve_runtime_path(DATA/'sources/eccc_weather_geomet/raw/live')]:
        paths.extend(folder.rglob('*.json'))
    for path in paths:
        if path.name.endswith('.meta.json'):continue
        meta=metadata(path)
        obj=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(obj,dict):continue
        for f in obj.get('features',[]):
            p=f.get('properties',{})
            if not p.get('msc_id-value') or not p.get('date_tm-value'):continue
            for row in normalize_swob(p,str(archive_relative(path, DATA)),meta.get('received_at_utc'),f.get('id')):
                key=(row['station_id'],row['field'],row['start'],row['end'])
                rank=(row.get('published_at') or '',row.get('available_at') or '',row['record_id'])
                old=rain.get(key)
                oldrank=(old.get('published_at') or '',old.get('available_at') or '',old['record_id']) if old else None
                if old is None or rank>oldrank:rain[key]=row
    return list(water.values()),list(rain.values()),issues


def station_windows(water,rain,config):
    by_station=defaultdict(list);weather=defaultdict(list)
    for r in water:
        if r['resolution']=='instantaneous':by_station[r['station_id']].append(r)
    for r in rain:weather[r['station_id']].append(r)
    output=[]
    for station in config['stations']:
        sid=station['station_id'];records=by_station[sid]
        interval=station_calculation_interval(station)
        if not records or not interval:
            output.append({'station_id':sid,'status':'no_instantaneous_water_or_calculation_cadence',
                'weather_station_id':station.get('weather_link',{}).get('weather_id'),'window_end':None,
                'precipitation_total_mm':None,'mean_precipitation_intensity_mm_h':None})
            continue
        records.sort(key=lambda r:r['observed_at']);latest=records[-1]
        ending=parse_time(latest['observed_at']);earliest=parse_time(records[0]['observed_at'])
        lookup={r['observed_at']:r for r in records};weather_id=station.get('weather_link',{}).get('weather_id')
        weather_records=weather[weather_id]
        # Anchor this snapshot at its latest water observation, not fetch time.
        windows=[]
        while ending>=earliest:
            stamp=ending.isoformat();observation=lookup.get(stamp)
            if observation:
                start=ending-timedelta(seconds=interval)
                candidates=[r for r in weather_records if parse_time(r['end'])>start and parse_time(r['start'])<ending]
                result=aggregate_precipitation(candidates,start.isoformat(),stamp)
                windows.append({'station_id':sid,'weather_station_id':weather_id,**result,
                    'level_m':observation['level_m'],'discharge_m3_s':observation['discharge_m3_s'],
                    'water_observed_at':stamp,'water_available_at':observation.get('available_at'),
                    'water_raw_path':observation['raw_path'],'water_ice_flag':observation.get('ice_flag',False),
                    'weather_distance_km':station.get('weather_link',{}).get('distance_km'),
                    'weather_spatial_role':'nearby_point_observation_not_basin_mean',
                    'aggregation_basis':'retrospective_archived_observations_not_operational_backtest',
                    'latest_for_station':observation is latest,
                    'calculation_interval_seconds':interval})
            ending-=timedelta(seconds=interval)
        output.extend(reversed(windows))
    return output


def calculate_sections(sections,profiles,links,windows,datums,calibration):
    latest={r['station_id']:r for r in windows if r.get('latest_for_station')}
    links={r['section_id']:r for r in links};datum_map={r['station_id']:r for r in datums.get('stations',[])}
    results=[];survey_geometry=[]
    for section in sections:
        sid=section['section_id'];profile=profiles.get(sid,[]);link=links[sid]
        station_id=link.get('station_id');water=latest.get(station_id);approval=calibration.get('sections',{}).get(sid,{})
        conversions=datum_map.get(station_id,{}).get('conversions',[])
        cgvd28=next((c for c in conversions if c['target_datum']=='CGVD28_conventional'),None)
        reasons=[]
        if len(profile)<2:reasons.append('insufficient_profile')
        if not water:reasons.append('no_water_observation')
        elif water.get('level_m') is None:reasons.append('missing_water_level')
        if water and water.get('water_ice_flag'):reasons.append('ice_conditions')
        if not cgvd28:reasons.append('no_compatible_documented_datum_conversion')
        # Evidence-reviewed calibration is separate from automatically generated links.
        required=['datum_verified','transfer_verified','profile_verified','banks_verified']
        for key in required:
            if not approval.get(key):reasons.append(key+'_not_confirmed')
        if approval and (approval.get('station_id')!=station_id or not approval.get('evidence')):
            reasons.append('calibration_station_or_evidence_mismatch')
        banks=approval.get('bank_elevations_m')
        if approval and (not isinstance(banks,list) or len(banks)!=2 or any(finite(z) is None for z in banks)):
            reasons.append('two_verified_bank_elevations_required')
        if approval and not all(approval.get(k) for k in ['valid_from','valid_to']):reasons.append('calibration_validity_missing')
        if approval and water and approval.get('valid_from') and approval.get('valid_to'):
            at=parse_time(water['water_observed_at'])
            if not parse_time(approval['valid_from'])<=at<=parse_time(approval['valid_to']):reasons.append('calibration_outside_validity')
        result={'section_id':sid,'station_id':station_id,'status':'indeterminate','reasons':reasons,
                'risk_level':None,'water_observed_at':water.get('water_observed_at') if water else None,
                'documented_gauge_zero_candidate_m':cgvd28['add_m'] if cgvd28 else None,
                'precipitation_total_mm':water.get('precipitation_total_mm') if water else None,
                'mean_precipitation_intensity_mm_h':water.get('mean_precipitation_intensity_mm_h') if water else None,
                'rainfall_role':'context_only_until_incremental_catchment_runoff_model_is_validated'}
        if not reasons:
            parameters={k:approval[k] for k in required}
            result.update(screen_section(profile,level_m=water['level_m']+approval.get('water_level_transfer_offset_m',0),
                gauge_zero_m=cgvd28['add_m'],discharge_m3_s=water['discharge_m3_s'],
                bank_elevations_m=approval.get('bank_elevations_m'),connected_offset_m=approval.get('connected_offset_m'),**parameters))
        results.append(result)
        h=section.get('survey_water_elevation_median_m')
        if h is not None and len(profile)>=2:
            geometry=section_geometry(profile,h)
            survey_geometry.append({'section_id':sid,**geometry,
                'status':'historical_survey_geometry_preview',
                'survey_years':section['survey_years'],
                'water_surface_basis':'median_of_positive_survey_Water_Level_Elevation_values',
                'water_surface_range_m':section.get('survey_water_elevation_range_m'),
                'profile_status':section['profile_status'],'live_water_level_used':False})
    return results,survey_geometry


def export_csv(path,records,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for row in records:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items() if k in fields})


def write_database(folder,tables):
    path=folder/'project.sqlite3';temporary=folder/'project.build.sqlite3'
    if temporary.exists():temporary.unlink()
    with closing(sqlite3.connect(temporary)) as db, db:
        for name,(records,key) in tables.items():
            # Table names are fixed internal literals; never provider text.
            db.execute(f'CREATE TABLE {name} (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
            db.executemany(f'INSERT INTO {name} VALUES (?,?)',[(str(key(r,i)),json.dumps(r,ensure_ascii=False,allow_nan=False)) for i,r in enumerate(records)])
        db.execute('CREATE TABLE manifest (built_at TEXT, note TEXT)')
        db.execute('INSERT INTO manifest VALUES (?,?)',(now(),'Derived snapshot; source files remain untouched'))
    temporary.replace(path)


def run_pipeline(*,rebuild_spatial=True):
    from rdr_gis.spatial import normalize_surveys,build_links
    folder=resolve_runtime_path(DATA/'processed/etl');folder.mkdir(parents=True,exist_ok=True)
    if rebuild_spatial:
        sections,points,profiles=normalize_surveys()
        links,mouths,coverage=build_links(sections,json.loads((resolve_runtime_path(DATA/'processed/station_master.json')).read_text()))
        for name,obj in [('sections',sections),('survey_points',points),('profiles',profiles),('section_station_links',links),
                         ('confluence_links',mouths),('station_section_coverage',coverage)]:save_json(folder/(name+'.json'),obj)
    else:
        sections,points,profiles,links,mouths,coverage=[json.loads((folder/(name+'.json')).read_text(encoding='utf-8')) for name in
            ['sections','survey_points','profiles','section_station_links','confluence_links','station_section_coverage']]
    config=json.loads((resolve_runtime_path(ROOT/'config/stations.json')).read_text())
    water,rain,issues=normalize_archives();print('Normalized water',len(water),'precipitation intervals',len(rain),flush=True)
    windows=station_windows(water,rain,config);print('Station windows',len(windows),flush=True)
    datum_path=resolve_runtime_path(DATA/'processed/station_datums.json')
    datums=json.loads(datum_path.read_text()) if datum_path.exists() else {'stations':[]}
    calibration=json.loads((resolve_runtime_path(ROOT/'config/section_calibration.json')).read_text())
    calculations,survey_geometry=calculate_sections(sections,profiles,links,windows,datums,calibration)
    for name,obj in [('water_observations',water),('precipitation_intervals',rain),('station_windows',windows),
                     ('section_calculations',calculations),('survey_geometry',survey_geometry),('normalization_issues',issues)]:
        save_json(folder/(name+'.json'),obj)
    exports=[('sections',sections,['section_id','study','river','source_section_id','line_status','profile_status','point_count',
        'profile_span_m','maximum_point_line_distance_m','longitude','latitude','reach_id','vertical_datum','bank_a_candidate_elevation_m','bank_b_candidate_elevation_m']),
        ('survey_points',points,['point_key','study','source_point_id','section_id','assignment_status','x_m','y_m','elevation_m','offset_m','line_distance_m','code','survey_date','vertical_datum']),
        ('station_windows',windows,['station_id','weather_station_id','window_start','window_end','status','level_m','discharge_m3_s',
          'precipitation_total_mm','mean_precipitation_intensity_mm_h','coverage_fraction','input_interval_count','water_observed_at','latest_for_station']),
        ('section_calculations',calculations,['section_id','station_id','status','reasons','risk_level','documented_gauge_zero_candidate_m',
          'area_m2','mean_velocity_m_s','freeboard_m','water_observed_at']),
        ('survey_geometry',survey_geometry,['section_id','status','water_surface_elevation_m','area_m2','surface_width_m','wet_components','profile_truncated','survey_years']),
        ('station_section_coverage',coverage,list(coverage[0]))]
    for name,rows,fields in exports:export_csv(folder/(name+'.csv'),rows,fields)
    write_database(folder,{
        'sections':(sections,lambda r,i:r['section_id']),'survey_points':(points,lambda r,i:r['point_key']),
        'section_station_links':(links,lambda r,i:r['section_id']),'confluences':(mouths,lambda r,i:r['confluence_id']),
        'station_datums':(datums['stations'],lambda r,i:r['station_id']),
        'water_observations':(water,lambda r,i:f"{r['station_id']}:{r['observed_at']}:{r['resolution']}"),
        'precipitation_intervals':(rain,lambda r,i:f"{r['station_id']}:{r['field']}:{r['end']}"),
        'station_windows':(windows,lambda r,i:f"{r['station_id']}:{r.get('window_end')}"),
        'section_calculations':(calculations,lambda r,i:r['section_id']),
        'survey_geometry':(survey_geometry,lambda r,i:r['section_id'])})
    report={'generated_at':now(),'scope':'Original full-basin catalogue retained; no fabricated coverage',
        'sections':len(sections),'survey_points':len(points),'profiles':len(profiles),'stations':len(config['stations']),
        'section_profile_status':dict(Counter(s['profile_status'] for s in sections)),
        'point_assignment_status':dict(Counter(s['assignment_status'] for s in points)),
        'section_station_link_methods':dict(Counter(s['link_method'] for s in links)),
        'stations_with_section_within_1km':sum(s['section_within_1km'] for s in coverage),
        'water_observations':len(water),'precipitation_intervals':len(rain),
        'precipitation_quality':dict(Counter(s.get('invalid_reason') or s['quality_status'] for s in rain)),
        'window_status':dict(Counter(s['status'] for s in windows)),
        'latest_window_status':dict(Counter(s['status'] for s in windows if s.get('latest_for_station'))),
        'section_calculation_status':dict(Counter(s['status'] for s in calculations)),
        'calculation_blockers':dict(Counter(reason for s in calculations for reason in s.get('reasons',[]))),
        'historical_survey_geometry_previews':len(survey_geometry),'live_collection_started':False,
        'datum_status':dict(Counter(s['status'] for s in datums['stations'])),
        'normalization_issues':len(issues)}
    save_json(resolve_runtime_path(DATA/'reports/etl_validation.json'),report)
    print(json.dumps(report,indent=2),flush=True)
    return report
