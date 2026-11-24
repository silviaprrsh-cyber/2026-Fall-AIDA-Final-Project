"""Opt-in six-depth MLP preparation/training using PostgreSQL routing inputs only.

The default action is read-only database preflight, not model fitting. Run via
``python -B run.py -m rdr_ml.train_routing_depth --help`` from the project root.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from project_paths import WORKSPACE
from .neural import ROUTING_FEATURES, ROUTING_NODES, RoutingDepthChain


DATA = WORKSPACE / 'courses/AIDA-2156/data'
LABEL = 'label_endpoint_depth_proxy_m'
SPLITS = ('60_20_20', '80_20')
EVENT_THRESHOLD_Q = 100.0
EVENT_JOIN_SECONDS = 72 * 3600
EVENT_PAD_SECONDS = 72 * 3600
MIN_EMBARGO_SECONDS = 7 * 24 * 3600
# Reviewed v2 SQL: maximum Medicine delay 50h15m + 3h spread + <25h
# for hourly truncation and the complete rainfall window. This is a bound on
# feature provenance only, not proof of target-independent preprocessing.
ROUTING_V2_LOOKBACK_BOUND_SECONDS = (78 * 60 + 15) * 60
LIMITATIONS = [
    'Only 05CC002 proxy depth supervises the loss; P01-P05 have no independent labels.',
    'Proxy depth is experimental, not verified physical water depth or flood risk.',
    'Historical routing preprocessing uses terminal observations. Neither holdout '
    'nor validation is an independent prospective forecasting assessment.',
    'Newest observations train the model and older observations are held out. '
    'This is retrospective reverse-time evaluation, not forward forecasting.',
    'High-flow events use a fixed Q >= 100 m3/s definition, 72-hour merging and '
    '72-hour padding. Subthreshold or longer events can remain unidentified.',
    'Event protection and source-overlap embargo alter nominal split percentages.',
    'Terminal-Q event grouping is split design, not a learned predictor or loss target.',
]


def utc(value):
    """Reject ambiguous naive times rather than assuming local time."""
    if not isinstance(value, datetime):
        value = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError('Every timestamp must include an explicit UTC offset')
    return value.astimezone(timezone.utc)


def iso(seconds):
    return datetime.fromtimestamp(float(seconds), timezone.utc).isoformat()


def digest_arrays(*arrays):
    digest = hashlib.sha256()
    for array in arrays:
        value = np.ascontiguousarray(array, dtype='<f8')
        digest.update(str(value.shape).encode('ascii'))
        digest.update(value.tobytes())
    return digest.hexdigest()


def prepare_rows(rows):
    """Use exactly twelve source-only fields; never impute from a held-out row."""
    times, features, labels = [], [], []
    excluded = {'missing_or_nonfinite_feature': 0, 'negative_feature': 0,
                'missing_nonfinite_or_negative_depth_label': 0}
    previous = None
    for row in rows:
        stamp = utc(row['arrival_at']).timestamp()
        if previous is not None and stamp <= previous:
            raise ValueError('Routing arrivals must be unique and strictly increasing')
        previous = stamp
        try:
            x = np.asarray([row[name] for name in ROUTING_FEATURES], dtype=np.float64)
        except (KeyError, ValueError, TypeError) as exc:
            if isinstance(exc, KeyError):
                raise ValueError('Routing view is missing a required source feature') from exc
            excluded['missing_or_nonfinite_feature'] += 1
            continue
        if not np.isfinite(x).all():
            excluded['missing_or_nonfinite_feature'] += 1
            continue
        if (x < 0).any():
            excluded['negative_feature'] += 1
            continue
        try:
            y = float(row[LABEL])
        except (ValueError, TypeError):
            y = float('nan')
        if not np.isfinite(y) or y < 0:
            excluded['missing_nonfinite_or_negative_depth_label'] += 1
            continue
        times.append(stamp)
        features.append(x)
        labels.append(y)
    if not times:
        raise ValueError('No complete finite nonnegative PostgreSQL training rows')
    return (np.asarray(times, dtype=np.float64),
            np.asarray(features, dtype=np.float64),
            np.asarray(labels, dtype=np.float64),
            {'database_rows': len(rows), 'eligible_rows': len(times), 'excluded': excluded})


def protected_events(terminal_flows):
    """Group raw PostgreSQL terminal high flows, including model-ineligible rows."""
    observations = []
    previous = None
    for row in terminal_flows:
        stamp = utc(row['arrival_at']).timestamp()
        if previous is not None and stamp <= previous:
            raise ValueError('Terminal flow timestamps must be unique and increasing')
        previous = stamp
        try:
            q = float(row['q_m3_s'])
        except (TypeError, ValueError):
            continue
        if np.isfinite(q) and q >= 0:
            observations.append((stamp, q))
    if not observations:
        raise ValueError('No valid PostgreSQL terminal flows for event protection')
    high = [(stamp, q) for stamp, q in observations if q >= EVENT_THRESHOLD_Q]
    groups = []
    for stamp, q in high:
        if not groups or stamp - groups[-1]['last_high'] > EVENT_JOIN_SECONDS:
            groups.append({'first_high': stamp, 'last_high': stamp,
                           'peak_at': stamp, 'peak_q_m3_s': q, 'high_rows': 1})
        else:
            group = groups[-1]
            group['last_high'] = stamp
            group['high_rows'] += 1
            if q > group['peak_q_m3_s']:
                group['peak_at'], group['peak_q_m3_s'] = stamp, q
    events = []
    for group in groups:
        event = dict(group, start=group['first_high'] - EVENT_PAD_SECONDS,
                     end=group['last_high'] + EVENT_PAD_SECONDS)
        if events and event['start'] <= events[-1]['end']:
            prior = events[-1]
            prior['last_high'], prior['end'] = event['last_high'], event['end']
            prior['high_rows'] += event['high_rows']
            if event['peak_q_m3_s'] > prior['peak_q_m3_s']:
                prior['peak_at'], prior['peak_q_m3_s'] = event['peak_at'], event['peak_q_m3_s']
        else:
            events.append(event)
    return events, observations


def partitions(times, events, kind, embargo_seconds):
    """Freeze reverse-time partitions without cutting any protected event."""
    if kind not in SPLITS or len(times) < 150:
        raise ValueError('Supported splits need at least 150 eligible rows')
    if not np.isfinite(embargo_seconds) or embargo_seconds < MIN_EMBARGO_SECONDS:
        raise ValueError('Embargo must be finite and at least seven days')
    n = len(times)
    fractions = (.2, .4) if kind == '60_20_20' else (.2,)
    names = ('test', 'validation', 'train') if kind == '60_20_20' else ('test', 'train')
    safe = np.ones(n, dtype=bool)
    safe[0] = False
    for event in events:
        safe &= ~((times >= event['start']) & (times <= event['end']))
    candidates = np.flatnonzero(safe)
    boundaries, boundary_audit = [], []
    previous = 0
    for fraction in fractions:
        nominal = int(np.floor(n * fraction))
        available = candidates[(candidates > previous) & (candidates < n)]
        if not len(available):
            raise ValueError('No chronological split boundary outside protected events')
        # Stable argmin selects the earlier timestamp on an exact distance tie.
        chosen = int(available[np.argmin(np.abs(available - nominal))])
        boundaries.append(float(times[chosen]))
        boundary_audit.append({'nominal_older_rows_floor': nominal,
                               'event_adjusted_older_rows': chosen,
                               'arrival_at': iso(times[chosen])})
        previous = chosen
    assignment = np.searchsorted(boundaries, times, side='right')
    excluded = np.zeros(n, dtype=bool)
    for boundary in boundaries:
        excluded |= np.abs(times - boundary) <= embargo_seconds
    embargo_rows = int(excluded.sum())
    event_audit = []
    for event in events:
        inside = (times >= event['start']) & (times <= event['end'])
        hit_embargo = any(event['end'] >= cut - embargo_seconds and
                          event['start'] <= cut + embargo_seconds for cut in boundaries)
        if hit_embargo:
            excluded |= inside
        surviving = np.unique(assignment[inside & ~excluded])
        if len(surviving) > 1:
            raise AssertionError('Protected event crosses a partition')
        event_audit.append({
            'start_at': iso(event['start']), 'end_at': iso(event['end']),
            'first_high_at': iso(event['first_high']), 'last_high_at': iso(event['last_high']),
            'peak_at': iso(event['peak_at']), 'peak_q_m3_s': event['peak_q_m3_s'],
            'high_flow_observations': event['high_rows'],
            'eligible_model_rows': int(inside.sum()),
            'disposition': 'excluded_whole_event_by_embargo' if hit_embargo else
                           names[int(surviving[0])] if len(surviving) else 'no_eligible_rows',
            'range_edge_censored': bool(event['start'] < times[0] or event['end'] > times[-1]),
        })
    indices = {name: np.flatnonzero((assignment == j) & ~excluded)
               for j, name in enumerate(names)}
    if any(len(values) < 30 for values in indices.values()):
        raise ValueError('Fewer than 30 rows remain in a partition after event/embargo guards')
    retained = sum(len(values) for values in indices.values())
    counts = {}
    for j, name in enumerate(names):
        values = indices[name]
        counts[name] = {'before_embargo': int((assignment == j).sum()), 'rows': len(values),
                        'fraction_of_retained': len(values) / retained,
                        'fraction_of_eligible': len(values) / n,
                        'first_arrival_at': iso(times[values[0]]),
                        'last_arrival_at': iso(times[values[-1]])}
    report = {'requested': kind, 'direction': 'oldest_test_newest_train',
              'rounding': 'floor(N*0.2), and floor(N*0.4) for 60/20/20; nearest event-safe cut',
              'boundaries': boundary_audit, 'embargo_seconds_each_side': embargo_seconds,
              'direct_embargo_rows': embargo_rows,
              'additional_whole_event_exclusions': int(excluded.sum()) - embargo_rows,
              'excluded_rows': int(excluded.sum()), 'retained_rows': retained,
              'counts': counts, 'events': event_audit}
    return indices, report


def assert_peak_in_train(times, indices, report, observations):
    """Preserve the requested 2026 high-flow training exposure, when present."""
    current = [(stamp, q) for stamp, q in observations
               if datetime.fromtimestamp(stamp, timezone.utc).year == 2026
               and times[0] <= stamp <= times[-1]]
    if not current:
        report['peak_2026'] = {'status': 'not_in_requested_range'}
        return
    stamp, q = max(current, key=lambda item: item[1])
    train = indices['train']
    included = times[train[0]] <= stamp <= times[train[-1]]
    event = next((e for e in report['events'] if utc(e['start_at']).timestamp() <= stamp
                  <= utc(e['end_at']).timestamp()), None)
    if event is not None:
        included = included and event['disposition'] == 'train'
    report['peak_2026'] = {'arrival_at': iso(stamp), 'q_m3_s': q,
                           'in_training_period': bool(included),
                           'exact_arrival_has_eligible_model_row': bool(np.any(times[train] == stamp))}
    if not included:
        raise ValueError('The largest 2026 terminal flow is not in retained training; '
                         'review the requested range, not test metrics')


def prepare(config_path, start_at, end_at, split='both', embargo_seconds=MIN_EMBARGO_SECONDS):
    from rdr_eda.postgres import read_forward_routing_context, read_forward_routing_view
    if start_at >= end_at:
        raise ValueError('Expected a nonempty [start-at, end-at) range')
    context = read_forward_routing_context(config_path, start_at, end_at)
    rows = read_forward_routing_view(config_path, start_at, end_at)
    times, x, y, row_audit = prepare_rows(rows)
    events, observations = protected_events(context['terminal_flows'])
    lookback = context.get('max_source_lookback_seconds', ROUTING_V2_LOOKBACK_BOUND_SECONDS)
    if lookback is not None:
        lookback = float(lookback)
        if not np.isfinite(lookback) or lookback < 0:
            raise ValueError('Invalid source-overlap lookback from PostgreSQL')
        embargo_seconds = max(embargo_seconds, lookback)
    distances = np.asarray(context['distances_m'], dtype=np.float64)
    if distances.shape != (6,) or not np.isfinite(distances).all() or (distances < 0).any():
        raise ValueError('PostgreSQL must supply six finite nonnegative node distances')
    kinds = SPLITS if split == 'both' else (split,)
    splits, reports = {}, {}
    for kind in kinds:
        splits[kind], reports[kind] = partitions(times, events, kind, embargo_seconds)
        assert_peak_in_train(times, splits[kind], reports[kind], observations)
        train = splits[kind]['train']
        transformed = np.log1p(x[train])
        reports[kind]['training_only_normalization'] = {
            'transform': 'log1p', 'center': transformed.mean(axis=0).tolist(),
            'scale': np.maximum(transformed.std(axis=0), 1e-3).tolist(),
            'label_scale_m': max(float(y[train].std()), .1)}
    if len(kinds) == 2 and not np.array_equal(splits[SPLITS[0]]['test'], splits[SPLITS[1]]['test']):
        raise ValueError('The two protocols must share the same older test cohort')
    config = json.loads(Path(config_path).read_text(encoding='utf-8'))
    report = {
        'status': 'prepared_not_trained', 'created_at': datetime.now(timezone.utc).isoformat(),
        'source': 'postgresql_only', 'database': config['database'], 'schema': config['schema'],
        'dataset_id': config['dataset_id'], 'range_start_inclusive': start_at.isoformat(),
        'range_end_exclusive': end_at.isoformat(), 'input_features_order': list(ROUTING_FEATURES),
        'output_nodes_order': list(ROUTING_NODES), 'label': LABEL,
        'training_loss': 'MSE of 05CC002 proxy depth only, scaled using training labels only',
        'row_audit': row_audit, 'eligible_arrays_sha256': digest_arrays(times, x, y),
        'routing_sql_sha256': context['routing_sql_sha256'],
        'distances_m': distances.tolist(),
        'event_policy': {'terminal_q_threshold_m3_s': EVENT_THRESHOLD_Q,
                         'merge_gap_hours': 72, 'padding_hours': 72},
        'source_lookback_seconds': lookback,
        'source_lookback_basis': 'reviewed v2 SQL upper bound, not target-independence',
        'source_overlap_proof': 'guard covers reported source lookback' if lookback is not None else
                                'not proven: only a conservative seven-day minimum is available',
        'splits': reports, 'limitations': LIMITATIONS,
    }
    return {'times': times, 'features': x, 'labels': y, 'distances': distances,
            'splits': splits, 'report': report, 'protected_events': events}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n',
                    encoding='utf-8')


def save_preparation(folder, prepared):
    """Exclusive new directory: never replace an existing artifact or model."""
    folder = Path(folder).resolve()
    if not folder.is_relative_to((DATA / 'processed').resolve()):
        raise ValueError('Output must be a new directory under courses/AIDA-2156/data/processed')
    folder.mkdir(parents=True, exist_ok=False)
    arrays = {'arrival_timestamp_seconds': prepared['times'], 'features': prepared['features'],
              'label_endpoint_depth_proxy_m': prepared['labels'], 'distances_m': prepared['distances']}
    for kind, groups in prepared['splits'].items():
        for name, indices in groups.items():
            arrays[kind + '_' + name + '_indices'] = indices
    path = folder / 'prepared_inputs.npz'
    np.savez_compressed(path, **arrays)
    prepared['report']['prepared_inputs_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    write_json(folder / 'preflight.json', prepared['report'])
    return folder


def predict(model, features, batch_size=2048):
    model.eval()
    outputs = []
    with torch.no_grad():
        for start in range(0, len(features), batch_size):
            outputs.append(model(torch.as_tensor(features[start:start + batch_size],
                                                 dtype=torch.float32)).cpu().numpy())
    return np.concatenate(outputs, axis=0)


def metrics(predictions, labels):
    errors = predictions - labels
    if not np.isfinite(errors).all():
        raise ValueError('Nonfinite terminal predictions')
    return {'rows': len(labels), 'bias_m': float(errors.mean()),
            'mae_m': float(np.abs(errors).mean()), 'rmse_m': float(np.sqrt(np.mean(errors ** 2)))}


def fit(prepared, folder, epochs=100, patience=15, batch_size=512, seed=42, both_early_stop=False):
    """Explicit opt-in only. Never use test predictions to select weights/epochs."""
    if min(epochs, patience, batch_size) < 1:
        raise ValueError('Positive epochs, patience and batch size required')
    torch.set_num_threads(2)
    torch.use_deterministic_algorithms(True)
    x, y = prepared['features'], prepared['labels']
    training_reports = {}
    for kind, groups in prepared['splits'].items():
        torch.manual_seed(seed)
        rng = np.random.default_rng(seed)
        full_train = groups['train']
        train = full_train
        validation = groups.get('validation')
        inner_audit = None
        if both_early_stop and kind == '80_20':
            times = prepared['times']
            inner, inner_audit = partitions(times[full_train], prepared['protected_events'],
                                           '80_20', MIN_EMBARGO_SECONDS)
            train, validation = full_train[inner['train']], full_train[inner['test']]
            assert np.intersect1d(validation, groups['test']).size == 0
            assert np.intersect1d(train, validation).size == 0
            assert times[train[0]]-times[validation[-1]] > MIN_EMBARGO_SECONDS
            assert_peak_in_train(times, {'train': train}, inner_audit,
                                 [(utc(e['peak_at']).timestamp(), e['peak_q_m3_s'])
                                  for e in inner_audit['events']])
        transformed = np.log1p(x[train])
        center = transformed.mean(axis=0)
        scale = np.maximum(transformed.std(axis=0), 1e-3)
        label_scale = max(float(y[train].std()), .1)
        model = RoutingDepthChain(center, scale, prepared['distances'])
        optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=1e-4)
        history, best, selected, stale = [], float('inf'), None, 0
        selected_epoch = 0
        for epoch in range(1, epochs + 1):
            model.train()
            order, loss_sum = rng.permutation(train), 0.0
            for start in range(0, len(order), batch_size):
                indices = order[start:start + batch_size]
                prediction = model(torch.as_tensor(x[indices], dtype=torch.float32))[:, -1]
                target = torch.as_tensor(y[indices], dtype=torch.float32)
                loss = ((prediction - target) / label_scale).square().mean()
                if not torch.isfinite(loss):
                    raise ValueError('Nonfinite training loss; no model was saved')
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                optimizer.step()
                loss_sum += float(loss.detach()) * len(indices)
            record = {'epoch': epoch, 'train_scaled_mse': loss_sum / len(train)}
            if validation is not None:
                validation_pred = predict(model, x[validation])[:, -1]
                objective = float(np.mean(((validation_pred - y[validation]) / label_scale) ** 2))
                if not np.isfinite(objective):
                    raise ValueError('Nonfinite validation objective')
                record['validation_scaled_mse'] = objective
                if objective < best - 1e-7:
                    best, selected_epoch, stale = objective, epoch, 0
                    selected = copy.deepcopy(model.state_dict())
                else:
                    stale += 1
            else:
                selected_epoch = epoch
            history.append(record)
            if validation is not None and stale >= patience:
                break
        if selected is not None:
            model.load_state_dict(selected)
        refit_history = []
        if inner_audit is not None:
            # Internal validation determines epoch count only. Final fit uses the entire outer 80%.
            train = full_train
            transformed = np.log1p(x[train])
            center = transformed.mean(axis=0)
            scale = np.maximum(transformed.std(axis=0), 1e-3)
            label_scale = max(float(y[train].std()), .1)
            torch.manual_seed(seed)
            rng = np.random.default_rng(seed)
            model = RoutingDepthChain(center, scale, prepared['distances'])
            optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=1e-4)
            for ep in range(1, selected_epoch+1):
                model.train()
                order = rng.permutation(train)
                total = 0.0
                for start in range(0, len(order), batch_size):
                    ids = order[start:start+batch_size]
                    predicted = model(torch.as_tensor(x[ids], dtype=torch.float32))[:, -1]
                    target = torch.as_tensor(y[ids], dtype=torch.float32)
                    loss = ((predicted-target)/label_scale).square().mean()
                    if not torch.isfinite(loss):
                        raise ValueError('Nonfinite refit loss')
                    optimizer.zero_grad()
                    loss.backward()
                    torch.nn.utils.clip_grad_norm_(model.parameters(),5.0)
                    optimizer.step()
                    total += float(loss.detach())*len(ids)
                refit_history.append({'epoch':ep,'train_scaled_mse':total/len(train)})
            np.savez_compressed(folder/'internal_selection_80_20.npz',
                                fit_indices=full_train[inner['train']], validation_indices=validation)
        # First and only test evaluation occurs after all selection is complete.
        scores, predictions = {}, {}
        for name, indices in groups.items():
            outputs = predict(model, x[indices])
            scores[name] = metrics(outputs[:, -1], y[indices])
            predictions[name + '_depths_m'] = outputs
            predictions[name + '_indices'] = indices
        model_path = folder / ('model_' + kind + '.pt')
        torch.save(model.state_dict(), model_path)
        restored = RoutingDepthChain(center, scale, prepared['distances'])
        restored.load_state_dict(torch.load(model_path, map_location='cpu', weights_only=True))
        if not np.array_equal(predict(model, x[train[:10]]), predict(restored, x[train[:10]])):
            raise AssertionError('Saved model failed deterministic reload check')
        np.savez_compressed(folder / ('predictions_' + kind + '.npz'), **predictions)
        training_reports[kind] = {
            'selected_epoch': selected_epoch, 'epochs_completed': epoch,
            'epoch_selection': ('internal chronological validation then fresh full-80 refit'
                                if inner_audit is not None else 'designated validation split only'
                                if validation is not None else 'fixed preset epochs'),
            'internal_selection_partition': inner_audit, 'full_train_refit_history': refit_history,
            'maximum_epochs': epochs, 'patience': patience if validation is not None else None,
            'seed': seed, 'batch_size': batch_size, 'learning_rate': .001,
            'normalization': 'log1p features; center/std from this split training rows only',
            'center': center.tolist(), 'scale': scale.tolist(), 'label_scale': label_scale,
            'history': history, 'endpoint_metrics': scores,
            'intermediate_validation': 'P01-P05 are not independently labelled or validated',
            'model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
            'reload_check': 'bitwise_equal_on_10_training_rows',
        }
    write_json(folder / 'training_report.json', {
        'status': 'trained_explicit_opt_in', 'protocol': prepared['report'],
        'torch_version': str(torch.__version__), 'results': training_reports})
    return training_reports


def checks():
    """Synthetic forward/backward checks only; no optimizer, database or files."""
    torch.manual_seed(42)
    x = np.arange(1, 49, dtype=np.float64).reshape(4, 12) / 10
    model = RoutingDepthChain(np.zeros(12), np.ones(12), [0, 100, 200, 300, 400, 500])
    outputs = model(torch.as_tensor(x, dtype=torch.float32))
    assert outputs.shape == (4, 6) and torch.isfinite(outputs).all() and (outputs >= 0).all()
    outputs[:, -1].square().mean().backward()
    assert all(any(p.grad is not None and p.grad.abs().sum() > 0 for p in block.parameters())
               for block in model.blocks)
    times = utc('2024-01-01T00:00:00Z').timestamp() + np.arange(600) * 86400.0
    flows = [{'arrival_at': iso(t), 'q_m3_s': 150.0 if 115 <= i <= 125 else 20.0}
             for i, t in enumerate(times)]
    events, _ = protected_events(flows)
    a, ar = partitions(times, events, SPLITS[0], MIN_EMBARGO_SECONDS)
    b, _ = partitions(times, events, SPLITS[1], MIN_EMBARGO_SECONDS)
    assert np.array_equal(a['test'], b['test'])
    assert max(a['test']) < min(a['validation']) < max(a['validation']) < min(a['train'])
    assert set(a['train']).isdisjoint(a['test'])
    assert sum(len(v) for v in a.values()) + ar['excluded_rows'] == len(times)
    assert all(e['disposition'] != 'validation' for e in ar['events'])
    json.dumps(ar, allow_nan=False)
    print('Synthetic checks passed: six positive depth outputs, terminal gradients through all '
          'six MLPs, chronological splits, whole-event guard, embargo and shared test cohort.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checks-only', '--self-test', action='store_true', dest='checks_only')
    parser.add_argument('--config', type=Path, default=WORKSPACE / 'shared-resources/config/postgres_dataset.json')
    parser.add_argument('--start-at', help='Inclusive timezone-aware arrival timestamp')
    parser.add_argument('--end-at', help='Exclusive timezone-aware arrival timestamp')
    parser.add_argument('--split', choices=('both',) + SPLITS, default='both')
    parser.add_argument('--embargo-hours', type=float, default=168.0,
                        help='Per-side minimum, at least 168h; widened to the PG source lookback if available')
    parser.add_argument('--output', type=Path,
                        help='Optional NEW processed-data directory for immutable prepared arrays/protocol')
    parser.add_argument('--train', action='store_true', help='EXPLICIT opt-in to fitting; default is preflight only')
    parser.add_argument('--both-early-stop', action='store_true',
                        help='Use identical validation early stopping, with internal 80/20 validation and full-80 refit')
    parser.add_argument('--epochs', type=int, default=100, help='Maximum for 60/20/20; fixed preset for 80/20')
    parser.add_argument('--patience', type=int, default=15, help='60/20/20 validation only')
    parser.add_argument('--batch-size', type=int, default=512)
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    if args.checks_only:
        if args.train or args.output:
            parser.error('--checks-only cannot train or write output')
        checks()
        return
    if not args.start_at or not args.end_at:
        parser.error('PostgreSQL preflight requires explicit --start-at and --end-at')
    if args.train and not args.output:
        parser.error('--train requires a new --output directory')
    if args.output and args.output.exists():
        parser.error('--output already exists; use a new directory, never an existing model folder')
    if min(args.epochs, args.patience, args.batch_size) < 1:
        parser.error('Epochs, patience and batch size must be positive')
    prepared = prepare(args.config, utc(args.start_at), utc(args.end_at), args.split,
                       args.embargo_hours * 3600)
    prepared['report']['training_plan'] = {
        'epochs': args.epochs, 'patience_60_20_20': args.patience,
        'batch_size': args.batch_size, 'seed': args.seed,
        '80_20_selection': ('chronological internal validation, then full-80 refit using selected epoch'
                            if args.both_early_stop else 'fixed preset epochs, never select against test'),
        '60_20_20_selection': 'designated validation only',
    }
    folder = save_preparation(args.output, prepared) if args.output else None
    print(json.dumps(prepared['report'], ensure_ascii=False, indent=2, allow_nan=False), flush=True)
    if args.train:
        report = fit(prepared, folder, args.epochs, args.patience, args.batch_size, args.seed, args.both_early_stop)
        print(json.dumps({'status': 'trained', 'results': {
            name: {'selected_epoch': result['selected_epoch'], 'endpoint_metrics': result['endpoint_metrics']}
            for name, result in report.items()}}, indent=2, allow_nan=False), flush=True)


if __name__ == '__main__':
    main()
