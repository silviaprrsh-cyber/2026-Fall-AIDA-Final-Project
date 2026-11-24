"""Train only the weather-aware segmented neural main model on chronological views."""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from API.observations import parse_time
from project_paths import WORKSPACE
from rdr_eda.postgres import read_training_views
from .core import Dataset, Chain, numeric_pair
from .neural import WeatherChain, nearest_labels, error_metrics, checks

DATA=WORKSPACE/'courses/AIDA-2156/data'


def write(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')


def prepare(dataset, folder):
    """Keep source alignment, but do not screen inputs by intermediate baseline success."""
    policy=dataset.policy
    key=hashlib.sha256((dataset.sha256+dataset.geometry_sha256+json.dumps(policy,sort_keys=True)+
                       'neural_inputs_v1_guard_7days').encode()).hexdigest()
    npz=folder/'prepared_inputs.npz'
    manifest=folder/'prepared_inputs.json'
    if npz.exists() and manifest.exists():
        meta=json.loads(manifest.read_text())
        if meta['identity']==key and meta['npz_sha256']==hashlib.sha256(npz.read_bytes()).hexdigest():
            with np.load(npz,allow_pickle=False) as arrays:
                return {k:arrays[k] for k in arrays.files},meta
    endpoint=[r for r in dataset.index['05CC002'].rows if numeric_pair(r)]
    times=np.array([parse_time(r['observed_at']).timestamp() for r in endpoint],dtype=np.float64)
    values=np.array([[r['discharge_m3_s'],r['experimental_variable_depth_m']] for r in endpoint])
    order=np.argsort(times); times,values=times[order],values[order]
    if np.any(np.diff(times)<=0):raise ValueError('Endpoint times must be unique')
    parts={name:[parse_time(t) for t in dataset.partitions[name]] for name in ['train','validation','test']}
    boundaries=[parts['train'][0].timestamp(),parts['validation'][0].timestamp(),
                parts['test'][0].timestamp(),times[-1]+1]
    arrays={'endpoint_times':times,'endpoint_values':values,'boundaries':np.array(boundaries)}
    audit={}
    base=Chain(dataset)
    for j,(name,origins) in enumerate(parts.items()):
        records=[];excluded=Counter()
        for n,t in enumerate(origins):
            # Guard every possible label against crossing partition boundaries.
            if t.timestamp()+policy['max_transit_seconds']+policy['target_match_tolerance_seconds']>=boundaries[j+1]:
                excluded['seven_day_label_boundary_guard']+=1;continue
            r=base.predict(t)
            sources=[s for s in r['states'] if s.get('state_kind')=='source_geometry_adapter']
            if len(sources)!=2 or not r.get('feature_station') or not r.get('lake_feature') or not r['lake_feature'].get('level_m'):
                excluded[r['status']]+=1;continue
            if any(parse_time(s['observed_at'])>t for s in r['source_records']):
                raise ValueError('Future hydrometric input')
            if parse_time(r['weather_features']['latest_source_observed_at'])>t:
                raise ValueError('Future weather input')
            q=sum(s['discharge_m3_s'] for s in sources)
            h=sum(s['discharge_m3_s']*s['experimental_variable_depth_m'] for s in sources)/q
            v=sum(s['discharge_m3_s']*s['velocity_m_s'] for s in sources)/q
            delay=max(parse_time(s['estimated_arrival_at']).timestamp() for s in sources)-t.timestamp()
            wf=r['weather_features']['features']
            context=r['feature_station']['features']+[
                np.log1p(wf['precipitation_1h_mm']),np.log1p(wf['precipitation_6h_mm']),
                np.log1p(wf['precipitation_24h_mm']),wf['temperature_c'],r['lake_feature']['level_m']]
            records.append([t.timestamp(),q,h,v,delay,*context])
            if n and n%10000==0:print('Prepared',name,n,'of',len(origins),flush=True)
        if len(records)<30:raise ValueError('Insufficient neural inputs for '+name)
        arrays[name]=np.asarray(records,dtype=np.float64)
        audit[name]={'view_origins':len(origins),'prepared':len(records),'excluded':dict(excluded)}
        print('Input audit',name,audit[name],flush=True)
    np.savez_compressed(npz,**arrays)
    meta={'identity':key,'source_dataset_id':dataset.source_metadata['dataset_id'],
          'combined_input_sha256':dataset.sha256,'weather_manifest_sha256':dataset.weather.sha256,
          'geometry_sha256':dataset.geometry_sha256,'audit':audit,
          'npz_sha256':hashlib.sha256(npz.read_bytes()).hexdigest(),
          'input_context':['log1p_Q_05CC007','log1p_stage_05CC007','Q_trend_1h','stage_trend_1h',
                           'log1p_precip_1h','log1p_precip_6h','log1p_precip_24h','temperature_c','lake_level_m'],
          'source_alignment':'Existing branch adapters; fixed 24-hour 05CC007 lag, not learned by this MLP.',
          'splits':'Original PostgreSQL 60/20/20 boundaries; seven-day plus tolerance guard before each upper boundary.'}
    write(manifest,meta)
    return arrays,meta


def geometry(dataset):
    grids=[];areas=[];distances=[];audit=[]
    for i,s in enumerate(dataset.segments):
        profile=dataset.profiles[s['section_id']]
        cap=min(profile[0][1],profile[-1][1])-min(z for x,z in profile)
        if cap<=.02:raise ValueError('Insufficient surveyed depth range')
        grid=np.geomspace(.01,cap*.999,1024)
        area=np.array([dataset.area(s['section_id'],float(h)) for h in grid])
        samples=np.geomspace(.012,cap*.998,67)
        exact=np.array([dataset.area(s['section_id'],float(h)) for h in samples])
        error=np.max(np.abs(np.interp(samples,grid,area)-exact)/exact)
        if error>.05:raise ValueError('Area surrogate error exceeds 5 percent')
        grids.append(grid);areas.append(area);distances.append(s['distance_m'] or 0)
        audit.append({'node':s['output_node_id'],'section_id':s['section_id'],
                      'depth_cap_m':float(grid[-1]),'max_checked_relative_area_error':float(error)})
    return np.array(grids),np.array(areas),distances,audit


def predict_all(model,records,batch=2048):
    states=[]
    model.eval()
    with torch.no_grad():
        for lo in range(0,len(records),batch):
            r=records[lo:lo+batch]
            state,_=model(torch.tensor(r[:,1:5],dtype=torch.float32),torch.tensor(r[:,5:],dtype=torch.float32))
            states.append(state.numpy())
    return np.concatenate(states)


def score(model,records,arrays,part,label_scale):
    states=predict_all(model,records)
    labels,valid,stamps,offset=nearest_labels(records[:,0],states[:,-1,4],arrays['endpoint_times'],
        arrays['endpoint_values'],arrays['boundaries'][part],arrays['boundaries'][part+1])
    error=((states[:,-1,:2]-labels)/label_scale)**2
    objective=float(np.where(valid,np.mean(error,axis=1),1e6).mean())
    return objective,error_metrics(states[:,-1,:2],labels,valid),states,labels,valid,stamps,offset


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epochs',type=int,default=100)
    parser.add_argument('--patience',type=int,default=15)
    parser.add_argument('--batch-size',type=int,default=512)
    parser.add_argument('--output',type=Path,default=DATA/'processed/segment_nn_weather_60_20_20')
    parser.add_argument('--checks-only',action='store_true')
    args=parser.parse_args()
    torch.set_num_threads(2);torch.manual_seed(42);np.random.seed(42)
    torch.use_deterministic_algorithms(True)
    checks()
    if args.checks_only:return
    if min(args.epochs,args.patience,args.batch_size)<1:raise ValueError('Positive finite training bounds required')
    folder=args.output.resolve()
    if not folder.is_relative_to(DATA/'processed'):raise ValueError('Output outside processed data')
    folder.mkdir(parents=True,exist_ok=True)
    if (folder/'model.pt').exists():raise ValueError('Model already exists; select a new output directory')
    started=time.perf_counter()
    policy=json.loads((WORKSPACE/'shared-resources/config/segment_ml_weather.json').read_text())
    tables,parts,metadata=read_training_views(WORKSPACE/'shared-resources/config/postgres_dataset.json')
    dataset=Dataset(None,policy,tables=tables,partitions=parts,source_metadata=metadata)
    arrays,identity=prepare(dataset,folder)
    grids,areas,distances,area_audit=geometry(dataset)
    train=arrays['train'];validation=arrays['validation']
    center=train[:,5:].mean(0);scale=np.maximum(train[:,5:].std(0),1e-3)
    model=WeatherChain(grids,areas,distances,center,scale)
    # Label scales use training-period observations only, never validation/test values.
    train_endpoint=arrays['endpoint_values'][(arrays['endpoint_times']>=arrays['boundaries'][0]) &
                                            (arrays['endpoint_times']<arrays['boundaries'][1])]
    label_scale=np.maximum(train_endpoint.std(0),[1.,.1])
    # Freeze eligible origin cohorts with the initial model; failures remain in audits.
    cohorts={};initial_audit={}
    for part,name in enumerate(['train','validation','test']):
        initial=score(model,arrays[name],arrays,part,label_scale)
        cohorts[name]=arrays[name][initial[4]]
        initial_audit[name]=initial[1]
        if len(cohorts[name])<30:raise ValueError('Too few arrival-matched origins: '+name)
    train,validation=cohorts['train'],cohorts['validation']
    best=score(model,validation,arrays,1,label_scale)[0]
    selected=copy.deepcopy(model.state_dict());selected_epoch=0;stale=0
    history=[{'epoch':0,'validation_objective':best}]
    optimizer=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=1e-4)
    rng=np.random.default_rng(42)
    print('Training six weather-aware MLPs jointly:',{k:len(v) for k,v in cohorts.items()},flush=True)
    for epoch in range(1,args.epochs+1):
        model.train();order=rng.permutation(len(train));loss_sum=0.
        for start in range(0,len(order),args.batch_size):
            rows=train[order[start:start+args.batch_size]]
            state,delta=model(torch.tensor(rows[:,1:5],dtype=torch.float32),torch.tensor(rows[:,5:],dtype=torch.float32))
            labels,valid,_,_=nearest_labels(rows[:,0],state[:,-1,4].detach().numpy(),arrays['endpoint_times'],
                arrays['endpoint_values'],arrays['boundaries'][0],arrays['boundaries'][1])
            y=torch.tensor(labels,dtype=torch.float32)
            squared=((state[:,-1,:2]-y)/torch.tensor(label_scale,dtype=torch.float32)).square().mean(1)
            # Fixed denominator and a large invalid-label penalty prevent silently dropping hard cases.
            loss=torch.where(torch.tensor(valid),squared,torch.full_like(squared,1e6)).mean()
            loss=loss+.001*delta.square().mean()+.01*torch.relu(state[:,-1,4]/604800-1).square().mean()
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.)
            optimizer.step();loss_sum+=float(loss.detach())*len(rows)
        val=score(model,validation,arrays,1,label_scale)
        record={'epoch':epoch,'training_objective':loss_sum/len(train),
                'validation_objective':val[0],'validation':val[1]}
        history.append(record)
        if val[0]<best-1e-7:
            best=val[0];selected=copy.deepcopy(model.state_dict());selected_epoch=epoch;stale=0
        else:stale+=1
        if epoch==1 or epoch%5==0:print('Epoch',epoch,'validation',val[1],'selected',selected_epoch,flush=True)
        write(folder/'training_progress.json',{'history':history,'selected_epoch':selected_epoch})
        if stale>=args.patience:break
    model.load_state_dict(selected)
    outputs={};saved=[]
    for part,name in enumerate(['train','validation','test']):
        result=score(model,cohorts[name],arrays,part,label_scale)
        outputs[name]=result[1]
        if name=='test':
            for row,states,labels,valid,stamp,offset in zip(cohorts[name],*result[2:]):
                saved.append({'forecast_origin_at':datetime.fromtimestamp(row[0],timezone.utc).isoformat(),
                    'label_observed_at':datetime.fromtimestamp(stamp,timezone.utc).isoformat(),
                    'label_offset_seconds':float(offset),'valid_match':bool(valid),
                    'label_discharge_m3_s':float(labels[0]),'label_experimental_depth_m':float(labels[1]),
                    'states':[{'node_id':s['output_node_id'],'Q_m3_s':float(v[0]),'experimental_depth_m':float(v[1]),
                               'area_m2':float(v[2]),'velocity_m_s':float(v[3]),'arrival_delay_seconds':float(v[4])}
                              for s,v in zip(dataset.segments,states)]})
    torch.save(model.state_dict(),folder/'model.pt')
    restored=WeatherChain(grids,areas,distances,center,scale)
    restored.load_state_dict(torch.load(folder/'model.pt',map_location='cpu',weights_only=True))
    assert np.array_equal(predict_all(model,train[:10]),predict_all(restored,train[:10]))
    report={'model_type':'six_segment_weather_mlp_joint_endpoint','created_at':datetime.now(timezone.utc).isoformat(),
        'architecture':'Six independent 15-16-8-2 Tanh MLPs; recursive Q/depth, Q/A velocity, L/V travel time.',
        'parameters':sum(p.numel() for p in model.parameters()),'optimizer':'Adam','learning_rate':.001,
        'seed':42,'cpu_threads':2,'torch_version':str(torch.__version__),'epochs_completed':epoch,'selected_epoch':selected_epoch,
        'maximum_epochs':args.epochs,'early_stopping_patience':args.patience,'batch_size':args.batch_size,
        'inputs':identity,'policy':policy,'geometry':area_audit,'normalization_center':center.tolist(),
        'normalization_scale':scale.tolist(),'label_scales':label_scale.tolist(),'initial_model_cohort_metrics':initial_audit,
        'metrics':outputs,'history':history,'runtime_seconds':time.perf_counter()-started,
        'saved_model_sha256':hashlib.sha256((folder/'model.pt').read_bytes()).hexdigest(),'reload_check':'bitwise_equal_on_10_training_inputs',
        'limitations':['Gauge stage remains experimental variable depth; datum equivalence is not verified.',
            'Only endpoint supervision; intermediate states are not identifiable or independently validated.',
            'Discrete nearest-arrival labels are reassigned with stop-gradient each step, not differentiated.',
            'Stage is bounded by available surveyed section edges; no extrapolated flood-risk classifications.',
            'Fixed source branch alignment and 24-hour 05CC007 feature lag; not jointly learned.',
            'Point weather is not areal rainfall; only origin-available historical windows are used.',
            'The previously inspected test period is exploratory, not a new untouched test.',
            'Guarded and baseline-eligible cohorts differ from old random-search reports; raw metrics are not a controlled cross-model comparison.']}
    write(folder/'training_report.json',report)
    write(folder/'test_predictions.json',saved)
    write(DATA/'reports/segment_nn_weather_training_60_20_20.json',report)
    print(json.dumps({'selected_epoch':selected_epoch,'epochs_completed':epoch,'metrics':outputs,
                      'report':'courses/AIDA-2156/data/reports/segment_nn_weather_training_60_20_20.json'},indent=2),flush=True)


if __name__=='__main__':main()
