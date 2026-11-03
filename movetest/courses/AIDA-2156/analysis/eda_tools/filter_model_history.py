"""Screen complete official daily archives into date-aligned model candidates."""
import argparse
from collections import Counter
import csv
from datetime import date, datetime, timezone
import hashlib
import json
import math
from pathlib import Path

from project_paths import ROOT, WORKSPACE, resolve_runtime_path
from rdr_eda.project_etl import companion

BASE = WORKSPACE / 'courses/AIDA-2156/data'
STATIONS = ['05CB007', '05CB001', '05CC007', '05CC003', '05CC002']


def numeric(value):
    return isinstance(value, (int, float)) and math.isfinite(value) and value >= 0


def csv_file(path, rows, fields):
    with path.open('w', newline='', encoding='utf-8-sig') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    companion(path, 'Daily history derived by eda_tools.filter_model_history from the manifest-named official GeoMet pages. '
              'Dates have day precision. Blank fields represent missing measurements. Units are m and m3/s. '
              'Source symbols and provenance are retained. The split is a candidate date partition before propagation alignment. '
              'See README.md and screening_report.json for criteria and counts.',
              '由 eda_tools.filter_model_history 读取清单指定的官方 GeoMet 原始页生成。日期精度为日，空值代表缺测。'
              '单位为 m 和 m3/s，保留来源标记及出处。划分是传播对齐之前的候选日期划分。筛选规则和数量见 READMECN.md 与 screening_report.json。')


def build(manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    results = {row['station_id']: row for row in manifest['results']}
    if any(sid not in results or not results[sid]['complete'] for sid in STATIONS):
        raise ValueError('All five stations require complete downloads before screening')
    output = BASE / 'processed/model_daily_history' / manifest['run']
    output.mkdir(parents=True, exist_ok=True)
    records, by_station, provenance, summary = [], {}, {}, {}
    for sid in STATIONS:
        station = {}
        for relative in results[sid]['pages']:
            path = resolve_runtime_path(ROOT / relative)
            raw = path.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            meta = json.loads(path.with_suffix('.json.meta.json').read_text(encoding='utf-8'))
            if meta['status'] != 200 or digest != meta['sha256']:
                raise ValueError('Source integrity check failed')
            provenance[path.relative_to(WORKSPACE).as_posix()] = digest
            for feature in json.loads(raw)['features']:
                props = feature['properties']
                day = date.fromisoformat(props['DATE']).isoformat()
                if props['STATION_NUMBER'] != sid or day in station:
                    raise ValueError('Wrong station or duplicate station date')
                q, h = props.get('DISCHARGE'), props.get('LEVEL')
                row = {'station_id': sid, 'observation_date': day, 'resolution': 'daily_mean',
                       'discharge_m3_s': q, 'level_m': h,
                       'discharge_symbol': props.get('DISCHARGE_SYMBOL_EN'),
                       'level_symbol': props.get('LEVEL_SYMBOL_EN'),
                       'record_id': props.get('IDENTIFIER') or feature.get('id'),
                       'source_path': path.relative_to(WORKSPACE).as_posix(),
                       'received_at': meta.get('received_at_utc')}
                station[day] = row
        if len(station) != results[sid]['record_count']:
            raise ValueError('Manifest and normalized record counts differ')
        by_station[sid] = station
        records.extend(station.values())
        q_days = [day for day, row in station.items() if numeric(row['discharge_m3_s'])]
        h_days = [day for day, row in station.items() if numeric(row['level_m'])]
        summary[sid] = {'records': len(station), 'first_date': min(station), 'last_date': max(station),
                        'numeric_discharge_days': len(q_days), 'numeric_level_days': len(h_days),
                        'level_first_date': min(h_days) if h_days else None,
                        'level_last_date': max(h_days) if h_days else None}
    days = sorted(set.union(*(set(station) for station in by_station.values())))
    common, screened, audit = [], [], []
    for day in days:
        missing, flagged, nonpositive = [], [], []
        wide = {'observation_date': day}
        for sid in STATIONS:
            row = by_station[sid].get(day)
            measures = ['level_m'] if sid == '05CC003' else ['discharge_m3_s', 'level_m']
            if row is None:
                missing.append(sid + ':no_record')
                continue
            for key in measures:
                wide[sid + '_' + key] = row[key]
                if not numeric(row[key]):
                    missing.append(sid + ':' + key)
                elif row[key] == 0:
                    nonpositive.append(sid + ':' + key)
                symbol = 'discharge_symbol' if key == 'discharge_m3_s' else 'level_symbol'
                wide[sid + '_' + symbol] = row[symbol]
                if row[symbol] not in (None, ''):
                    flagged.append(sid + ':' + str(row[symbol]))
            wide[sid + '_record_id'] = row['record_id']
            wide[sid + '_source_path'] = row['source_path']
        status = 'missing_required_value' if missing else 'source_flagged' if flagged else 'zero_input' if nonpositive else 'selected'
        audit.append({'observation_date': day, 'status': status,
                      'missing_fields': json.dumps(missing), 'source_flags': json.dumps(flagged),
                      'zero_fields': json.dumps(nonpositive)})
        if not missing:
            wide['screening_status'] = status
            common.append(wide)
            if status == 'selected':
                screened.append(wide)
    assignments = []
    first, second = int(len(screened)*0.6), int(len(screened)*0.6)+int(len(screened)*0.2)
    for i, row in enumerate(screened):
        assignments.append({'observation_date': row['observation_date'],
                            'partition': 'training' if i < first else 'validation' if i < second else 'test',
                            'role': 'candidate_before_daily_propagation_alignment'})
    tables = {'station_daily': records, 'common_numeric_daily': common,
              'screened_daily': screened, 'daily_screening_audit': audit, 'daily_split_assignments': assignments}
    for name, rows in tables.items():
        fields = list(dict.fromkeys(key for row in rows for key in row)) or ['observation_date']
        csv_file(output / (name + '.csv'), rows, fields)
    runs = []
    for row in screened:
        day = date.fromisoformat(row['observation_date'])
        if not runs or (day-date.fromisoformat(runs[-1]['end'])).days != 1:
            runs.append({'start': day.isoformat(), 'end': day.isoformat(), 'days': 1})
        else:
            runs[-1]['end'] = day.isoformat()
            runs[-1]['days'] += 1
    report = {'created_at': datetime.now(timezone.utc).isoformat(), 'download_run': manifest['run'],
              'download_manifest': str(manifest_path.relative_to(WORKSPACE)), 'stations': summary,
              'raw_daily_records': len(records), 'common_numeric_days': len(common),
              'screened_days': len(screened), 'screened_first_date': screened[0]['observation_date'] if screened else None,
              'screened_last_date': screened[-1]['observation_date'] if screened else None,
              'screening_counts': dict(Counter(row['status'] for row in audit)),
              'partition_counts': dict(Counter(row['partition'] for row in assignments)),
              'continuous_selected_blocks': runs, 'source_sha256': provenance,
              'criteria': 'Four river Q and levels plus lake level, finite positive values, all required source symbols blank.',
              'training_status': 'daily_candidates_only_requires_day_resolution_model_and_lag_alignment'}
    path = output / 'screening_report.json'
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    companion(path, 'Screening counts, continuous date blocks and original-page hashes produced by filter_model_history. '
              'Supports audit and daily model preparation. This file invokes nothing.',
              'filter_model_history 生成的筛选数量、连续日期段及原始页哈希，用于审计和日尺度模型准备。文件自身不调用程序。')
    (output / 'README.md').write_text(
        '# Historical daily model candidates\n\n'
        f'Download run `{manifest["run"]}` contains {len(records):,} daily station records. '
        f'There are {len(common):,} dates with every required numeric field and {len(screened):,} dates in the conservative subset.\n\n'
        '- `station_daily.csv` retains all five stations, source symbols, missing values and page provenance.\n'
        '- `common_numeric_daily.csv` joins four river Q/level pairs and the lake level on the source date.\n'
        '- `screened_daily.csv` requires positive finite measurements and blank symbols on all required fields. '
        'Ice, estimated and partial-day records stay in the other tables for later sensitivity analysis.\n'
        '- `daily_screening_audit.csv` records missing fields, symbols, zero values and exclusion reasons for every date.\n'
        '- `daily_split_assignments.csv` assigns selected dates chronologically to 60/20/20, with integer rounding.\n'
        '- `screening_report.json` contains per-station coverage, continuous date blocks and original-page hashes.\n\n'
        'Dates retain daily precision. The selected dates include seasonal gaps. These are candidates before day-resolution '
        'propagation alignment. The current subdaily ML entry point needs a daily-resolution adaptation before using them. '
        'Daily means do not supply exact arrival-time observations.\n\n'
        f'Reproduce from movetest with `python -B run.py -m eda_tools.filter_model_history --manifest {manifest_path.relative_to(WORKSPACE).as_posix()}`.\n',
        encoding='utf-8')
    (output / 'READMECN.md').write_text(
        '# 历史日值模型候选数据\n\n'
        f'下载批次 `{manifest["run"]}` 包含 {len(records):,} 条站点日值记录。所有必需字段均有有效数值的日期为 {len(common):,} 天，保守子集为 {len(screened):,} 天。\n\n'
        '- `station_daily.csv` 保留五站全部记录、来源标记、缺测与原始页出处。\n'
        '- `common_numeric_daily.csv` 按来源日期关联四个河流站的 Q/水位和湖泊水位。\n'
        '- `screened_daily.csv` 要求所有必需字段为有限正值且来源标记为空。冰情、估算和部分日记录仍保留在其他表内，供敏感性分析。\n'
        '- `daily_screening_audit.csv` 逐日记录缺失字段、来源标记、零值和排除原因。\n'
        '- `daily_split_assignments.csv` 将筛选日期按时间顺序以 60/20/20 划分，数量按整数取整。\n'
        '- `screening_report.json` 保存分站覆盖、连续日期段及原始页哈希。\n\n'
        '日期精度为日，所选日期存在季节性间断。这些是日尺度传播对齐前的候选数据，现有亚日尺度 ML 入口需适配日尺度后才能使用。日均值无法提供精确到达时刻的观测。\n\n'
        f'在 movetest 中复现 `python -B run.py -m eda_tools.filter_model_history --manifest {manifest_path.relative_to(WORKSPACE).as_posix()}`。\n',
        encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['raw_daily_records','common_numeric_days','screened_days',
                                                  'screened_first_date','screened_last_date','partition_counts']}, indent=2))
    print(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', required=True, type=Path)
    args = parser.parse_args()
    build(args.manifest.resolve())


if __name__ == '__main__':
    main()
