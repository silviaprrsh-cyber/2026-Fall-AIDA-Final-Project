"""Train-only route calibration, then frozen-route endpoint neural experiment.

This is an offline retrospective experiment. No database/network calls are made.
Old checkpoints supply static geometry buffers only, never learned weights.
"""
import argparse
import copy
import csv
import itertools
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch

from project_paths import WORKSPACE
from .neural import WeatherChain, error_metrics
from .route_neural import align, digest, fractions, predict, SOURCES
from .train_neural import write
from .weather import Weather

DATA = WORKSPACE / 'courses/AIDA-2156/data'
DEFAULT_CACHE = DATA / 'processed/segment_nn_weather_route_bounded_60_20_20_grid'
GRID = (.25, .5, .75)


def timestamp(value):
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('Explicit timezone required')
    return dt.timestamp()


def iso(value):
    return datetime.fromtimestamp(float(value), timezone.utc).isoformat()


def past_index(times, origins):
    return np.searchsorted(times, origins, side='right') - 1


def audit_context(seeds, policy):
    """Recheck cached weather and lake values against immutable local sources."""
    weather = Weather(policy['weather_manifest'])
    lake_file = DATA / 'processed/model_unit_history/20261103T070414Z/05CC003_observations.csv'
    with lake_file.open(encoding='utf-8-sig', newline='') as handle:
        rows = [(timestamp(r['observed_at']), float(r['level_m']))
                for r in csv.DictReader(handle) if r['level_m'] and float(r['level_m']) > 0]
    lake = np.asarray(sorted(rows))
    indices = past_index(lake[:, 0], seeds[:, 0])
    if np.any(indices < 0):
        raise ValueError('Missing historical lake value')
    chosen = lake[indices]
    ages = seeds[:, 0] - chosen[:, 0]
    if np.any(ages < 0) or np.any(ages > policy['lake_max_age_seconds']):
        raise ValueError('Lake feature is future or stale')
    if not np.allclose(chosen[:, 1], seeds[:, 5], rtol=0, atol=1e-9):
        raise ValueError('Cached lake value does not reproduce from local observations')
    latest = []
    for row in seeds:
        _, detail = weather.at(datetime.fromtimestamp(row[0], timezone.utc))
        wf = detail['features']
        expected = [np.log1p(wf['precipitation_1h_mm']), np.log1p(wf['precipitation_6h_mm']),
                    np.log1p(wf['precipitation_24h_mm']), wf['temperature_c']]
        if not np.allclose(row[1:5], expected, rtol=0, atol=1e-9):
            raise ValueError('Cached weather features do not reproduce')
        at = timestamp(detail['latest_source_observed_at'])
        if at > row[0]:
            raise ValueError('Future weather input')
        latest.append(at)
    return {'checked_origins': len(seeds), 'lake_sha256': digest(lake_file),
            'weather_manifest_sha256': weather.sha256, 'future_lake_or_weather_inputs': 0,
            'max_lake_age_seconds': float(ages.max()),
            'publication_time_availability_verified': False}


def align_period(arrays, seeds, logits, lower, upper):
    """History before lower is allowed; sources after origin and labels outside are not."""
    if len(seeds) == 0:
        raise ValueError('Empty period')
    local = dict(arrays)
    local['boundaries'] = np.array([arrays['boundaries'][0], upper])
    result = align(local, seeds, logits, 0)
    mask = ((seeds[:, 0] >= lower) & (seeds[:, 0] < upper) &
            (result['label_times'] >= lower) & (result['label_times'] < upper) &
            (result['label_times'] >= seeds[:, 0]))
    result['valid'] &= mask
    result['invalid_reasons']['period_origin_or_target_boundary'] = int((~mask).sum())
    result['origins'] = seeds[:, 0].copy()
    v = result['valid']
    if np.any(result['source_rows'][v, :, 0] > seeds[v, 0, None]):
        raise AssertionError('Future hydrometric source')
    if np.any(result['speeds'][v] > result['source_rows'][v, :, 3] * (1 + 1e-12)):
        raise AssertionError('Route speed exceeds experimental cap')
    return result


def proxy_features(aligned):
    return np.column_stack([aligned['initial'][:, :3], aligned['context']])


def ridge_fit(x, y):
    center = x.mean(0)
    scale = np.maximum(x.std(0), 1e-3)
    design = np.column_stack([np.ones(len(x)), np.clip((x-center)/scale, -8, 8)])
    penalty = np.eye(design.shape[1]); penalty[0, 0] = 0
    coef = np.linalg.solve(design.T @ design + penalty, design.T @ y)
    return center, scale, coef


def ridge_predict(x, fit):
    center, scale, coef = fit
    return np.column_stack([np.ones(len(x)), np.clip((x-center)/scale, -8, 8)]) @ coef


def coverage_objective(predicted, labels, valid, scale):
    """Fixed population: invalid costs 1; bounded valid squared error costs [0,1)."""
    losses = np.ones(len(valid), dtype=float)
    e = np.mean(((predicted[valid] - labels[valid])/scale)**2, axis=1)
    losses[valid] = e/(1+e)
    return float(losses.mean())


def calibrate_routes(arrays, train_seeds, train_start, train_end):
    """Select route with an inner chronological holdout, entirely inside training.

    A lightweight ridge proxy ranks routes. It is not a physical-speed estimator,
    and its bounded-error plus missingness objective must be reported explicitly.
    No validation/test inputs or labels are needed by this function.
    """
    if len(train_seeds) < 100:
        raise ValueError('Insufficient training origins for inner split')
    cut = float(train_seeds[int(.75*len(train_seeds)), 0])
    fit_seeds = train_seeds[train_seeds[:, 0] < cut]
    hold_seeds = train_seeds[train_seeds[:, 0] >= cut]
    # Physically remove future records, not merely rely on masks.
    restricted = dict(arrays)
    for k in range(3):
        src = arrays['source'+str(k)]
        restricted['source'+str(k)] = src[src[:, 0] < train_end]
    ep = (arrays['endpoint_times'] >= train_start) & (arrays['endpoint_times'] < cut)
    scale = np.maximum(arrays['endpoint_values'][ep].std(0), [1., .1])
    selected_ep = arrays['endpoint_times'] < train_end
    restricted['endpoint_times'] = arrays['endpoint_times'][selected_ep]
    restricted['endpoint_values'] = arrays['endpoint_values'][selected_ep]
    candidates = []
    for candidate in itertools.product(GRID, repeat=3):
        f = np.asarray(candidate); logits = np.log(f/(1-f))
        fit = align_period(restricted, fit_seeds, logits, train_start, cut)
        hold = align_period(restricted, hold_seeds, logits, cut, train_end)
        nfit, nhold = int(fit['valid'].sum()), int(hold['valid'].sum())
        row = {'fractions': list(candidate), 'fit_matched': nfit,
               'holdout_candidates': len(hold_seeds), 'holdout_matched': nhold,
               'holdout_coverage': nhold/len(hold_seeds), 'eligible': min(nfit, nhold) >= 30}
        if row['eligible']:
            reg = ridge_fit(proxy_features(fit)[fit['valid']], fit['labels'][fit['valid']])
            prediction = ridge_predict(proxy_features(hold), reg)
            row['objective'] = coverage_objective(prediction, hold['labels'], hold['valid'], scale)
            row['proxy_metrics'] = error_metrics(prediction, hold['labels'], hold['valid'])
        candidates.append(row)
    usable = [r for r in candidates if r['eligible']]
    if not usable:
        raise ValueError('No route has sufficient inner fit and holdout pairs')
    winner = min(usable, key=lambda r: (r['objective'], -r['holdout_matched'], r['fractions']))
    f = np.asarray(winner['fractions']); logits = np.log(f/(1-f))
    return logits, {'method': 'training_only_chronological_ridge_proxy',
        'inner_boundary_utc': iso(cut), 'training_end_exclusive_utc': iso(train_end),
        'fit_candidates': len(fit_seeds), 'holdout_candidates': len(hold_seeds),
        'objective': 'mean(valid: normalized_MSE/(1+normalized_MSE), invalid: 1); fixed denominator',
        'scale_from_inner_fit_labels': scale.tolist(), 'ridge_penalty': 1.,
        'selected': winner, 'candidates': candidates,
        'route_frozen_before_validation_and_test': True}


def fit_network(model, train, validation, scales, epochs, patience):
    rng = np.random.default_rng(42)
    optimizer = torch.optim.Adam(model.parameters(), lr=.001, weight_decay=1e-4)
    ids = np.flatnonzero(train['valid'])
    def objective():
        predictions = predict(model, validation)[:, -1, :2]
        v = validation['valid']
        return float(np.mean(((predictions[v]-validation['labels'][v])/scales)**2))
    best = objective(); chosen = 0; selected = copy.deepcopy(model.state_dict())
    history = [{'epoch': 0, 'validation_objective': best}]; stale = 0
    for epoch in range(1, epochs+1):
        model.train(); order = rng.permutation(ids); total = 0.
        for start in range(0, len(order), 512):
            ix = order[start:start+512]
            states, delta = model(torch.tensor(train['initial'][ix], dtype=torch.float32),
                                  torch.tensor(train['context'][ix], dtype=torch.float32))
            labels = torch.tensor(train['labels'][ix], dtype=torch.float32)
            loss = ((states[:, -1, :2]-labels)/torch.tensor(scales, dtype=torch.float32)).square().mean()+.001*delta.square().mean()
            optimizer.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.); optimizer.step()
            total += float(loss.detach())*len(ix)
        val = objective(); history.append({'epoch': epoch, 'training_objective': total/len(ids), 'validation_objective': val})
        if val < best-1e-7:
            best = val; chosen = epoch; selected = copy.deepcopy(model.state_dict()); stale = 0
        else:
            stale += 1
        if epoch == 1 or epoch % 5 == 0:
            print('Epoch', epoch, 'selected', chosen, 'validation', val, flush=True)
        if stale >= patience:
            break
    model.load_state_dict(selected); model.eval()
    return history, chosen


def population_summary(aligned):
    v = aligned['valid']; labels = aligned['labels'][v]
    return {'candidates': len(v), 'matched': int(v.sum()), 'coverage': float(v.mean()),
            'origin_days': int(len(np.unique(np.floor(aligned['origins'][v]/86400)))),
            'unique_target_times': int(len(np.unique(aligned['label_times'][v]))),
            'Q_range_m3_s': [float(labels[:, 0].min()), float(labels[:, 0].max())] if len(labels) else None,
            'Q_ge_100': int((labels[:, 0] >= 100).sum()), 'Q_ge_200': int((labels[:, 0] >= 200).sum()),
            'invalid_reasons_nonexclusive': aligned['invalid_reasons']}


def reported_metrics(predictions, labels, valid):
    if len(valid):
        return error_metrics(predictions, labels, valid)
    return {'origins':0,'matched':0,'coverage':None,
            'discharge':{'bias':None,'mae':None,'rmse':None},
            'variable_depth':{'bias':None,'mae':None,'rmse':None}}


def metrics_with_baselines(arrays, aligned, states):
    v = aligned['valid']; pred = states[:, -1, :2]
    j = past_index(arrays['endpoint_times'], aligned['origins'])
    safe = v & (j >= 0)
    clipped = np.maximum(j, 0)
    age = aligned['origins']-arrays['endpoint_times'][clipped]
    safe &= age <= 3600
    persistence = arrays['endpoint_values'][clipped]
    result = {'population': population_summary(aligned), 'model': error_metrics(pred, aligned['labels'], v),
              'persistence_comparison': {'role': 'extra endpoint-current input not used by network',
                  'max_observation_age_seconds': 3600, 'common_matched': int(safe.sum()),
                  'model_same_rows': error_metrics(pred, aligned['labels'], safe),
                  'persistence_same_rows': error_metrics(persistence, aligned['labels'], safe)}, 'subsets': {}}
    for name, subset in [('high_flow_ge100', aligned['labels'][:, 0] >= 100),
                         ('high_flow_ge200', aligned['labels'][:, 0] >= 200),
                         ('early_june', (aligned['label_times'] >= timestamp('2026-05-30T00:00:00Z')) & (aligned['label_times'] < timestamp('2026-06-15T00:00:00Z'))),
                         ('late_june_july_event', (aligned['label_times'] >= timestamp('2026-06-24T00:00:00Z')) & (aligned['label_times'] < timestamp('2026-07-11T00:00:00Z'))),
                         ('june_july', (aligned['label_times'] >= timestamp('2026-06-01T00:00:00Z')) & (aligned['label_times'] < timestamp('2026-08-01T00:00:00Z'))),
                         ('august_onward', aligned['label_times'] >= timestamp('2026-08-01T00:00:00Z'))]:
        result['subsets'][name] = {'candidate_count': int(subset.sum()),
            'scope': 'aligned target-time or target-value subset; availability conditional, not an independently fixed event population',
            'model': reported_metrics(pred[subset], aligned['labels'][subset], v[subset]),
            'persistence_common': reported_metrics(persistence[subset], aligned['labels'][subset], safe[subset]),
            'model_on_persistence_rows': reported_metrics(pred[subset], aligned['labels'][subset], safe[subset])}
    return result


def fresh_network(geometry, center, scale):
    """Only immutable geometric buffers are reused; learned layers are ignored."""
    return WeatherChain(geometry['depths'], geometry['areas'], geometry['distances'], center, scale)


def protected_inventory():
    files = [p for directory in (DATA/'processed').glob('segment_*') if directory.is_dir()
             for p in directory.rglob('*') if p.is_file()]
    files += [p for p in (DATA/'reports').glob('segment_*') if p.is_file()]
    return {str(p.relative_to(WORKSPACE)): digest(p) for p in files}


def load_frozen(folder):
    folder = Path(folder)
    report = json.loads((folder/'training_report.json').read_text())
    if report['model_type'] != 'six_segment_train_only_frozen_route':
        raise ValueError('Unsupported model type')
    if digest(folder/'model.pt') != report['saved_model_sha256']:
        raise ValueError('Model checksum mismatch')
    checkpoint = torch.load(folder/'model.pt', map_location='cpu', weights_only=True)
    w = checkpoint['network']
    model = WeatherChain(w['depths'], w['areas'], w['distances'], w['center'], w['scale'])
    model.load_state_dict(w); model.eval()
    return model, checkpoint['route_logits'].numpy(), report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, default=DEFAULT_CACHE)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--train-end', default='2026-04-01T00:00:00Z')
    parser.add_argument('--validation-end', default='2026-06-01T00:00:00Z')
    parser.add_argument('--epochs', type=int, default=100)
    parser.add_argument('--patience', type=int, default=20)
    parser.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args()
    if min(args.epochs, args.patience) < 1:
        raise ValueError('Positive finite training bounds required')
    cache, folder = args.cache.resolve(), args.output.resolve()
    if not cache.is_relative_to((DATA/'processed').resolve()) or not folder.is_relative_to((DATA/'processed').resolve()):
        raise ValueError('Cache and output must be within local processed directory')
    if folder.exists():
        raise ValueError('Output already exists; never overwrite any experiment')
    manifest = json.loads((cache/'route_inputs.json').read_text())
    if digest(cache/'route_inputs.npz') != manifest['cache_sha256']:
        raise ValueError('Input cache checksum mismatch')
    previous = json.loads((cache/'training_report.json').read_text())
    if digest(cache/'model.pt') != previous['saved_model_sha256']:
        raise ValueError('Geometry checkpoint checksum mismatch')
    arrays = dict(np.load(cache/'route_inputs.npz', allow_pickle=False))
    seeds = np.concatenate([arrays[n] for n in ['train', 'validation', 'test']])
    seeds = seeds[np.argsort(seeds[:, 0])]
    if np.any(np.diff(seeds[:, 0]) <= 0):
        raise ValueError('Duplicate or unsorted origins')
    bounds = [float(arrays['boundaries'][0]), timestamp(args.train_end), timestamp(args.validation_end), float(arrays['boundaries'][-1])]
    if not np.all(np.diff(bounds) > 0):
        raise ValueError('Invalid chronological boundaries')
    policy = json.loads((WORKSPACE/'shared-resources/config/segment_ml_weather.json').read_text())
    provenance = audit_context(seeds, policy)
    if provenance['weather_manifest_sha256'] != manifest['weather_manifest_sha256']:
        raise ValueError('Weather manifest differs from frozen cache')
    partitions = {n: seeds[(seeds[:, 0] >= bounds[i]) & (seeds[:, 0] < bounds[i+1])] for i,n in enumerate(['train','validation','test'])}
    protected = protected_inventory()
    logits, calibration = calibrate_routes(arrays, partitions['train'], bounds[0], bounds[1])
    aligned = {n: align_period(arrays, partitions[n], logits, bounds[i], bounds[i+1]) for i,n in enumerate(partitions)}
    for name, al in aligned.items():
        if al['valid'].sum() < 30:
            raise ValueError('Insufficient frozen-route matched samples: '+name)
    folder.mkdir(exist_ok=False)
    write(folder/'route_calibration.json', calibration)
    write(folder/'input_audit.json', {'cache': str(cache.relative_to(WORKSPACE)), 'cache_sha256': manifest['cache_sha256'],
          'boundaries_utc': [iso(x) for x in bounds], 'context': provenance,
          'populations': {n: population_summary(al) for n,al in aligned.items()},
          'old_preparation_exclusions_not_recovered': True})
    write(folder/'previous_artifacts.json', protected)
    (folder/'training_source.py').write_text(Path(__file__).read_text(encoding='utf-8-sig'), encoding='utf-8')
    write(folder/'implementation_manifest.json', {str(f.relative_to(WORKSPACE)): digest(f)
          for f in [Path(__file__), Path(__file__).with_name('route_neural.py'),
                    Path(__file__).with_name('neural.py'), Path(__file__).with_name('weather.py')]})
    print('Frozen route', dict(zip(SOURCES, fractions(logits))), flush=True)
    print('Populations', {n:population_summary(v) for n,v in aligned.items()}, flush=True)
    if args.prepare_only:
        return
    torch.set_num_threads(2); torch.manual_seed(42); torch.use_deterministic_algorithms(True)
    geometry = torch.load(cache/'model.pt', map_location='cpu', weights_only=True)['network']
    train = aligned['train']; valid = train['valid']
    center = train['context'][valid].mean(0); scale = np.maximum(train['context'][valid].std(0), 1e-3)
    # Read static geometry only; all network layers are newly initialized.
    model = fresh_network(geometry, center, scale)
    scales = np.maximum(train['labels'][valid].std(0), [1., .1])
    history, chosen = fit_network(model, train, aligned['validation'], scales, args.epochs, args.patience)
    torch.save({'network': model.state_dict(), 'route_logits': torch.tensor(logits)}, folder/'model.pt')
    results = {}; predictions = {}
    for name, al in aligned.items():
        states = predict(model, al); predictions[name] = states
        results[name] = metrics_with_baselines(arrays, al, states)
    # Original saved checkpoint is historical, including exposure to this new test.
    old_model = WeatherChain(geometry['depths'], geometry['areas'], geometry['distances'], geometry['center'], geometry['scale'])
    old_model.load_state_dict(geometry); old_model.eval()
    old_logits = np.log(np.array([previous['route_fractions'][sid] for sid in SOURCES])/(1-np.array([previous['route_fractions'][sid] for sid in SOURCES])))
    old_al = align_period(arrays, partitions['test'], old_logits, bounds[2], bounds[3])
    old_states = predict(old_model, old_al)
    new_al = aligned['test']; common = new_al['valid'] & old_al['valid']
    exact = common & (new_al['label_times'] == old_al['label_times'])
    comparison = {'historical_checkpoint_exposed_to_new_test_period': True,
        'common_origins': int(common.sum()), 'common_origins_identical_target_time': int(exact.sum()),
        'only_identical_target_metrics_comparable': True,
        'new_same_target': error_metrics(predictions['test'][:,-1,:2], new_al['labels'], exact),
        'old_same_target': error_metrics(old_states[:,-1,:2], old_al['labels'], exact)}
    report = {'model_type':'six_segment_train_only_frozen_route', 'created_at':datetime.now(timezone.utc).isoformat(),
        'seed':42,'epochs_completed':len(history)-1,'selected_epoch':chosen,
        'route_fractions':dict(zip(SOURCES,fractions(logits).tolist())), 'route_calibration':calibration,
        'boundaries_utc':[iso(x) for x in bounds], 'metrics':results, 'historical_comparison':comparison,
        'history':history,'label_scales_training_only':scales.tolist(),
        'saved_model_sha256':digest(folder/'model.pt'),
        'limitations':['Retrospective reused data; not a fresh blind test.',
            'Ridge proxy selects routes inside training; not a validated physical-speed calibration.',
            'Gauge stage is not verified physical depth; intermediate targets lack independent labels.',
            'Cached weather/lake exclusions from original preparation were not reconstructed.',
            'Input observation-time causality is checked; historical publication-time availability is unknown.',
            'Missingness remains; coverage and event results must accompany errors.',
            'Historical checkpoint comparison is descriptive, not independent validation.']}
    preserved = all(digest(WORKSPACE/path) == value for path,value in protected.items())
    if not preserved:
        raise AssertionError('Protected old artifact changed')
    report['old_artifacts_unchanged'] = preserved
    write(folder/'training_report.json', report)
    restored, restored_logits, _ = load_frozen(folder)
    if not np.array_equal(restored_logits, logits):
        raise AssertionError('Frozen route changed on reload')
    sample = align_period(arrays, partitions['train'][:10], logits, bounds[0], bounds[1])
    if not np.array_equal(predict(model,sample),predict(restored,sample)):
        raise AssertionError('Reload predictions differ')
    np.savez_compressed(folder/'test_predictions.npz', origins=new_al['origins'],
        label_times=new_al['label_times'], labels=new_al['labels'], valid=new_al['valid'],
        states=predictions['test'], source_times=new_al['source_rows'][:,:,0],
        common_arrivals=new_al['common_arrivals'], route_speeds=new_al['speeds'])
    write(folder/'verification.json', {'model_reload_exact':True,'old_artifacts_unchanged':True,'protected_artifact_count':len(protected),
        'future_source_inputs':0,'context_rechecked':provenance,'train_only_calibration':True,
        'source_sha256':digest(Path(__file__))})
    print(json.dumps({'selected_epoch':chosen,'route_fractions':report['route_fractions'],
          'test':results['test']['model'],'comparison':comparison}),flush=True)


if __name__ == '__main__':
    main()
