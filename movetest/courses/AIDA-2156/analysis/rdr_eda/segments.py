"""Prepare independent segment inputs and arrival-aligned downstream labels."""
from bisect import bisect_left, bisect_right
from collections import Counter
from datetime import timedelta
import csv
import hashlib
import json
import math

from API.observations import parse_time
from project_paths import ROOT, WORKSPACE


def elapsed_seconds(distance_m, velocity_m_s):
    """A preliminary L/V transit estimate, not a calibrated flood-wave lag."""
    if velocity_m_s is None:
        return None
    speed = float(velocity_m_s)
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError('Velocity must be finite and positive')
    if not math.isfinite(distance_m) or distance_m < 0:
        raise ValueError('Distance must be finite and nonnegative')
    return distance_m / speed


class ObservationIndex:
    def __init__(self, rows):
        self.rows = sorted((r for r in rows if r.get('observed_at')), key=lambda r: parse_time(r['observed_at']))
        self.times = [parse_time(r['observed_at']) for r in self.rows]

    def previous(self, at, max_age):
        i = bisect_right(self.times, at) - 1
        if i < 0:
            return None, None, 'no_prior_observation'
        age = (at - self.times[i]).total_seconds()
        return self.rows[i], age, 'usable' if age <= max_age else 'stale'

    def nearest(self, at, tolerance):
        if at is None:
            return None, None, 'arrival_unavailable'
        i = bisect_left(self.times, at)
        choices = [j for j in [i - 1, i] if 0 <= j < len(self.rows)]
        if not choices:
            return None, None, 'no_downstream_observations'
        # Equal-distance ties select the earlier observation, independent of receipt order.
        j = min(choices, key=lambda j: (abs((self.times[j] - at).total_seconds()), self.times[j]))
        offset = (self.times[j] - at).total_seconds()
        return self.rows[j], offset, 'matched' if abs(offset) <= tolerance else 'outside_tolerance'


def graph(tables, policy):
    stations = {s['station_id']: s for s in tables['stations']}
    end = stations[policy['validation_station_id']]['mainstem_chainage_or_confluence_m']
    nodes = sorted((t for t in tables['prediction_targets'] if t['chainage_from_dickson_m'] < end),
                   key=lambda t: t['chainage_from_dickson_m'])
    nearest = min((s for s in tables['sections'] if s['river'] == 'RED DEER RIVER'),
                  key=lambda s: abs(s['selected_river_chainage_m'] - end))
    nodes.append({'target_id': policy['validation_station_id'], 'chainage_from_dickson_m': end,
                  'section_id': None, 'nearest_section_id': nearest['section_id']})
    rivers = {r.get('station_id'): r for r in tables['river_inputs'] if r.get('station_id')}
    legs, segments = [], []
    for i, node in enumerate(nodes):
        sid = f'M{i+1:02d}'; dest = node['target_id']; at = node['chainage_from_dickson_m']
        upstream = policy['initial_input_station_ids'] if i == 0 else [nodes[i-1]['target_id']]
        distances = []
        for source in upstream:
            if i == 0:
                station = stations[source]
                main_length = at - station['mainstem_chainage_or_confluence_m']
                tributary_length = rivers.get(source, {}).get('length_m', 0)
            else:
                main_length = at - nodes[i-1]['chainage_from_dickson_m']; tributary_length = 0
            distance = main_length + tributary_length
            if distance <= 0:
                raise ValueError('Segment route must run upstream to downstream')
            distances.append(distance)
            legs.append({'leg_id': f'{sid}:{source}', 'segment_id': sid, 'source_node_id': source,
                         'destination_node_id': dest, 'distance_m': distance,
                         'mainstem_distance_m': main_length, 'tributary_distance_m': tributary_length,
                         'distance_basis': 'selected_GIS_river_route_not_straight_line',
                         'hydraulic_transfer_verified': False})
        segments.append({'segment_id': sid, 'sequence': i+1, 'input_node_ids': upstream,
                         'output_node_id': dest, 'previous_segment_id': f'M{i:02d}' if i else None,
                         'section_id': node.get('section_id') or node.get('nearest_section_id'),
                         'section_link_type': 'on_section' if node.get('section_id') else 'nearest_candidate',
                         'output_chainage_m': at, 'distance_m': distances[0] if i else None,
                         'lake_feature_station_id': policy['lake_station_id'] if dest == policy['lake_target_id'] else None,
                         'validation_node_id': policy['validation_station_id'],
                         'output_role': 'validation_location' if dest == policy['validation_station_id'] else 'unobserved_prediction'})
    return segments, legs


def read_states(builder, path, segments, origins, source_nodes):
    """Optional prior submodel outputs; never replace them with downstream truth."""
    if path is None:
        return {}
    path = path.resolve()
    if not path.is_relative_to(WORKSPACE):
        raise ValueError('State input must be within movetest')
    nodes = {s['output_node_id'] for s in segments} | set(source_nodes)
    states = {}
    for r in csv.DictReader(builder.read(path).splitlines()):
        key = (r['trajectory_id'], r['node_id'])
        if key in states or r['node_id'] not in nodes or r['trajectory_id'] not in origins:
            raise ValueError('Duplicate or unknown trajectory/node in model states')
        if r.get('state_kind') != 'model_prediction' or not r.get('model_version'):
            raise ValueError('States require state_kind=model_prediction and a model_version')
        origin = origins[r['trajectory_id']]
        if not r.get('training_data_end_at') or parse_time(r['training_data_end_at']) >= origin:
            raise ValueError('Model training data must precede the trajectory origin')
        for field in ['discharge_m3_s', 'variable_depth_m', 'velocity_m_s']:
            value = float(r[field]) if r.get(field) else None
            if value is not None and (not math.isfinite(value) or value < 0 or field == 'velocity_m_s' and value == 0):
                raise ValueError(f'Invalid model state {field}')
            r[field] = value
        states[key] = r
    return states


def speed_for(leg, departure, policy, prior_state):
    if prior_state and prior_state.get('velocity_m_s') is not None:
        return prior_state['velocity_m_s'], 'upstream_submodel:' + prior_state['model_version']
    return None, 'awaiting_submodel_velocity'


def build_segment_tables(builder, tables, state_path=None):
    policy = builder.obj(ROOT / 'config/segment_etl.json')
    if policy.get('velocity_source') != 'submodel_outputs':
        raise ValueError('This pipeline uses submodel-predicted velocities only')
    for name in ['source_max_age_seconds', 'lake_max_age_seconds', 'target_match_tolerance_seconds', 'merge_arrival_tolerance_seconds']:
        if not isinstance(policy[name], (int, float)) or isinstance(policy[name], bool) or not math.isfinite(policy[name]) or policy[name] < 0:
            raise ValueError(f'Invalid policy: {name}')
    segments, legs = graph(tables, policy)
    water = tables['water_observations']
    seeds = [r for r in water if r['station_id'] == policy['seed_station_id']]
    origins = {f"{r['station_id']}@{r['observed_at']}": parse_time(r['observed_at']) for r in seeds}
    states = read_states(builder, state_path, segments, origins, policy['initial_input_station_ids'])
    indexes = {sid: ObservationIndex([r for r in water if r['station_id'] == sid])
               for sid in policy['initial_input_station_ids'] + [policy['validation_station_id']]}
    lake = ObservationIndex(tables['lake_reference'])
    profiles = {s['section_id']: s for s in tables['sections']}
    station_windows = {(w['station_id'], w['window_end']): w for w in tables['station_windows']}
    master, arrival_legs = [], []
    for trajectory, origin in sorted(origins.items()):
        endpoint = None; trajectory_rows = []; cumulative_valid = True
        seed_leg = next(l for l in legs if l['source_node_id'] == policy['seed_station_id'])
        seed_speed, _ = speed_for(seed_leg, origin, policy, states.get((trajectory, policy['seed_station_id'])))
        seed_travel = elapsed_seconds(seed_leg['distance_m'], seed_speed)
        merge_target = origin + timedelta(seconds=seed_travel) if seed_travel is not None else None
        for segment in segments:
            sid = segment['segment_id']; previous = segment['input_node_ids'][0]
            prior_state = states.get((trajectory, previous)) if segment['sequence'] > 1 else None
            row = {'trajectory_id': trajectory, 'forecast_origin_at': origin.isoformat(), **segment,
                   'input_discharge_m3_s': prior_state.get('discharge_m3_s') if prior_state else None,
                   'input_variable_depth_m': prior_state.get('variable_depth_m') if prior_state else None,
                   'input_velocity_m_s': prior_state.get('velocity_m_s') if prior_state else None,
                   'input_state_status': 'station_inputs' if segment['sequence'] == 1 else 'model_prediction' if prior_state else 'awaiting_upstream_submodel',
                   'input_state_model_version': prior_state.get('model_version') if prior_state else None,
                   'input_state_training_end_at': prior_state.get('training_data_end_at') if prior_state else None,
                   'output_discharge_m3_s': None, 'output_variable_depth_m': None, 'output_velocity_m_s': None,
                   'prediction_status': 'not_computed_by_ETL'}
            own_state = states.get((trajectory, segment['output_node_id']))
            if own_state:
                for field in ['discharge_m3_s', 'variable_depth_m', 'velocity_m_s']:
                    row['output_' + field] = own_state.get(field)
                row['prediction_status'] = 'supplied_submodel_output_not_computed_by_ETL'
            features_known = True; station_times = []; arrivals = []
            for leg in [l for l in legs if l['segment_id'] == sid]:
                if segment['sequence'] == 1:
                    source_state = states.get((trajectory, leg['source_node_id']))
                    speed, basis = speed_for(leg, origin, policy, source_state)
                    leg_travel = elapsed_seconds(leg['distance_m'], speed)
                    required_departure = merge_target - timedelta(seconds=leg_travel) if merge_target and leg_travel is not None else origin
                    observation, age, status = indexes[leg['source_node_id']].previous(min(origin, required_departure), policy['source_max_age_seconds'])
                    if required_departure > origin:
                        status = 'future_input_required_not_used'
                    prefix = 'input_' + leg['source_node_id'] + '_'
                    for field in ['observed_at', 'received_at', 'discharge_m3_s', 'experimental_variable_depth_m', 'source_path', 'level_quality', 'discharge_quality']:
                        row[prefix + field] = observation.get(field) if observation else None
                        if status != 'usable' and field in {'discharge_m3_s', 'experimental_variable_depth_m'}:
                            row[prefix + field] = None
                    row[prefix + 'required_departure_at'] = required_departure.isoformat() if merge_target else None
                    row[prefix + 'age_seconds'] = age; row[prefix + 'status'] = status
                    known = bool(observation and observation.get('received_at') and parse_time(observation['received_at']) <= origin)
                    features_known = features_known and known
                    row[prefix + 'known_at_forecast_origin'] = known
                    departure = parse_time(observation['observed_at']) if observation and status == 'usable' else None
                    if observation and status == 'usable':
                        station_times.append(observation['observed_at'])
                    row[prefix + 'velocity_m_s'] = speed
                    row[prefix + 'velocity_basis'] = basis
                    row[prefix + 'distance_to_P01_m'] = leg['distance_m']
                else:
                    departure = endpoint
                    speed, basis = speed_for(leg, departure, policy, prior_state)
                travel = elapsed_seconds(leg['distance_m'], speed)
                arrival = departure + timedelta(seconds=travel) if departure is not None and travel is not None else None
                arrival_legs.append({'trajectory_id': trajectory, **leg,
                                     'departure_at': departure.isoformat() if departure else None,
                                     'velocity_m_s': speed, 'velocity_basis': basis, 'travel_seconds': travel,
                                     'arrival_at': arrival.isoformat() if arrival else None,
                                     'status': 'estimated_L_over_V' if arrival else 'missing_departure_or_velocity'})
                arrivals.append(arrival)
            all_arrivals = all(a is not None for a in arrivals)
            spread = (max(arrivals) - min(arrivals)).total_seconds() if all_arrivals else None
            endpoint = max(arrivals) if all_arrivals else None
            if segment['sequence'] == 1 and (spread is None or spread > policy['merge_arrival_tolerance_seconds']):
                cumulative_valid = False
            row['estimated_arrival_at'] = endpoint.isoformat() if endpoint else None
            row['arrival_status'] = 'estimated' if endpoint and cumulative_valid else 'unaligned_initial_arrivals' if endpoint else 'awaiting_velocity_or_upstream_arrival'
            row['initial_arrival_spread_seconds'] = spread if segment['sequence'] == 1 else None
            row['source_time_spread_seconds'] = (max(map(parse_time, station_times)) - min(map(parse_time, station_times))).total_seconds() if station_times else None
            row['historical_replay_eligible'] = features_known if segment['sequence'] == 1 else False
            section = profiles.get(row['section_id'], {})
            for field in ['min_bed_elevation_m', 'profile_points', 'profile_status', 'vertical_datum']:
                row['section_' + field] = section.get(field)
            row['sylvan_lake_level_m'] = None; row['sylvan_lake_observed_at'] = None
            row['sylvan_lake_received_at'] = None; row['sylvan_lake_age_seconds'] = None
            row['sylvan_lake_feature_status'] = 'not_used_in_this_segment'
            row['sylvan_lake_source_path'] = None
            if segment['lake_feature_station_id']:
                obs, age, status = lake.previous(origin, policy['lake_max_age_seconds'])
                row['sylvan_lake_level_m'] = obs.get('level_m') if obs and status == 'usable' else None
                row['sylvan_lake_observed_at'] = obs.get('observed_at') if obs else None
                row['sylvan_lake_received_at'] = obs.get('received_at') if obs else None
                row['sylvan_lake_source_path'] = obs.get('source_path') if obs else None
                row['sylvan_lake_age_seconds'] = age; row['sylvan_lake_feature_status'] = status
            context = station_windows.get((policy['seed_station_id'], origin.isoformat()), {})
            row['origin_weather_station_id'] = context.get('weather_station_id')
            row['origin_precipitation_total_mm'] = context.get('precipitation_total_mm')
            row['origin_mean_intensity_mm_h'] = context.get('mean_precipitation_intensity_mm_h')
            row['origin_precipitation_coverage'] = context.get('coverage_fraction')
            row['weather_context_role'] = 'origin_weather_only_not_future_segment_rainfall'
            trajectory_rows.append(row)
        candidate, offset, status = indexes[policy['validation_station_id']].nearest(endpoint, policy['target_match_tolerance_seconds'])
        accepted = status == 'matched' and cumulative_valid
        for row in trajectory_rows:
            row.update({'label_node_id': policy['validation_station_id'],
                        'label_scope': 'chain_endpoint_only_not_intermediate_truth',
                        'label_expected_arrival_at': endpoint.isoformat() if endpoint else None,
                        'label_candidate_observed_at': candidate['observed_at'] if candidate else None,
                        'label_time_offset_seconds': offset,
                        'label_match_status': status if cumulative_valid or endpoint is None else 'initial_arrivals_not_aligned',
                        'label_discharge_m3_s': candidate['discharge_m3_s'] if accepted else None,
                        'label_variable_depth_m': candidate['experimental_variable_depth_m'] if accepted else None,
                        'label_received_at': candidate.get('received_at') if candidate else None,
                        'label_source_path': candidate.get('source_path') if candidate else None,
                        'label_level_quality': candidate.get('level_quality') if candidate else None,
                        'label_discharge_quality': candidate.get('discharge_quality') if candidate else None})
        master.extend(trajectory_rows)
    if not master:
        raise ValueError('No instantaneous seed observations for segment trajectories')
    assert len({(r['trajectory_id'], r['segment_id']) for r in master}) == len(master)
    assert all(r['sylvan_lake_level_m'] is None for r in master if r['output_node_id'] != policy['lake_target_id'])
    summary = {'trajectory_count': len(origins), 'segment_count': len(segments),
               'arrival_status': dict(Counter(r['arrival_status'] for r in master)),
               'endpoint_label_status': dict(Counter(r['label_match_status'] for r in master if r['output_node_id'] == policy['validation_station_id'])),
               'policy': policy, 'state_rows_loaded': len(states),
               'timing_note': 'L/V is preliminary. Labels match downstream observation time, not receipt time. No same-time fallback.',
               'lake_note': 'Lake elevation is an ML feature only in P03 to P04, never converted to outlet discharge.'}
    return {'model_segments': segments, 'model_segment_legs': legs,
            'segment_training': master, 'segment_arrivals': arrival_legs}, summary


def feature_contract(tables):
    """Whitelist predictor columns; endpoint labels and own predictions are excluded."""
    result = {}
    for segment in tables['model_segments']:
        features = ['section_min_bed_elevation_m', 'section_profile_points',
                    'origin_precipitation_total_mm', 'origin_mean_intensity_mm_h',
                    'origin_precipitation_coverage']
        if segment['sequence'] == 1:
            for node in segment['input_node_ids']:
                features += ['input_' + node + '_' + field for field in
                             ['discharge_m3_s', 'experimental_variable_depth_m', 'age_seconds', 'distance_to_P01_m']]
        else:
            features += ['input_discharge_m3_s', 'input_variable_depth_m', 'input_velocity_m_s', 'distance_m']
        if segment['lake_feature_station_id']:
            features += ['sylvan_lake_level_m', 'sylvan_lake_age_seconds']
        result[segment['segment_id']] = {'features': features,
                                         'profile_join': 'section_id -> section_profile_points',
                                         'joint_endpoint_labels': ['label_discharge_m3_s', 'label_variable_depth_m'],
                                         'intermediate_observed_labels_available': False,
                                         'exclude_from_predictors': ['label_*', 'output_*', 'prediction_status', 'label_candidate_observed_at']}
    return result


def postgres_export(folder, tables):
    """Create a transactional, immutable snapshot schema; never overwrite other schemas."""
    content = json.dumps(tables, sort_keys=True, ensure_ascii=False, allow_nan=False)
    schema = 'rdr_segments_' + hashlib.sha256(content.encode('utf-8')).hexdigest()[:12]
    def literal(value):
        if value is None:
            return 'NULL'
        if isinstance(value, bool):
            return 'TRUE' if value else 'FALSE'
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, (dict, list)):
            value = json.dumps(value, ensure_ascii=False, allow_nan=False)
        return "'" + str(value).replace("'", "''") + "'"
    with (folder / 'segments_postgresql.sql').open('w', encoding='utf-8') as f:
        f.write('BEGIN;\nSET standard_conforming_strings = on;\nCREATE SCHEMA "' + schema + '";\n')
        for name, rows in tables.items():
            fields = list(dict.fromkeys(k for r in rows for k in r))
            cols = []
            for key in fields:
                values = [r[key] for r in rows if r.get(key) is not None]
                typ = 'BOOLEAN' if values and all(isinstance(v, bool) for v in values) else 'DOUBLE PRECISION' if values and all(isinstance(v, (int, float)) for v in values) else 'TIMESTAMPTZ' if key.endswith('_at') else 'TEXT'
                # All-null numeric prediction slots must still have numeric database types.
                if not values and key.endswith(('_m', '_m_s', '_m3_s', '_seconds', '_mm', '_mm_h')):
                    typ = 'DOUBLE PRECISION'
                cols.append('"' + key + '" ' + typ)
            primary = ['segment_id'] if name == 'model_segments' else ['leg_id'] if name == 'model_segment_legs' else ['trajectory_id', 'segment_id'] if name == 'segment_training' else ['trajectory_id', 'leg_id']
            cols.append('PRIMARY KEY (' + ','.join('"' + k + '"' for k in primary) + ')')
            if name in {'model_segment_legs', 'segment_training'}:
                cols.append(f'FOREIGN KEY ("segment_id") REFERENCES "{schema}"."model_segments" ("segment_id")')
            if name == 'segment_arrivals':
                cols.append(f'FOREIGN KEY ("leg_id") REFERENCES "{schema}"."model_segment_legs" ("leg_id")')
            f.write(f'CREATE TABLE "{schema}"."{name}" (' + ','.join(cols) + ');\n')
            for start in range(0, len(rows), 200):
                f.write(f'INSERT INTO "{schema}"."{name}" VALUES\n')
                f.write(',\n'.join('(' + ','.join(literal(r.get(k)) for k in fields) + ')' for r in rows[start:start+200]) + ';\n')
        f.write('COMMIT;\n')
    return schema
