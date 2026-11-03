"""Project-local PostgreSQL credentials and read-only training-view access."""
from datetime import datetime, timezone
import json
import os

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from project_paths import WORKSPACE


def connection_options():
    keys = {'PGHOST': 'host', 'PGPORT': 'port', 'PGDATABASE': 'dbname',
            'PGUSER': 'user', 'PGPASSWORD': 'password', 'PGSSLMODE': 'sslmode'}
    values = {key: os.environ[key] for key in keys if os.environ.get(key)}
    path = WORKSPACE / '.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip() or line.lstrip().startswith('#') or '=' not in line:
                continue
            name, value = line.split('=', 1)
            name, value = name.strip(), value.strip()
            if name in keys:
                if len(value)>1 and value[0]==value[-1] and value[0] in {'"', "'"}:
                    value = value[1:-1]
                values[name] = value
    if not values.get('PGDATABASE'):
        raise ValueError('Set PGDATABASE in the movetest .env file')
    return {**{keys[key]: value for key,value in values.items()}, 'connect_timeout': 10,
            'application_name': 'rdr_joint_ml'}


def connect():
    options = connection_options()
    try:
        return psycopg.connect(**options, row_factory=dict_row)
    except psycopg.Error as exc:
        message = str(exc)
        if options.get('password'):
            message = message.replace(options['password'], '[redacted]')
        raise RuntimeError('PostgreSQL connection failed: '+message) from None


def json_value(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return value


def read_training_views(config_path):
    config = json.loads(config_path.read_text(encoding='utf-8'))
    schema = config['schema']
    tables, partitions = {}, {}
    with connect() as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        if db.execute('SELECT current_database() AS name').fetchone()['name'] != config['database']:
            raise ValueError('The .env database differs from the configured dataset database')
        def read(view):
            with db.cursor(name='read_'+view) as cursor:
                cursor.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(schema,view)))
                return [{key:json_value(value) for key,value in row.items()} for row in cursor]
        metadata = read('v_dataset_metadata')[0]
        metadata.pop('source_manifest', None)
        if metadata['dataset_id'] != config['dataset_id']:
            raise ValueError('Database dataset identifier differs from the configured snapshot')
        for name in ['model_segments','model_segment_legs','sections','section_profile_points']:
            tables[name] = read('v_'+name)
        tables['water_observations'] = read('v_input_history') + read('v_endpoint_observations')
        tables['lake_reference'] = read('v_lake_history')
        for name in ['train','validation','test']:
            rows = read(config.get('partition_views', {}).get(name, 'v_'+name))
            partitions[name] = sorted(row['forecast_origin_at'] for row in rows)
        metadata['source'] = 'postgresql_views'
        metadata['schema'] = schema
        metadata['database'] = config['database']
        metadata['view_counts'] = {name:len(values) for name,values in partitions.items()}
    return tables, partitions, metadata
