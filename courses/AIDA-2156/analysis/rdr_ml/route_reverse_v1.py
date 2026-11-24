"""Original V1 architecture with later training and earlier held-out evaluation.

Reverse-time retrospective experiment, not prospective forecasting evidence.
Training route selection must retain the observed training-period flow peak.
"""
import argparse
import json
import itertools
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from project_paths import WORKSPACE
from .neural import WeatherChain, error_metrics
from .route_neural import align, digest, fractions, predict, SOURCES
from .route_frozen import (DATA, DEFAULT_CACHE, timestamp, iso, audit_context,
    ridge_fit, ridge_predict, proxy_features, coverage_objective, population_summary,
    fit_network, metrics_with_baselines, protected_inventory, write)

PERIODS = {
    'train': ('2026-06-01T00:00:00Z', None),
    'validation': ('2026-04-01T00:00:00Z', '2026-06-01T00:00:00Z'),
    'test': (None, '2026-04-01T00:00:00Z')}


def strict_align(arrays, seeds, logits, lower, upper):
    """All sources, trends, weather history, origins and labels stay in one period."""
    if not len(seeds): raise ValueError('Empty period')
    a=dict(arrays);a['boundaries']=np.array([lower,upper])
    result=align(a,seeds,logits,0)
    guard=(seeds[:,0]>=lower+25*3600)&(seeds[:,0]<upper)
    guard&=(result['label_times']>=lower)&(result['label_times']<upper)&(result['label_times']>=seeds[:,0])
    result['valid']&=guard
    result['invalid_reasons']['weather_history_or_period_guard']=int((~guard).sum())
    result['origins']=seeds[:,0].copy()
    v=result['valid'];src=result['source_rows'][v,:,0]
    if np.any(src<lower) or np.any(src>seeds[v,0,None]):raise AssertionError('Source time crosses period or is future')
    return result


def calibrate(arrays,seeds,lower,upper):
    cut=float(seeds[int(.75*len(seeds)),0])
    fit_seeds=seeds[seeds[:,0]<cut];hold_seeds=seeds[seeds[:,0]>=cut]
    local=dict(arrays)
    for k in range(3):
        src=arrays['source'+str(k)];local['source'+str(k)]=src[(src[:,0]>=lower)&(src[:,0]<upper)]
    em=(arrays['endpoint_times']>=lower)&(arrays['endpoint_times']<upper)
    local['endpoint_times']=arrays['endpoint_times'][em];local['endpoint_values']=arrays['endpoint_values'][em]
    scales=np.maximum(local['endpoint_values'][local['endpoint_times']<cut].std(0),[1.,.1])
    peak=float(local['endpoint_values'][:,0].max());rows=[]
    for combo in itertools.product([.25,.5,.75],repeat=3):
        f=np.asarray(combo);logits=np.log(f/(1-f))
        full=strict_align(local,seeds,logits,lower,upper)
        matched_peak=int((full['valid']&np.isclose(full['labels'][:,0],peak,rtol=0,atol=1e-9)).sum())
        fit=strict_align(local,fit_seeds,logits,lower,cut)
        # Inner holdout may use past inputs from the SAME outer training period.
        # Fit labels end before cut; holdout labels start at cut.
        hold=strict_align(local,hold_seeds,logits,lower,upper)
        hold['valid'] &= hold['label_times'] >= cut
        nfit=int(fit['valid'].sum());nhold=int(hold['valid'].sum())
        row={'fractions':list(combo),'matched_training_peak_rows':matched_peak,
             'training_matched':int(full['valid'].sum()),'fit_matched':nfit,'holdout_matched':nhold,
             'holdout_candidates':len(hold_seeds),'eligible':matched_peak>0 and min(nfit,nhold)>=30}
        if row['eligible']:
            reg=ridge_fit(proxy_features(fit)[fit['valid']],fit['labels'][fit['valid']])
            prediction=ridge_predict(proxy_features(hold),reg)
            row['objective']=coverage_objective(prediction,hold['labels'],hold['valid'],scales)
            row['proxy_metrics']=error_metrics(prediction,hold['labels'],hold['valid'])
        rows.append(row)
    eligible=[r for r in rows if r['eligible']]
    if not eligible: raise ValueError('No route preserves actual training peak with adequate calibration samples')
    best=min(eligible,key=lambda r:(r['objective'],-r['holdout_matched'],r['fractions']))
    f=np.asarray(best['fractions'])
    return np.log(f/(1-f)),{'method':'training_only_inner_chronological_ridge_proxy_with_peak_retention_constraint',
        'training_observed_peak_m3_s':peak,'peak_constraint_uses_training_labels_only':True,
        'inner_holdout_history':'past-only inputs within outer training period; labels separated at inner boundary',
        'inner_boundary_utc':iso(cut),'fit_candidates':len(fit_seeds),'holdout_candidates':len(hold_seeds),
        'objective':'fixed denominator; valid normalized_MSE/(1+normalized_MSE), missing=1',
        'inner_fit_scales':scales.tolist(),'selected':best,'candidates':rows,
        'route_frozen_before_outer_validation_or_test':True}


def load_reverse(folder):
    folder=Path(folder);report=json.loads((folder/'training_report.json').read_text())
    if report['model_type']!='v1_reverse_time_frozen_route':raise ValueError('Unexpected model')
    if digest(folder/'model.pt')!=report['saved_model_sha256']:raise ValueError('Checkpoint mismatch')
    ck=torch.load(folder/'model.pt',map_location='cpu',weights_only=True);w=ck['network']
    model=WeatherChain(w['depths'],w['areas'],w['distances'],w['center'],w['scale']);model.load_state_dict(w);model.eval()
    return model,ck['route_logits'].numpy(),report


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--epochs',type=int,default=100);parser.add_argument('--patience',type=int,default=20)
    args=parser.parse_args();folder=args.output.resolve()
    if min(args.epochs,args.patience)<1:raise ValueError('Finite positive run bounds required')
    if not folder.is_relative_to((DATA/'processed').resolve()) or folder.exists():raise ValueError('Use a new processed output directory')
    cache=DEFAULT_CACHE;manifest=json.loads((cache/'route_inputs.json').read_text())
    if digest(cache/'route_inputs.npz')!=manifest['cache_sha256']:raise ValueError('Cache checksum mismatch')
    historic=json.loads((cache/'training_report.json').read_text())
    if digest(cache/'model.pt')!=historic['saved_model_sha256']:raise ValueError('Geometry checkpoint checksum mismatch')
    arrays=dict(np.load(cache/'route_inputs.npz',allow_pickle=False));seeds=np.concatenate([arrays[n] for n in ['train','validation','test']]);seeds=seeds[np.argsort(seeds[:,0])]
    if np.any(np.diff(seeds[:,0])<=0):raise ValueError('Duplicate origins')
    periods={n:(timestamp(lo) if lo else float(arrays['boundaries'][0]),timestamp(hi) if hi else float(arrays['boundaries'][-1])) for n,(lo,hi) in PERIODS.items()}
    policy=json.loads((WORKSPACE/'shared-resources/config/segment_ml_weather.json').read_text())
    provenance=audit_context(seeds,policy)
    if provenance['weather_manifest_sha256']!=manifest['weather_manifest_sha256']:raise ValueError('Weather identity differs')
    parts={n:seeds[(seeds[:,0]>=lo)&(seeds[:,0]<hi)] for n,(lo,hi) in periods.items()}
    protected=protected_inventory()
    logits,calibration=calibrate(arrays,parts['train'],*periods['train'])
    aligned={n:strict_align(arrays,parts[n],logits,*periods[n]) for n in ['train','validation']}
    if any(a['valid'].sum()<30 for a in aligned.values()):raise ValueError('Insufficient training/validation matches')
    tr=aligned['train'];v=tr['valid'];peak=calibration['training_observed_peak_m3_s']
    if not np.any(np.isclose(tr['labels'][v,0],peak,rtol=0,atol=1e-9)):raise AssertionError('Training peak lost')
    folder.mkdir(exist_ok=False)
    write(folder/'previous_artifacts.json',protected);write(folder/'route_calibration.json',calibration)
    (folder/'training_source.py').write_text(Path(__file__).read_text(encoding='utf-8-sig'),encoding='utf-8')
    write(folder/'implementation_manifest.json',{str(p.relative_to(WORKSPACE)):digest(p) for p in [Path(__file__),Path(__file__).with_name('route_frozen.py'),Path(__file__).with_name('route_neural.py'),Path(__file__).with_name('neural.py')]})
    protocol={'architecture':'original V1 WeatherChain, freshly initialized; no V2 changes',
        'periods_utc':{n:[iso(lo),iso(hi)] for n,(lo,hi) in periods.items()},
        'evaluation':'reverse-time retrospective transfer; not a future-forecast simulation or untouched blind test',
        'all_input_windows_and_targets_inside_period':True,'weather_guard_hours':25,
        'route_fractions':dict(zip(SOURCES,fractions(logits).tolist())),
        'training_population_before_fit':population_summary(tr),'validation_population':population_summary(aligned['validation']),
        'matched_training_peak_rows':int((v&np.isclose(tr['labels'][:,0],peak,rtol=0,atol=1e-9)).sum())}
    write(folder/'protocol_before_test.json',protocol)
    print('Reverse protocol',json.dumps(protocol),flush=True)
    torch.set_num_threads(2);torch.manual_seed(42);torch.use_deterministic_algorithms(True)
    geometry=torch.load(cache/'model.pt',map_location='cpu',weights_only=True)['network']
    center=tr['context'][v].mean(0);scale=np.maximum(tr['context'][v].std(0),1e-3);scales=np.maximum(tr['labels'][v].std(0),[1.,.1])
    model=WeatherChain(geometry['depths'],geometry['areas'],geometry['distances'],center,scale)
    history,chosen=fit_network(model,tr,aligned['validation'],scales,args.epochs,args.patience)
    torch.save({'network':model.state_dict(),'route_logits':torch.tensor(logits)},folder/'model.pt')
    write(folder/'checkpoint_selection_before_test.json',{'selected_epoch':chosen,'history':history,'model_sha256':digest(folder/'model.pt')})
    aligned['test']=strict_align(arrays,parts['test'],logits,*periods['test'])
    results={};states={}
    for n,a in aligned.items():
        states[n]=predict(model,a);results[n]=metrics_with_baselines(arrays,a,states[n])
        q=a['labels'][:,0];valid=a['valid']
        results[n]['signed_high_flow']={}
        for threshold in [100,140,200]:
            pop=q>=threshold;mask=valid&pop;error=states[n][mask,-1,0]-q[mask]
            results[n]['signed_high_flow'][str(threshold)]={'candidates':int(pop.sum()),'matched':int(mask.sum()),
                'bias_m3_s':float(error.mean()) if len(error) else None,'mae_m3_s':float(abs(error).mean()) if len(error) else None,
                'under_fraction':float((error<0).mean()) if len(error) else None}
    report={'model_type':'v1_reverse_time_frozen_route','created_at':datetime.now(timezone.utc).isoformat(),
        'protocol':protocol,'route_calibration':calibration,'epochs_completed':len(history)-1,'selected_epoch':chosen,
        'metrics':results,'history':history,'context_verification':provenance,'saved_model_sha256':digest(folder/'model.pt'),
        'limitations':['Later data train the model; earlier holdout assesses retrospective transfer, not prospective forecasting.',
            'All these historical periods have been inspected during prior development; not a fresh blind test.',
            'Training includes the observed 284 m3/s peak by an explicit training-only route eligibility condition.',
            'Validation labels select the stopping epoch only; they never enter gradient fitting or route calibration. Test labels are evaluation-only. External input and target periods remain disjoint.',
            'Gauge-stage datum, path speed and intermediate predictions remain experimentally unverified.',
            'Fixed prepared-cache exclusions remain; matched point counts are not independent event counts.']}
    if not all(digest(WORKSPACE/k)==sha for k,sha in protected.items()):raise AssertionError('Prior artifacts changed')
    report['old_artifacts_unchanged']=True;write(folder/'training_report.json',report)
    restored,rl,_=load_reverse(folder);sample=strict_align(arrays,parts['train'][:10],logits,*periods['train'])
    if not np.array_equal(predict(model,sample),predict(restored,sample)) or not np.array_equal(rl,logits):raise AssertionError('Reload mismatch')
    for n,a in aligned.items():
        np.savez_compressed(folder/(n+'_predictions.npz'),origins=a['origins'],label_times=a['label_times'],labels=a['labels'],valid=a['valid'],states=states[n],source_times=a['source_rows'][:,:,0])
    write(folder/'verification.json',{'reload_exact':True,'prior_files_unchanged':True,'protected_count':len(protected),
        'training_peak_m3_s':peak,'training_peak_rows':protocol['matched_training_peak_rows'],
        'source_sha256':digest(Path(__file__)),'checkpoint_saved_before_test_evaluation':True})
    print(json.dumps({'selected_epoch':chosen,'metrics':{n:results[n]['model'] for n in results},'high_flow':{n:results[n]['signed_high_flow'] for n in results}}),flush=True)


if __name__=='__main__':main()
