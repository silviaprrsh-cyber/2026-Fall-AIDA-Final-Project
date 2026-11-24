"""Validate archived ECCC rain and stage it in a caller-owned PostgreSQL transaction."""
from datetime import datetime, timezone
import hashlib
import json
from urllib.parse import parse_qs, urlsplit

from psycopg import sql
from psycopg.types.json import Jsonb

from project_paths import WORKSPACE
from rdr_ml.weather import Weather, instant


POLICY_PATH = WORKSPACE / 'shared-resources/config/segment_ml_weather.json'
NEWER_MANIFEST = ('courses/AIDA-2156/data/sources/eccc_climate_hourly/raw/'
                  '20260601_20261111_3025484_monthly/manifest.json')
STATION_ID = '3025484'
STATION_NAME = 'RED DEER REGIONAL A'
PARSER_VERSION = 'forward-weather-postgres-v1'


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False, allow_nan=False)


def _digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _aware(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Archive receipt time and selection bounds need explicit timezones')
    return stamp.astimezone(timezone.utc)


def _load_archive(manifest_relative_path):
    """Validate one monthly archive with the existing Weather parser and API checks."""
    manifest_path = (WORKSPACE / manifest_relative_path).resolve()
    archive_root = (WORKSPACE / 'courses/AIDA-2156/data/sources/eccc_climate_hourly/raw').resolve()
    if not manifest_path.is_relative_to(archive_root):
        raise ValueError('Weather manifest must remain inside the climate-hourly source archive')
    manifest_raw = manifest_path.read_bytes()
    manifest = json.loads(manifest_raw)
    weather = Weather(manifest_path.relative_to(WORKSPACE))
    manifest_sha256 = _digest(manifest_raw)
    if weather.sha256 != manifest_sha256:
        raise ValueError('Weather manifest changed while being read')
    if (manifest['station_id'] != STATION_ID or manifest['station_name'] != STATION_NAME
            or manifest.get('complete') is not True):
        raise ValueError('A complete archive of the selected Red Deer station is required')
    start, end = _aware(manifest['start']), _aware(manifest['end'])
    if start >= end:
        raise ValueError('Weather selection bounds must be ordered')

    rows, all_ids, page_paths, months = {}, set(), set(), set()
    archived_count = 0
    for page in manifest['pages']:
        source = (WORKSPACE / page['path']).resolve()
        if not source.is_relative_to(manifest_path.parent) or source in page_paths:
            raise ValueError('Weather page is outside its archive or repeated')
        page_paths.add(source)
        raw = source.read_bytes()
        if _digest(raw) != page['sha256']:
            raise ValueError('Weather page checksum mismatch')
        sidecar = json.loads(source.with_suffix('.meta.json').read_bytes())
        for field in ('sha256', 'params', 'url', 'received_at'):
            if sidecar[field] != page[field]:
                raise ValueError('Weather manifest and archival metadata disagree: ' + field)
        params = page['params']
        year, month = params['LOCAL_YEAR'], params['LOCAL_MONTH']
        if (params.get('CLIMATE_IDENTIFIER') != STATION_ID or params.get('f') != 'json'
                or params.get('limit') != 1000 or not 1 <= month <= 12
                or (year, month) in months):
            raise ValueError('Unexpected or duplicate monthly weather query')
        months.add((year, month))
        parsed_url = urlsplit(page['url'])
        if (parsed_url.scheme != 'https' or parsed_url.netloc != 'api.weather.gc.ca'
                or parsed_url.path != '/collections/climate-hourly/items'
                or parsed_url.fragment
                or parse_qs(parsed_url.query) != {k: [str(v)] for k, v in params.items()}):
            raise ValueError('Weather archival request URL does not match its parameters')
        received_at = _aware(page['received_at']).isoformat()
        obj = json.loads(raw)
        features = obj['features']
        if (not isinstance(features, list) or obj.get('numberMatched') != len(features)
                or obj.get('numberReturned') != len(features) or page['rows'] != len(features)
                or any(link.get('rel') == 'next' for link in obj.get('links', []))):
            raise ValueError('Weather monthly response is incomplete or inconsistent')
        archived_count += len(features)
        for feature in features:
            p, identifier = feature['properties'], feature['id']
            if not isinstance(identifier, str) or not identifier or identifier in all_ids:
                raise ValueError('Weather feature identifiers must be unique and nonempty')
            all_ids.add(identifier)
            if (p['CLIMATE_IDENTIFIER'] != STATION_ID or p['STATION_NAME'] != STATION_NAME
                    or p['PROVINCE_CODE'] != 'AB' or p['LOCAL_YEAR'] != year
                    or p['LOCAL_MONTH'] != month or p['ID'] != identifier):
                raise ValueError('Provider did not honor the selected station or monthly filter')
            at = instant(p['UTC_DATE'])
            if at.minute or at.second or at.microsecond:
                raise ValueError('Non-hourly weather timestamp')
            if not start <= at < end:
                continue
            if at in rows:
                raise ValueError('Duplicate weather timestamp')
            existing = weather.rows[at]
            if existing['source_id'] != identifier:
                raise ValueError('Source feature differs from the current Weather parser')
            rows[at] = {
                'observed_at': at.isoformat(),
                'rain_mm': existing['precipitation'],
                'source_station_id': STATION_ID,
                'source_feature_id': identifier,
                'precipitation_flag': p.get('PRECIP_AMOUNT_FLAG'),
                'source_received_at': received_at,
                'source_path': source.relative_to(WORKSPACE).as_posix(),
                'source_sha256': page['sha256'],
                'source_manifest_sha256': manifest_sha256,
                'provenance': {
                    'provider': 'Environment and Climate Change Canada',
                    'collection': 'climate-hourly', 'source_url': page['url'],
                    'request_params': params, 'source_feature': feature,
                    'parser_version': PARSER_VERSION,
                    'utc_date_policy': 'Provider UTC_DATE is interpreted as UTC, including zone-less strings',
                    'rain_policy': 'Finite nonnegative unflagged PRECIP_AMOUNT; all other values remain NULL',
                    'role': 'nearby_point_context_not_catchment_average',
                    'receipt_time_replay_verified': False,
                },
            }
    expected_months = set()
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        expected_months.add((year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    if (months != expected_months or archived_count != manifest['rows']
            or archived_count != manifest['number_matched'] or set(rows) != set(weather.rows)
            or not rows):
        raise ValueError('Weather archive totals, month coverage or selected rows disagree')
    ordered = [rows[at] for at in sorted(rows)]
    metadata = {
        'parser_version': PARSER_VERSION, 'source': 'ECCC climate-hourly OGC API',
        'station_id': STATION_ID, 'station_name': STATION_NAME, 'province_code': 'AB',
        'provider_note': 'ECCC station in Alberta, not an Alberta provincial weather feed',
        'manifest_path': manifest_path.relative_to(WORKSPACE).as_posix(),
        'manifest_sha256': manifest_sha256,
        'source_manifest': manifest,
        'hourly_payload_sha256': _digest(_canonical(ordered).encode('utf-8')),
        'archived_rows': archived_count, 'selected_rows': len(ordered),
        'nonnull_rain_rows': sum(row['rain_mm'] is not None for row in ordered),
        'null_rain_rows': sum(row['rain_mm'] is None for row in ordered),
        'start': start.isoformat(), 'end_exclusive': end.isoformat(),
        'first_observed_at': ordered[0]['observed_at'],
        'last_observed_at': ordered[-1]['observed_at'],
        'absent_hours_within_observed_span': int((max(rows) - min(rows)).total_seconds() / 3600)
                                             + 1 - len(rows),
        'zero_fill_applied': False, 'receipt_time_replay_verified': False,
        'role': 'nearby_point_context_not_catchment_average',
    }
    return ordered, metadata


def load_forward_weather():
    """Merge two cached snapshots read-only, selecting the later receipt on overlap."""
    policy_raw = POLICY_PATH.read_bytes()
    configured = json.loads(policy_raw)['weather_manifest']
    paths = list(dict.fromkeys((configured, NEWER_MANIFEST)))
    rows, archives, overlap_count, revised_rain_count = {}, [], 0, 0
    for path in paths:
        archive_rows, archive_metadata = _load_archive(path)
        archives.append(archive_metadata)
        for row in archive_rows:
            stamp = row['observed_at']
            previous = rows.get(stamp)
            if previous is not None:
                overlap_count += 1
                if previous['rain_mm'] != row['rain_mm']:
                    revised_rain_count += 1
                old_time = _aware(previous['source_received_at'])
                new_time = _aware(row['source_received_at'])
                if new_time == old_time and previous['provenance']['source_feature'] != row['provenance']['source_feature']:
                    raise ValueError('Conflicting weather revisions with identical receipt times')
                if new_time <= old_time:
                    continue
            rows[stamp] = row
    ordered = [rows[stamp] for stamp in sorted(rows)]
    manifest_hashes = [archive['manifest_sha256'] for archive in archives]
    bundle_sha256 = _digest(_canonical(manifest_hashes).encode('utf-8'))
    metadata = {
        'parser_version': PARSER_VERSION, 'source': 'ECCC climate-hourly OGC API',
        'station_id': STATION_ID, 'station_name': STATION_NAME, 'province_code': 'AB',
        'provider_note': 'ECCC station in Alberta, not an Alberta provincial weather feed',
        'manifest_sha256': bundle_sha256, 'weather_bundle_sha256': bundle_sha256,
        'manifest_sha256_role': 'SHA-256 of ordered source-manifest hashes, not a single file',
        'policy_path': POLICY_PATH.relative_to(WORKSPACE).as_posix(),
        'policy_sha256': _digest(policy_raw), 'source_archives': archives,
        'source_manifest_sha256s': manifest_hashes,
        'hourly_payload_sha256': _digest(_canonical(ordered).encode('utf-8')),
        'selected_rows': len(ordered),
        'nonnull_rain_rows': sum(row['rain_mm'] is not None for row in ordered),
        'null_rain_rows': sum(row['rain_mm'] is None for row in ordered),
        'first_observed_at': ordered[0]['observed_at'],
        'last_observed_at': ordered[-1]['observed_at'],
        'start': min(archive['start'] for archive in archives),
        'end_exclusive': max(archive['end_exclusive'] for archive in archives),
        'overlapping_hours': overlap_count, 'overlap_changed_rain_hours': revised_rain_count,
        'overlap_policy': 'Latest source-page received_at wins, including its NULL and flag values',
        'selected_rows_by_manifest': {
            digest: sum(row['source_manifest_sha256'] == digest for row in ordered)
            for digest in manifest_hashes},
        'absent_hours_within_observed_span': int(
            (_aware(ordered[-1]['observed_at']) - _aware(ordered[0]['observed_at'])).total_seconds()
            / 3600) + 1 - len(ordered),
        'zero_fill_applied': False, 'receipt_time_replay_verified': False,
        'role': 'nearby_point_context_not_catchment_average',
    }
    return ordered, metadata


def stage_forward_weather(db, schema):
    """Stage exact source rows; caller owns connection, schema, transaction and commit.

    Existing identical rows are accepted. Any changed or extra row fails verification,
    so the caller must roll back on failure. No source files or existing rows are changed.
    """
    if db.autocommit:
        raise ValueError('Weather staging requires a caller-owned non-autocommit transaction')
    rows, metadata = load_forward_weather()
    hourly = sql.Identifier(schema, 'routing_weather_hourly')
    imports = sql.Identifier(schema, 'routing_weather_imports')
    bundles = sql.Identifier(schema, 'routing_weather_bundles')
    db.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
        bundle_sha256 text PRIMARY KEY, hourly_payload_sha256 text NOT NULL,
        imported_at timestamptz NOT NULL DEFAULT now(), metadata jsonb NOT NULL)''').format(bundles))
    db.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
        manifest_sha256 text PRIMARY KEY, hourly_payload_sha256 text NOT NULL,
        imported_at timestamptz NOT NULL DEFAULT now(), metadata jsonb NOT NULL)''').format(imports))
    db.execute(sql.SQL('''CREATE TABLE IF NOT EXISTS {} (
        observed_at timestamptz PRIMARY KEY,
        rain_mm double precision CHECK (rain_mm >= 0 AND rain_mm < 'Infinity'::double precision),
        source_station_id text NOT NULL, source_feature_id text NOT NULL UNIQUE,
        precipitation_flag text, source_received_at timestamptz NOT NULL,
        source_path text NOT NULL, source_sha256 text NOT NULL,
        source_manifest_sha256 text NOT NULL REFERENCES {}(manifest_sha256),
        provenance jsonb NOT NULL)''').format(hourly, imports))
    for archive in metadata['source_archives']:
        db.execute(sql.SQL('''INSERT INTO {} (manifest_sha256, hourly_payload_sha256, metadata)
            VALUES (%s, %s, %s) ON CONFLICT (manifest_sha256) DO NOTHING''').format(imports),
            (archive['manifest_sha256'], archive['hourly_payload_sha256'], Jsonb(archive)))
    db.execute(sql.SQL('''INSERT INTO {} (bundle_sha256, hourly_payload_sha256, metadata)
        VALUES (%s, %s, %s) ON CONFLICT (bundle_sha256) DO NOTHING''').format(bundles),
        (metadata['weather_bundle_sha256'], metadata['hourly_payload_sha256'], Jsonb(metadata)))
    columns = list(rows[0])
    statement = sql.SQL('INSERT INTO {} ({}) VALUES ({}) ON CONFLICT DO NOTHING').format(
        hourly, sql.SQL(', ').join(map(sql.Identifier, columns)),
        sql.SQL(', ').join(sql.Placeholder() for _ in columns))
    with db.cursor() as cursor:
        cursor.executemany(statement, [tuple(Jsonb(row[name]) if name == 'provenance' else row[name]
                                            for name in columns) for row in rows])
    with db.cursor() as cursor:
        cursor.execute(sql.SQL('SELECT {} FROM {} ORDER BY observed_at').format(
            sql.SQL(', ').join(map(sql.Identifier, columns)), hourly))
        stored = []
        for item in cursor.fetchall():
            row = dict(item) if isinstance(item, dict) else dict(zip(columns, item))
            for name in ('observed_at', 'source_received_at'):
                row[name] = row[name].astimezone(timezone.utc).isoformat()
            stored.append(row)
    if _digest(_canonical(stored).encode('utf-8')) != metadata['hourly_payload_sha256']:
        raise ValueError('Existing PostgreSQL weather rows differ from the selected immutable archive')
    for archive in metadata['source_archives']:
        saved = db.execute(sql.SQL('SELECT metadata FROM {} WHERE manifest_sha256=%s').format(imports),
                           (archive['manifest_sha256'],)).fetchone()
        saved_metadata = saved['metadata'] if isinstance(saved, dict) else saved[0]
        if saved_metadata != archive:
            raise ValueError('Existing PostgreSQL weather import provenance differs')
    saved = db.execute(sql.SQL('SELECT metadata FROM {} WHERE bundle_sha256=%s').format(bundles),
                       (metadata['weather_bundle_sha256'],)).fetchone()
    saved_metadata = saved['metadata'] if isinstance(saved, dict) else saved[0]
    if saved_metadata != metadata:
        raise ValueError('Existing PostgreSQL weather bundle provenance differs')
    return {**metadata, 'table': schema + '.routing_weather_hourly',
            'provenance_table': schema + '.routing_weather_imports',
            'bundle_table': schema + '.routing_weather_bundles',
            'database_rows_verified': len(stored), 'committed_by_helper': False}


if __name__ == '__main__':
    _, report = load_forward_weather()
    report['source_archives'] = [{key: value for key, value in archive.items()
                                  if key != 'source_manifest'} for archive in report['source_archives']]
    print(json.dumps(report, indent=2))
