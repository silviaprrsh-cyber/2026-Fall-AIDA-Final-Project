"""Bounded, resumable Wateroffice unit-value downloads with monthly requests."""
import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from API.client import fetch
from project_paths import WORKSPACE
from rdr_eda.project_etl import companion

URL = 'https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline'
BASE = WORKSPACE / 'courses/AIDA-2156/data'
STATIONS = ['05CB007', '05CB001', '05CC007', '05CC003', '05CC002']


def stamp(value):
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('UTC offset is required')
    return result.astimezone(timezone.utc)


def months_before(value, months):
    ordinal = value.year * 12 + value.month - 1 - months
    year, month = ordinal // 12, ordinal % 12 + 1
    return value.replace(year=year, month=month, day=min(value.day, calendar.monthrange(year, month)[1]))


def windows(start, end):
    result = []
    while start < end:
        next_month = (start.replace(year=start.year+1, month=1, day=1, hour=0, minute=0, second=0)
                      if start.month == 12 else start.replace(month=start.month+1, day=1, hour=0, minute=0, second=0))
        stop = min(end, next_month)
        result.append((start, stop))
        start = stop
    return result


def describe_csv(path, job):
    counts, first, last = {}, {}, {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        if len(header) < 9 or header[0].strip() != 'ID' or header[1] != 'Date':
            raise ValueError('Unexpected Wateroffice unit-value CSV header')
        for row in reader:
            if not row:
                continue
            if len(row) != len(header) or row[0] != job['station_id'] or row[2] not in job['parameters']:
                raise ValueError('Unexpected station, parameter or CSV row length')
            observed = stamp(row[1])
            if not stamp(job['start']) <= observed <= stamp(job['end']):
                raise ValueError('Observation outside requested time interval')
            parameter = row[2]
            counts[parameter] = counts.get(parameter, 0)+1
            first[parameter] = min(first.get(parameter, row[1]), row[1])
            last[parameter] = max(last.get(parameter, row[1]), row[1])
    return {'parameter_rows': counts, 'first_observed_at': first, 'last_observed_at': last,
            'row_count': sum(counts.values()), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def notes(path, purpose):
    companion(path, purpose + ' Created by API.download_unit_history. Source timestamps and receipt timestamps remain separate. '
              'Monthly request boundaries may repeat a record. See the run manifest and the unit-value analysis for deduplication and gaps.',
              '由 API.download_unit_history 生成的逐次观测原始响应、元数据或下载清单。来源观测时间与本地接收时间分别保留。'
              '月度请求边界可能重复记录，去重和缺测说明见运行清单与逐次观测分析。')


def acquire(job, run):
    updated = dict(job)
    params = {'stations[]': job['station_id'], 'parameters[]': job['parameters'],
              'start_date': stamp(job['start']).strftime('%Y-%m-%d %H:%M:%S'),
              'end_date': stamp(job['end']).strftime('%Y-%m-%d %H:%M:%S')}
    for attempt in range(1, 4):
        relative = f'raw/unit_values/{run}/{job["station_id"]}/{job["chunk_id"]}_attempt{attempt}.csv'
        try:
            path = fetch(URL, relative, params, reuse=True, timeout=180)
            details = describe_csv(path, job)
            notes(path, 'Original official unit-value CSV, parameter 46 for level and 47 for flow.')
            notes(path.with_suffix('.csv.meta.json'), 'HTTP provenance and original-response checksum.')
            updated.update(details, status='downloaded' if details['row_count'] else 'empty',
                           path=path.relative_to(WORKSPACE).as_posix(), attempts=attempt)
            print(job['station_id'], job['chunk_id'], updated['status'], details['row_count'], flush=True)
            return updated
        except Exception as exc:
            updated.update(status='failed', attempts=attempt, error=str(exc))
            if attempt < 3:
                time.sleep(2**attempt)
    print(job['station_id'], job['chunk_id'], 'FAILED', flush=True)
    return updated


def save_manifest(path, manifest):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8')
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', help='Resume the frozen window and jobs of an existing run')
    parser.add_argument('--start', help='Timezone-aware start, default 18 calendar months before end')
    parser.add_argument('--end', help='Timezone-aware end, default current UTC time')
    args = parser.parse_args()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    run = args.run_id or now.strftime('%Y%m%dT%H%M%SZ')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run):
        raise ValueError('Invalid run identifier')
    directory = BASE / 'reports/unit_history' / run
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'download_manifest.json'
    if path.exists():
        if args.start or args.end:
            raise ValueError('Resume uses the existing frozen dates')
        manifest = json.loads(path.read_text(encoding='utf-8'))
    else:
        end = stamp(args.end) if args.end else now
        start = stamp(args.start) if args.start else months_before(end, 18)
        if start >= end:
            raise ValueError('Start must precede end')
        jobs = []
        for sid in STATIONS:
            for begin, finish in windows(start, end):
                jobs.append({'station_id': sid, 'parameters': ['46'] if sid == '05CC003' else ['46', '47'],
                             'start': begin.isoformat(), 'end': finish.isoformat(),
                             'chunk_id': begin.strftime('%Y%m%dT%H%M%S'), 'status': 'pending'})
        manifest = {'run': run, 'endpoint': URL, 'start': start.isoformat(), 'end': end.isoformat(),
                    'window': '18_calendar_months_default', 'jobs': jobs,
                    'time_basis': 'UTC_observation_times', 'daily_data_used': False}
        save_manifest(path, manifest)
    notes(path, 'Frozen request plan, progress, checksums and per-station monthly outcomes.')
    pending = [(i, job) for i, job in enumerate(manifest['jobs']) if job['status'] not in {'downloaded', 'empty'}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(acquire, job, run): i for i, job in pending}
        for future in as_completed(futures):
            manifest['jobs'][futures[future]] = future.result()
            save_manifest(path, manifest)
    manifest['requests_complete'] = all(job['status'] in {'downloaded', 'empty'} for job in manifest['jobs'])
    manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
    manifest['completeness_note'] = 'All planned HTTP intervals processed. Missing provider observations may still exist.'
    save_manifest(path, manifest)
    print(path, flush=True)
    if not manifest['requests_complete']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
