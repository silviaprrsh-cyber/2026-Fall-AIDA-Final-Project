"""Cache official station-specific vertical-datum evidence once, without polling."""
from project_paths import resolve_runtime_path, archive_relative
import json
import re
import sys
import hashlib
from datetime import date, datetime
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from bs4 import BeautifulSoup


from rdr.storage import DATA, save_json, now
from API.client import fetch


BENCHMARK_PARSER_VERSION = 'bhr-local-v1'
BENCHMARK_POLICY_VERSION = 'bhr-evidence-only-v1'


def _benchmark_entries(page_text):
    """Read the first-page inventory, not the differently referenced history table."""
    lines = page_text.splitlines()
    header = next(i for i, line in enumerate(lines)
                  if 'Name' in line and 'Date Constructed' in line and 'Description' in line)
    end = next(i for i in range(header + 1, len(lines)) if 'Date Time' in lines[i])
    # A wrapped name in the history-table header can precede "Date Time".
    while end > header and not re.search(r'[A-Za-z]', lines[end - 1]):
        end -= 1
    name_end = lines[header].index('Elevation (m)')
    description_start = lines[header].index('Status') + len('Status')
    pattern = re.compile(
        r'^\s*(.*?)\s{3,}(-?\d+\.\d+)\s{3,}(\d{4}-\d{2}-\d{2})\s{3,}'
        r'(?:(\d{4}-\d{2}-\d{2})\s{3,})?(active primary|active|inactive)\s{3,}(.*)$')
    entries = []
    for line in lines[header + 1:end]:
        match = pattern.match(line)
        if match:
            name, elevation, constructed, removed, status, description = match.groups()
            date.fromisoformat(constructed)
            if removed:
                date.fromisoformat(removed)
                if removed < constructed or status != 'inactive':
                    raise ValueError('Inconsistent benchmark removal date/status')
            elif status == 'inactive':
                raise ValueError('Inactive benchmark lacks removal date')
            entries.append({'entry_index': len(entries), 'page': 1, 'name': name.strip(),
                            'elevation_m': float(elevation), 'constructed_date': constructed,
                            'removed_date': removed, 'status': status, 'datum_label': None,
                            'description': description.strip()})
        elif line.strip():
            if not entries or line[name_end:description_start].strip():
                raise ValueError('Unrecognized benchmark inventory row')
            name_part = line[:name_end].strip()
            if name_part:
                entries[-1]['name'] += ' ' + name_part
            description = line[description_start:].strip()
            if description:
                entries[-1]['description'] += ' ' + description
    if not entries or sum(e['name'] == 'Gauge Datum' for e in entries) != 1:
        raise ValueError('Expected exactly one Gauge Datum inventory entry')
    if sum(e['status'] == 'active primary' for e in entries) != 1:
        raise ValueError('Expected exactly one active primary benchmark')
    for entry in entries:
        # These labels describe the inventory entry only, not a conversion contract.
        description = entry['description']
        if re.search(r'Approx\.\s+GSC', description):
            entry['datum_label'] = 'Approx. GSC'
        elif re.search(r'\bGSC\b', description):
            entry['datum_label'] = 'GSC'
        elif '(Assumed)' in description:
            entry['datum_label'] = 'Assumed'
    return entries


def _benchmark_history_notes(page_texts):
    """Keep short dated review comments; do not infer offsets from observed BM values."""
    notes, seen = [], set()
    for page_number, page_text in enumerate(page_texts, 1):
        in_history, current = False, None
        for line in page_text.splitlines() + ['Date Time Comments']:
            is_header = 'Date Time' in line and 'Comments' in line
            match = re.match(r'^\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})\s+', line)
            if is_header or match or 'Environment and Climate Change Canada' in line:
                if current and current['comment']:
                    key = (current['observed_at_local'], current['comment'])
                    if key not in seen:
                        notes.append(current)
                        seen.add(key)
                current = None
            if is_header:
                in_history = True
            elif match and in_history:
                when = match.group(1)
                if when.startswith(('2025-', '2026-', '2019-09-04', '2019-10-09')):
                    comment = re.split(r'\s{3,}', line.strip())[-1]
                    current = {'page': page_number, 'observed_at_local': when.replace(' ', 'T'),
                               'comment': comment if re.search(r'[A-Za-z]', comment) else ''}
            elif current and line.strip():
                # Comments are rightmost. Wrapped party names near the left are not comments.
                continuation = re.split(r'\s{3,}', line.strip())[-1]
                if len(line) - len(line.lstrip()) > 160:
                    current['comment'] += ' ' + continuation
    return notes


def _cached_benchmark_conversions(station_id, workspace):
    """Inspect archived WaterOffice evidence locally; never fetch or overwrite it."""
    path = resolve_runtime_path(DATA / f'sources/eccc_wateroffice/raw/datums/{station_id}.html')
    if not path.is_file():
        return []
    content = path.read_bytes()
    source_sha256 = hashlib.sha256(content).hexdigest()
    metadata_path = path.with_name(path.name + '.meta.json')
    metadata = json.loads(metadata_path.read_text(encoding='utf-8')) if metadata_path.is_file() else {}
    if metadata.get('sha256') and metadata['sha256'] != source_sha256:
        raise ValueError(f'Cached datum-page hash mismatch: {station_id}')
    soup = BeautifulSoup(content, 'html.parser')
    text = (soup.find('main') or soup).get_text(' ', strip=True)
    if f'Vertical datum information for {station_id}' not in text:
        raise ValueError(f'Cached datum-page station mismatch: {station_id}')
    source_match = re.search(r'Data is published in (.*?)\.', text)
    if not source_match:
        return []
    matches = list(re.finditer(r'To convert to (.*?),\s*add\s+(-?\d+(?:\.\d+)?)\s*m\.', text))
    candidates = []
    for i, match in enumerate(matches):
        target_label, add_m = match.groups()
        if '2013:EPOCH2010' not in target_label:
            continue
        section = text[match.end():matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        uncertainty = re.search(r'This conversion has an uncertainty of \+/-\s*([\d.]+)\s*m', section)
        publication = re.search(r'This conversion factor was published on ([^.]+)\.', section)
        published_raw = publication.group(1) if publication else None
        published_date = None
        if published_raw:
            try:
                published_date = datetime.strptime(published_raw, '%B %d, %Y').date().isoformat()
            except ValueError:
                pass  # Preserve the source's malformed date, e.g. January 0, 1900.
        remarks = section.split('Frequently Asked Questions about Datums')[0].strip()
        candidates.append({
            'source_datum': source_match.group(1), 'target_datum': 'CGVD2013_e2010',
            'target_label': target_label, 'add_m': float(add_m),
            'uncertainty_m': float(uncertainty.group(1)) if uncertainty else None,
            'published_date_raw': published_raw, 'published_date': published_date,
            'publication_date_status': 'valid' if published_date else 'missing_or_invalid',
            'source_path': path.resolve().relative_to(workspace).as_posix(),
            'source_sha256': source_sha256, 'source_received_at': metadata.get('received_at_utc'),
            'source_url': metadata.get('url') or f'https://wateroffice.ec.gc.ca/report/datum_e.html?stn={station_id}',
            'temporal_status': 'no_explicit_effective_interval_in_cached_page',
            'effective_from': None, 'effective_to': None,
            'evidence': match.group(0), 'remarks': remarks,
            'application_scope': 'same_gauge_water_surface_elevation_only_not_depth',
        })
    return candidates


def parse_benchmark_history_reports(directory=None):
    """Return local BHR evidence without network, file, database or model writes.

    Inventory elevations can mix local and historical geodetic reference systems.
    A retired Gauge Datum is not a bed elevation or evidence that stage changed.
    BHR-only eligibility stays false; published same-gauge WSE candidates remain
    separate for an opt-in, provenance-aware consumer to review.
    """
    from pypdf import PdfReader  # Existing optional dependency, not needed by inspect().

    workspace = Path(__file__).resolve().parents[1]
    directory = Path(directory) if directory is not None else resolve_runtime_path(
        DATA / 'sources/eccc_documentation/manual/benchmark_history_reports')
    paths = sorted(path for path in directory.iterdir() if path.is_file()
                   and re.fullmatch(r'\d{2}[A-Z]{2}\d{3}_\d{8}_BHR\.PDF', path.name, re.I))
    if not paths:
        raise ValueError('No local Benchmark History Reports found')
    reports = []
    seen_stations = set()
    for path in paths:
        reader = PdfReader(path)
        page_texts = [page.extract_text(extraction_mode='layout') for page in reader.pages]
        first = page_texts[0]
        location = re.search(r'Location Identifier: (\w+), Location Name: ([^\r\n]+)', first)
        period = re.search(r'Period Selected: (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) to End of Record', first)
        generated = re.search(r'Benchmark History\s+([A-Za-z]+ \d{1,2}, \d{4})\s*\|\s*1 of (\d+)', first)
        utc = re.search(r'UTC Offset: ([+-]\d{2}:\d{2})', first)
        if not all((location, period, generated, utc)):
            raise ValueError(f'Unrecognized Benchmark History Report header: {path.name}')
        station_id = location.group(1)
        if station_id != path.name[:7] or int(generated.group(2)) != len(reader.pages):
            raise ValueError(f'Benchmark report filename/page-count mismatch: {path.name}')
        report_date = datetime.strptime(generated.group(1), '%b %d, %Y').date()
        selected_start = date.fromisoformat(period.group(1).split(' ')[0])
        if report_date.strftime('%Y%m%d') != path.name[8:16] or selected_start > report_date:
            raise ValueError(f'Benchmark report date mismatch: {path.name}')
        if station_id in seen_stations:
            raise ValueError(f'Duplicate station Benchmark History Report: {station_id}')
        seen_stations.add(station_id)
        if any(f'Location Identifier: {station_id},' not in text for text in page_texts):
            raise ValueError(f'Mixed station pages in report: {path.name}')
        entries = _benchmark_entries(first)
        candidates = _cached_benchmark_conversions(station_id, workspace)
        reports.append({
            'station_id': station_id, 'station_name': location.group(2).strip(),
            'source_path': path.resolve().relative_to(workspace).as_posix(),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'report_date': report_date.isoformat(),
            'selected_start': selected_start.isoformat(), 'selected_end': 'End of Record',
            'utc_offset': utc.group(1), 'page_count': len(reader.pages), 'entries': entries,
            'history_notes': _benchmark_history_notes(page_texts),
            'published_conversion_candidates': candidates,
            'eligibility': {
                'status': 'bhr_evidence_only_not_conversion_authority', 'conversion_eligible': False,
                'verified_add_m': None, 'target_datum': None,
                'reason': ('The BHR inventory alone does not establish a conversion of the observation series. '
                           'Published same-gauge CGVD2013e2010 factors are preserved separately when available; '
                           'their application requires matching input datum and temporal review. Gauge Datum '
                           'removal is not proof of stage discontinuity or factor expiry. No bed elevation, '
                           'cross-section transfer or true-depth label is established by these reports.'),
            },
        })
    return {'parser_version': BENCHMARK_PARSER_VERSION, 'policy_version': BENCHMARK_POLICY_VERSION,
            'reports': reports}


def inspect(station):
    sid = station['station_id']
    url = 'https://wateroffice.ec.gc.ca/report/datum_e.html'
    result = {'station_id': sid, 'metadata_datum': station.get('vertical_datum'),
              'source_url': url+'?stn='+sid, 'conversions': [], 'status': 'unavailable'}
    try:
        path = fetch(url, f'sources/eccc_wateroffice/raw/datums/{sid}.html', {'stn': sid}, timeout=25)
        soup = BeautifulSoup(path.read_text(encoding='utf-8'), 'html.parser')
        main = soup.find('main') or soup
        text = main.get_text(' ', strip=True)
        result['raw_path'] = str(archive_relative(path, DATA))
        if f'Vertical datum information for {sid}' not in text:
            result['status'] = 'station_page_not_confirmed'
            return result
        result['status'] = 'no_published_conversion'
        for match in re.finditer(r'To convert to (.*?),\s*add\s+(-?\d+(?:\.\d+)?)\s*m\.', text):
            label, offset = match.groups()
            result['conversions'].append({'target_label': label, 'add_m': float(offset),
                'target_datum': 'CGVD28_conventional' if label == 'GEODETIC SURVEY OF CANADA DATUM' else
                    'CGVD2013' if '2013' in label else 'other_or_local_adjustment',
                'evidence_text': match.group(0), 'status': 'official_published_conversion'})
        if result['conversions']: result['status'] = 'published_conversions_found'
        result['datum_caution'] = 'GSC datum is conventionally CGVD28; absolute accuracy, epoch and section transfer still require review.'
    except Exception as exc:
        result['error'] = type(exc).__name__
    return result


def main():
    stations = json.loads((resolve_runtime_path(DATA/'processed/station_master.json')).read_text())
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = []
        for record in pool.map(inspect, stations):
            records.append(record)
            print(record['station_id'], record['status'], flush=True)
    save_json(resolve_runtime_path(DATA/'processed/station_datums.json'), {'checked_at': now(), 'stations': records})


if __name__ == '__main__': main()
