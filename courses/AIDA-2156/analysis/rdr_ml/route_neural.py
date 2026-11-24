"""Bounded route-speed alignment and jointly supervised weather-aware segments.

Route fractions are fitted by training-only coordinate search interleaved with
joint neural updates. Nearest-observation matching is discrete, not differentiable.
"""
import argparse
import copy
from collections import Counter
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import time

import numpy as np
import torch

from API.observations import parse_time
from project_paths import WORKSPACE
from rdr_eda.postgres import read_training_views
from .core import Dataset, numeric_pair
from .neural import WeatherChain, error_metrics
from .train_neural import geometry, write

DATA = WORKSPACE / 'courses/AIDA-2156/data'
NAME = 'segment_nn_weather_route_bounded_60_20_20'
SOURCES = ['05CB007', '05CB001', '05CC007']
TOLERANCE = 1800.


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stamp(t):
    return datetime.fromtimestamp(float(t), timezone.utc).isoformat()


def nearest(times, wanted):
    """Return nearest observation; exact ties select the later observation."""
    right = np.clip(np.searchsorted(times, wanted), 0, len(times)-1)
    left = np.clip(right-1, 0, len(times)-1)
    return np.where(np.abs(times[left]-wanted) < np.abs(times[right]-wanted), left, right)


def fractions(logits):
    return 1. / (1. + np.exp(-np.clip(logits, -20, 20)))


def nearest_past_arrival(arrival, observed, wanted, cutoff, lower, upper):
    """Exact nearest eligible arrival with past departures; ties choose later.

    Range-minimum queries locate the closest eligible neighbor on either side.
    This is exact even when arrivals are not monotonic in departure time.
    """
    eligible = np.flatnonzero((observed >= lower) & (observed < upper))
    if not len(eligible):
        return np.zeros(len(wanted),dtype=int), np.zeros(len(wanted),dtype=bool)
    order = eligible[np.argsort(arrival[eligible],kind='stable')]
    times = arrival[order]; pos = np.searchsorted(times,wanted)
    choices=[]; founds=[]
    for reverse in [False,True]:
        ids=order[::-1] if reverse else order
        ends=len(order)-pos if reverse else pos
        levels=int(np.floor(np.log2(len(order))))+1
        table=np.full((levels,len(order)),np.inf)
        table[0]=observed[ids]
        for level in range(1,levels):
            half=1<<(level-1); length=len(order)-(1<<level)+1
            table[level,:length]=np.minimum(table[level-1,:length],table[level-1,half:half+length])
        def minimum(start,end):
            size=np.maximum(end-start,1); level=np.floor(np.log2(size)).astype(int)
            return np.where(end>start,np.minimum(table[level,np.clip(start,0,len(order)-1)],
                            table[level,np.clip(end-(1<<level),0,len(order)-1)]),np.inf)
        lo=np.zeros(len(wanted),dtype=int); hi=ends.copy()
        found=minimum(lo,hi)<=cutoff
        for _ in range(levels+1):
            mid=(lo+hi)//2
            good=minimum(mid,ends)<=cutoff
            lo=np.where(good,mid,lo); hi=np.where(good,hi,mid)
        choices.append(ids[np.clip(lo,0,len(ids)-1)]); founds.append(found)
    left,right=choices; lf,rf=founds
    use_left=lf & (~rf | (np.abs(arrival[left]-wanted)<np.abs(arrival[right]-wanted)))
    return np.where(use_left,left,right), lf|rf


def prepare(d, folder):
    """Freeze observed-stage area constraints independently of learned depths."""
    audit = {'preparation_version':2, 'source_dataset': d.source_metadata, 'geometry_sha256': d.geometry_sha256,
             'weather_manifest_sha256': d.weather.sha256, 'sources': {}, 'partitions': {}}
    a = {}
    tail = sum(float(s['distance_m'] or 0) for s in d.segments[1:])
    source_legs = {r['source_node_id']: r for r in d.legs if r['source_node_id'] in SOURCES}
    distances = np.array([source_legs[s]['distance_m'] + tail for s in SOURCES])
    # The dam boundary ends at the first confluence, before tributary additions.
    first_confluence_chainage = source_legs['05CB007']['distance_m'] - max(
        source_legs[s]['mainstem_distance_m'] for s in SOURCES[1:])
    for k, sid in enumerate(SOURCES):
        river = d.policy['source_rivers'][sid]
        limit = first_confluence_chainage if k == 0 else source_legs[sid]['tributary_distance_m']
        sections = sorted(s['section_id'] for s in d.sections.values()
                          if s['river'] == river and s['selected_river_chainage_m'] is not None
                          and 0 <= s['selected_river_chainage_m'] <= limit
                          and s['section_id'] in d.profiles)
        if not sections:
            raise ValueError('No pre-confluence profiles for ' + sid)
        rows = [r for r in d.index[sid].rows if numeric_pair(r)]
        rows.sort(key=lambda r: parse_time(r['observed_at']))
        heights = sorted({float(r['experimental_variable_depth_m']) for r in rows})
        lookup = {}
        for h in heights:
            valid = []
            for j, section in enumerate(sections):
                try:
                    area = d.area(section, h)
                    if np.isfinite(area) and area > 0:
                        valid.append((area, j))
                except ValueError:
                    pass
            lookup[h] = (*min(valid), len(valid)) if valid else None
        records = []; excluded = Counter()
        for r in rows:
            h = float(r['experimental_variable_depth_m']); q = float(r['discharge_m3_s'])
            item = lookup[h]
            if item is None:
                excluded['no_valid_pre_confluence_area_at_observed_stage'] += 1
                continue
            area, j, count = item
            records.append([parse_time(r['observed_at']).timestamp(), q, h, q/area, area, j, count])
        a['source'+str(k)] = np.asarray(records, dtype=np.float64)
        if not len(records):
            raise ValueError('No capped observations for ' + sid)
        audit['sources'][sid] = {'distance_to_endpoint_m': float(distances[k]),
            'pre_confluence_route_limit_m': float(limit), 'sections': sections,
            'numeric_observations': len(rows), 'usable_capped_observations': len(records),
            'excluded': dict(excluded), 'unique_observed_depths': len(heights),
            'area_rule': 'Minimum valid connected wetted area at source observed experimental depth; profiles above their surveyed edges or invalid are excluded per record.',
            'depth_transfer': 'Same source experimental depth applied to available pre-confluence profiles; unverified spatial transfer, not model output.',
            'speed_cap_quantiles_m_s': np.quantile(a['source'+str(k)][:,3],[0,.5,.95,1]).tolist()}
        print('Prepared speed limits', sid, len(records), 'sections', len(sections), flush=True)
    endpoint = sorted([r for r in d.index['05CC002'].rows if numeric_pair(r)],
                      key=lambda r: parse_time(r['observed_at']))
    a['endpoint_times'] = np.array([parse_time(r['observed_at']).timestamp() for r in endpoint])
    a['endpoint_values'] = np.array([[r['discharge_m3_s'], r['experimental_variable_depth_m']] for r in endpoint])
    a['distances'] = distances
    names = ['train', 'validation', 'test']
    a['boundaries'] = np.array([parse_time(d.partitions[n][0]).timestamp() for n in names] + [a['endpoint_times'][-1]+1])
    for part, name in enumerate(names):
        records = []; excluded = Counter()
        for value in d.partitions[name]:
            at = parse_time(value); t = at.timestamp()
            try:
                _, weather = d.weather.at(at)
            except ValueError as exc:
                excluded[str(exc)] += 1; continue
            lake, _, status = d.lake.previous(at, d.policy['lake_max_age_seconds'])
            if status != 'usable' or not lake.get('level_m') or parse_time(lake['observed_at']) < parse_time(d.partitions[name][0]):
                excluded['lake_missing_or_outside_partition'] += 1; continue
            wf = weather['features']
            records.append([t, np.log1p(wf['precipitation_1h_mm']), np.log1p(wf['precipitation_6h_mm']),
                            np.log1p(wf['precipitation_24h_mm']), wf['temperature_c'], lake['level_m']])
        a[name] = np.asarray(records, dtype=np.float64)
        audit['partitions'][name] = {'view_origins': len(d.partitions[name]), 'prepared': len(records), 'excluded': dict(excluded)}
        print('Prepared origins', name, audit['partitions'][name], flush=True)
    for key in ['endpoint_times']:
        assert np.all(np.diff(a[key]) > 0)
    for k in range(3):
        assert np.all(np.diff(a['source'+str(k)][:,0]) > 0)
    np.savez_compressed(folder/'route_inputs.npz', **a)
    audit['cache_sha256'] = digest(folder/'route_inputs.npz')
    write(folder/'route_inputs.json', audit)
    return a, audit


def align(a, seeds, logits, part):
    """Align all paths to the dam path arrival, rejecting future source inputs."""
    t = seeds[:,0]; n = len(t); fraction = fractions(logits)
    lower, upper = a['boundaries'][part:part+2]
    selected = []; speeds = []; arrivals = []; indices = []
    valid = np.ones(n, dtype=bool); reasons = {}
    common = None
    for k in range(3):
        src = a['source'+str(k)]
        v = src[:,3]*fraction[k]
        elapsed = a['distances'][k]/v
        arrival = src[:,0]+elapsed
        if k == 0:
            idx = nearest(src[:,0], t)
            common = arrival[idx]
            okay = src[idx,0] == t
        else:
            # Sorting arrivals allows stage-dependent speeds to be non-monotonic.
            # Future departures are rejected, never silently read as predictors.
            idx, found = nearest_past_arrival(arrival,src[:,0],common,t,lower,upper)
            okay = found & (np.abs(arrival[idx]-common) <= TOLERANCE)
        row = src[idx]
        okay &= (row[:,0] <= t) & (row[:,0] >= lower) & np.isfinite(elapsed[idx])
        reasons[SOURCES[k]+'_alignment_invalid'] = ~okay
        valid &= okay
        selected.append(row); speeds.append(v[idx]); arrivals.append(arrival[idx]); indices.append(idx)
    label_idx = nearest(a['endpoint_times'], common)
    label_t = a['endpoint_times'][label_idx]
    target_valid = (label_t >= lower) & (label_t < upper) & (label_t >= t) & (common >= t) & (common < upper) & (np.abs(label_t-common) <= TOLERANCE)
    valid &= target_valid; reasons['endpoint_match_invalid'] = ~target_valid
    cc = a['source2']; before = np.searchsorted(cc[:,0], selected[2][:,0]-3600, side='right')-1
    j = np.clip(before, 0, len(cc)-1); previous = cc[j]
    trend_valid = (before >= 0) & (selected[2][:,0]-previous[:,0] <= 7200) & (previous[:,0] >= lower)
    valid &= trend_valid; reasons['feature_trend_missing_or_outside_partition'] = ~trend_valid
    elapsed_h = np.maximum((selected[2][:,0]-previous[:,0])/3600, 1e-6)
    feature = np.column_stack([np.log1p(selected[2][:,1]), np.log1p(selected[2][:,2]),
                               (selected[2][:,1]-previous[:,1])/elapsed_h,
                               (selected[2][:,2]-previous[:,2])/elapsed_h])
    q = selected[0][:,1]+selected[1][:,1]
    h = (selected[0][:,1]*selected[0][:,2]+selected[1][:,1]*selected[1][:,2])/q
    v = (selected[0][:,1]*speeds[0]+selected[1][:,1]*speeds[1])/q
    initial = np.column_stack([q,h,v,np.zeros(n)])
    context = np.column_stack([feature,seeds[:,1:]])
    return {'initial': initial, 'context': context, 'valid': valid,
            'labels': a['endpoint_values'][label_idx], 'label_times': label_t,
            'common_arrivals': common, 'source_rows': np.stack(selected,1),
            'speeds': np.stack(speeds,1), 'source_arrivals': np.stack(arrivals,1),
            'invalid_reasons': {k:int(v.sum()) for k,v in reasons.items()}}


def predict(model, aligned):
    pieces = []
    model.eval()
    with torch.no_grad():
        for start in range(0,len(aligned['valid']),2048):
            x = torch.tensor(aligned['initial'][start:start+2048],dtype=torch.float32)
            z = torch.tensor(aligned['context'][start:start+2048],dtype=torch.float32)
            pieces.append(model(x,z)[0].numpy())
    return np.concatenate(pieces)


def score(model, aligned, scale):
    states = predict(model,aligned)
    loss = np.mean(((states[:,-1,:2]-aligned['labels'])/scale)**2,axis=1)
    objective = float(np.where(aligned['valid'],loss,1e6).mean())
    return objective, error_metrics(states[:,-1,:2],aligned['labels'],aligned['valid']), states


def checks():
    assert nearest(np.array([0.,600.]),np.array([240.,300.,360.])).tolist() == [0,1,1]
    cap = np.array([.1,1.,20.])
    for x in [-100.,0.,100.]:
        v = fractions(np.array([x,x,x]))*cap
        assert np.all(v>0) and np.all(v<=cap)
    a = {'boundaries': np.array([0.,10000.,20000.,30000.]),'distances':np.array([600.,600.,600.]),
         'endpoint_times':np.arange(0.,10000.,600.),'endpoint_values':np.ones((17,2))}
    for k in range(3):
        t=np.arange(0.,10000.,600.)
        a['source'+str(k)] = np.column_stack([t,np.ones(17)*10,np.ones(17),np.ones(17)*2,np.ones(17)*5,np.zeros(17),np.ones(17)])
    seeds=np.array([[3600.,0.,0.,0.,10.,999.],[4200.,0.,0.,0.,10.,999.]])
    r=align(a,seeds,np.zeros(3),0)
    assert r['valid'].all() and np.all(r['common_arrivals']==seeds[:,0]+600)
    assert np.all(r['source_rows'][:,:,0]<=seeds[:,0,None])
    assert np.all(r['speeds']<=r['source_rows'][:,:,3])
    idx, valid=nearest_past_arrival(np.array([500.,610.,700.]),np.array([10.,200.,20.]),
                                  np.array([600.]),np.array([100.]),0,1000)
    assert valid[0] and idx[0]==2
    rng=np.random.default_rng(7); obs=np.arange(200.)
    arrivals=obs+rng.uniform(1,500,200); wanted=rng.uniform(0,700,100); cut=rng.uniform(0,200,100)
    idx,valid=nearest_past_arrival(arrivals,obs,wanted,cut,20,180)
    for i in range(len(wanted)):
        eligible=np.flatnonzero((obs>=20)&(obs<180)&(obs<=cut[i]))
        assert valid[i]==bool(len(eligible))
        if len(eligible):
            expected=min(eligible,key=lambda j:(abs(arrivals[j]-wanted[i]),-arrivals[j]))
            assert idx[i]==expected
    a['boundaries'][1]=4000
    assert not align(a,seeds,np.zeros(3),0)['valid'].any()
    print('Checks passed: later ties, hard cap, source arrival alignment, past-only sources, partition guard.',flush=True)


def load_trained(folder):
    folder=Path(folder); report=json.loads((folder/'training_report.json').read_text())
    if report['model_type']!='six_segment_weather_mlp_bounded_total_route':
        raise ValueError('Unexpected model type')
    if digest(folder/'model.pt')!=report['saved_model_sha256']:
        raise ValueError('Checkpoint checksum mismatch')
    state=torch.load(folder/'model.pt',map_location='cpu',weights_only=True)
    w=state['network']
    model=WeatherChain(w['depths'],w['areas'],w['distances'],w['center'],w['scale'])
    model.load_state_dict(w); model.eval()
    return model,state['route_logits'].numpy(),report


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--epochs',type=int,default=100); p.add_argument('--patience',type=int,default=20)
    p.add_argument('--output',type=Path,default=DATA/'processed'/(NAME+'_grid'))
    p.add_argument('--speed-search',choices=['robust-grid','initial-cohort'],default='robust-grid')
    p.add_argument('--checks-only',action='store_true'); p.add_argument('--prepare-only',action='store_true')
    args=p.parse_args(); checks()
    if args.checks_only:return
    if min(args.epochs,args.patience)<1:raise ValueError('Finite positive bounds required')
    torch.set_num_threads(2); torch.manual_seed(42); np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    folder=args.output.resolve()
    if not folder.is_relative_to((DATA/'processed').resolve()):raise ValueError('Output outside processed directory')
    if (folder/'model.pt').exists():raise ValueError('Never overwrite an existing model')
    folder.mkdir(parents=True,exist_ok=True); started=time.perf_counter()
    old=DATA/'processed/segment_nn_weather_60_20_20'
    old_paths=list(old.glob('*'))+[DATA/'reports/segment_nn_weather_training_60_20_20.json']
    first=DATA/'processed'/NAME
    if folder!=first and (first/'model.pt').exists():
        old_paths+=list(first.glob('*'))+[DATA/'reports/segment_nn_weather_training_route_bounded_60_20_20.json']
    protected={str(f.relative_to(WORKSPACE)):digest(f) for f in old_paths if f.is_file()}
    write(folder/'previous_artifacts.json',protected)
    policy=json.loads((WORKSPACE/'shared-resources/config/segment_ml_weather.json').read_text())
    tables,parts,metadata=read_training_views(WORKSPACE/'shared-resources/config/postgres_dataset.json')
    d=Dataset(None,policy,tables=tables,partitions=parts,source_metadata=metadata)
    cache=folder/'route_inputs.json'
    if not cache.exists() and folder!=first and (first/'route_inputs.json').exists():
        import shutil
        shutil.copy2(first/'route_inputs.json',cache)
        shutil.copy2(first/'route_inputs.npz',folder/'route_inputs.npz')
    if cache.exists() and json.loads(cache.read_text()).get('preparation_version')==2:
        audit=json.loads(cache.read_text())
        assert audit['source_dataset']['dataset_id']==metadata['dataset_id']
        assert audit['geometry_sha256']==d.geometry_sha256 and audit['weather_manifest_sha256']==d.weather.sha256
        assert audit['cache_sha256']==digest(folder/'route_inputs.npz')
        with np.load(folder/'route_inputs.npz',allow_pickle=False) as z:a={k:z[k] for k in z.files}
    else:a,audit=prepare(d,folder)
    grids,areas,distances,area_audit=geometry(d)
    logits=np.zeros(3)
    names=['train','validation','test']; cohorts={}; initial_audit={}
    grid_fractions=np.array([.25,.5,.75])
    grid_logits=np.log(grid_fractions/(1-grid_fractions))
    robust={name:np.ones(len(a[name]),dtype=bool) for name in names}
    if args.speed_search=='robust-grid':
        for candidate in itertools.product(grid_logits,repeat=3):
            for part,name in enumerate(names):
                robust[name]&=align(a,a[name],np.array(candidate),part)['valid']
        print('Common cohorts across all 27 route-speed combinations:',{n:int(m.sum()) for n,m in robust.items()},flush=True)
    for part,name in enumerate(names):
        al=align(a,a[name],logits,part)
        initial_audit[name]={'prepared':len(a[name]),'matched':int(al['valid'].sum()),'invalid_reasons':al['invalid_reasons']}
        mask=al['valid']&robust[name]
        cohorts[name]=a[name][mask]
        initial_audit[name]['frozen_comparable_cohort']=int(mask.sum())
        if len(cohorts[name])<30:raise ValueError('Insufficient bounded route matches: '+name+' '+str(initial_audit[name]))
    write(folder/'alignment_readiness.json',{'audit':initial_audit,'route_fraction_initial':fractions(logits).tolist()})
    print('Frozen cohorts',initial_audit,flush=True)
    if args.prepare_only:return
    train_al=align(a,cohorts['train'],logits,0)
    center=train_al['context'].mean(0); scale=np.maximum(train_al['context'].std(0),1e-3)
    model=WeatherChain(grids,areas,distances,center,scale)
    ep=a['endpoint_values'][(a['endpoint_times']>=a['boundaries'][0])&(a['endpoint_times']<a['boundaries'][1])]
    label_scale=np.maximum(ep.std(0),[1.,.1])
    initial_metrics={name:score(model,align(a,cohorts[name],logits,i),label_scale)[1] for i,name in enumerate(names)}
    val_al=align(a,cohorts['validation'],logits,1)
    best=score(model,val_al,label_scale)[0]; selected=copy.deepcopy(model.state_dict()); best_logits=logits.copy()
    chosen=0; stale=0; history=[{'epoch':0,'validation_objective':best,'fractions':fractions(logits).tolist()}]
    optimizer=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=1e-4)
    rng=np.random.default_rng(42)
    speed_search=[]
    for epoch in range(1,args.epochs+1):
        # Coordinate proposals use only fixed training cohorts and endpoint loss.
        # Every block and all route parameters share the same endpoint objective.
        if epoch>1 and epoch%5==0:
            current=score(model,train_al,label_scale)[0]
            for k in range(3):
                candidates=[]
                proposals=grid_logits if args.speed_search=='robust-grid' else logits[k]+np.array([-.25,.25])
                for value in proposals:
                    candidate=logits.copy(); candidate[k]=value
                    al=align(a,cohorts['train'],candidate,0)
                    loss=score(model,al,label_scale)[0]
                    candidates.append((loss,candidate,al))
                loss,candidate,al=min(candidates,key=lambda x:x[0])
                accepted=loss<current-1e-7
                speed_search.append({'epoch':epoch,'station':SOURCES[k],'candidate_objective':loss,
                                     'prior_objective':current,'accepted':accepted})
                if accepted:current=loss;logits=candidate;train_al=al
            val_al=align(a,cohorts['validation'],logits,1)
        model.train(); order=rng.permutation(len(cohorts['train'])); total=0.
        for start in range(0,len(order),512):
            ids=order[start:start+512]
            state,delta=model(torch.tensor(train_al['initial'][ids],dtype=torch.float32),
                              torch.tensor(train_al['context'][ids],dtype=torch.float32))
            y=torch.tensor(train_al['labels'][ids],dtype=torch.float32)
            e=((state[:,-1,:2]-y)/torch.tensor(label_scale,dtype=torch.float32)).square().mean(1)
            loss=torch.where(torch.tensor(train_al['valid'][ids]),e,torch.full_like(e,1e6)).mean()+.001*delta.square().mean()
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optimizer.step()
            total+=float(loss.detach())*len(ids)
        val=score(model,val_al,label_scale)
        history.append({'epoch':epoch,'training_objective':total/len(order),'validation_objective':val[0],
                        'validation':val[1],'fractions':fractions(logits).tolist()})
        if val[0]<best-1e-7:
            best=val[0];selected=copy.deepcopy(model.state_dict());best_logits=logits.copy();chosen=epoch;stale=0
        else:stale+=1
        write(folder/'training_progress.json',{'history':history,'selected_epoch':chosen,'speed_search':speed_search})
        if epoch==1 or epoch%5==0:print('Epoch',epoch,'selected',chosen,'fractions',fractions(logits).tolist(),'validation',val[1],flush=True)
        if stale>=args.patience:break
    model.load_state_dict(selected);logits=best_logits
    metrics={}; full_metrics={}; speed_audits={}; saved=[]
    for part,name in enumerate(names):
        al=align(a,cohorts[name],logits,part); result=score(model,al,label_scale)
        metrics[name]=result[1]
        full=align(a,a[name],logits,part)
        full_metrics[name]={'metrics':score(model,full,label_scale)[1],'invalid_reasons':full['invalid_reasons']}
        speed_audits[name]={}
        for k,sid in enumerate(SOURCES):
            valid=al['valid'];v=al['speeds'][valid,k];caps=al['source_rows'][valid,k,3]
            assert np.all(v>0) and np.all(v<=caps)
            speed_audits[name][sid]={'estimated_speed_quantiles_m_s':np.quantile(v,[0,.5,.95,1]).tolist(),
                'cap_violations':int(np.sum(v>caps)), 'fraction_of_cap':float(fractions(logits)[k]),
                'transit_hours_quantiles':np.quantile(a['distances'][k]/v/3600,[0,.5,.95,1]).tolist()}
        if name=='test':
            for j,row in enumerate(cohorts[name]):
                state=result[2][j]; delay=al['common_arrivals'][j]-row[0]
                # The anchor path representative velocity supplies timing, not the
                # independently estimated local Q/A velocities of section states.
                p01_distance=next(r['distance_m'] for r in d.legs if r['source_node_id']=='05CB007')
                chainages=np.r_[p01_distance,p01_distance+np.cumsum([s['distance_m'] for s in d.segments[1:]])]
                saved.append({'forecast_origin_at':stamp(row[0]),'estimated_endpoint_arrival_at':stamp(al['common_arrivals'][j]),
                    'label_observed_at':stamp(al['label_times'][j]),'label_offset_seconds':float(al['label_times'][j]-al['common_arrivals'][j]),
                    'valid_match':bool(al['valid'][j]),'label_discharge_m3_s':float(al['labels'][j,0]),
                    'label_experimental_depth_m':float(al['labels'][j,1]),
                    'sources':[{'station_id':sid,'observed_at':stamp(al['source_rows'][j,k,0]),
                        'Q_m3_s':float(al['source_rows'][j,k,1]),'experimental_depth_m':float(al['source_rows'][j,k,2]),
                        'path_speed_estimated_m_s':float(al['speeds'][j,k]),'path_speed_cap_m_s':float(al['source_rows'][j,k,3]),
                        'minimum_valid_area_m2':float(al['source_rows'][j,k,4]),
                        'controlling_section_id':audit['sources'][sid]['sections'][int(al['source_rows'][j,k,5])],
                        'valid_area_section_count':int(al['source_rows'][j,k,6]),
                        'estimated_arrival_at':stamp(al['source_arrivals'][j,k]),
                        'alignment_offset_seconds':float(al['source_arrivals'][j,k]-al['common_arrivals'][j])} for k,sid in enumerate(SOURCES)],
                    'states':[{'node_id':s['output_node_id'],'Q_m3_s':float(v[0]),'experimental_depth_m':float(v[1]),
                        'area_m2':float(v[2]),'local_velocity_estimated_m_s':float(v[3]),
                        'estimated_arrival_at':stamp(row[0]+delay*chainages[i]/a['distances'][0])}
                        for i,(s,v) in enumerate(zip(d.segments,state))]})
    torch.save({'network':model.state_dict(),'route_logits':torch.tensor(logits)},folder/'model.pt')
    preserved=all(digest(WORKSPACE/path)==value for path,value in protected.items())
    assert preserved
    effective_policy={k:v for k,v in policy.items() if k not in ['feature_lag_initial_seconds','feature_lag_range_seconds','source_geometry_note','weather_note','note','max_transit_seconds']}
    effective_policy.update({'route_speed':'sigmoid(fitted_logit)*Q/min_valid_pre_confluence_A(observed_experimental_depth)',
        'fixed_24_hour_lag_used':False,'arrival':'source_observation_time+total_route_distance/estimated_path_speed',
        'maximum_transit_seconds':None,'partition_rule':'Every source, trend reference, lake feature and endpoint label stays in its temporal partition; arrivals must precede its upper boundary.',
        'alignment_anchor':'05CB007','nearest_tie':'later','source_alignment_tolerance_seconds':TOLERANCE,
        'route_parameters':'three fitted global route fractions, interleaved training-only coordinate search',
        'speed_search':args.speed_search,'candidate_route_fractions':grid_fractions.tolist() if args.speed_search=='robust-grid' else None,
        'lake_role':'past-only independent P04 level feature','05CC007_role':'aligned independent Q/stage/trend features; not direct discharge addition'})
    report={'model_type':'six_segment_weather_mlp_bounded_total_route','created_at':datetime.now(timezone.utc).isoformat(),
        'architecture':'Six 15-16-8-2 MLPs jointly supervised at 05CC002; three bounded route fractions fitted with interleaved training-only coordinate search.',
        'parameters':sum(p.numel() for p in model.parameters())+3,'policy':effective_policy,'seed':42,'torch_version':str(torch.__version__),
        'epochs_completed':epoch,'selected_epoch':chosen,'split':'chronological PostgreSQL 60/20/20 with original boundaries',
        'initial_alignment_audit':initial_audit,'initial_model_metrics':initial_metrics,'metrics':metrics,
        'all_prepared_origin_evaluation':full_metrics,'speed_constraint_audit':speed_audits,
        'route_fractions':dict(zip(SOURCES,fractions(logits).tolist())),'inputs':audit,'geometry':area_audit,
        'history':history,'speed_search':speed_search,'label_scales':label_scale.tolist(),
        'previous_artifacts_unchanged':preserved,'saved_model_sha256':digest(folder/'model.pt'),
        'runtime_seconds':time.perf_counter()-started,
        'limitations':['Observed gauge stage is experimental variable depth, not verified physical water depth.',
            'Source depth is transferred unchanged to pre-confluence sections only to form an independent experimental speed cap.',
            'Only valid available surveyed sections constrain the cap; coverage is incomplete and excluded sections are not inferred.',
            'Path representative speed is estimated, not API-measured velocity or validated flood-wave celerity.',
            'Discrete nearest-arrival matching is non-differentiable; three speed fractions use alternating coordinate search, not backpropagation.',
            'Arrival matching searches past departures within the same partition; missing matches remain missing.',
            'Robust-grid cohorts are valid under all 27 predeclared combinations; fractions are searched at 0.25, 0.5 and 0.75 of the cap, not over every possible continuous speed.',
            'The small common cohort is supplemented with all-prepared-origin coverage and error reports; neither guarantees coverage of all events.',
            'Intermediate section outputs remain unobserved and not uniquely identifiable from endpoint supervision.',
            'Previously inspected test period remains exploratory, not a new independent test.',
            'Retrospective observation-time inputs do not establish publication/receipt-time availability.',
            'New arrival times and cohorts mean old and new headline errors are not a controlled same-label comparison.']}
    write(folder/'training_report.json',report);write(folder/'test_predictions.json',saved)
    restored,loaded_logits,_=load_trained(folder)
    sample=align(a,cohorts['train'][:10],loaded_logits,0)
    assert np.array_equal(predict(model,sample),predict(restored,sample))
    report['reload_check']='bitwise_equal_on_10_training_inputs'
    write(folder/'training_report.json',report)
    write(DATA/'reports'/(folder.name.replace('segment_nn_weather','segment_nn_weather_training')+'.json'),report)
    print(json.dumps({'selected_epoch':chosen,'metrics':metrics,'route_fractions':report['route_fractions'],
                      'old_artifacts_unchanged':preserved},indent=2),flush=True)


if __name__=='__main__':main()
