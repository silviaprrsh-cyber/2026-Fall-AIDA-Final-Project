"""Project-local PostgreSQL credentials and read-only training-view access."""
from datetime import datetime, timezone
import json
import os

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

from project_paths import WORKSPACE


from project_tools.database import connection_options, connect


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


def read_forward_routing_view(config_path, start_at, end_at):
    """Read an explicit historical model input range from PostgreSQL only."""
    if (start_at.tzinfo is None or end_at.tzinfo is None or
            start_at.utcoffset() is None or end_at.utcoffset() is None or start_at >= end_at):
        raise ValueError('Routing requires a nonempty timezone-aware [start, end) range')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    with connect('rdr_forward_training_read') as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        actual = db.execute('SELECT current_database() AS name').fetchone()['name']
        if actual != config['database']:
            raise ValueError('Database differs from the configured routing dataset')
        schema = config['schema']
        metadata = db.execute(sql.SQL('SELECT dataset_id FROM {}').format(
            sql.Identifier(schema, 'v_dataset_metadata'))).fetchone()
        if metadata['dataset_id'] != config['dataset_id']:
            raise ValueError('Database dataset identifier differs from the configured snapshot')
        query = sql.SQL('SELECT * FROM {} WHERE arrival_at >= %s AND arrival_at < %s ORDER BY arrival_at').format(
            sql.Identifier(schema, 'v_routing_training'))
        with db.cursor(name='read_forward_routing') as cursor:
            cursor.execute(query, (start_at, end_at))
            return [{key: json_value(value) for key, value in row.items()} for row in cursor]


def read_forward_routing_context(config_path, start_at, end_at):
    """Read ordered route geometry and terminal flow context for split planning."""
    if (start_at.tzinfo is None or end_at.tzinfo is None or
            start_at.utcoffset() is None or end_at.utcoffset() is None or start_at >= end_at):
        raise ValueError('Routing requires a nonempty timezone-aware [start, end) range')
    config = json.loads(config_path.read_text(encoding='utf-8'))
    schema = config['schema']
    with connect('rdr_forward_training_context') as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        actual = db.execute('SELECT current_database() AS name').fetchone()['name']
        if actual != config['database']:
            raise ValueError('Database differs from the configured routing dataset')

        def table(name):
            return sql.Identifier(schema, name)

        metadata = db.execute(sql.SQL('SELECT dataset_id FROM {}').format(table('v_dataset_metadata'))).fetchone()
        if metadata['dataset_id'] != config['dataset_id']:
            raise ValueError('Database dataset identifier differs from the configured snapshot')
        audit = db.execute(sql.SQL('SELECT view_sql_sha256 FROM {} WHERE version IN (%s,%s,%s) ORDER BY version DESC LIMIT 1').format(
            table('routing_import_audit')), ('v2','v3','v4')).fetchone()
        if not audit:
            raise ValueError('Required depth routing view version v2 or newer is not installed')
        segments = db.execute(sql.SQL('SELECT sequence, output_node_id, distance_m FROM {}').format(
            table('v_model_segments'))).fetchall()
        segments.sort(key=lambda row: int(row['sequence']))
        canonical = ('P01','P02','P03','P04','P05','05CC002')
        if tuple(row['output_node_id'] for row in segments) != canonical:
            raise ValueError('PostgreSQL route geometry does not identify the six expected nodes')
        flows_query = sql.SQL('SELECT observed_at AS arrival_at, discharge_m3_s AS q_m3_s FROM {} '
                              'WHERE station_id=%s AND observed_at >= %s AND observed_at < %s ORDER BY observed_at')
        terminal_flows = db.execute(flows_query.format(table('routing_discharge')),
                                   ('05CC002', start_at, end_at)).fetchall()
    return {'distances_m': tuple(float(row['distance_m'] or 0) for row in segments),
            'terminal_flows': terminal_flows, 'routing_sql_sha256': audit['view_sql_sha256']}
