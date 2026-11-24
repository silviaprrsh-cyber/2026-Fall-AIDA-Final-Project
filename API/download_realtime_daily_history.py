"""Archive the five model stations' complete 60-month real-time daily product.

This is a provisional daily product, not the approved HYDAT archive. Original
CSV values, missing values and all quality fields are retained without filtering.
"""
import argparse
import csv
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
from pathlib import Path
import re
import threading
import time
from requests import Request

from API.client import fetch
from API.download_unit_history import months_before, stamp, windows
from project_paths import WORKSPACE, ROOT, resolve_runtime_path
from rdr.paths import source_relative_path

URL = 'https://wateroffice.ec.gc.ca/services/real_time_data/csv/inline'
DOCUMENTATION = 'https://wateroffice.ec.gc.ca/services/index_e.html'
BASE = WORKSPACE / 'courses/AIDA-2156/data'
STATIONS = ['05CB007', '05CB001', '05CC007', '05CC003', '05CC002']
_gate = threading.Lock()
_next_request = 0.0
_rate_limited = 0
_stop = threading.Event()


def companion(path, english, chinese):
    path.with_name(path.name + '.md').write_text('# ' + path.name + '\n\n' + english + '\n', encoding='utf-8')
    path.with_name(path.name + 'CN.md').write_text('# ' + path.name + '\n\n' + chinese + '\n', encoding='utf-8')


def retry_seconds(value, now=None):
    """Accept Retry-After delta seconds and RFC HTTP dates."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            return max(0.0, (date - (now or datetime.now(timezone.utc))).total_seconds())
        except (TypeError, ValueError, OverflowError):
            return None


def paced():
    global _next_request
    with _gate:
        delay = max(0.0, _next_request - time.monotonic())
        if _stop.wait(delay):
            return False
        _next_request = time.monotonic() + 0.5
    return not _stop.is_set()


def describe_csv(path, job):
    counts, first, last, keys = Counter(), {}, {}, set()
    field_nonempty, quality = Counter(), {}
    rows = 0
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.reader(stream)
        header = next(reader, [])
        if len(header) != 9 or header[0].strip() != 'ID' or header[1] != 'Date':
            raise ValueError('Unexpected real-time daily CSV header')
        for row in reader:
            if not row:
                continue
            if len(row) != len(header) or row[0] != job['station_id'] or row[2] not in job['parameters']:
                raise ValueError('Unexpected CSV station, parameter or column count')
            observed = stamp(row[1])
            if not stamp(job['start']) <= observed <= stamp(job['end']):
                raise ValueError('Daily timestamp outside requested interval')
            parameter = row[2]
            counts[parameter] += 1
            first[parameter] = min(first.get(parameter, row[1]), row[1])
            last[parameter] = max(last.get(parameter, row[1]), row[1])
            keys.add((row[0], row[1], parameter))
            rows += 1
            for index, value in enumerate(row):
                if value:
                    field_nonempty[str(index)] += 1
                if index >= 4:
                    quality.setdefault(str(index), Counter())[value] += 1
    body = path.read_bytes()
    return {'row_count': rows, 'unique_record_count': len(keys),
            'duplicate_key_rows': rows - len(keys), 'parameter_rows': dict(counts),
            'first_observed_at': first, 'last_observed_at': last,
            'csv_fields': header, 'field_nonempty_counts': dict(field_nonempty),
            'quality_value_counts_by_column_index': quality,
            'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def next_target(run, job, minimum_attempt=1):
    attempt = minimum_attempt
    while True:
        relative = f'raw/realtime_daily_history/{run}/{job["station_id"]}/{job["chunk_id"]}_attempt{attempt}.csv'
        target = resolve_runtime_path(ROOT / 'data' / source_relative_path(URL, relative))
        if (not target.exists() and not target.with_suffix('.csv.meta.json').exists()
                and not target.with_suffix('.csv.failure.json').exists()):
            return attempt, relative
        attempt += 1


def recover_archived_job(job, run):
    """Recover completed CSVs left behind by an interrupted manifest write."""
    folder = BASE / 'sources/eccc_wateroffice/raw/realtime_daily_history' / run / job['station_id']
    params = {'stations[]': job['station_id'], 'parameters[]': job['parameters'],
              'start_date': stamp(job['start']).strftime('%Y-%m-%d %H:%M:%S'),
              'end_date': stamp(job['end']).strftime('%Y-%m-%d %H:%M:%S')}
    requested_url = Request('GET', URL, params=params).prepare().url
    candidates = list(folder.glob(job['chunk_id'] + '_attempt*.csv'))
    candidates.sort(key=lambda p: int(p.stem.rsplit('_attempt', 1)[1]), reverse=True)
    for path in candidates:
        try:
            meta = json.loads(path.with_suffix('.csv.meta.json').read_text(encoding='utf-8'))
            body = path.read_bytes()
            if (meta.get('status') != 200 or meta.get('url') != requested_url
                    or meta.get('bytes') != len(body) or meta.get('sha256') != hashlib.sha256(body).hexdigest()):
                continue
            stats = describe_csv(path, job)
        except (OSError, ValueError, KeyError):
            continue
        result = dict(job)
        archived_path = path.relative_to(WORKSPACE).as_posix()
        attempts = list(job.get('attempts', []))
        if not any(a.get('path') == archived_path for a in attempts):
            attempts.append({'attempt': int(path.stem.rsplit('_attempt', 1)[1]),
                             'status': 'validated', 'path': archived_path,
                             'started_at': meta.get('requested_at_utc'),
                             'recovered_after_local_manifest_failure': True})
        result.update(stats, status='downloaded' if stats['row_count'] else 'empty',
                      path=archived_path, attempts=attempts,
                      recovered_from_existing_validated_archive=True)
        return result
    return job


def acquire(job, run):
    global _next_request, _rate_limited
    result = dict(job)
    result['attempts'] = list(job.get('attempts', []))
    params = {'stations[]': job['station_id'], 'parameters[]': job['parameters'],
              'start_date': stamp(job['start']).strftime('%Y-%m-%d %H:%M:%S'),
              'end_date': stamp(job['end']).strftime('%Y-%m-%d %H:%M:%S')}
    for retry in range(3):
        if not paced():
            result.update(status='deferred', error='Run paused after provider rate limiting')
            return result
        minimum_attempt = max((a['attempt'] for a in result['attempts']), default=0) + 1
        attempt, relative = next_target(run, job, minimum_attempt)
        detail = {'attempt': attempt, 'relative_path': relative,
                  'started_at': datetime.now(timezone.utc).isoformat()}
        try:
            path = fetch(URL, relative, params, reuse=False, timeout=180)
            stats = describe_csv(path, job)
            detail.update(status='validated', path=path.relative_to(WORKSPACE).as_posix())
            result['attempts'].append(detail)
            companion(path, 'Original Wateroffice real-time daily CSV. Parameters 3=level and 6=flow. All values and quality columns are preserved; not approved HYDAT history.',
                      'Wateroffice 实时日均原始 CSV。参数 3 为水位，6 为流量。保留全部值和质量字段，不等同于 HYDAT 审定历史。')
            companion(path.with_suffix('.csv.meta.json'), 'HTTP provenance and original byte checksum for the corresponding CSV.',
                      '对应 CSV 的 HTTP 来源、收取时间和原始字节校验和。')
            result.update(stats, status='downloaded' if stats['row_count'] else 'empty',
                          path=path.relative_to(WORKSPACE).as_posix())
            print(job['station_id'], job['chunk_id'], result['status'], stats['row_count'], flush=True)
            return result
        except Exception as exc:
            response = getattr(exc, 'response', None)
            status = response.status_code if response is not None else None
            wait_header = response.headers.get('Retry-After') if response is not None else None
            delay = retry_seconds(wait_header)
            detail.update(status='failed', http_status=status, error=str(exc),
                          retry_after=wait_header, retry_after_seconds=delay)
            target = resolve_runtime_path(ROOT / 'data' / source_relative_path(URL, relative))
            failure_path = target.with_suffix('.csv.failure.json')
            failure_path.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation also records connection failures with no HTTP body.
            with failure_path.open('x', encoding='utf-8') as failure:
                json.dump(detail, failure, ensure_ascii=False, indent=2)
            companion(failure_path, 'Failure evidence for one distinct request attempt. The original HTTP body and metadata, when present, remain beside it.',
                      '一次独立请求尝试的失败记录。若存在 HTTP 响应正文和元数据，它们原样保存在旁边。')
            if target.exists():
                companion(target, 'Unmodified response from a failed or invalid attempt; do not use as validated observations.',
                          '失败或校验未通过尝试的原始响应，不作为已验证观测。')
            if target.with_suffix('.csv.meta.json').exists():
                companion(target.with_suffix('.csv.meta.json'), 'Original HTTP provenance for the failed attempt.',
                          '失败尝试的原始 HTTP 来源信息。')
            result['attempts'].append(detail)
            result.update(status='failed', error=str(exc))
            if delay is not None and delay > 120:
                _stop.set()
                result['status'] = 'deferred'
                break
            if status == 429:
                with _gate:
                    _rate_limited += 1
                    if _rate_limited >= 2 or (delay is not None and delay > 120):
                        _stop.set()
                    else:
                        _next_request = max(_next_request, time.monotonic() + max(delay or 0, 5))
                if _stop.is_set():
                    result['status'] = 'deferred'
                    break
            elif status is not None and 400 <= status < 500:
                break
            if retry < 2 and _stop.wait(max(delay or 0, 2 ** (retry + 1))):
                break
    print(job['station_id'], job['chunk_id'], result['status'], flush=True)
    return result


def save_manifest(path, manifest):
    temp = path.with_suffix('.json.tmp')
    temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    # Windows may briefly deny replacement while an indexer or reader holds it.
    # Preserve the complete temporary file and retry only this local operation.
    for attempt in range(8):
        try:
            temp.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(min(0.1 * 2 ** attempt, 2))


def summarize(jobs):
    records, raw_counts = {}, Counter()
    duplicate_rows = conflicting_keys = 0
    for job in jobs:
        if job['status'] not in {'downloaded', 'empty'}:
            continue
        with (WORKSPACE / job['path']).open(encoding='utf-8-sig', newline='') as stream:
            reader = csv.reader(stream)
            next(reader)
            for row in reader:
                if not row:
                    continue
                key = (row[0], row[2], row[1])
                raw_counts[(row[0], row[2])] += 1
                if key in records:
                    duplicate_rows += 1
                    conflicting_keys += records[key] != row
                records[key] = row
    coverage = []
    for sid, parameter in sorted(raw_counts):
        times = sorted(k[2] for k in records if k[:2] == (sid, parameter))
        dates = {stamp(t).date() for t in times}
        coverage.append({'station_id': sid, 'parameter': parameter,
                         'raw_rows': raw_counts[(sid, parameter)], 'unique_records': len(times),
                         'first_observed_at': times[0], 'last_observed_at': times[-1],
                         'distinct_utc_dates': len(dates),
                         'missing_utc_dates_between_first_last': (max(dates)-min(dates)).days+1-len(dates)})
    return {'raw_rows': sum(raw_counts.values()), 'unique_record_count': len(records),
            'duplicate_key_rows': duplicate_rows, 'conflicting_duplicate_key_rows': conflicting_keys,
            'coverage': coverage,
            'note': 'No quality filtering. UTC calendar gaps are provider absence, not proof of failed HTTP intervals. Raw files are never deduplicated or aligned.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', help='Resume a frozen run; a new ID creates an isolated run')
    parser.add_argument('--start', help='Timezone-aware start; default 60 calendar months before end')
    parser.add_argument('--end', help='Timezone-aware end; default current UTC time')
    parser.add_argument('--dry-run', action='store_true', help='Print plan without network or file writes')
    args = parser.parse_args()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    run = args.run_id or now.strftime('%Y%m%dT%H%M%SZ')
    if not re.fullmatch(r'[A-Za-z0-9_-]+', run):
        raise ValueError('Invalid run identifier')
    directory = BASE / 'reports/realtime_daily_history' / run
    path = directory / 'download_manifest.json'
    if path.exists():
        if args.start or args.end:
            raise ValueError('Resume uses frozen dates')
        manifest = json.loads(path.read_text(encoding='utf-8'))
    else:
        end = stamp(args.end) if args.end else now
        start = stamp(args.start) if args.start else months_before(end, 60)
        if start >= end:
            raise ValueError('Start must precede end')
        jobs = [{'station_id': sid, 'parameters': ['3'] if sid == '05CC003' else ['3', '6'],
                 'start': begin.isoformat(), 'end': finish.isoformat(),
                 'chunk_id': begin.strftime('%Y%m%dT%H%M%S'), 'status': 'pending'}
                for sid in STATIONS for begin, finish in windows(start, end)]
        manifest = {'run': run, 'endpoint': URL, 'provider_documentation': DOCUMENTATION,
                    'product': 'Wateroffice real-time daily means, separate from approved HYDAT',
                    'start': start.isoformat(), 'end': end.isoformat(),
                    'max_workers': 2, 'minimum_request_start_spacing_seconds': 0.5,
                    'maximum_attempts_per_job_per_invocation': 3, 'jobs': jobs}
    if args.dry_run:
        print(json.dumps({'run': run, 'start': manifest['start'], 'end': manifest['end'],
                          'stations': STATIONS, 'jobs': len(manifest['jobs']),
                          'network_calls': 0, 'writes': 0}, indent=2))
        return
    directory.mkdir(parents=True, exist_ok=True)
    # Validate resume artifacts; missing or changed files are fetched to a new attempt.
    for index, job in enumerate(manifest['jobs']):
        if job['status'] in {'downloaded', 'empty'}:
            artifact = WORKSPACE / job['path']
            if not artifact.exists() or hashlib.sha256(artifact.read_bytes()).hexdigest() != job['sha256']:
                job['status'] = 'pending'
        if job['status'] not in {'downloaded', 'empty'}:
            manifest['jobs'][index] = recover_archived_job(job, run)
    save_manifest(path, manifest)
    companion(path, 'Frozen monthly requests, original CSV checksums, attempt evidence, quality-field counts and unfiltered coverage. Resume with --run-id. Real-time daily means are not approved HYDAT history.',
              '冻结的月度请求、原始 CSV 校验和、尝试记录、质量字段计数和未筛选覆盖情况。使用 --run-id 继续。实时日均不等同于 HYDAT 审定历史。')
    pending = [(i, job) for i, job in enumerate(manifest['jobs']) if job['status'] not in {'downloaded', 'empty'}]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {pool.submit(acquire, job, run): i for i, job in pending}
        for future in as_completed(futures):
            manifest['jobs'][futures[future]] = future.result()
            save_manifest(path, manifest)
    manifest['requests_complete'] = all(j['status'] in {'downloaded', 'empty'} for j in manifest['jobs'])
    manifest['finished_at'] = datetime.now(timezone.utc).isoformat()
    manifest['status_counts'] = dict(Counter(j['status'] for j in manifest['jobs']))
    manifest['summary'] = summarize(manifest['jobs'])
    save_manifest(path, manifest)
    print(path, flush=True)
    if not manifest['requests_complete']:
        raise SystemExit(2)


if __name__ == '__main__':
    main()
