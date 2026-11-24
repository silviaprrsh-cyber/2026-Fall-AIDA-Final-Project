"""Import an immutable unit-value snapshot and create joint-training SQL views."""
import argparse
from datetime import datetime, timezone
import hashlib
import ipaddress
import json
import math
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


def benchmark_json(value):
    """Canonical, finite JSON for reproducible evidence identities."""
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False)


def benchmark_connection_options():
    """Reject remote targets before sending credentials, including DNS aliases."""
    options = connection_options('rdr_benchmark_history')
    host = options.get('host', '')
    address = '127.0.0.1' if host.lower() == 'localhost' else host
    try:
        local = ipaddress.ip_address(address).is_loopback
    except ValueError:
        local = False
    if not local:
        raise ValueError('Benchmark import requires an explicit loopback PostgreSQL host')
    options['hostaddr'] = address
    return options


def benchmark_payload():
    """Read existing local evidence without downloading or generating files."""
    from API.fetch_station_datums import parse_benchmark_history_reports
    payload = parse_benchmark_history_reports()
    reports = payload['reports']
    expected = {'05CB007', '05CB001', '05CC007', '05CC002', '05CC003'}
    if len(reports) != 5 or {r['station_id'] for r in reports} != expected:
        raise ValueError('Exactly the five selected benchmark reports are required')
    for report in reports:
        source = (WORKSPACE / report['source_path']).resolve()
        if not source.is_relative_to(BASE / 'sources/eccc_documentation/manual/benchmark_history_reports'):
            raise ValueError('Benchmark PDF must remain in its existing source archive')
        if digest_file(source) != report['sha256']:
            raise ValueError('Benchmark PDF identity changed during extraction')
        eligibility = report['eligibility']
        if eligibility['conversion_eligible'] or eligibility.get('verified_add_m') is not None:
            raise ValueError('This evidence-only import cannot certify conversion or physical depth')
        indices = [entry['entry_index'] for entry in report['entries']]
        if len(indices) != len(set(indices)) or not indices:
            raise ValueError('Benchmark entry identifiers must be unique and nonempty')
        for entry in report['entries']:
            if not math.isfinite(entry['elevation_m']) or not 1 <= entry['page'] <= report['page_count']:
                raise ValueError('Invalid benchmark elevation or evidence page')
        for candidate in report.get('published_conversion_candidates', []):
            if not math.isfinite(candidate['add_m']):
                raise ValueError('A published conversion candidate must be finite')
            candidate_path = (WORKSPACE / candidate['source_path']).resolve()
            if not candidate_path.is_relative_to(BASE / 'sources'):
                raise ValueError('Published conversion evidence must remain in local source archives')
            if digest_file(candidate_path) != candidate['source_sha256']:
                raise ValueError('Published conversion evidence hash mismatch')
            if candidate.get('source_received_at'):
                stamp = datetime.fromisoformat(candidate['source_received_at'].replace('Z', '+00:00'))
                if stamp.tzinfo is None:
                    raise ValueError('Source receipt time requires an explicit timezone')
    payload['reports'] = sorted(reports, key=lambda row: row['station_id'])
    benchmark_json(payload)
    return payload


def benchmark_baseline(db, schema):
    """Check the original dataset counts and default view definitions, read-only."""
    counts = {}
    for name in ('parameter_observations', 'station_observations', 'v_train', 'v_validation', 'v_test'):
        counts[name] = db.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(
            sql.Identifier(schema, name))).fetchone()['n']
    definitions = db.execute('SELECT viewname, definition FROM pg_views WHERE schemaname=%s '
                             "AND viewname NOT LIKE 'v_benchmark_%%' "
                             "AND viewname <> 'v_observations_benchmark_context' ORDER BY viewname",
                             (schema,)).fetchall()
    return {'counts': counts, 'default_view_sha256': hashlib.sha256(
        benchmark_json(definitions).encode('utf-8')).hexdigest()}


def benchmark_view_digest(db, schema):
    definitions = db.execute('SELECT viewname, definition FROM pg_views WHERE schemaname=%s '
        "AND (viewname LIKE 'v_benchmark_%%' OR viewname='v_observations_benchmark_context') "
        'ORDER BY viewname', (schema,)).fetchall()
    if len(definitions) != 4:
        raise ValueError('Expected exactly the four additive benchmark evidence views')
    return hashlib.sha256(benchmark_json(definitions).encode('utf-8')).hexdigest()


def create_benchmark_tables_and_views(db, schema):
    """Add evidence objects only; never replace existing observation/training views."""
    def execute(statement):
        return db.execute(sql.SQL(statement).format(s=sql.Identifier(schema)))
    execute('CREATE TABLE IF NOT EXISTS {s}.benchmark_history_imports ('
            'bundle_id text PRIMARY KEY, base_dataset_id text NOT NULL, parser_version text NOT NULL, '
            'policy_version text NOT NULL, imported_at timestamptz NOT NULL DEFAULT now(), '
            'source_manifest jsonb NOT NULL, view_definition_sha256 text NOT NULL)')
    execute('CREATE TABLE IF NOT EXISTS {s}.benchmark_history_reports ('
            'bundle_id text NOT NULL REFERENCES {s}.benchmark_history_imports(bundle_id), '
            'station_id text NOT NULL, report_sha256 text NOT NULL, source_path text NOT NULL, '
            'report_date date NOT NULL, normalized_metadata jsonb NOT NULL, '
            'PRIMARY KEY(bundle_id, station_id))')
    execute('CREATE TABLE IF NOT EXISTS {s}.benchmark_history_entries ('
            'bundle_id text NOT NULL, station_id text NOT NULL, entry_index integer NOT NULL, '
            'page integer NOT NULL CHECK(page > 0), name text NOT NULL, elevation_m double precision NOT NULL, '
            'constructed_date date, removed_date date, status text NOT NULL, datum_label text, '
            'normalized_entry jsonb NOT NULL, PRIMARY KEY(bundle_id, station_id, entry_index), '
            'FOREIGN KEY(bundle_id, station_id) REFERENCES {s}.benchmark_history_reports(bundle_id, station_id))')
    views = {
        'v_benchmark_history_reports': '''SELECT r.bundle_id, r.station_id, r.report_sha256, r.source_path,
            r.report_date, i.base_dataset_id, i.parser_version, i.policy_version,
            r.normalized_metadata->>'station_name' AS station_name,
            r.normalized_metadata->>'selected_start' AS report_selected_start,
            r.normalized_metadata->'eligibility'->>'status' AS eligibility_status,
            false AS verified_conversion_eligible, false AS physical_depth_eligible,
            r.normalized_metadata->'eligibility'->>'reason' AS eligibility_reason,
            r.normalized_metadata->'published_conversion_candidates' AS published_conversion_candidates
            FROM {s}.benchmark_history_reports r JOIN {s}.benchmark_history_imports i USING(bundle_id)''',
        'v_benchmark_history_entries': '''SELECT e.bundle_id, e.station_id, e.entry_index, e.page, e.name,
            e.elevation_m, e.constructed_date, e.removed_date, e.status, e.datum_label,
            e.normalized_entry->>'description' AS description, r.report_sha256, r.source_path, r.report_date
            FROM {s}.benchmark_history_entries e JOIN {s}.benchmark_history_reports r USING(bundle_id,station_id)''',
        'v_benchmark_history_conversion_candidates': '''SELECT r.bundle_id, r.station_id,
            c.value->>'source_datum' AS source_datum, c.value->>'target_datum' AS target_datum,
            (c.value->>'add_m')::double precision AS candidate_add_m,
            (c.value->>'uncertainty_m')::double precision AS published_uncertainty_m,
            c.value->>'published_date_raw' AS published_date_raw,
            nullif(c.value->>'source_received_at','')::timestamptz AS source_received_at,
            c.value->>'source_path' AS conversion_source_path,
            c.value->>'source_sha256' AS conversion_source_sha256,
            c.value->>'temporal_status' AS temporal_applicability,
            c.value->>'evidence' AS conversion_evidence,
            false AS verified_conversion_eligible
            FROM {s}.benchmark_history_reports r
            CROSS JOIN LATERAL jsonb_array_elements(coalesce(
                r.normalized_metadata->'published_conversion_candidates','[]'::jsonb)) c(value)''',
        'v_observations_benchmark_context': '''SELECT o.station_id, o.observed_at,
            o.level_m AS reported_water_level_m, o.discharge_m3_s, o.level_quality, o.discharge_quality,
            o.source_path AS observation_source_path, o.received_at AS observation_received_at,
            r.bundle_id, r.base_dataset_id, r.report_sha256, r.source_path AS benchmark_source_path,
            r.report_date, r.eligibility_status, r.eligibility_reason,
            c.source_datum, c.target_datum, c.candidate_add_m, c.published_uncertainty_m,
            c.published_date_raw, c.source_received_at AS conversion_source_received_at,
            c.conversion_source_path, c.conversion_source_sha256, c.temporal_applicability,
            CASE WHEN o.level_m IS NOT NULL AND c.source_received_at IS NOT NULL
                AND o.observed_at <= c.source_received_at
                THEN o.level_m + c.candidate_add_m END AS candidate_water_surface_elevation_m,
            CASE WHEN c.candidate_add_m IS NULL THEN 'no_published_candidate'
                WHEN c.source_received_at IS NULL THEN 'source_snapshot_time_unavailable'
                WHEN o.observed_at > c.source_received_at THEN 'after_source_snapshot_not_applied'
                WHEN o.level_m IS NULL THEN 'missing_observed_level'
                ELSE 'conditional_same_gauge_arithmetic_temporal_applicability_unconfirmed' END
                AS candidate_status,
            false AS verified_conversion_eligible, false AS physical_depth_eligible,
            false AS training_ready
            FROM {s}.v_observations o JOIN {s}.v_benchmark_history_reports r USING(station_id)
            LEFT JOIN {s}.v_benchmark_history_conversion_candidates c USING(bundle_id,station_id)''',
    }
    for name, statement in views.items():
        existing = db.execute('SELECT definition FROM pg_views WHERE schemaname=%s AND viewname=%s',
                              (schema, name)).fetchone()
        if existing is None:
            db.execute(sql.SQL('CREATE VIEW {} AS ').format(sql.Identifier(schema, name)) +
                       sql.SQL(statement).format(s=sql.Identifier(schema)))
        # Existing evidence views are checked, never silently replaced, on a repeat import.
    return views


def verify_benchmark_bundle(db, config, bundle_id, payload):
    schema = config['schema']
    def table(name):
        return sql.Identifier(schema, name)
    imported = db.execute(sql.SQL('SELECT * FROM {} WHERE bundle_id=%s').format(
        table('benchmark_history_imports')), (bundle_id,)).fetchone()
    expected_manifest = {key: value for key, value in payload.items() if key != 'reports'}
    expected_manifest['reports'] = [{k: r[k] for k in ('station_id', 'source_path', 'sha256')}
                                    for r in payload['reports']]
    if imported is None or imported['base_dataset_id'] != config['dataset_id'] or \
            imported['source_manifest'] != expected_manifest or \
            imported['view_definition_sha256'] != benchmark_view_digest(db, schema):
        raise ValueError('Stored benchmark import identity differs from current evidence')
    stored = db.execute(sql.SQL('SELECT * FROM {} WHERE bundle_id=%s ORDER BY station_id').format(
        table('benchmark_history_reports')), (bundle_id,)).fetchall()
    if len(stored) != len(payload['reports']):
        raise ValueError('Stored benchmark report count mismatch')
    for saved, report in zip(stored, payload['reports']):
        metadata = {key: value for key, value in report.items() if key != 'entries'}
        if saved['station_id'] != report['station_id'] or saved['normalized_metadata'] != metadata or \
                saved['report_sha256'] != report['sha256'] or saved['source_path'] != report['source_path']:
            raise ValueError('Stored report evidence differs from source extraction')
        entries = db.execute(sql.SQL('SELECT normalized_entry FROM {} WHERE bundle_id=%s '
                                     'AND station_id=%s ORDER BY entry_index').format(
            table('benchmark_history_entries')), (bundle_id, report['station_id'])).fetchall()
        if [row['normalized_entry'] for row in entries] != sorted(report['entries'], key=lambda row: row['entry_index']):
            raise ValueError('Stored benchmark entries differ from source extraction')
    counts = {}
    for name in ('v_benchmark_history_reports', 'v_benchmark_history_entries',
                 'v_benchmark_history_conversion_candidates', 'v_observations_benchmark_context'):
        counts[name] = db.execute(sql.SQL('SELECT count(*) AS n FROM {} WHERE bundle_id=%s').format(
            table(name)), (bundle_id,)).fetchone()['n']
    stations = db.execute(sql.SQL('SELECT station_id, count(*) AS observation_rows, '
        'count(candidate_water_surface_elevation_m) AS conditional_wse_rows, '
        "count(*) FILTER(WHERE candidate_status='after_source_snapshot_not_applied') AS newer_rows_not_applied, "
        'count(*) FILTER(WHERE training_ready) AS training_ready_rows '
        'FROM {} WHERE bundle_id=%s GROUP BY station_id ORDER BY station_id').format(
        table('v_observations_benchmark_context')), (bundle_id,)).fetchall()
    baseline_count = db.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(
        table('v_observations'))).fetchone()['n']
    if counts['v_observations_benchmark_context'] != baseline_count:
        raise ValueError('Benchmark context must preserve exactly one row per source observation per bundle')
    if any(row['training_ready_rows'] for row in stations):
        raise ValueError('Unreviewed benchmark context must never become training-ready')
    return {'view_counts': counts, 'stations': stations}


def run_benchmark_history(mode):
    """Use the existing import pipeline for a separately identified evidence layer."""
    import psycopg
    from psycopg.rows import dict_row
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    payload = benchmark_payload()
    bundle_id = hashlib.sha256(benchmark_json({
        'base_dataset_id': config['dataset_id'], 'evidence': payload,
        'view_policy': 'same_gauge_candidate_before_source_receipt_not_depth_v1',
    }).encode('utf-8')).hexdigest()
    result = {'mode': mode, 'database': config['database'], 'schema': config['schema'],
              'base_dataset_id': config['dataset_id'], 'benchmark_bundle_id': bundle_id,
              'report_count': len(payload['reports']),
              'entry_count': sum(len(r['entries']) for r in payload['reports']),
              'training_started': False, 'default_training_configuration_changed': False,
              'training_ready': False,
              'limitation': 'Conditional same-gauge water-surface elevation is not verified temporal conversion or physical depth.'}
    if mode == 'check':
        result['status'] = 'local_source_validation_passed_no_database_changes'
        print(json.dumps(result, indent=2))
        return result
    options = benchmark_connection_options()
    with psycopg.connect(**options, row_factory=dict_row) as db:
        if mode == 'verify':
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        db.execute("SET LOCAL lock_timeout = '10s'")
        db.execute("SET LOCAL statement_timeout = '120s'")
        server = db.execute('SELECT current_database() AS database, host(inet_server_addr()) AS address').fetchone()
        if server['database'] != config['database'] or not server['address'] or \
                not ipaddress.ip_address(server['address']).is_loopback:
            raise ValueError('Connection is not the configured local database')
        schema = config['schema']
        original = db.execute(sql.SQL('SELECT dataset_id FROM {}').format(
            sql.Identifier(schema, 'dataset_metadata'))).fetchone()
        if original is None or original['dataset_id'] != config['dataset_id']:
            raise ValueError('Original immutable dataset identity mismatch')
        before = benchmark_baseline(db, schema)
        if mode == 'import':
            db.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (schema + ':benchmark_history',))
            create_benchmark_tables_and_views(db, schema)
            existing = db.execute(sql.SQL('SELECT 1 FROM {} WHERE bundle_id=%s').format(
                sql.Identifier(schema, 'benchmark_history_imports')), (bundle_id,)).fetchone()
            result['reused_existing_bundle'] = existing is not None
            if existing is None:
                manifest = {key: value for key, value in payload.items() if key != 'reports'}
                manifest['reports'] = [{k: r[k] for k in ('station_id', 'source_path', 'sha256')}
                                       for r in payload['reports']]
                db.execute(sql.SQL('INSERT INTO {}(bundle_id,base_dataset_id,parser_version,policy_version,'
                    'source_manifest,view_definition_sha256) VALUES(%s,%s,%s,%s,%s,%s)').format(
                    sql.Identifier(schema, 'benchmark_history_imports')),
                    (bundle_id, config['dataset_id'], payload['parser_version'], payload['policy_version'],
                     Jsonb(manifest), benchmark_view_digest(db, schema)))
                for report in payload['reports']:
                    metadata = {key: value for key, value in report.items() if key != 'entries'}
                    db.execute(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s)').format(
                        sql.Identifier(schema, 'benchmark_history_reports')),
                        (bundle_id, report['station_id'], report['sha256'], report['source_path'],
                         report['report_date'], Jsonb(metadata)))
                    for entry in report['entries']:
                        db.execute(sql.SQL('INSERT INTO {} VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)').format(
                            sql.Identifier(schema, 'benchmark_history_entries')),
                            (bundle_id, report['station_id'], entry['entry_index'], entry['page'], entry['name'],
                             entry['elevation_m'], entry.get('constructed_date'), entry.get('removed_date'),
                             entry['status'], entry.get('datum_label'), Jsonb(entry)))
        result.update(verify_benchmark_bundle(db, config, bundle_id, payload))
        after = benchmark_baseline(db, schema)
        if before != after or CONFIG.read_bytes() != config_bytes:
            raise ValueError('Original dataset counts, view definitions or configuration changed')
        result['baseline_integrity'] = after
        result['server_is_loopback'] = True
    result['status'] = 'committed_and_verified' if mode == 'import' else 'read_only_verification_passed'
    print(json.dumps(result, indent=2))
    return result


def digest_file(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        while block := stream.read(1024*1024):
            digest.update(block)
    return digest.hexdigest()


def bed_proxy_payload():
    """Frozen reviewed evidence, not a claim of certified gauge depth.

    Fresh official responses on 2026-11-17 were byte-identical to the archived
    datum pages. Retain both identities/times rather than rewriting that archive.
    No network requests, new source files, or changes to training are needed.
    """
    from bs4 import BeautifulSoup
    fresh = {
        '05CB001': ('ebf7689bae759fc45c7c69414ce3f78443b72158f228ffa833b971418d74eaa8', '18:49:23.827254'),
        '05CB007': ('6fff0ac8e08c77bd59849dd7930650fd63615389c451f93efaf193261ddbe3e8', '18:49:23.911157'),
        '05CC002': ('56ea534434f4e1e683925dcf8eb9985637eeca614fd1106adffe5718b2d0bbaf', '18:49:23.996308'),
        '05CC003': ('609880cc31c2738b0a0197454b82bf8e54ad0389ac9d79d5ee8881399a636841', '18:49:24.073492'),
        '05CC007': ('4cecc16a628b189112bd25a8ac3ce4fb156207cac3cbeebb93a6185abafcff37', '18:49:24.147227'),
    }
    grid = {
        'name': 'ca_nrc_HT2_2010v70_CGG2013a.tif',
        'source_url': 'https://cdn.proj.org/ca_nrc_HT2_2010v70_CGG2013a.tif',
        'sha256': '6f1f405626f6b132d42b84584f31cadb88e038026ca692b5b3a61cd82fb92e11',
        'operation': 'CGVD28 height to CGVD2013a(2010) height',
        'pipeline': '+proj=pipeline +step +proj=unitconvert +xy_in=deg +xy_out=rad '
                    '+step +proj=vgridshift +grids=ca_nrc_HT2_2010v70_CGG2013a.tif +multiplier=-1 '
                    '+step +proj=unitconvert +xy_in=rad +xy_out=deg',
        'coordinate_policy': 'Evaluated at each selected survey point longitude/latitude; not at gauge.',
        'limitation': 'Regional vertical alignment does not verify the original local survey adjustment, '
                      'gauge-to-section water-surface transfer, or contemporary bed morphology.',
    }
    survey_base = 'courses/AIDA-2362/data/sources/alberta_flood_surveys/manual/'
    sources = [
        {'source_path': survey_base + 'Red Deer/SURVEY_DATA.gdb',
         'sha256': '9a3871d35209c5b9ad045b3d0be19b95cc5719ef7611001d5b7295140375a222'},
        {'source_path': survey_base + 'Red Deer County and Markerville/A_FieldSurvey.gdb',
         'sha256': '5c6f1c0d78eb1f24ed60b4f3d66d1dddf0eaeea51abb66d189acaefa4309147f'},
    ]
    for source in sources:
        directory = WORKSPACE / source['source_path']
        files = [{'file': p.relative_to(directory).as_posix(), 'sha256': digest_file(p)}
                 for p in sorted(directory.rglob('*')) if p.is_file() and '.lock' not in p.name]
        if not files or hashlib.sha256(benchmark_json(files).encode()).hexdigest() != source['sha256']:
            raise ValueError('Bed-proxy raw survey source identity mismatch')
        source['hash_method'] = 'SHA256 of canonical sorted relative-file/SHA256 manifest, excluding .lock files'
    county_url = 'https://www.alberta.ca/system/files/epa-draft-red-deer-county-markerville-main-report-mar-2024.pdf'
    rows = [
        {'station_id': '05CB001', 'bed_elevation_source_m': 904.969, 'bed_source_datum': 'CGVD28',
         'bed_elevation_aligned_m': 905.0766975456263, 'comparison_datum': 'CGVD2013_e2010',
         'stage_add_m': 904.948, 'depth_enabled': True, 'source_path': sources[1]['source_path'],
         'source_url': county_url, 'layer': 'FLD_CrossSectionTopoSurvey', 'fid': 2579, 'point_id': 3578,
         'point_type': 'UNDERWATER', 'longitude': -114.14049816541034, 'latitude': 52.02789051080891,
         'survey_year': 2022, 'survey_date': None, 'photo_supported_date': '2022-10-20',
         'station_to_selected_point_m': 41.46, 'selection': 'LRD016A nearby underwater minimum',
         'alternatives_not_used': [{'elevation_source_m': 904.750, 'distance_m': 53.17,
                                    'reason': 'Alternative nearby point, not selected proxy'}],
         'datum_alignment': grid, 'limitation': 'Nearby section proxy, not an exact gauge-bed survey. '
                       'Raw point dates are blank; photo date is context, not a populated point attribute.'},
        {'station_id': '05CB007', 'bed_elevation_source_m': 909.720, 'bed_source_datum': 'CGVD28',
         'bed_elevation_aligned_m': 909.8269472310508, 'comparison_datum': 'CGVD2013_e2010',
         'stage_add_m': 910.212, 'depth_enabled': True, 'source_path': sources[1]['source_path'],
         'source_url': county_url, 'layer': 'FLD_CrossSectionTopoSurvey', 'fid': 10625, 'point_id': 11624,
         'point_type': 'UNDERWATER', 'longitude': -114.2175455698327, 'latitude': 52.05889030198428,
         'survey_year': 2022, 'survey_date': None, 'photo_supported_date': '2022-10-21',
         'station_to_selected_point_m': 93.13, 'selection': 'RDR112 western near-tunnel outlet branch minimum',
         'alternatives_not_used': [{'elevation_source_m': 909.430,
                                    'reason': 'Eastern gated spillway component, wrong branch'}],
         'datum_alignment': grid, 'limitation': 'Outlet-basin proxy, not tunnel floor or gauge-bed elevation. '
                       'Photos distinguish western flowing outlet from eastern gated spillway; raw point dates blank.'},
        {'station_id': '05CC002', 'bed_elevation_source_m': 849.522, 'bed_source_datum': 'CGVD28',
         'bed_elevation_aligned_m': 849.5955450123237, 'comparison_datum': 'CGVD2013_e2010',
         'stage_add_m': 847.992, 'depth_enabled': True, 'source_path': sources[0]['source_path'],
         'source_report_path': survey_base + 'Red Deer/ep-draft-red-deer-survey-base-data-report-mar-2021.pdf',
         'layer': 'Survey_Points', 'fid': 15173, 'point_id': 'MD201709230317', 'point_type': 'S4',
         'longitude': -113.82444388927479, 'latitude': 52.27081924943147,
         'survey_year': 2017, 'survey_date': '2017-09-23', 'station_to_section_line_m': 27.86,
         'station_to_selected_point_m': 96.38, 'selection': 'R38 minimum surveyed profile point',
         'datum_alignment': grid, 'limitation': '2017 nearby section proxy. Gauge relocation in 2019 and '
                       'subsequent bed change are not resolved by a vertical grid shift.'},
        {'station_id': '05CC007', 'bed_elevation_source_m': 909.98, 'bed_source_datum': 'GSC_report',
         'bed_elevation_aligned_m': 909.98, 'comparison_datum': 'GSC_report',
         'stage_add_m': 909.436, 'depth_enabled': True, 'report_year': 2006,
         'survey_year': None, 'survey_date': None,
         'source_url': 'https://open.alberta.ca/dataset/b2fb39c4-2b31-403f-8ac8-d0c3633130b4/resource/'
                       'a0091970-a456-42f0-830a-9cae42acff73/download/eckville-medicine-2006-study.pdf',
         'source_sha256': '6a662d127eda4044437e9ee44763de5aefb9008d8b2ceabc0d187b3d039e7a33',
         'pdf_page': 37, 'table': '5.1', 'selection': 'XS1 minimum channel elevation, near gauge',
         'datum_alignment': {'method': 'Same GSC system in report: report explicitly uses stage + 909.436 m',
                             'bed_shift_m': 0.0},
         'limitation': 'Old same-reach cross-section proxy. Both gauge and XS1 are described about 15 m '
                       'upstream of Highway 11 bridge; this is not a 15 m gauge-to-section distance. '
                       'No CGVD2013 factor is mixed into this GSC calculation.'},
        {'station_id': '05CC003', 'bed_elevation_source_m': 935.5522, 'bed_source_datum': 'MSL_unverified',
         'bed_elevation_aligned_m': None, 'comparison_datum': 'CGVD2013_e2010',
         'stage_add_m': 0.073, 'depth_enabled': False, 'survey_year': None, 'survey_date': None,
         'source_url': 'https://ags.aer.ca/publications/all-publications/dig-2008-0515',
         'download_url': 'https://static.ags.aer.ca/files/document/DIG/DIG_2008_0515.zip',
         'source_sha256': '2084dd264835016364f7525207a0baa1eaad24ae91fd86122fbb8b2cfb4c03a7',
         'archive_entry': 'sylv_dem_tm.asc', 'grid_row_zero_based_north_to_south': 224,
         'grid_column_zero_based': 215, 'cell_center_x': 561125, 'cell_center_y': 5793725,
         'horizontal_crs': 'EPSG:3400', 'cell_size_m': 50, 'station_to_cell_center_m': 23.9,
         'selection': 'Nearest lake-bed grid cell',
         'datum_alignment': {'method': 'Not performed: MSL label does not establish compatible vertical datum'},
         'limitation': 'Spatial match metadata only. No depth subtraction until the lake-bed vertical datum '
                       'and shoreline-cell representativeness are established.'},
    ]
    archived = {r['station_id']: r for r in benchmark_payload()['reports']}
    for row in rows:
        station = row['station_id']
        old = archived[station]['published_conversion_candidates'][0]
        expected_hash, received = fresh[station]
        if old['source_sha256'] != expected_hash:
            raise ValueError('Reviewed datum response does not match preserved archived page')
        factor = dict(old)
        factor['archived_source_received_at'] = factor['source_received_at']
        factor['source_received_at'] = '2026-11-17T' + received + '+00:00'
        factor['refresh_identity'] = 'Fresh official response byte-identical to archived source'
        if station == '05CC007':
            text = BeautifulSoup((WORKSPACE / old['source_path']).read_bytes(), 'html.parser').get_text(' ', strip=True)
            evidence = 'To convert to GEODETIC SURVEY OF CANADA DATUM, add 909.436 m.'
            if evidence not in text:
                raise ValueError('Reviewed GSC factor absent from official source')
            factor = {'source_datum': old['source_datum'], 'target_datum': 'GSC_report',
                      'add_m': 909.436, 'evidence': evidence, 'source_url': old['source_url'],
                      'source_path': old['source_path'], 'source_sha256': expected_hash,
                      'source_received_at': factor['source_received_at'],
                      'archived_source_received_at': old['source_received_at'],
                      'effective_from': None, 'effective_to': None,
                      'temporal_status': 'no_explicit_effective_interval; same conversion stated in 2006 report'}
        if factor['add_m'] != row['stage_add_m'] or factor['target_datum'] != row['comparison_datum']:
            raise ValueError('Proxy and stage conversion datums do not match')
        row['stage_conversion'] = factor
        row['benchmark_history_notes'] = archived[station]['history_notes']
        row['benchmark_report_sha256'] = archived[station]['sha256']
        if row['depth_enabled'] != (row['bed_elevation_aligned_m'] is not None):
            raise ValueError('Only aligned river proxies may produce approximate depths')
    payload = {'parser_version': 'bed-proxy-reviewed-v1', 'policy_version': 'approximate-depth-study-window-v1',
               'reviewed_at': '2026-11-17', 'analysis_start': '2025-05-03T00:00:00+00:00',
               'analysis_end_exclusive': '2026-11-04T00:00:00+00:00', 'survey_source_manifests': sources,
               'temporal_policy': 'Window is analysis scope, NOT a certified datum-effective interval. '
                   'Current factors are conditionally applied to the frozen 2025-2026 observation period only. '
                   'Fresh receipt ceiling replaces the older Sep30 review ceiling for this new bundle only. '
                   'Earlier station histories are not extrapolated. Publication/removal dates are not effective dates.',
               'training_ready': False, 'references': sorted(rows, key=lambda r: r['station_id'])}
    benchmark_json(payload)
    return payload


def bed_proxy_views():
    return {
        'v_bed_proxy_references': '''SELECT r.*, i.base_dataset_id, i.policy_version,
            i.analysis_start, i.analysis_end_exclusive FROM {s}.bed_proxy_references r
            JOIN {s}.bed_proxy_imports i USING(bundle_id)''',
        'v_observations_bed_proxy_context': '''WITH matched AS (
            SELECT o.station_id, o.observed_at, o.level_m AS reported_water_level_m,
                o.discharge_m3_s, o.level_quality, o.discharge_quality,
                o.source_path AS observation_source_path, o.received_at AS observation_received_at,
                i.bundle_id, i.base_dataset_id, i.policy_version,
                r.station_id IS NOT NULL AS proxy_matched, r.bed_elevation_source_m, r.bed_source_datum,
                r.bed_elevation_aligned_m, r.comparison_datum, r.stage_add_m, r.depth_enabled,
                r.normalized_reference->>'selection' AS proxy_selection,
                r.normalized_reference->>'limitation' AS proxy_limitation,
                i.analysis_start, i.analysis_end_exclusive, r.conversion_source_received_at,
                o.observed_at >= i.analysis_start AND o.observed_at < i.analysis_end_exclusive
                    AND o.observed_at <= r.conversion_source_received_at AS within_review_scope,
                CASE WHEN o.observed_at >= i.analysis_start AND o.observed_at < i.analysis_end_exclusive
                    AND o.observed_at <= r.conversion_source_received_at
                    THEN o.level_m + r.stage_add_m END AS approximate_water_surface_elevation_m
            FROM {s}.v_observations o CROSS JOIN {s}.bed_proxy_imports i
            LEFT JOIN {s}.bed_proxy_references r ON r.bundle_id=i.bundle_id AND r.station_id=o.station_id
        ), estimated AS (
            SELECT *, CASE WHEN depth_enabled THEN approximate_water_surface_elevation_m -
                bed_elevation_aligned_m END AS approximate_depth_m FROM matched
        ) SELECT *, approximate_depth_m < 0 AS negative_depth,
            CASE WHEN NOT proxy_matched THEN 'missing_station_reference'
                WHEN reported_water_level_m IS NULL THEN 'missing_observed_level'
                WHEN NOT within_review_scope THEN 'outside_review_scope'
                WHEN NOT depth_enabled THEN 'bed_vertical_datum_unverified_no_depth'
                WHEN approximate_depth_m < 0 THEN 'negative_approximate_depth_review_required'
                ELSE 'approximate_nearby_bed_proxy_temporal_and_spatial_assumptions' END AS depth_status,
            false AS training_ready, false AS gauge_bed_link_verified,
            false AS temporal_datum_verified, false AS hydraulic_transfer_verified,
            false AS contemporary_bed_verified
            FROM estimated''',
    }


def bed_proxy_baseline(db, schema):
    baseline = benchmark_baseline(db, schema)
    definitions = db.execute('SELECT viewname,definition FROM pg_views WHERE schemaname=%s '
        "AND viewname NOT IN ('v_bed_proxy_references','v_observations_bed_proxy_context') ORDER BY viewname",
        (schema,)).fetchall()
    baseline['default_view_sha256'] = hashlib.sha256(benchmark_json(definitions).encode()).hexdigest()
    return baseline


def run_bed_proxies(mode):
    """Add/verify a versioned lookup and one observation row per bundle, locally."""
    import psycopg
    from psycopg.rows import dict_row
    payload = bed_proxy_payload()
    config_bytes = CONFIG.read_bytes()
    config = json.loads(config_bytes)
    views = bed_proxy_views()
    payload['view_sql'] = views
    bundle_id = hashlib.sha256(benchmark_json({'base_dataset_id': config['dataset_id'],
        'evidence': payload, 'view_sql': views}).encode()).hexdigest()
    result = {'mode': mode, 'database': config['database'], 'schema': config['schema'],
              'bed_proxy_bundle_id': bundle_id, 'reference_count': len(payload['references']),
              'training_started': False, 'training_ready': False}
    if mode == 'check':
        result['status'] = 'local_evidence_validation_passed_no_database_changes'
        print(json.dumps(result, indent=2))
        return result
    with psycopg.connect(**benchmark_connection_options(), row_factory=dict_row) as db:
        if mode == 'verify':
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        db.execute("SET LOCAL lock_timeout = '10s'")
        db.execute("SET LOCAL statement_timeout = '120s'")
        server = db.execute('SELECT current_database() AS database, host(inet_server_addr()) AS address').fetchone()
        if server['database'] != config['database'] or not server['address'] or \
                not ipaddress.ip_address(server['address']).is_loopback:
            raise ValueError('Bed-proxy import requires the configured local database')
        schema = config['schema']
        def execute(statement, params=None):
            return db.execute(sql.SQL(statement).format(s=sql.Identifier(schema)), params)
        original = execute('SELECT dataset_id FROM {s}.dataset_metadata').fetchone()
        if original is None or original['dataset_id'] != config['dataset_id']:
            raise ValueError('Original immutable dataset identity mismatch')
        before = bed_proxy_baseline(db, schema)
        if mode == 'import':
            db.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (schema + ':bed_proxy',))
            execute('CREATE TABLE IF NOT EXISTS {s}.bed_proxy_imports ('
                'bundle_id text PRIMARY KEY, base_dataset_id text NOT NULL, policy_version text NOT NULL, '
                'analysis_start timestamptz NOT NULL, analysis_end_exclusive timestamptz NOT NULL, '
                'imported_at timestamptz NOT NULL DEFAULT now(), source_manifest jsonb NOT NULL, '
                'view_definition_sha256 text NOT NULL, CHECK(analysis_start < analysis_end_exclusive))')
            execute('CREATE TABLE IF NOT EXISTS {s}.bed_proxy_references ('
                'bundle_id text NOT NULL REFERENCES {s}.bed_proxy_imports(bundle_id), station_id text NOT NULL, '
                'bed_elevation_source_m double precision NOT NULL, bed_source_datum text NOT NULL, '
                'bed_elevation_aligned_m double precision, comparison_datum text NOT NULL, '
                'stage_add_m double precision NOT NULL, conversion_source_received_at timestamptz NOT NULL, '
                'depth_enabled boolean NOT NULL, normalized_reference jsonb NOT NULL, '
                'PRIMARY KEY(bundle_id,station_id), '
                'CHECK(depth_enabled = (bed_elevation_aligned_m IS NOT NULL)))')
            for name, statement in views.items():
                exists = db.execute('SELECT 1 FROM pg_views WHERE schemaname=%s AND viewname=%s',
                                    (schema, name)).fetchone()
                if exists is None:
                    db.execute(sql.SQL('CREATE VIEW {} AS ').format(sql.Identifier(schema, name)) +
                               sql.SQL(statement).format(s=sql.Identifier(schema)))
        definitions = db.execute('SELECT viewname,definition FROM pg_views WHERE schemaname=%s '
            'AND viewname=ANY(%s) ORDER BY viewname', (schema, list(views))).fetchall()
        if len(definitions) != len(views):
            raise ValueError('Missing bed-proxy evidence views')
        view_hash = hashlib.sha256(benchmark_json(definitions).encode()).hexdigest()
        prior = execute('SELECT source_manifest,view_definition_sha256 FROM {s}.bed_proxy_imports').fetchall()
        if any(p['source_manifest'].get('view_sql') != views or p['view_definition_sha256'] != view_hash
               for p in prior):
            raise ValueError('Existing proxy view definitions/policy differ; an explicit migration is required')
        existing = execute('SELECT * FROM {s}.bed_proxy_imports WHERE bundle_id=%s', (bundle_id,)).fetchone()
        if mode == 'import' and existing is None:
            execute('INSERT INTO {s}.bed_proxy_imports(bundle_id,base_dataset_id,policy_version,analysis_start,'
                'analysis_end_exclusive,source_manifest,view_definition_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s)',
                (bundle_id, config['dataset_id'], payload['policy_version'], payload['analysis_start'],
                 payload['analysis_end_exclusive'], Jsonb(payload), view_hash))
            for row in payload['references']:
                execute('INSERT INTO {s}.bed_proxy_references VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                    (bundle_id, row['station_id'], row['bed_elevation_source_m'], row['bed_source_datum'],
                     row['bed_elevation_aligned_m'], row['comparison_datum'], row['stage_add_m'],
                     row['stage_conversion']['source_received_at'], row['depth_enabled'], Jsonb(row)))
        result['reused_existing_bundle'] = existing is not None
        saved = execute('SELECT * FROM {s}.bed_proxy_imports WHERE bundle_id=%s', (bundle_id,)).fetchone()
        if saved is None or saved['source_manifest'] != payload or saved['view_definition_sha256'] != view_hash \
                or saved['base_dataset_id'] != config['dataset_id']:
            raise ValueError('Stored bed-proxy bundle identity differs from reviewed evidence')
        stored = execute('SELECT * FROM {s}.bed_proxy_references WHERE bundle_id=%s ORDER BY station_id',
                         (bundle_id,)).fetchall()
        if len(stored) != 5 or [r['normalized_reference'] for r in stored] != payload['references']:
            raise ValueError('Stored proxy references differ from reviewed evidence')
        for row, expected in zip(stored, payload['references']):
            for key in ('station_id', 'bed_elevation_source_m', 'bed_source_datum', 'bed_elevation_aligned_m',
                        'comparison_datum', 'stage_add_m', 'depth_enabled'):
                if row[key] != expected[key]:
                    raise ValueError('Typed proxy columns differ from evidence: ' + key)
            if row['conversion_source_received_at'] != datetime.fromisoformat(expected['stage_conversion']['source_received_at']):
                raise ValueError('Conversion source receipt mismatch')
        if saved['analysis_start'] != datetime.fromisoformat(payload['analysis_start']) or \
                saved['analysis_end_exclusive'] != datetime.fromisoformat(payload['analysis_end_exclusive']):
            raise ValueError('Analysis window differs from reviewed policy')
        duplicate = execute('SELECT 1 FROM {s}.v_observations_bed_proxy_context WHERE bundle_id=%s '
            'GROUP BY station_id,observed_at HAVING count(*)<>1 LIMIT 1', (bundle_id,)).fetchone()
        stations = execute('SELECT station_id,count(*) AS observation_rows, '
            'count(*) FILTER(WHERE proxy_matched) AS matched_rows, '
            'count(reported_water_level_m) AS stage_rows, count(approximate_depth_m) AS approximate_depth_rows, '
            'count(*) FILTER(WHERE approximate_depth_m IS NULL) AS null_depth_rows, '
            'count(*) FILTER(WHERE negative_depth) AS negative_depth_rows, '
            'count(*) FILTER(WHERE training_ready) AS training_ready_rows, '
            'min(approximate_depth_m) AS minimum_approximate_depth_m, '
            'max(approximate_depth_m) AS maximum_approximate_depth_m '
            'FROM {s}.v_observations_bed_proxy_context WHERE bundle_id=%s GROUP BY station_id ORDER BY station_id',
            (bundle_id,)).fetchall()
        originals = execute('SELECT station_id,count(*) AS observation_rows,count(level_m) AS stage_rows '
            'FROM {s}.v_observations GROUP BY station_id ORDER BY station_id').fetchall()
        if duplicate or len(stations) != len(originals):
            raise ValueError('Proxy join duplicated or lost observation keys')
        for row, source in zip(stations, originals):
            if any(row[key] != source[key] for key in ('station_id','observation_rows','stage_rows')) or \
                    row['matched_rows'] != source['observation_rows'] or row['training_ready_rows']:
                raise ValueError('Proxy context failed observation-count or training-isolation checks')
            expected_depth = 0 if row['station_id'] == '05CC003' else source['stage_rows']
            if row['approximate_depth_rows'] != expected_depth:
                raise ValueError('Unexpected missing approximate depths in the selected study window')
        missing_stage_with_depth = execute('SELECT 1 FROM {s}.v_observations_bed_proxy_context '
            'WHERE bundle_id=%s AND reported_water_level_m IS NULL AND approximate_depth_m IS NOT NULL LIMIT 1',
            (bundle_id,)).fetchone()
        if missing_stage_with_depth or before != bed_proxy_baseline(db, schema) or CONFIG.read_bytes() != config_bytes:
            raise ValueError('Original dataset/configuration integrity or null preservation failed')
        result.update({'stations': stations, 'baseline_integrity': before, 'server_is_loopback': True,
                       'observation_rows': sum(r['observation_rows'] for r in stations),
                       'approximate_depth_rows': sum(r['approximate_depth_rows'] for r in stations)})
    result['status'] = 'committed_and_verified' if mode == 'import' else 'read_only_verification_passed'
    print(json.dumps(result, indent=2))
    return result


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




def routing_verify(db, schema):
    from eda_tools.wave_time_alignment import EXPECTED
    counts = {r['station_id']: r['n'] for r in db.execute(
        'SELECT station_id,count(*) AS n FROM routing_discharge GROUP BY station_id')}
    if counts != EXPECTED:
        raise ValueError(f'Routing observation coverage does not match both archived API runs: {counts}')
    zero_count = db.execute('SELECT count(*) AS n FROM v_routing_dickson_zero WHERE is_imputed').fetchone()['n']
    if zero_count != 1694:
        raise ValueError(f'Unexpected count of designated missing Dickson slots: {zero_count}')
    weather_count = db.execute(
        'SELECT count(*) AS n,count(rain_mm) AS observed FROM routing_weather_hourly').fetchone()
    if not weather_count['observed']:
        raise ValueError('No observed rain in the routed weather archive')
    parcel = db.execute("""
        SELECT count(*) AS n, sum(parcel_m3) AS input_m3,
               count(*) FILTER (WHERE lag_bins=360) AS fast,
               count(*) FILTER (WHERE lag_bins BETWEEN 361 AND 602) AS transition,
               count(*) FILTER (WHERE rain_hour_utc IS NULL OR rain_hour_utc>=source_at) AS bad_weather_times
        FROM v_routing_medicine_parcels
    """).fetchone()
    arrived = db.execute("SELECT sum(discharge_m3_s)*300 AS total_m3, "
        "count(*) FILTER(WHERE arriving_centers>=2) AS overlaps "
        "FROM v_routing_medicine_arrivals").fetchone()
    if (parcel['n'] != counts['05CC007'] or parcel['bad_weather_times'] or
        parcel['fast'] != 1248 or parcel['transition'] != 1814 or arrived['overlaps'] != 1448 or
        not math.isclose(parcel['input_m3'], arrived['total_m3'], rel_tol=1e-11)):
        raise ValueError('Medicine source count, timing, overlap or volume parity failed: '
                         + str((parcel, arrived)))
    source_ledger = db.execute("SELECT station_id,count(*) AS n,count(DISTINCT source_at) AS unique_n "
                               "FROM v_routing_short_volume_parcels GROUP BY station_id").fetchall()
    if len(source_ledger)!=2 or any(row['n']!=row['unique_n'] or row['n']!=counts[row['station_id']]
                                    for row in source_ledger):
        raise ValueError(f'Short-route source ledger duplicated or dropped a measurement: {source_ledger}')
    short_volume = db.execute("""
      WITH actual AS (
        SELECT station_id, count(*) AS n, sum(discharge_m3_s)*300 AS volume_m3
        FROM routing_discharge WHERE station_id IN ('05CB007','05CB001') GROUP BY station_id
      ), delivered AS (
        SELECT station_id,sum(parcel_count) AS n, sum(volume_m3) AS volume_m3,
               count(*) FILTER(WHERE parcel_count>1) AS overlapping_arrival_bins,
               count(*) FILTER(WHERE NOT is_imputed AND last_source_at>=arrival_at) AS noncausal_bins
        FROM v_routing_short_volume_arrivals GROUP BY station_id
      )
      SELECT a.station_id, a.n AS source_parcels, d.n AS routed_parcels,
             a.volume_m3 AS input_volume_m3, d.volume_m3 AS routed_volume_m3,
             d.overlapping_arrival_bins, d.noncausal_bins
      FROM actual a JOIN delivered d USING(station_id)
    """).fetchall()
    if len(short_volume)!=2 or any(
        row['source_parcels']!=row['routed_parcels'] or row['noncausal_bins']
        or not math.isclose(row['input_volume_m3'], row['routed_volume_m3'], rel_tol=1e-10)
        for row in short_volume
    ):
        raise ValueError(f'Short-route source intervals must be routed exactly once: {short_volume}')
    coverage = db.execute("""
      SELECT count(*) AS all_groups, count(DISTINCT arrival_at) AS unique_groups,
             count(*) FILTER (WHERE hydro_complete) AS complete_groups,
             count(*) FILTER (WHERE red_deer_observed_q_m3_s>=200) AS high_groups,
             count(*) FILTER (WHERE hydro_complete AND red_deer_observed_q_m3_s>=200) AS complete_high_groups,
             count(*) FILTER (WHERE dickson_is_imputed) AS attached_dickson_zeros,
             count(*) FILTER (WHERE dickson_q_m3_s IS NULL) AS unmatched_dickson_after_fill,
             count(*) FILTER (WHERE dickson_is_imputed AND (dickson_q_m3_s IS DISTINCT FROM 0
                         OR dickson_source_file_id IS NOT NULL)) AS bad_dickson_zeros,
             count(*) FILTER (WHERE dickson_arrival_parcel_count>0 AND NOT dickson_is_imputed)
               AS observed_dickson_groups,
             count(*) FILTER (WHERE hydro_complete AND
                (upstream_total_q_m3_s IS NULL OR abs(upstream_total_q_m3_s*300-upstream_total_volume_m3)>1e-7)
                ) AS bad_combined_volumes,
             max(upstream_total_q_m3_s) FILTER (WHERE arrival_at='2025-06-21 13:10+00'::timestamptz)
               AS joint_q_at_2025_test_peak,
             max(dickson_q_m3_s) FILTER (WHERE arrival_at='2025-06-21 13:10+00'::timestamptz)
               AS dickson_q_at_2025_test_peak,
             count(*) FILTER (WHERE hydro_complete AND endpoint_depth_proxy_m IS NOT NULL
                AND arrival_at='2025-06-21 13:10+00'::timestamptz) AS peak_2025_eligible,
             count(*) FILTER (WHERE endpoint_depth_proxy_m IS NOT NULL) AS proxy_label_rows,
             count(*) FILTER (WHERE hydro_complete AND endpoint_depth_proxy_m IS NOT NULL) AS experimental_depth_groups,
             count(*) FILTER (WHERE hydro_complete AND endpoint_depth_proxy_m IS NOT NULL
               AND red_deer_observed_q_m3_s>=200) AS experimental_depth_high_groups,
             count(*) FILTER (WHERE hydro_complete AND
                (dickson_rain_1h_mm IS NULL OR little_red_deer_rain_1h_mm IS NULL OR medicine_rain_1h_mm IS NULL))
               AS rejected_weather_contract,
             count(*) FILTER (WHERE (dickson_source_at IS NOT NULL AND
                   (dickson_source_at>=arrival_at OR dickson_rain_hour_utc>=dickson_source_at))
                 OR (little_red_deer_source_at IS NOT NULL AND
                   (little_red_deer_source_at>=arrival_at OR little_red_deer_rain_hour_utc>=little_red_deer_source_at))
                 OR medicine_last_source_at>=arrival_at) AS bad_source_times
      FROM v_routing_arrival_audit
    """).fetchone()
    if (coverage['all_groups'] != counts['05CC002'] or coverage['unique_groups'] != coverage['all_groups']
            or coverage['bad_source_times'] or coverage['rejected_weather_contract']
            or coverage['unmatched_dickson_after_fill'] or coverage['bad_dickson_zeros']
            or coverage['bad_combined_volumes']
            or coverage['attached_dickson_zeros'] + coverage['observed_dickson_groups'] != coverage['all_groups']):
        raise ValueError(f'Final routing audit does not preserve one valid row per target time: {coverage}')
    return {'schema': schema, 'discharge_observations': counts, 'weather_hours': weather_count,
            'dickson_imputed_source_slots': zero_count, 'medicine': {**parcel, **arrived},
            'short_volume': [{**row, 'routed_parcels':int(row['routed_parcels'])} for row in short_volume], **coverage}




def stage_short_lag_calibration(db):
    """Derive historical time hints from PostgreSQL; views do the actual matching."""
    import numpy as np
    from eda_tools.wave_time_alignment import Series, STATIONS, TARGET, short_route_arrival_hints
    data = {}
    times = {}
    for station in STATIONS:
        rows = db.execute(
            'SELECT observed_at, discharge_m3_s, source_file_id, quality_flags, approval '
            'FROM routing_discharge WHERE station_id=%s ORDER BY observed_at', (station,)).fetchall()
        times[station] = [r['observed_at'] for r in rows]
        data[station] = Series(station,
            np.array([at.timestamp()/3600 for at in times[station]]),
            np.array([r['discharge_m3_s'] for r in rows]),
            [r['quality_flags'] for r in rows], [r['approval'] for r in rows],
            np.array([r['source_file_id'] for r in rows]), {})
    hints = short_route_arrival_hints(data)
    db.execute("""
      CREATE TABLE routing_short_lag_calibration (
        station_id text NOT NULL CHECK (station_id IN ('05CB007','05CB001')),
        target_at timestamptz NOT NULL,
        desired_epoch_hour double precision NOT NULL,
        proposed_method text NOT NULL,
        PRIMARY KEY(station_id,target_at))
    """)
    with db.cursor() as cursor:
        with cursor.copy('COPY routing_short_lag_calibration FROM STDIN') as copy:
            for station, result in hints.items():
                for at, desired, method in zip(times[TARGET], result['desired_source_time'], result['proposed_method']):
                    copy.write_row((station, at, float(desired), str(method)))
    db.execute('ANALYZE routing_short_lag_calibration')
    expected = {}
    for station, result in hints.items():
        expected[station] = [times[station][int(i)] if i>=0 else None for i in result['index']]
    return times[TARGET], expected


def verify_short_alignment(db, target_times, expected):
    """Independently compare every SQL observation selection with unchanged Python rules."""
    with db.cursor(name='check_short_alignment') as cursor:
        cursor.execute('SELECT station_id,arrival_at,source_at,is_imputed '
                       'FROM v_routing_short_arrivals ORDER BY station_id,arrival_at')
        counters = {}
        for row in cursor:
            station = row['station_id']
            i = counters.get(station, 0)
            at = None if row['is_imputed'] else row['source_at']
            if row['arrival_at'] != target_times[i] or at != expected[station][i]:
                raise ValueError('PostgreSQL historical source mismatch: '
                                 f"{station} {row['arrival_at']} {at} vs {expected[station][i]}")
            counters[station] = i+1
    if counters != {s:len(target_times) for s in expected}:
        raise ValueError('PostgreSQL changed short-route alignment coverage')


def run_routing_views(mode):
    """Install or update the same local PostgreSQL routing views transactionally."""
    from eda_tools.stage_forward_weather import stage_forward_weather
    from eda_tools.wave_time_alignment import EXPECTED, read_sources
    config = json.loads(CONFIG.read_text(encoding='utf-8'))
    schema = config['schema']
    sql_text = Path(__file__).with_name('routing_views.sql').read_text(encoding='utf-8-sig')
    volume_sql = Path(__file__).with_name('routing_short_volume.sql').read_text(encoding='utf-8-sig')
    marker = 'CREATE OR REPLACE VIEW v_routing_arrival_audit AS'
    if sql_text.count(marker)!=1:
        raise ValueError('Cannot place short-volume definitions before the arrival audit')
    sql_text = sql_text.replace(marker, volume_sql+'\n'+marker)
    options = benchmark_connection_options()
    options['application_name'] = 'rdr_forward_routing'
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(**options, row_factory=dict_row) as db:
        if mode == 'verify':
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        db.execute("SET LOCAL statement_timeout = '360s'")
        db.execute("SET LOCAL work_mem = '48MB'")
        db.execute(sql.SQL('SET LOCAL search_path TO {}, pg_catalog').format(sql.Identifier(schema)))
        if db.execute('SELECT current_database() AS name').fetchone()['name'] != config['database']:
            raise ValueError('The configured PostgreSQL database does not match')
        if db.execute('SELECT dataset_id FROM dataset_metadata').fetchone()['dataset_id'] != config['dataset_id']:
            raise ValueError('The configured hydrometric snapshot does not match')
        if mode == 'install':
            db.execute("SELECT pg_advisory_xact_lock(hashtext('rdr_forward_routing_v1'))")
            implementation_sha = hashlib.sha256(sql_text.encode()).hexdigest()
            db.execute("""
                CREATE TABLE IF NOT EXISTS routing_import_audit (
                  version text PRIMARY KEY, imported_at timestamptz DEFAULT clock_timestamp(),
                  discharge_manifest jsonb NOT NULL, discharge_counts jsonb NOT NULL,
                  weather_metadata jsonb NOT NULL, view_sql_sha256 text NOT NULL)
            """)
            previous = db.execute(
                "SELECT * FROM routing_import_audit WHERE version IN ('v1','v2','v3','v4') ORDER BY version DESC LIMIT 1").fetchone()
            if previous and previous['version']=='v4' and previous['view_sql_sha256'] != implementation_sha:
                raise ValueError('Routing v4 already installed with different SQL; preserve its audit')
            if not previous:
                data, manifest = read_sources()
                if len(manifest)!=152 or {s:len(x.time) for s,x in data.items()}!=EXPECTED:
                    raise ValueError('The audited WaterOffice acquisition inventory has changed')
                db.execute("""
                  CREATE TABLE routing_discharge_files (
                    source_file_id integer PRIMARY KEY, station_id text NOT NULL, acquisition_run text NOT NULL,
                    source_path text NOT NULL UNIQUE, sha256 text NOT NULL, byte_count bigint NOT NULL);
                  CREATE TABLE routing_discharge (
                    station_id text NOT NULL, observed_at timestamptz NOT NULL,
                    discharge_m3_s double precision NOT NULL CHECK
                      (discharge_m3_s >= 0 AND discharge_m3_s < 'Infinity'::double precision),
                    source_file_id integer NOT NULL REFERENCES routing_discharge_files(source_file_id),
                    quality_flags text NOT NULL, approval text NOT NULL,
                    PRIMARY KEY(station_id,observed_at),
                    CHECK (mod(extract(epoch FROM observed_at),300)=0));
                """)
                fields=('source_file_id','station_id','acquisition_run','path','sha256','bytes')
                with db.cursor() as cursor:
                    with cursor.copy('COPY routing_discharge_files FROM STDIN') as copy:
                        for row in manifest:
                            copy.write_row(tuple(row[k] for k in fields))
                    with cursor.copy('COPY routing_discharge FROM STDIN') as copy:
                        for station, series in data.items():
                            for i, hour in enumerate(series.time):
                                at = datetime.fromtimestamp(round(float(hour)*3600), timezone.utc)
                                copy.write_row((station, at, float(series.q[i]), int(series.provenance[i]),
                                                series.flags[i], series.approval[i]))
                weather = stage_forward_weather(db, schema)
                discharge_counts = {s:x.stats for s,x in data.items()}
                db.execute('ANALYZE routing_discharge')
                db.execute('ANALYZE routing_weather_hourly')
            else:
                manifest, discharge_counts, weather = (previous[k] for k in
                    ('discharge_manifest','discharge_counts','weather_metadata'))
            if not previous or previous['version']=='v1':
                target_times, selected = stage_short_lag_calibration(db)
                if previous:
                    db.execute('ALTER VIEW v_routing_training RENAME COLUMN label_q_m3_s TO label_endpoint_depth_proxy_m')
            if not previous or previous['version'] in ('v1','v2','v3'):
                db.execute(sql_text)
                if not previous or previous['version']=='v1':
                    verify_short_alignment(db, target_times, selected)
                db.execute("INSERT INTO routing_import_audit "
                           "(version,discharge_manifest,discharge_counts,weather_metadata,view_sql_sha256) "
                           "VALUES ('v4',%s,%s,%s,%s)",
                           (Jsonb(manifest),Jsonb(discharge_counts),Jsonb(weather),implementation_sha))
        result = routing_verify(db, schema)
    print(json.dumps(result,indent=2),flush=True)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--units',type=Path,default=DEFAULT_UNITS)
    parser.add_argument('--geometry',type=Path,default=DEFAULT_GEOMETRY)
    parser.add_argument('--split', choices=['60-20-20','80-20'], default='60-20-20')
    parser.add_argument('--benchmark-history', choices=['check', 'import', 'verify'],
                        help='Validate, add, or verify local benchmark evidence without changing training defaults')
    parser.add_argument('--bed-proxies', choices=['check', 'import', 'verify'],
                        help='Validate, add, or verify approximate bed-proxy context; never train or rewrite observations')
    parser.add_argument('--routing-views', choices=['install','verify'],
                        help='Install or verify the additive PostgreSQL-only forward routing package')
    args=parser.parse_args()
    if args.routing_views:
        if args.bed_proxies or args.benchmark_history:
            parser.error('Select only one add-on mode')
        run_routing_views(args.routing_views)
        return
    if args.bed_proxies:
        if args.benchmark_history:
            parser.error('Select one evidence mode at a time')
        try:
            run_bed_proxies(args.bed_proxies)
        except Exception as exc:
            if isinstance(exc, (ValueError, FileNotFoundError)):
                raise SystemExit(str(exc)) from None
            raise SystemExit('Bed-proxy operation failed (' + type(exc).__name__ +
                             '); no successful database commit is reported.') from None
        return
    if args.benchmark_history:
        try:
            run_benchmark_history(args.benchmark_history)
        except Exception as exc:
            # Driver exceptions can contain connection data; keep failure output credential-safe.
            if isinstance(exc, (ValueError, FileNotFoundError)):
                raise SystemExit(str(exc)) from None
            raise SystemExit('Benchmark operation failed (' + type(exc).__name__ +
                             '); no successful database commit is reported.') from None
        return
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
