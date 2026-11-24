"""Shared project PostgreSQL configuration and credential-safe connections."""
import os
import psycopg
from psycopg.rows import dict_row
from project_paths import WORKSPACE

def connection_options(application_name="rdr_joint_ml"):
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
        raise ValueError('Set PGDATABASE in the project .env file')
    return {**{keys[key]: value for key,value in values.items()}, 'connect_timeout': 10,
            'application_name': application_name}


def connect(application_name="rdr_joint_ml"):
    options = connection_options(application_name)
    try:
        return psycopg.connect(**options, row_factory=dict_row)
    except psycopg.Error as exc:
        message = str(exc)
        if options.get('password'):
            message = message.replace(options['password'], '[redacted]')
        raise RuntimeError('PostgreSQL connection failed: '+message) from None
