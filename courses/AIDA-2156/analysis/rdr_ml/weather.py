"""Past-only observed weather features with explicit hourly coverage and provenance."""
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math

import numpy as np
from project_paths import WORKSPACE

FEATURE_NAMES = ['precipitation_1h_mm', 'precipitation_6h_mm', 'precipitation_24h_mm', 'temperature_c']
SCALES = np.array([10., 30., 60., 20.])


def instant(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def clean(value, flag, minimum=None):
    # Trace and estimated/flagged observations remain missing in this strict experiment.
    if value is None or flag not in (None, ''):
        return None
    number = float(value)
    if not math.isfinite(number) or (minimum is not None and number < minimum):
        return None
    return number


class Weather:
    def __init__(self, relative_path):
        path = (WORKSPACE / relative_path).resolve()
        if not path.is_relative_to(WORKSPACE) or not path.is_file():
            raise ValueError('Weather archive manifest must exist within workspace')
        self.manifest = json.loads(path.read_text())
        if not self.manifest.get('complete') or self.manifest['station_id'] != '3025484':
            raise ValueError('Incomplete archive or unassociated weather station')
        self.sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
        self.rows = {}
        for page in self.manifest['pages']:
            source = (WORKSPACE / page['path']).resolve()
            if not source.is_relative_to(WORKSPACE):
                raise ValueError('Weather page outside workspace')
            raw = source.read_bytes()
            if hashlib.sha256(raw).hexdigest() != page['sha256']:
                raise ValueError('Weather archive checksum mismatch')
            for feature in json.loads(raw)['features']:
                p = feature['properties']
                if p['CLIMATE_IDENTIFIER'] != '3025484':
                    raise ValueError('Unexpected weather station')
                at = instant(p['UTC_DATE'])
                if not instant(self.manifest['start']) <= at < instant(self.manifest['end']):
                    continue
                if at.minute or at.second:
                    raise ValueError('Non-hourly weather timestamp')
                row = {'precipitation': clean(p.get('PRECIP_AMOUNT'), p.get('PRECIP_AMOUNT_FLAG'), 0),
                       'temperature': clean(p.get('TEMP'), p.get('TEMP_FLAG')),
                       'source_id': feature['id']}
                if at in self.rows and self.rows[at] != row:
                    raise ValueError('Conflicting weather revision at same timestamp')
                self.rows[at] = row

    @lru_cache(maxsize=100000)
    def at(self, origin):
        # One-hour safety delay avoids using an unfinished hour even if the
        # provider hour labels are interpreted as starts rather than ends.
        end = origin.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        rows = [self.rows.get(end - timedelta(hours=i)) for i in range(24)]
        if any(r is None or r['precipitation'] is None for r in rows):
            raise ValueError('missing_or_flagged_weather_24h')
        if rows[0]['temperature'] is None:
            raise ValueError('missing_or_flagged_temperature')
        values = [sum(r['precipitation'] for r in rows[:n]) for n in [1, 6, 24]]
        values.append(rows[0]['temperature'])
        return np.asarray(values) / SCALES, {
            'station_id': '3025484', 'latest_source_observed_at': end.isoformat(),
            'oldest_source_observed_at': (end-timedelta(hours=23)).isoformat(),
            'features': dict(zip(FEATURE_NAMES, values)),
            'mean_precipitation_intensity_mm_h': dict(zip(['1h', '6h', '24h'],
                                                         [values[0], values[1]/6, values[2]/24])),
            'complete_hour_count': 24, 'safety_delay_hours': 1,
            'source_manifest_sha256': self.sha256,
            'role': 'nearby_point_context_not_catchment_average',
            'receipt_time_replay_verified': False}

    def audit(self, partitions):
        result = {}
        for name, origins in partitions.items():
            reasons = {}
            kept = 0
            for value in origins:
                try:
                    self.at(instant(value))
                    kept += 1
                except ValueError as exc:
                    reason = str(exc)
                    reasons[reason] = reasons.get(reason, 0) + 1
            result[name] = {'origins': len(origins), 'weather_complete': kept, 'excluded': reasons}
        return result
