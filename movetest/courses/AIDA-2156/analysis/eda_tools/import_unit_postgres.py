"""Import an immutable unit-value snapshot and create joint-training SQL views."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3

from psycopg import sql
from psycopg.types.json import Jsonb

from project_paths import WORKSPACE
from rdr_eda.postgres import connect, connection_options
from rdr_eda.project_etl import companion

BASE = WORKSPACE / 'courses/AIDA-2156/data'
DEFAULT_UNITS = BASE/'processed/model_unit_history/20261103T070414Z/unit_observations.sqlite3'
DEFAULT_GEOMETRY = BASE/'processed/project_etl/project.sqlite3'
CONFIG = WORKSPACE/'shared-resources/config/postgres_dataset.json'


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            digest.update(block)
    return digest.hexdigest()


def copy_table(db, schema, source, table, target=None):
    target = target or table
    columns = source.execute(f'PRAGMA table_info("{table}")').fetchall()
    if not columns:
        raise ValueError('Missing source table '+table)
    definitions = []
    for column in columns:
        name, declared = column[1], column[2]
        kind = 'double precision' if declared.upper()=='REAL' else 'text'
        if name in {'observed_at','received_at'}:
            kind = 'timestamptz'
        definitions.append(sql.SQL('{} {}').format(sql.Identifier(name),sql.SQL(kind)))
    db.execute(sql.SQL('CREATE TABLE {} ({})').format(sql.Identifier(schema,target),sql.SQL(',').join(definitions)))
    with db.cursor() as cursor:
        with cursor.copy(sql.SQL('COPY {} FROM STDIN').format(sql.Identifier(schema,target))) as copy:
            for row in source.execute(f'SELECT * FROM "{table}"'):
                copy.write_row(row)
    count = db.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(schema,target))).fetchone()['n']
    expected = source.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    if count != expected:
        raise ValueError('Imported count mismatch for '+table)
    print('Imported',target,count,flush=True)
    return count


def create_views(db, schema):
    def execute(text):
        db.execute(sql.SQL(text).format(s=sql.Identifier(schema)))
    pivot = []
    for parameter,prefix in [('46','level'),('47','discharge')]:
        for field in ['value','qualifier','symbol','approval','grade','qualifiers','source_path','received_at']:
            suffix = ('m' if prefix=='level' else 'm3_s') if field=='value' else field
            pivot.append(f"max(CASE WHEN parameter='{parameter}' THEN {field} END) AS {prefix}_{suffix}")
    execute('CREATE MATERIALIZED VIEW {s}.station_observations AS SELECT station_id,observed_at,'+
            ','.join(pivot)+' FROM {s}.parameter_observations GROUP BY station_id,observed_at')
    execute('CREATE UNIQUE INDEX station_observations_key ON {s}.station_observations(station_id,observed_at)')
    execute('CREATE VIEW {s}.v_observations AS SELECT station_id,observed_at,level_m,discharge_m3_s,'
            "CASE WHEN station_id<>'05CC003' AND level_m>=0 THEN level_m END AS experimental_variable_depth_m,"
            'level_grade AS level_quality,discharge_grade AS discharge_quality,level_approval,discharge_approval,'
            'level_symbol,discharge_symbol,level_qualifier,discharge_qualifier,level_qualifiers,discharge_qualifiers,'
            'level_source_path AS source_path,discharge_source_path,'
            'greatest(level_received_at,discharge_received_at) AS received_at '
            'FROM {s}.station_observations')
    execute("CREATE VIEW {s}.v_input_history AS SELECT * FROM {s}.v_observations WHERE station_id IN ('05CB007','05CB001','05CC007')")
    execute("CREATE VIEW {s}.v_endpoint_observations AS SELECT * FROM {s}.v_observations WHERE station_id='05CC002'")
    execute("CREATE VIEW {s}.v_lake_history AS SELECT * FROM {s}.v_observations WHERE station_id='05CC003'")
    execute('ALTER TABLE {s}.candidate_splits ADD PRIMARY KEY(observed_at)')
    execute("ALTER TABLE {s}.candidate_splits ADD CHECK(partition IN ('training','validation','test'))")
    columns = ['c.observed_at AS forecast_origin_at','c.partition']
    joins = []
    for i,sid in enumerate(['05CB007','05CB001','05CC007','05CC003']):
        alias = 's'+str(i)
        joins.append(f"JOIN {{s}}.station_observations {alias} ON {alias}.station_id='{sid}' AND {alias}.observed_at=c.observed_at")
        columns.append(f'{alias}.level_m AS "{sid}_level_m"')
        if sid != '05CC003':
            columns.append(f'{alias}.discharge_m3_s AS "{sid}_discharge_m3_s"')
    execute('CREATE VIEW {s}.v_features AS SELECT '+','.join(columns)+' FROM {s}.candidate_splits c '+' '.join(joins))
    for view,partition in [('train','training'),('validation','validation'),('test','test')]:
        execute(f"CREATE VIEW {{s}}.v_{view} AS SELECT * FROM {{s}}.v_features WHERE partition='{partition}'")
    for table in ['model_segments','model_segment_legs','sections','section_profile_points','dataset_metadata']:
        execute(f'CREATE VIEW {{s}}.v_{table} AS SELECT * FROM {{s}}.{table}')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units',type=Path,default=DEFAULT_UNITS)
    parser.add_argument('--geometry',type=Path,default=DEFAULT_GEOMETRY)
    parser.add_argument('--split', choices=['60-20-20','80-20'], default='60-20-20')
    args=parser.parse_args()
    hashes={'unit_sha256':digest_file(args.units),'geometry_source_sha256':digest_file(args.geometry)}
    dataset_id=hashlib.sha256(json.dumps(hashes,sort_keys=True).encode()).hexdigest()
    schema='rdr_unit_'+dataset_id[:16]
    counts={}
    with sqlite3.connect(args.units.resolve().as_uri()+'?mode=ro',uri=True) as units, sqlite3.connect(args.geometry.resolve().as_uri()+'?mode=ro',uri=True) as geometry:
        with connect() as db:
            db.execute("SET LOCAL TIME ZONE 'UTC'")
            db.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',(schema,))
            exists=db.execute('SELECT EXISTS(SELECT 1 FROM pg_namespace WHERE nspname=%s) AS found',(schema,)).fetchone()['found']
            if exists:
                saved=db.execute(sql.SQL('SELECT dataset_id FROM {}').format(sql.Identifier(schema,'dataset_metadata'))).fetchone()
                if saved['dataset_id']!=dataset_id:
                    raise ValueError('Existing schema identifier mismatch')
            else:
                db.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(schema)))
                for table in ['parameter_observations','candidate_splits']:
                    counts[table]=copy_table(db,schema,units,table)
                db.execute(sql.SQL('ALTER TABLE {} ADD PRIMARY KEY(station_id,observed_at,parameter)').format(sql.Identifier(schema,'parameter_observations')))
                db.execute(sql.SQL("ALTER TABLE {} ADD CHECK(parameter IN ('46','47'))").format(sql.Identifier(schema,'parameter_observations')))
                for table in ['model_segments','model_segment_legs','sections','section_profile_points']:
                    counts[table]=copy_table(db,schema,geometry,table)
                db.execute(sql.SQL('CREATE TABLE {} (dataset_id text PRIMARY KEY, unit_sha256 text, geometry_source_sha256 text, imported_at timestamptz, source_manifest jsonb)').format(sql.Identifier(schema,'dataset_metadata')))
                report_path=args.units.parent/'analysis_report.json'
                source_report=json.loads(report_path.read_text(encoding='utf-8'))
                db.execute(sql.SQL('INSERT INTO {} VALUES (%s,%s,%s,%s,%s)').format(sql.Identifier(schema,'dataset_metadata')),
                           (dataset_id,hashes['unit_sha256'],hashes['geometry_source_sha256'],datetime.now(timezone.utc),Jsonb(source_report)))
                create_views(db,schema)
            if args.split == '80-20':
                for name, condition in [('train','row_number <= floor(total * 0.8)'),('validation','false'),('test','row_number > floor(total * 0.8)')]:
                    columns = 'forecast_origin_at, '+("'training'" if name=='train' else "'"+name+"'")+"::text AS partition, "+', '.join('"'+sid+'_'+field+'"' for sid in ['05CB007','05CB001','05CC007','05CC003'] for field in (['level_m'] if sid=='05CC003' else ['level_m','discharge_m3_s']))+', row_number, total'
                    db.execute(sql.SQL('CREATE OR REPLACE VIEW {} AS SELECT '+columns+' FROM (SELECT f.*, row_number() OVER (ORDER BY forecast_origin_at), count(*) OVER () AS total FROM {} f) ranked WHERE '+condition).format(sql.Identifier(schema,'v_8020_'+name),sql.Identifier(schema,'v_features')))
                    counts['v_8020_'+name] = db.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(schema,'v_8020_'+name))).fetchone()['n']
            for table in ['parameter_observations','candidate_splits','station_observations','model_segments','model_segment_legs','sections','section_profile_points','v_train','v_validation','v_test']:
                counts[table]=db.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(schema,table))).fetchone()['n']
            expected=units.execute('SELECT count(*) FROM parameter_observations').fetchone()[0]
            if counts['parameter_observations']!=expected:
                raise ValueError('Stored unit-value count mismatch')
            expected_splits=dict(units.execute('SELECT partition,count(*) FROM candidate_splits GROUP BY partition'))
            for view,name in [('v_train','training'),('v_validation','validation'),('v_test','test')]:
                if counts[view]!=expected_splits[name]:
                    raise ValueError('Training view count mismatch')
            database=db.execute('SELECT current_database() AS name').fetchone()['name']
    config={'database':database,'schema':schema,'dataset_id':dataset_id,'source':'postgresql_views'}
    config_path = CONFIG
    if args.split == '80-20':
        config['partition_views'] = {name:'v_8020_'+name for name in ['train','validation','test']}
        config_path = CONFIG.with_name('postgres_dataset_8020.json')
    config_path.write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
    companion(config_path,'Selects the immutable PostgreSQL unit-value snapshot and its training views. Credentials are loaded separately from movetest/.env.',
              '指定 PostgreSQL 逐次观测快照及训练 view。凭据单独从 movetest/.env 读取。')
    report={'imported_at':datetime.now(timezone.utc).isoformat(),**config,**hashes,'counts':counts,
            'daily_data_imported':False,'status':'imported_and_views_verified'}
    path=BASE/'reports/postgresql_unit_import.json'
    path.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    split_report = path.with_name('postgresql_unit_import_' + args.split.replace('-', '_') + '.json')
    split_report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    companion(split_report, 'Split-specific import verification; preserves both partition checks.',
              '\u5206\u522b\u4fdd\u7559\u4e24\u79cd\u5212\u5206\u7684\u5bfc\u5165\u6838\u5b9e\u8bb0\u5f55\u3002')
    companion(path,'Verified PostgreSQL import, snapshot hashes and table/view counts. Created by import_unit_postgres.',
              'import_unit_postgres 生成的 PostgreSQL 导入核实记录，包含快照哈希和表/view 数量。')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
