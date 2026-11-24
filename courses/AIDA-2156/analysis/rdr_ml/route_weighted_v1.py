"""Weighted V1 with a training-only high-flow validation interval and unchanged external test."""
import argparse,json,copy
from pathlib import Path
from datetime import datetime,timezone
import numpy as np
import torch
from .route_reverse_v1 import strict_align
from .route_frozen import *
from .route_neural import predict,fractions,SOURCES
from .neural import WeatherChain


def subset(a,mask):
    n=len(a['valid'])
    result={k:(x[mask].copy() if isinstance(x,np.ndarray) and len(x)==n else copy.deepcopy(x)) for k,x in a.items()}
    result['invalid_reasons']={}  # Subset is already matched; global exclusions are reported separately.
    return result


def isolated_split(a):
    # Conservative two-hour trend guard and 25-hour weather/lake guard.
    start=np.minimum(a['source_rows'][:,:,0].min(1)-7200,a['origins']-25*3600)
    end=np.maximum(a['label_times'],a['common_arrivals'])
    best=None
    # Timestamp/count-only selection, never optimize held-out values or errors.
    for cut in np.arange(timestamp('2025-06-01T00:00:00Z'),timestamp('2026-01-01T00:00:00Z'),3600):
        train=a['valid']&(start>=cut);test=a['valid']&(end<cut)
        nt,ne=int(train.sum()),int(test.sum())
        if not min(nt,ne):continue
        score=abs(ne/(nt+ne)-.2)
        if best is None or score<best[0]:best=(score,cut,train,test)
    if best is None:raise ValueError('No isolated split')
    _,cut,tr,te=best
    tm,em=tr,te
    assert not np.any(tm&em)
    assert np.all(start[tm]>=cut) and np.all(end[em]<cut)
    return tm,em,{'boundary_utc':iso(cut),'global_matched':int(a['valid'].sum()),
        'before_ratio_trim_train':int(tr.sum()),'before_ratio_trim_test':int(te.sum()),
        'train':int(tm.sum()),'test':int(em.sum()),'development_fraction':float(tm.sum()/(tm.sum()+em.sum())),
        'excluded_from_global_matches':int(a['valid'].sum()-tm.sum()-em.sum()),
        'split_uses':'timestamps and counts only; strict whole-window isolation; no ratio-only trimming',
        'route_calibration_scope':'reused route selected only from 2026-06 onward, wholly within current development period'}


def new_model(geometry,a):
    v=a['valid'];torch.manual_seed(42)
    return WeatherChain(geometry['depths'],geometry['areas'],geometry['distances'],
        a['context'][v].mean(0),np.maximum(a['context'][v].std(0),1e-3))


HIGH_FLOW=100.
HIGH_WEIGHT=5.

def weights(q):
    return np.where(q>=HIGH_FLOW,HIGH_WEIGHT,1.)

def event_masks(a):
    lo=timestamp('2026-05-28T00:00:00Z');hi=timestamp('2026-06-25T00:00:00Z')
    end=np.maximum(a['label_times'],a['common_arrivals'])
    validation=(a['label_times']>=lo)&(end<hi)
    fit=(end<lo)|(a['origins']>=hi)
    assert not np.any(fit&validation)
    return fit,validation,lo,hi

def fit_network(model,train,validation,scales,epochs,patience):
    rng=np.random.default_rng(42);opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=1e-4)
    ids=np.flatnonzero(train['valid']);w=weights(train['labels'][:,0]);v=validation['valid'];vw=weights(validation['labels'][v,0])
    def objective():
        pred=predict(model,validation)[v,-1,:2];errors=np.mean(((pred-validation['labels'][v])/scales)**2,axis=1)
        return float(np.average(errors,weights=vw))
    best=objective();chosen=0;selected=copy.deepcopy(model.state_dict());history=[{'epoch':0,'validation_objective':best}];stale=0
    for epoch in range(1,epochs+1):
        model.train();order=rng.permutation(ids);total=0.
        for start in range(0,len(order),512):
            ix=order[start:start+512];states,delta=model(torch.tensor(train['initial'][ix],dtype=torch.float32),torch.tensor(train['context'][ix],dtype=torch.float32));labels=torch.tensor(train['labels'][ix],dtype=torch.float32)
            per=((states[:,-1,:2]-labels)/torch.tensor(scales,dtype=torch.float32)).square().mean(1)
            loss=(per*torch.tensor(w[ix],dtype=torch.float32)).mean()/float(w.mean())+.001*delta.square().mean()
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);opt.step();total+=float(loss.detach())*len(ix)
        val=objective();history.append({'epoch':epoch,'training_objective':total/len(ids),'validation_objective':val})
        if val<best-1e-7:best=val;chosen=epoch;selected=copy.deepcopy(model.state_dict());stale=0
        else:stale+=1
        if epoch==1 or epoch%5==0:print('Weighted epoch',epoch,'selected',chosen,'validation',val,flush=True)
        if stale>=patience:break
    model.load_state_dict(selected);model.eval();return history,chosen


def refit(model,a,scales,epochs):
    rng=np.random.default_rng(42);opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=1e-4)
    ids=np.flatnonzero(a['valid']);history=[]
    for epoch in range(1,epochs+1):
        model.train();order=rng.permutation(ids);total=0.
        for i in range(0,len(order),512):
            ix=order[i:i+512];states,delta=model(torch.tensor(a['initial'][ix],dtype=torch.float32),torch.tensor(a['context'][ix],dtype=torch.float32))
            per=((states[:,-1,:2]-torch.tensor(a['labels'][ix],dtype=torch.float32))/torch.tensor(scales,dtype=torch.float32)).square().mean(1)
            loss=(per*torch.tensor(weights(a['labels'][ix,0]),dtype=torch.float32)).mean()/float(weights(a['labels'][:,0]).mean())+.001*delta.square().mean()
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);opt.step();total+=float(loss.detach())*len(ix)
        history.append({'epoch':epoch,'training_objective':total/len(ids)})
        if epoch==1 or epoch%5==0:print('Full80 refit',epoch,flush=True)
    model.eval();return history


def joined_proxy_depths(values, times, expected, offset, station):
    """Exact timestamp join, preserving Q/stage and applying no second offset."""
    if not len(values) or not np.all(np.diff(values[:,0])>0):raise ValueError('Missing or duplicate proxy observation keys')
    if not np.allclose(values[:,3]-values[:,2],offset,rtol=0,atol=1e-8):raise ValueError('Proxy is not the reviewed single station offset')
    ix=np.searchsorted(values[:,0],times)
    if np.any(ix>=len(values)) or not np.array_equal(values[np.minimum(ix,len(values)-1),0],times):
        raise ValueError('Proxy context does not cover every frozen routing key: '+station)
    selected=values[ix]
    if not np.allclose(selected[:,1:3],expected,rtol=0,atol=1e-8):raise ValueError('Frozen source Q/stage differs from database: '+station)
    if not np.all(np.isfinite(selected[:,3])) or np.any(selected[:,3]<=0):raise ValueError('Invalid approximate depth: '+station)
    return selected[:,3].copy()


def proxy_depth_inputs(arrays, bundle_id, config_path):
    """Read a reviewed proxy bundle without changing legacy hydraulic routing.

    This is an opt-in coordinate sensitivity experiment, not a new physical
    routing model. Source timestamps, Q, legacy cap/area and route distances
    stay fixed. The database values replace only station depth features/labels.
    """
    from rdr_eda.postgres import psycopg, sql, dict_row
    from eda_tools.import_unit_postgres import benchmark_connection_options
    config=json.loads(config_path.read_text(encoding='utf-8'))
    result={k:v.copy() for k,v in arrays.items()}
    stations=SOURCES+['05CC002']; offsets={}; audit={}
    options=benchmark_connection_options()  # Reject/pin remote hosts before sending credentials.
    options['application_name']='rdr_approximate_depth_read_only'
    try:connection=psycopg.connect(**options,row_factory=dict_row)
    except psycopg.Error:raise RuntimeError('Local approximate-depth database connection failed') from None
    with connection as db:
        db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        db.execute("SET LOCAL TIME ZONE 'UTC'")
        server=db.execute('SELECT current_database() AS name, host(inet_server_addr()) AS host').fetchone()
        if server['name']!=config['database'] or server['host'] not in ('127.0.0.1','::1'):
            raise ValueError('Proxy database must be the configured local loopback dataset')
        def query(statement,params=()):
            return db.execute(sql.SQL(statement).format(s=sql.Identifier(config['schema'])),params)
        bundle=query('SELECT base_dataset_id,source_manifest,view_definition_sha256 FROM {s}.bed_proxy_imports WHERE bundle_id=%s',(bundle_id,)).fetchone()
        if bundle is None or bundle['base_dataset_id']!=config['dataset_id'] or bundle['source_manifest']['training_ready'] is not False:
            raise ValueError('Expected reviewed approximate-only bundle for this dataset')
        refs=query('SELECT station_id,stage_add_m,bed_elevation_aligned_m,depth_enabled FROM {s}.v_bed_proxy_references WHERE bundle_id=%s',(bundle_id,)).fetchall()
        if len(refs)!=5:raise ValueError('Proxy reference population changed')
        for r in refs:
            if r['station_id']=='05CC003':
                if r['depth_enabled'] or r['bed_elevation_aligned_m'] is not None:raise ValueError('Lake must remain level-only')
            else:offsets[r['station_id']]=float(r['stage_add_m']-r['bed_elevation_aligned_m'])
        if set(offsets)!=set(stations):raise ValueError('Unexpected river proxy stations')
        for k,sid in enumerate(stations):
            rows=query('SELECT observed_at,reported_water_level_m,approximate_depth_m,discharge_m3_s,training_ready FROM {s}.v_observations_bed_proxy_context WHERE bundle_id=%s AND station_id=%s AND approximate_depth_m IS NOT NULL ORDER BY observed_at',(bundle_id,sid)).fetchall()
            if any(r['training_ready'] for r in rows):raise ValueError('Physical-depth readiness unexpectedly changed')
            values=np.array([[r['observed_at'].timestamp(),r['discharge_m3_s'] if r['discharge_m3_s'] is not None else np.nan,r['reported_water_level_m'],r['approximate_depth_m']] for r in rows],dtype=float)
            if k<3:
                original=arrays['source'+str(k)]; times=original[:,0]; expected=original[:,1:3]
            else:
                times=arrays['endpoint_times'];expected=arrays['endpoint_values']
            depths=joined_proxy_depths(values,times,expected,offsets[sid],sid)
            if k<3:result['source'+str(k)][:,2]=depths
            else:result['endpoint_values'][:,1]=depths
            audit[sid]={'joined_frozen_keys':len(times),'depth_minus_reported_stage_m':offsets[sid],
                        'approximate_depth_range_m':[float(depths.min()),float(depths.max())]}
    return result,{'bundle_id':bundle_id,'database':config['database'],'schema':config['schema'],
        'base_dataset_id':config['dataset_id'],'view_definition_sha256':bundle['view_definition_sha256'],
        'training_ready':False,'stations':audit,'offsets_m':offsets,'lake_level_unchanged':True,
        'read_only_repeatable_read':True,'server_is_loopback':True,'route_policy':'Frozen legacy stage-derived caps/areas, selected fractions, source keys and arrival times; NOT hydraulically recalibrated.',
        'depth_policy':'Use approximate depth once at each gauge; no additional stage/bed offset. Unchanged section-local geometry is an unvalidated depth-transfer assumption.'}


def tail_metrics(predictions, labels):
    result={}
    for threshold in [100,140,200]:
        m=labels[:,0]>=threshold
        result[str(threshold)]={'n':int(m.sum()),'metrics':reported_metrics(predictions[m],labels[m],np.ones(int(m.sum()),dtype=bool)),
            'q_under_fraction':float((predictions[m,0]<labels[m,0]).mean()) if m.any() else None}
    return result


def geometry_usage(model,part):
    """Count numerical interpolation/bounded-state limits, not physical validity."""
    states=predict(model,part);before=np.column_stack([part['initial'][:,1],states[:,:-1,1]])
    lo=model.depths[:,0].detach().numpy();hi=model.depths[:,-1].detach().numpy()
    return {'samples':len(before),'incoming_below_grid_by_segment':(before<lo).sum(0).tolist(),
        'incoming_above_grid_by_segment':(before>hi).sum(0).tolist(),
        'output_near_lower_1pct_by_segment':(states[:,:,1]<=lo+.01*(hi-lo)).sum(0).tolist(),
        'output_near_upper_1pct_by_segment':(states[:,:,1]>=hi-.01*(hi-lo)).sum(0).tolist(),
        'interpretation':'Numerical diagnostic only; same-depth spatial transfer and intermediate predictions remain unvalidated.'}


def stage_control_comparison(part, states, control_folder, name, endpoint_offset):
    report=json.loads((control_folder/'training_report.json').read_text())
    if digest(control_folder/'model.pt')!=report['saved_model_sha256'] or not json.loads((control_folder/'verification.json').read_text())['reload_exact']:
        raise ValueError('Stage control checkpoint not verified')
    with np.load(control_folder/(name+'_predictions.npz'),allow_pickle=False) as old:
        for key in ['origins','label_times']:
            if not np.array_equal(part[key],old[key]):raise ValueError('Control comparison keys differ')
        if not np.array_equal(part['source_rows'][:,:,0],old['source_times']):raise ValueError('Control source times differ')
        control_labels=old['labels'].copy();control_labels[:,1]+=endpoint_offset
        if not np.allclose(part['labels'],control_labels,rtol=0,atol=1e-8):raise ValueError('Control target values differ after one coordinate conversion')
        baseline=old['states'][:,-1,:2].copy();baseline[:,1]+=endpoint_offset
    if states is None:
        return {'common_origins':len(part['valid']),'identical_population':True}
    prediction=states[:,-1,:2];valid=np.ones(len(prediction),dtype=bool)
    stage_prediction=prediction.copy();stage_prediction[:,1]-=endpoint_offset
    stage_labels=part['labels'].copy();stage_labels[:,1]-=endpoint_offset
    return {'common_origins':len(prediction),'identical_origin_source_arrival_target_population':True,
        'control_folder':str(control_folder.relative_to(WORKSPACE)),'control_checkpoint_sha256':report['saved_model_sha256'],
        'target_basis':'approximate endpoint depth; archived stage prediction and label translated by the same fixed offset once',
        'depth_model':error_metrics(prediction,part['labels'],valid),'stage_control_on_depth_basis':error_metrics(baseline,part['labels'],valid),
        'depth_model_on_reported_stage_basis':error_metrics(stage_prediction,stage_labels,valid),
        'depth_model_high_flow':tail_metrics(prediction,part['labels']),'stage_control_high_flow':tail_metrics(baseline,part['labels'])}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--approximate-depth-bundle',help='Opt-in reviewed PostgreSQL proxy bundle; default keeps legacy stage experiment')
    parser.add_argument('--pg-config',type=Path,default=WORKSPACE/'shared-resources/config/postgres_dataset.json')
    parser.add_argument('--checks-only',action='store_true',help='Save preflight only, do not train')
    args=parser.parse_args();folder=args.output.resolve()
    if folder.exists() or not folder.is_relative_to((DATA/'processed').resolve()):raise ValueError('Use new processed output')
    prior=DATA/'processed/segment_nn_weather_reverse_v1_20261110';rr=json.loads((prior/'training_report.json').read_text())
    if not json.loads((prior/'verification.json').read_text())['reload_exact']:raise ValueError('Prior not verified')
    manifest=json.loads((DEFAULT_CACHE/'route_inputs.json').read_text())
    if digest(DEFAULT_CACHE/'route_inputs.npz')!=manifest['cache_sha256']:raise ValueError('Cache mismatch')
    arrays=dict(np.load(DEFAULT_CACHE/'route_inputs.npz',allow_pickle=False));seeds=np.concatenate([arrays[n] for n in ['train','validation','test']]);seeds=seeds[np.argsort(seeds[:,0])]
    policy=json.loads((WORKSPACE/'shared-resources/config/segment_ml_weather.json').read_text());provenance=audit_context(seeds,policy)
    if provenance['weather_manifest_sha256']!=manifest['weather_manifest_sha256']:raise ValueError('Weather provenance mismatch')
    geometry_report=json.loads((DEFAULT_CACHE/'training_report.json').read_text())
    if digest(DEFAULT_CACHE/'model.pt')!=geometry_report['saved_model_sha256']:raise ValueError('Geometry checkpoint mismatch')
    fs=np.array([rr['protocol']['route_fractions'][k] for k in SOURCES]);logits=np.log(fs/(1-fs))
    depth_context=None;control_folder=DATA/'processed/segment_nn_weather_weighted_v1_20261110'
    legacy_arrays=arrays
    if args.approximate_depth_bundle:
        arrays,depth_context=proxy_depth_inputs(arrays,args.approximate_depth_bundle,args.pg_config)
    a=strict_align(arrays,seeds,logits,float(arrays['boundaries'][0]),float(arrays['boundaries'][-1]))
    tm,em,split=isolated_split(a);train=subset(a,tm);test=subset(a,em)
    if train['labels'][:,0].max()!=284:raise ValueError('Training peak absent')
    fm,vm,event_start,event_end=event_masks(train)
    if train['labels'][fm,0].max()!=284:raise ValueError('Peak lost from inner fitting')
    fixed=np.load(DATA/'processed/segment_nn_weather_reverse_8020_20261110/test_predictions.npz')
    for key in ['origins','label_times','labels']:
        observed=test[key].copy()
        if key=='labels' and depth_context:observed[:,1]-=depth_context['offsets_m']['05CC002']
        if not np.allclose(observed,fixed[key],rtol=0,atol=1e-8):raise ValueError('External test population changed')
    fit=subset(train,fm);val=subset(train,vm)
    if not np.any(val['labels'][:,0]>=HIGH_FLOW):raise ValueError('High-flow validation absent')
    if min(len(fit['valid']),len(val['valid']))<30:raise ValueError('Too few inner samples')
    protected=protected_inventory();folder.mkdir();write(folder/'previous_artifacts.json',protected)
    protocol={'split':split,'route_fractions':fs.tolist(),'architecture':'fresh original V1 WeatherChain',
        'inner_fit':population_summary(fit),'inner_validation':population_summary(val),'inner_event_utc':[iso(event_start),iso(event_end)],'weighting':{'flow_threshold_m3_s':HIGH_FLOW,'high_weight':HIGH_WEIGHT,'other_weight':1,'applies_to':'both normalized Q and level errors; symmetric under/over'},'test_population_unchanged':True,
        'inner_boundary_purged':int(len(train['valid'])-fm.sum()-vm.sum()),
        'final_train':population_summary(train),'final_test':population_summary(test),
        'selection':'max100 epochs/patience20 on internal validation; fresh refit full80 for selected epoch count; test prediction errors evaluated once afterward; population ranges inspected before fitting',
        'limitations':['Retrospective reverse-time transfer, not future forecasting. Historical test previously inspected.',
            '80/20 is the final isolated matched population, not all raw observations. Source windows can exclude many rows.',
            'The route is reused from a later training-only calibration; no new test labels select route or stopping epoch.',
            'Internal validation is a high-flow target interval for epoch tuning, not an independent-event guarantee. Known past upstream histories may overlap fitting histories; endpoint target labels do not. The frozen route previously saw some validation-period labels.',
            'Current endpoint persistence uses an extra input unavailable to the network.']}
    geometry=torch.load(DEFAULT_CACHE/'model.pt',map_location='cpu',weights_only=True)['network'];model=new_model(geometry,fit)
    protocol['approximate_depth_context']=depth_context
    protocol['depth_coordinate']='approximate_gauge_depth' if depth_context else 'reported_stage_as_experimental_depth'
    if depth_context:
        old=strict_align(legacy_arrays,seeds,logits,float(arrays['boundaries'][0]),float(arrays['boundaries'][-1]))
        for key in ['valid','origins','label_times','common_arrivals','source_arrivals','speeds']:
            if not np.array_equal(a[key],old[key]):raise ValueError('Depth sensitivity changed frozen timing/coverage')
        if not np.array_equal(arrays['train'],legacy_arrays['train']) or not np.array_equal(arrays['test'],legacy_arrays['test']):raise ValueError('Lake/weather changed')
        limits=geometry['depths'][-1,[0,-1]].tolist()
        if train['labels'][:,1].min()<=limits[0] or train['labels'][:,1].max()>=limits[1]:raise ValueError('Training depth labels outside endpoint grid')
        protocol['limitations'] += ['Approximate proxy depth is not surveyed gauge-bed depth; training_ready remains false.',
            'The same gauge series changes only by a constant. No new time-varying hydrologic information has been added.',
            'Routing intentionally remains the legacy stage-based matched control. Local section geometry and unobserved intermediate depth transfer are not recalibrated or physically validated.',
            'Comparison isolates a feature/target coordinate change within V1, not a fully corrected hydraulic model or a fresh untouched test.']
        protocol['preflight']={'geometry_limits_m':geometry['depths'][:,[0,-1]].tolist(),
            'initial_geometry_usage':geometry_usage(model,fit),'frozen_timing_and_coverage_exact':True,
            'train_control_population':stage_control_comparison(train,None,control_folder,'train',depth_context['offsets_m']['05CC002'])['common_origins'],
            'test_control_population':stage_control_comparison(test,None,control_folder,'test',depth_context['offsets_m']['05CC002'])['common_origins']}
        np.savez_compressed(folder/'approximate_depth_inputs.npz',**arrays)
        protocol['approximate_depth_inputs_sha256']=digest(folder/'approximate_depth_inputs.npz')
    write(folder/'protocol_before_test.json',protocol);(folder/'training_source.py').write_bytes(Path(__file__).read_bytes())
    print('Protocol',json.dumps(protocol),flush=True);torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    if args.checks_only:
        assert all(digest(WORKSPACE/k)==sha for k,sha in protected.items())
        write(folder/'verification.json',{'preflight_passed':True,'training_run':False,'old_artifacts_unchanged':True,'protected_count':len(protected)})
        return
    history,chosen=fit_network(model,fit,val,np.maximum(fit['labels'].std(0),[1.,.1]),100,20)
    write(folder/'epoch_selection_before_test.json',{'selected_epoch':chosen,'history':history})
    model=new_model(geometry,train);refit_history=refit(model,train,np.maximum(train['labels'].std(0),[1.,.1]),chosen)
    torch.save({'network':model.state_dict(),'route_logits':torch.tensor(logits)},folder/'model.pt')
    write(folder/'checkpoint_before_test.json',{'sha256':digest(folder/'model.pt'),'selected_epoch':chosen})
    results={};peak_rows={}
    for name,part in [('train',train),('test',test)]:
        states=predict(model,part);results[name]=metrics_with_baselines(arrays,part,states);q=part['labels'][:,0];err=states[:,-1,0]-q
        if depth_context:
            results[name]['stage_control_comparison']=stage_control_comparison(part,states,control_folder,name,depth_context['offsets_m']['05CC002'])
            results[name]['geometry_usage']=geometry_usage(model,part)
        results[name]['signed_high_flow']={str(t):{'n':int((q>=t).sum()),'bias':float(err[q>=t].mean()) if (q>=t).any() else None,'mae':float(abs(err[q>=t]).mean()) if (q>=t).any() else None,'under_fraction':float((err[q>=t]<0).mean()) if (q>=t).any() else None} for t in [100,140,200]}
        ix=np.flatnonzero(q==q.max());peak_rows[name]=[{'time':iso(part['label_times'][i]),'observed':part['labels'][i].tolist(),'predicted':states[i,-1,:2].tolist()} for i in ix]
        np.savez_compressed(folder/(name+'_predictions.npz'),origins=part['origins'],label_times=part['label_times'],labels=part['labels'],states=states,source_times=part['source_rows'][:,:,0])
    ck=torch.load(folder/'model.pt',map_location='cpu',weights_only=True);restored=new_model(geometry,train);restored.load_state_dict(ck['network']);restored.eval()
    sample=subset(train,np.arange(len(train['valid']))<32);assert np.array_equal(predict(model,sample),predict(restored,sample))
    assert all(digest(WORKSPACE/k)==sha for k,sha in protected.items())
    report={'model_type':'weighted_v1_approximate_depth_frozen_route' if depth_context else 'weighted_v1_same_80_20_test','created_at':datetime.now(timezone.utc).isoformat(),'protocol':protocol,'selected_epoch':chosen,'selection_history':history,'refit_history':refit_history,'metrics':results,'peak_rows':peak_rows,'saved_model_sha256':digest(folder/'model.pt'),'context_verification':provenance}
    write(folder/'training_report.json',report);write(folder/'verification.json',{'reload_exact':True,'old_artifacts_unchanged':True,'protected_count':len(protected),'achieved_development_fraction':len(train['valid'])/(len(train['valid'])+len(test['valid'])),'source_sha256':digest(Path(__file__))})
    print(json.dumps({'selected_epoch':chosen,'metrics':{n:x['model'] for n,x in results.items()},'high_flow':{n:x['signed_high_flow'] for n,x in results.items()},'peak_rows':peak_rows}),flush=True)

if __name__=='__main__':main()
