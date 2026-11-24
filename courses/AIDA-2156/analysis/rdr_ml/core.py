"""Small endpoint-supervised models; no invented intermediate training labels."""
from collections import Counter
from datetime import datetime, timedelta, timezone
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path
import sqlite3

import numpy as np

from API.observations import parse_time
from rdr_eda.hydraulics import section_geometry
from rdr_eda.segments import ObservationIndex

PARAMETER_COUNT = 23


def positive(value):
    return value is not None and math.isfinite(float(value)) and float(value) > 0


def numeric_pair(row):
    return row and positive(row.get('discharge_m3_s')) and positive(row.get('experimental_variable_depth_m'))


class Dataset:
    """Read the complete ETL snapshot without updating it or contacting providers."""
    def __init__(self, path, policy, *, tables=None, partitions=None, source_metadata=None):
        self.path = Path(path).resolve() if path is not None else None
        self.partitions = partitions
        self.source_metadata = source_metadata or {"source": "sqlite_snapshot"}
        self.policy = policy
        self.weather = None
        self.use_weather = bool(policy.get('weather_enabled', False))
        if policy.get('weather_manifest'):
            from .weather import Weather
            self.weather = Weather(policy['weather_manifest'])
        if self.use_weather and self.weather is None:
            raise ValueError('Weather-enabled model requires a verified archive')
        self.parameter_count = PARAMETER_COUNT + (48 if self.use_weather else 0)
        if policy.get('schema_version') != 2 or policy.get('training_mode') != 'joint_endpoint_loss':
            raise ValueError('Use schema 2 with joint_endpoint_loss training')
        if policy.get('wet_component') != 'connected_to_lowest_surveyed_point':
            raise ValueError('Unsupported experimental wet-component selection')
        if policy.get('feature_station_id') != '05CC007':
            raise ValueError('This chain requires the 05CC007 independent feature input')
        if any(not positive(policy.get(key)) for key in [
                'feature_lag_initial_seconds', 'feature_lag_range_seconds', 'feature_trend_window_seconds']):
            raise ValueError('Feature lag and trend settings must be finite and positive')
        if tables is None:
            if self.path is None or not self.path.is_file():
                raise ValueError('Run the scoped ETL first: SQLite input does not exist')
            with sqlite3.connect(self.path.as_uri() + '?mode=ro', uri=True) as db:
                db.row_factory = sqlite3.Row
                tables = {name: [dict(row) for row in db.execute('SELECT * FROM ' + name)]
                          for name in ['model_segments', 'model_segment_legs', 'sections',
                                       'section_profile_points', 'water_observations', 'lake_reference']}
            self.sha256 = hashlib.sha256(self.path.read_bytes()).hexdigest()
        else:
            self.sha256 = self.source_metadata['dataset_id']
        if self.weather is not None:
            self.sha256 = hashlib.sha256((self.sha256 + self.weather.sha256).encode()).hexdigest()
        self.segments = sorted(tables['model_segments'], key=lambda row: row['sequence'])
        self.legs = tables['model_segment_legs']
        self.sections = {row['section_id']: row for row in tables['sections']}
        self.profiles = {}
        for row in tables['section_profile_points']:
            self.profiles.setdefault(row['section_id'], []).append((row['offset_m'], row['elevation_m']))
        self.profiles = {section: sorted(points) for section,points in self.profiles.items()}
        water = tables['water_observations']
        grouped = {}
        for row in water:
            grouped.setdefault(row['station_id'], []).append(row)
        self.index = {sid: ObservationIndex(rows) for sid, rows in grouped.items()}
        self.lake = ObservationIndex(tables['lake_reference'])
        self.sources = ['05CB007', '05CB001', '05CC007']
        self.origins = self.index['05CB007'].times
        self.geometry_sha256 = hashlib.sha256(json.dumps(
            self.profiles, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        if [s['output_node_id'] for s in self.segments] != ['P01', 'P02', 'P03', 'P04', 'P05', '05CC002']:
            raise ValueError('Unexpected chain: review the model graph before training')
        if policy['section_zero'] != 'minimum_surveyed_elevation_experimental':
            raise ValueError('Unsupported section-zero convention')

    def readiness(self):
        issues, mappings = [], []
        for sid in self.sources:
            if sid == self.policy['feature_station_id']:
                mappings.append({'station_id': sid, 'input_role': 'independent_features_with_learned_lag',
                                 'selected_section_id': None, 'section_required': False})
                continue
            selected = self.policy['source_section_ids'].get(sid)
            river = self.policy['source_rivers'][sid]
            candidates = sorted((s for s in self.sections.values() if s['river'] == river),
                                key=lambda s: abs(s['selected_river_chainage_m']))
            nearest = candidates[0] if candidates else None
            mappings.append({'station_id': sid, 'selected_section_id': selected,
                             'nearest_candidate': nearest['section_id'] if nearest else None,
                             'candidate_distance_from_route_start_m': nearest['selected_river_chainage_m'] if nearest else None,
                             'transfer_verified': False})
            if selected not in self.profiles:
                issues.append(f'{sid}: source section not assigned or absent')
            elif self.sections[selected]['river'] != river:
                issues.append(f'{sid}: source section is on another river')
        for section in {s['section_id'] for s in self.segments} | set(self.policy['source_section_ids'].values()):
            if section not in self.profiles:
                if section is not None:
                    issues.append(f'{section}: section profile absent')
                continue
            try:
                points = self.profiles[section]
                section_geometry(points, min(z for x, z in points) + 1)
            except (ValueError, TypeError) as exc:
                issues.append(f'{section}: {exc}')
        return {'ready_for_calibration': not issues, 'blocking_issues': issues,
                'source_sections': mappings, 'trajectory_count': len(self.origins),
                'segment_count': len(self.segments), 'input_sha256': self.sha256,
                'section_zero': self.policy['section_zero'], 'intermediate_ground_truth': False,
                'receipt_time_replay_verified': False, 'hydraulic_validation': False,
                'data_source': self.source_metadata,
                'weather_enabled': self.use_weather,
                'weather_manifest_sha256': self.weather.sha256 if self.weather else None,
                'weather_coverage': self.weather.audit(self.partitions) if self.weather and self.partitions else None,
                'view_candidate_count': sum(map(len,self.partitions.values())) if self.partitions is not None else None}

    @lru_cache(maxsize=65536)
    def area(self, section, depth):
        points = self.profiles[section]
        lowest_offset, lowest_elevation = min(points, key=lambda point: (point[1], point[0]))
        result = section_geometry(points, lowest_elevation + depth, connected_offset_m=lowest_offset)
        if result['profile_truncated']:
            raise ValueError('water_surface_above_survey_edge')
        if result['wet_components'] != 1:
            raise ValueError('disconnected_wetted_components')
        if not positive(result['area_m2']):
            raise ValueError('zero_wetted_area')
        return result['area_m2']

    def geometry(self, section, depth, discharge):
        area = self.area(section, depth)
        return area, discharge / area

    def common_origins(self):
        """Require numeric observations from every input and endpoint at the seed time."""
        times = []
        coverage = {}
        for station_id in ['05CB007', '05CB001', '05CC007', '05CC002', '05CC003']:
            index = self.lake if station_id == '05CC003' else self.index[station_id]
            valid = [row for row in index.rows if
                     (positive(row.get('level_m')) if station_id == '05CC003' else numeric_pair(row))]
            observed = {parse_time(row['observed_at']) for row in valid}
            times.append(observed)
            coverage[station_id] = {'valid_records': len(observed),
                                    'first_observed_at': min(observed).isoformat() if observed else None,
                                    'last_observed_at': max(observed).isoformat() if observed else None}
        if self.partitions is not None:
            common = sorted(parse_time(value) for values in self.partitions.values() for value in values)
            if len(common) != len(set(common)):
                raise ValueError('PostgreSQL partition views overlap')
            if not set(common).issubset(set.intersection(*times)):
                raise ValueError('PostgreSQL views contain origins missing numeric observations')
            selection = 'postgresql_training_validation_test_views'
        else:
            common = sorted(set.intersection(*times))
            selection = 'exact_common_numeric_observation_timestamps'
        return common, {'selection': selection,
                        'all_seed_origins': len(self.origins), 'common_origins': len(common),
                        'stations': coverage,
                        'common_timestamps': [time.isoformat() for time in common]}


class Chain:
    """Six recursive parameter blocks fitted jointly through endpoint loss.

    Q_out = Q_in * exp(a + lake_a * standardized_lake).
    h_out = h_in * exp(b + lake_b * standardized_lake) * (Q_out/Q_in)^p.
    The lake terms exist only in M04. Velocity is always Q_out/A(h_out).
    The fixed exponent and zero-centered coefficient penalty are explicit priors.
    """
    def __init__(self, dataset, parameters=None, lake_center=0.0, lake_scale=1.0):
        self.data = dataset
        self.parameters = np.zeros(dataset.parameter_count) if parameters is None else np.asarray(parameters, dtype=float)
        if self.parameters.shape != (dataset.parameter_count,) or not np.isfinite(self.parameters).all():
            raise ValueError(f'Expected {dataset.parameter_count} finite joint model parameters')
        self.lake_center = float(lake_center)
        self.lake_scale = float(lake_scale)
        if not math.isfinite(self.lake_center) or not positive(self.lake_scale):
            raise ValueError('Lake center must be finite and scale must be positive')

    def predict(self, origin):
        d, p = self.data, self.data.policy
        origin = parse_time(origin) if isinstance(origin, str) else origin
        trajectory = '05CB007@' + origin.isoformat()
        result = {'trajectory_id': trajectory, 'forecast_origin_at': origin.isoformat(),
                  'status': 'pending', 'states': [], 'source_records': [], 'lake_feature': None}
        try:
            weather_features = None
            if d.weather is not None:
                weather_features, result['weather_features'] = d.weather.at(origin)
            branches = []
            planned = None
            for sid in d.sources:
                if sid == p['feature_station_id']:
                    continue
                section = p['source_section_ids'][sid]
                if section not in d.profiles:
                    raise ValueError('missing_source_section:' + sid)
                distance = next(l['distance_m'] for l in d.legs if l['source_node_id'] == sid)
                row, _, status = d.index[sid].previous(origin, p['source_max_age_seconds'])
                if status != 'usable' or not numeric_pair(row):
                    raise ValueError('missing_source_observation:' + sid)
                # Iterate the departure-time lookup using the selected record's geometry.
                converged = False
                for _ in range(12):
                    q, h = float(row['discharge_m3_s']), float(row['experimental_variable_depth_m'])
                    area, v = d.geometry(section, h, q)
                    lag = distance / v
                    if lag > p['max_transit_seconds']:
                        raise ValueError('source_transit_exceeds_limit:' + sid)
                    if sid == '05CB007':
                        planned = parse_time(row['observed_at']) + timedelta(seconds=lag)
                        converged = True
                        break
                    departure = planned - timedelta(seconds=lag)
                    if departure > origin:
                        raise ValueError('future_source_required:' + sid)
                    previous, _, status = d.index[sid].previous(departure, p['source_max_age_seconds'])
                    if status != 'usable' or not numeric_pair(previous):
                        raise ValueError('missing_departure_observation:' + sid)
                    if previous['observed_at'] == row['observed_at']:
                        converged = True
                        break
                    row = previous
                if not converged:
                    raise ValueError('departure_iteration_not_converged:' + sid)
                arrival = parse_time(row['observed_at']) + timedelta(seconds=lag)
                branches.append((q, h, arrival))
                result['source_records'].append({'station_id': sid, 'observed_at': row['observed_at'],
                                                'received_at': row.get('received_at'), 'source_path': row.get('source_path'),
                                                'level_quality': row.get('level_quality'),
                                                'discharge_quality': row.get('discharge_quality')})
                result['states'].append({'node_id': sid, 'discharge_m3_s': q, 'experimental_variable_depth_m': h,
                                         'velocity_m_s': v, 'area_m2': area, 'section_id': section,
                                         'state_kind': 'source_geometry_adapter', 'estimated_arrival_at': arrival.isoformat()})
            arrivals = [b[2] for b in branches]
            if (max(arrivals) - min(arrivals)).total_seconds() > p['merge_arrival_tolerance_seconds']:
                raise ValueError('branch_arrivals_not_aligned')
            at = max(arrivals)
            q = sum(b[0] for b in branches)
            h = sum(b[0] * b[1] for b in branches) / q
            lag = p['feature_lag_initial_seconds'] + self.parameters[22] * p['feature_lag_range_seconds']
            if lag <= 0 or lag > p['max_transit_seconds']:
                raise ValueError('invalid_feature_station_lag')
            departure = at - timedelta(seconds=float(lag))
            if departure > origin:
                raise ValueError('future_feature_station_input_required')
            index = d.index[p['feature_station_id']]
            feature_row, _, feature_status = index.previous(departure, p['source_max_age_seconds'])
            if feature_status != 'usable' or not numeric_pair(feature_row):
                raise ValueError('missing_feature_station_observation')
            previous_time = parse_time(feature_row['observed_at']) - timedelta(seconds=p['feature_trend_window_seconds'])
            trend_row, _, trend_status = index.previous(previous_time, p['source_max_age_seconds'])
            if trend_status != 'usable' or not numeric_pair(trend_row):
                raise ValueError('missing_feature_station_trend')
            feature_q = float(feature_row['discharge_m3_s'])
            feature_h = float(feature_row['experimental_variable_depth_m'])
            hours = (parse_time(feature_row['observed_at']) - parse_time(trend_row['observed_at'])).total_seconds()/3600
            features = np.array([math.log1p(feature_q), math.log1p(feature_h),
                                 (feature_q-float(trend_row['discharge_m3_s']))/hours,
                                 (feature_h-float(trend_row['experimental_variable_depth_m']))/hours])
            result['feature_station'] = {'station_id': p['feature_station_id'],
                                         'lag_seconds': float(lag), 'required_departure_at': departure.isoformat(),
                                         'features': features.tolist(), 'feature_names': ['log1p_Q', 'log1p_stage', 'Q_change_per_hour', 'stage_change_per_hour']}
            for role, record in [('feature', feature_row), ('trend_history', trend_row)]:
                result['source_records'].append({'station_id': p['feature_station_id'], 'role': role,
                                                'observed_at': record['observed_at'], 'received_at': record.get('received_at'),
                                                'source_path': record.get('source_path')})
            lake, _, lake_status = d.lake.previous(origin, p['lake_max_age_seconds'])
            lake_valid = lake_status == 'usable' and positive(lake.get('level_m'))
            lake_z = (float(lake['level_m']) - self.lake_center) / self.lake_scale if lake_valid else 0.0
            result['lake_feature'] = {'status': lake_status, 'used_by': 'M04',
                                      'observed_at': lake['observed_at'] if lake_valid else None,
                                      'level_m': lake['level_m'] if lake_valid else None}
            # Missing lake data cannot silently stand in for mean elevation.
            if not lake_valid:
                raise ValueError('missing_lake_feature')
            for i, segment in enumerate(d.segments):
                if i:
                    at += timedelta(seconds=float(segment['distance_m']) / velocity)
                if (at - origin).total_seconds() > p['max_transit_seconds']:
                    raise ValueError('chain_transit_exceeds_limit')
                a, b = self.parameters[2*i:2*i+2]
                if i == 0:
                    a += float(np.dot(self.parameters[14:18], features))
                    b += float(np.dot(self.parameters[18:22], features))
                if segment['output_node_id'] == 'P04':
                    a += self.parameters[12] * lake_z
                    b += self.parameters[13] * lake_z
                if d.use_weather:
                    coefficients = self.parameters[23 + i*8:23 + (i+1)*8]
                    a += float(np.dot(coefficients[:4], weather_features))
                    b += float(np.dot(coefficients[4:], weather_features))
                next_q = q * math.exp(float(np.clip(a, -5, 5)))
                next_h = h * math.exp(float(np.clip(b, -5, 5))) * (next_q/q)**p['depth_discharge_exponent']
                area, velocity = d.geometry(segment['section_id'], next_h, next_q)
                q, h = next_q, next_h
                result['states'].append({'node_id': segment['output_node_id'], 'segment_id': segment['segment_id'],
                                         'discharge_m3_s': q, 'experimental_variable_depth_m': h,
                                         'velocity_m_s': velocity, 'area_m2': area, 'section_id': segment['section_id'],
                                         'estimated_arrival_at': at.isoformat(), 'state_kind': 'model_prediction'})
            result.update(status='predicted', estimated_arrival_at=at.isoformat())
        except (ValueError, OverflowError) as exc:
            result['status'] = str(exc)
        return result

    def scored(self, origin, lower=None, upper=None):
        result = self.predict(origin)
        if result['status'] != 'predicted':
            return result
        row, offset, status = self.data.index['05CC002'].nearest(
            parse_time(result['estimated_arrival_at']), self.data.policy['target_match_tolerance_seconds'])
        if status != 'matched' or not numeric_pair(row):
            result['label_status'] = 'no_arrival_matched_numeric_pair'
            return result
        observed = parse_time(row['observed_at'])
        source_times = [parse_time(r['observed_at']) for r in result['source_records']]
        source_times.append(parse_time(result['lake_feature']['observed_at']))
        # Earlier feature history is available at forecast time and may cross the split.
        # Downstream labels and forecast origins must stay in their assigned partition.
        forecast_origin = parse_time(result['forecast_origin_at'])
        if lower and (observed < lower or forecast_origin < lower):
            result['label_status'] = 'purged_before_split'
            return result
        if upper and (observed >= upper or forecast_origin >= upper or max(source_times) >= upper):
            result['label_status'] = 'purged_at_split'
            return result
        result.update(label_status='matched', label_observed_at=row['observed_at'],
                      label_received_at=row.get('received_at'), label_time_offset_seconds=offset,
                      label_discharge_m3_s=row['discharge_m3_s'],
                      label_variable_depth_m=row['experimental_variable_depth_m'])
        return result


def metrics(rows):
    matched = [r for r in rows if r.get('label_status') == 'matched']
    report = {'trajectories': len(rows), 'matched': len(matched),
              'coverage': len(matched)/len(rows) if rows else 0,
              'status_counts': dict(Counter(r.get('label_status', r['status']) for r in rows))}
    for name, prediction, label in [('discharge', 'discharge_m3_s', 'label_discharge_m3_s'),
                                    ('variable_depth', 'experimental_variable_depth_m', 'label_variable_depth_m')]:
        errors = np.array([r['states'][-1][prediction] - r[label] for r in matched])
        report[name] = {'mae': float(np.abs(errors).mean()) if len(errors) else None,
                        'rmse': float(np.sqrt((errors**2).mean())) if len(errors) else None,
                        'bias': float(errors.mean()) if len(errors) else None}
    return report


class InsufficientSplit(ValueError):
    """Carry the partition audit when a requested split cannot support training."""
    def __init__(self, report):
        super().__init__('Insufficient arrival-aligned samples for the requested split')
        self.report = report


def partition_origins(origins, policy):
    fractions = [policy[key] for key in ['training_fraction', 'validation_fraction', 'test_fraction']]
    if not positive(fractions[0]) or fractions[1] < 0 or not positive(fractions[2]) or not math.isclose(sum(fractions), 1):
        raise ValueError('Training and test fractions must be positive; validation may be zero; fractions must sum to one')
    first = int(len(origins)*fractions[0])
    second = first + int(len(origins)*fractions[1])
    if not 0 < first <= second < len(origins) or (fractions[1] > 0 and first == second):
        raise ValueError('Insufficient origins for the requested chronological partitions')
    return origins[:first], origins[first:second], origins[second:]


def fit(dataset, iterations=None):
    """Bounded joint parameter-vector search on calibration origins only."""
    p = dataset.policy
    ready = dataset.readiness()
    if not ready['ready_for_calibration']:
        raise ValueError('; '.join(ready['blocking_issues']))
    origins, overlap = dataset.common_origins()
    if len(origins) < 3:
        raise ValueError('Insufficient forecast origins')
    train, holdout, test = partition_origins(origins, p)
    if dataset.partitions is not None:
        selected = [sorted(parse_time(value) for value in dataset.partitions[name])
                    for name in ['train', 'validation', 'test']]
        if selected != [train, holdout, test]:
            raise ValueError('PostgreSQL view partitions differ from the configured chronological ratios')
        train, holdout, test = selected
    has_validation = bool(holdout)
    split, test_split = holdout[0] if has_validation else test[0], test[0]
    probe = Chain(dataset)
    print('Checking arrival alignment in training, validation and test views...', flush=True)
    train_count = sum(probe.scored(t, upper=split).get('label_status') == 'matched' for t in train)
    holdout_count = sum(probe.scored(t, lower=split, upper=test_split).get('label_status') == 'matched' for t in holdout)
    test_count = sum(probe.scored(t, lower=test_split).get('label_status') == 'matched' for t in test)
    print('Eligible baseline pairs:', train_count, holdout_count, test_count, flush=True)
    overlap['split_fractions'] = [p['training_fraction'], p['validation_fraction'], p['test_fraction']]
    overlap['validation_start_at'] = split.isoformat() if has_validation else None
    overlap['test_start_at'] = test_split.isoformat()
    overlap['partitions'] = {name: {'origins': len(group), 'matched_after_purge': count,
                                   'timestamps': [time.isoformat() for time in group]}
                             for name, group, count in [('training', train, train_count),
                                                        ('validation', holdout, holdout_count), ('test', test, test_count)]}
    if (train_count < p['minimum_training_pairs'] or (has_validation and holdout_count < p['minimum_validation_pairs']) or
            test_count < p['minimum_test_pairs']):
        raise InsufficientSplit({'status': 'insufficient_split_samples', 'overlap_selection': overlap,
                                 'model_written': False, 'fallback_to_all_data': False})
    training_origin_set = set(train)
    lake_training_rows = [r for r in dataset.lake.rows
                          if parse_time(r['observed_at']) in training_origin_set and positive(r.get('level_m'))]
    lake_values = [float(r['level_m']) for r in lake_training_rows]
    if not lake_values:
        raise ValueError('No training-period instantaneous lake observations')
    center, scale = float(np.mean(lake_values)), max(float(np.std(lake_values)), 0.01)
    baseline = Chain(dataset, lake_center=center, lake_scale=scale)
    baseline_train = [baseline.scored(t, upper=split) for t in train]
    # Freeze eligible origins before optimization, so parameters cannot improve loss by dropping cases.
    eligible = [parse_time(r['forecast_origin_at']) for r in baseline_train if r.get('label_status') == 'matched']
    matched_baseline = [r for r in baseline_train if r.get('label_status') == 'matched']
    if matched_baseline:
        overlap['baseline_matched_origin_start'] = min(r['forecast_origin_at'] for r in matched_baseline)
        overlap['baseline_matched_origin_end'] = max(r['forecast_origin_at'] for r in matched_baseline)
        overlap['baseline_matched_target_start'] = min(r['label_observed_at'] for r in matched_baseline)
        overlap['baseline_matched_target_end'] = max(r['label_observed_at'] for r in matched_baseline)
    if len(eligible) < p['minimum_training_pairs']:
        raise ValueError(f'Only {len(eligible)} baseline arrival-aligned training pairs; need {p["minimum_training_pairs"]}')
    train_rows = [r for r in baseline_train if r.get('label_status') == 'matched']
    scales = [max(float(np.mean([abs(r[k]) for r in train_rows])), floor)
              for k, floor in [('label_discharge_m3_s', 1.0), ('label_variable_depth_m', 0.01)]]
    def loss(theta):
        model = Chain(dataset, theta, center, scale)
        errors = []
        for t in eligible:
            row = model.scored(t, upper=split)
            if row.get('label_status') != 'matched':
                return float('inf')
            last = row['states'][-1]
            errors.extend([(last['discharge_m3_s']-row['label_discharge_m3_s'])/scales[0],
                           (last['experimental_variable_depth_m']-row['label_variable_depth_m'])/scales[1]])
        return float(np.mean(np.square(errors)) + p['regularization']*np.mean(theta**2))
    validation_origins = [time for time in holdout
                          if baseline.scored(time, lower=split, upper=test_split).get('label_status') == 'matched']
    def validation_loss(theta):
        candidate_model = Chain(dataset, theta, center, scale)
        errors = []
        for time in validation_origins:
            row = candidate_model.scored(time, lower=split, upper=test_split)
            if row.get('label_status') != 'matched':
                return float('inf')
            state = row['states'][-1]
            errors.extend([(state['discharge_m3_s']-row['label_discharge_m3_s'])/scales[0],
                           (state['experimental_variable_depth_m']-row['label_variable_depth_m'])/scales[1]])
        return float(np.mean(np.square(errors)))
    theta = np.zeros(dataset.parameter_count)
    best = loss(theta)
    print('Joint training started with', len(eligible), 'training pairs', flush=True)
    selected_theta = theta.copy()
    selected_validation_loss = validation_loss(theta) if has_validation else None
    selected_iteration = 0
    rng = np.random.default_rng(p['random_seed'])
    budget = p['iterations'] if iterations is None else iterations
    if budget < 1:
        raise ValueError('Iterations must be positive')
    history = [{'iteration': 0, 'loss': best}]
    for i in range(budget):
        candidate = theta.copy()
        # Each proposal updates the complete chain under one downstream objective.
        candidate = np.clip(candidate + rng.normal(0, 0.025/(1+i/budget), dataset.parameter_count), -1, 1)
        value = loss(candidate)
        if value < best:
            theta, best = candidate, value
            score = validation_loss(theta) if has_validation else None
            history.append({'iteration': i+1, 'loss': best,
                            'validation_loss': score if score is not None and math.isfinite(score) else None})
            if not has_validation or score < selected_validation_loss:
                selected_theta = theta.copy()
                selected_validation_loss = score
                selected_iteration = i+1
        if (i+1)%10 == 0 or i+1 == budget:
            print('Joint iteration', i+1, 'of', budget, 'training loss', best, flush=True)
    theta = selected_theta
    model = Chain(dataset, theta, center, scale)
    print('Evaluating the selected checkpoint...', flush=True)
    calibration = [model.scored(t, upper=split) for t in train]
    validation_rows = [model.scored(t, lower=split, upper=test_split) for t in holdout]
    evaluation = [model.scored(t, lower=test_split) for t in test]
    baseline_evaluation = [baseline.scored(t, lower=test_split) for t in test]
    validation = metrics(evaluation)
    artifact = {'schema_version': 2, 'created_at': datetime.now(timezone.utc).isoformat(),
                'model_type': 'regularized_recursive_endpoint_calibration',
                'weather_manifest_sha256': dataset.weather.sha256 if dataset.weather else None,
                'weather_enabled': dataset.use_weather,
                'weather_features': ['precipitation_1h_mm', 'precipitation_6h_mm', 'precipitation_24h_mm', 'temperature_c'] if dataset.use_weather else [],
                'weather_fixed_scales': [10, 30, 60, 20] if dataset.use_weather else [],
                'weather_coefficients_by_segment': theta[23:].reshape(6,8).tolist() if dataset.use_weather else [],
                'parameters': theta.tolist(), 'lake_center': center, 'lake_scale': scale,
                'policy': p, 'training_data_end_at': max(
                    [r['label_observed_at'] for r in calibration if r.get('label_status') == 'matched'] +
                    [r['observed_at'] for r in lake_training_rows]),
                'split_at': split.isoformat(), 'test_split_at': test_split.isoformat(), 'input_sha256': dataset.sha256,
                'selected_iteration': selected_iteration,
                'iterations_completed': budget,
                'selection_basis': 'validation_loss' if has_validation else 'training_loss',
                'selection_data_end_at': test_split.isoformat(),
                'geometry_sha256': dataset.geometry_sha256,
                'training_mode': 'joint_endpoint_loss',
                'origin_selection': overlap['selection'],
                'data_source': dataset.source_metadata,
                'calibration_only': False,
                'selected_origin_timestamps': overlap['common_timestamps'],
                'feature_station': {'station_id': p['feature_station_id'],
                                    'discharge_coefficients': theta[14:18].tolist(),
                                    'depth_coefficients': theta[18:22].tolist(),
                                    'lag_seconds': float(p['feature_lag_initial_seconds'] + theta[22]*p['feature_lag_range_seconds'])},
                'segments': dataset.segments,
                'submodels': {segment['segment_id']: {
                    'output_node_id': segment['output_node_id'],
                    'log_discharge_factor': float(theta[2*i]),
                    'log_depth_factor': float(theta[2*i+1]),
                    'lake_log_discharge_coefficient': float(theta[12]) if i == 3 else None,
                    'lake_log_depth_coefficient': float(theta[13]) if i == 3 else None}
                    for i, segment in enumerate(dataset.segments)},
                'status': 'experimental_calibrated_not_hydraulically_validated',
                'holdout_sufficient': validation['matched'] >= p['minimum_test_pairs']}
    artifact['model_version'] = hashlib.sha256(json.dumps(artifact, sort_keys=True).encode()).hexdigest()[:16]
    common = {r['trajectory_id'] for r in evaluation if r.get('label_status') == 'matched'} & {
        r['trajectory_id'] for r in baseline_evaluation if r.get('label_status') == 'matched'}
    report = {'readiness': ready, 'calibration': metrics(calibration), 'holdout': validation,
              'validation': metrics(validation_rows), 'test': validation,
              'selected_iteration': selected_iteration,
              'iterations_completed': budget,
              'selection_basis': 'validation_loss' if has_validation else 'training_loss',
              'overlap_selection': overlap,
              'baseline_holdout': metrics(baseline_evaluation),
              'common_origin_model': metrics([r for r in evaluation if r['trajectory_id'] in common]),
              'common_origin_baseline': metrics([r for r in baseline_evaluation if r['trajectory_id'] in common]),
              'optimization': history, 'eligible_calibration_origins': len(eligible),
              'loss_scales': {'discharge_m3_s': scales[0], 'variable_depth_m': scales[1],
                              'basis': 'training_label_mean_absolute_value'},
              'weather_enabled': dataset.use_weather,
              'weather_manifest_sha256': dataset.weather.sha256 if dataset.weather else None,
              'parameter_count': dataset.parameter_count,
              'training_mode': 'joint_endpoint_loss',
              'uncertainty': 'No calibrated prediction intervals; intermediate parameters are not uniquely identifiable.',
              'replay': 'Retrospective observation-time hindcast; receipt-time availability is not established.',
              'baseline': 'Uncalibrated zero coefficients; same geometry, source alignment and arrival matching.',
              'risk_status': 'indeterminate'}
    return artifact, report, evaluation
