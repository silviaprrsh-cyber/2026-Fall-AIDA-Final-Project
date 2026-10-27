"""Interval-aware precipitation; no averaging of depths or double-counting rolling totals."""
from bisect import bisect_right
from datetime import timedelta, timezone
import math
import re
from API.observations import parse_time


def finite(value):
    try:
        result = float(value)
        return result if not isinstance(value, bool) and math.isfinite(result) else None
    except (TypeError, ValueError): return None


def normalize_swob(properties, raw_path, available_at=None, record_id=None):
    end = parse_time(properties['date_tm-value']).astimezone(timezone.utc)
    records = []
    for field, value in properties.items():
        match = re.fullmatch(r'pcpn_amt_pst(\d+)(mt|mts|min|mins|hr|hrs)', field)
        if not match: continue
        period = int(match[1]) * (3600 if match[2].startswith('hr') else 60)
        qa = properties.get(field+'-qa')
        flag = str(properties.get(field+'-data_flag-value', ''))
        flags = set(flag.split(','))
        amount = finite(value)
        unit = properties.get(field+'-uom')
        valid = amount is not None and amount >= 0 and period > 0
        reason = None
        if not valid: reason = 'missing_or_invalid_value'
        elif unit != 'mm': valid=False; reason='unsupported_unit'
        elif qa is not None and qa != 100: valid=False; reason='qa_not_passed'
        elif flags & {'2','4','7','8','9','10','11'}: valid=False; reason='estimated_incomplete_or_ambiguous_amount'
        elif '5' in flags: valid=False; reason='trace_amount_not_quantified'
        records.append({'station_id': str(properties['msc_id-value']),
            'record_id': str(record_id or properties.get('id', end.isoformat())), 'field': field,
            'start': (end-timedelta(seconds=period)).isoformat(), 'end': end.isoformat(),
            'amount_mm': amount, 'kind': 'accumulation', 'unit': unit, 'period_seconds': period,
            'qa': qa, 'data_flag': flag, 'valid': valid, 'invalid_reason': reason,
            'quality_status': 'qa_passed' if qa == 100 else 'derived_complete' if flags == {'1'} else 'qa_unspecified',
            'published_at': properties.get('processed_date_tm'), 'available_at': available_at,
            'raw_path': raw_path})
    return records


def aggregate_precipitation(records, start, end, *, as_of=None):
    """Select a maximum-coverage nonoverlapping set of complete measurement intervals.

    A trailing-hour total that exactly matches the target is usable once. A rolling
    interval crossing a target boundary is not prorated without a rainfall model.
    Mean interval intensities (mm/h) are integrated over their complete intervals.
    Partial coverage returns null totals, with partial amounts kept separately.
    """
    start, end = parse_time(start), parse_time(end)
    if end <= start: raise ValueError('A positive analysis window is required')
    deadline = parse_time(as_of) if as_of else None
    latest = {}
    excluded = 0
    for record in records:
        a,b = parse_time(record['start']),parse_time(record['end'])
        if b<=start or a>=end: continue
        if deadline:
            known = record.get('available_at')
            if not known or parse_time(known)>deadline: excluded+=1;continue
        key=(record.get('station_id'),record.get('field'),a,b)
        version=(record.get('published_at') or '',record.get('available_at') or '',record.get('record_id') or '')
        if key not in latest or version>latest[key][0]:latest[key]=(version,record)
    intervals=[]
    for _,record in latest.values():
        a,b=parse_time(record['start']),parse_time(record['end'])
        if not record.get('valid',True) or a<start or b>end or b<=a:excluded+=1;continue
        seconds=(b-a).total_seconds()
        if record.get('kind')=='intensity':
            rate=finite(record.get('intensity_mm_h'))
            amount=None if rate is None else rate*seconds/3600
        else:amount=finite(record.get('amount_mm'))
        if amount is None or amount<0:excluded+=1;continue
        intervals.append((a,b,amount,record))
    intervals.sort(key=lambda v:(v[1],v[0],v[3].get('field','')))
    ends=[v[1] for v in intervals]
    # Weighted interval scheduling maximizes covered time, never overlapping totals.
    best=[(0.0,[])]
    for index,(a,b,amount,record) in enumerate(intervals):
        predecessor=bisect_right(ends,a,0,index)
        candidate=(best[predecessor][0]+(b-a).total_seconds(),best[predecessor][1]+[index])
        previous=best[-1]
        best.append(candidate if candidate[0]>previous[0] or
                    (candidate[0]==previous[0] and len(candidate[1])<len(previous[1])) else previous)
    coverage,chosen=best[-1]
    duration=(end-start).total_seconds()
    total=sum(intervals[i][2] for i in chosen)
    complete=abs(coverage-duration)<1e-6
    return {'window_start':start.isoformat(),'window_end':end.isoformat(),
        'duration_seconds':duration,'status':'complete' if complete else 'partial' if coverage else 'missing',
        'coverage_fraction':min(1,coverage/duration),'precipitation_total_mm':total if complete else None,
        'mean_precipitation_intensity_mm_h':total/(duration/3600) if complete else None,
        'covered_amount_mm':total if coverage else None,'covered_seconds':coverage,
        'input_interval_count':len(chosen),'excluded_count':excluded,
        'quality_statuses':sorted({intervals[i][3].get('quality_status','unspecified') for i in chosen}),
        'provenance':[{'record_id':intervals[i][3].get('record_id'),
            'field':intervals[i][3].get('field'),'raw_path':intervals[i][3].get('raw_path'),
            'start':intervals[i][0].isoformat(),'end':intervals[i][1].isoformat()} for i in chosen]}
