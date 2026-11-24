"""Independent non-saturating flow-residual model with training-only tail weights.

Routes and chronological split are frozen from the train-only route experiment.
No test values enter fitting, threshold/scaling estimation or checkpoint selection.
Architecture was designed after prior test inspection; evaluation is retrospective.
"""
import argparse
import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from project_paths import WORKSPACE
from .neural import WeatherChain, error_metrics
from .route_neural import digest, predict, SOURCES
from .route_frozen import (DATA, DEFAULT_CACHE, align_period, audit_context, load_frozen,
    metrics_with_baselines, protected_inventory, reported_metrics, timestamp, write)

BASE = DATA / 'processed/segment_nn_weather_frozen_v1_20261110'


def raw_context(context):
    """Undo log compression for source discharge/stage and precipitation only."""
    out = context.clone() if torch.is_tensor(context) else np.array(context, copy=True)
    for k in [0, 1, 4, 5, 6]:
        out[..., k] = torch.expm1(context[..., k]) if torch.is_tensor(context) else np.expm1(context[..., k])
    return out


class TailChain(WeatherChain):
    def __init__(self, depths, areas, distances, center, scale, q_scale):
        super().__init__(depths, areas, distances, center, scale)
        self.register_buffer('q_scale', torch.tensor(float(q_scale), dtype=torch.float32))
        self.blocks = nn.ModuleList([nn.Sequential(nn.Linear(15,24),nn.SiLU(),
            nn.Linear(24,12),nn.SiLU(),nn.Linear(12,2)) for _ in range(6)])
        self.skips = nn.ModuleList([nn.Linear(15,2) for _ in range(6)])
        for block,skip in zip(self.blocks,self.skips):
            nn.init.zeros_(block[-1].weight); nn.init.zeros_(block[-1].bias)
            nn.init.zeros_(skip.weight); nn.init.zeros_(skip.bias)

    def forward(self, initial, context):
        q,h,velocity,elapsed=initial.unbind(1)
        # No fixed +-8 feature clamp, Tanh output cap, or exponential flow multiplier.
        z=(raw_context(context)-self.center)/self.scale
        states=[];corrections=[]
        for i,(block,skip) in enumerate(zip(self.blocks,self.skips)):
            if i:
                elapsed=elapsed+self.distances[i]/velocity.clamp_min(1e-5)
            lo,hi=self.depths[i,0],self.depths[i,-1]
            incoming_area=self.area(i,h)
            local=z.clone()
            if i!=0: local[:,:4]=0
            if i!=3: local[:,8]=0
            state=torch.stack([q/self.q_scale,h,velocity/5,
                torch.ones_like(q)*self.distances[i]/10000,
                incoming_area/1000,torch.ones_like(q)*hi/10],1)
            x=torch.cat([state,local],1)
            delta=skip(x)+.1*block(x)
            q=F.softplus(q+self.q_scale*delta[:,0])+1e-6
            ratio=((h-lo)/(hi-lo)).clamp(.001,.999)
            h=lo+(hi-lo)*torch.sigmoid(torch.logit(ratio)+delta[:,1])
            area=self.area(i,h);velocity=q/area.clamp_min(1e-6)
            states.append(torch.stack([q,h,area,velocity,elapsed],1));corrections.append(delta)
        return torch.stack(states,1),torch.stack(corrections,1)


def tail_weights(labels, threshold):
    """Symmetric high-flow emphasis, never an automatic upward prediction bias."""
    if torch.is_tensor(labels):
        return 1.+4.*(labels[:,0]>=threshold).to(labels.dtype)
    return 1.+4.*(np.asarray(labels)[:,0]>=threshold)


def objective(model, aligned, scales, threshold):
    valid=aligned['valid'];labels=aligned['labels'][valid]
    predictions=predict(model,aligned)[valid,-1,:2]
    e=np.mean(((predictions-labels)/scales)**2,axis=1)
    w=tail_weights(labels,threshold)
    return float(np.sum(w*e)/np.sum(w))


def train_tail(model, train, validation, scales, threshold, epochs, patience):
    ids=np.flatnonzero(train['valid']);rng=np.random.default_rng(42)
    optimizer=torch.optim.Adam(model.parameters(),lr=.0005,weight_decay=1e-4)
    scale=torch.tensor(scales,dtype=torch.float32)
    best=objective(model,validation,scales,threshold);chosen=0;stale=0
    selected=copy.deepcopy(model.state_dict());history=[{'epoch':0,'validation_weighted_objective':best}]
    for epoch in range(1,epochs+1):
        model.train();order=rng.permutation(ids);numerator=0.;denominator=0.
        for start in range(0,len(order),512):
            j=order[start:start+512]
            states,delta=model(torch.tensor(train['initial'][j],dtype=torch.float32),
                torch.tensor(train['context'][j],dtype=torch.float32))
            y=torch.tensor(train['labels'][j],dtype=torch.float32);w=tail_weights(y,threshold)
            e=((states[:,-1,:2]-y)/scale).square().mean(1)
            loss=(w*e).sum()/w.sum()+.0001*delta.square().mean()
            if not torch.isfinite(loss):raise ValueError('Nonfinite training loss')
            optimizer.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);optimizer.step()
            numerator+=float((w*e).sum().detach());denominator+=float(w.sum())
        val=objective(model,validation,scales,threshold)
        history.append({'epoch':epoch,'training_weighted_objective':numerator/denominator,'validation_weighted_objective':val})
        if val<best-1e-7:
            best=val;chosen=epoch;selected=copy.deepcopy(model.state_dict());stale=0
        else:stale+=1
        if epoch==1 or epoch%5==0:print('Tail epoch',epoch,'selected',chosen,'validation',val,flush=True)
        if stale>=patience:break
    model.load_state_dict(selected);model.eval()
    return history,chosen


def signed_metrics(states, aligned, mask, population=None):
    if population is None: population=np.ones(len(mask),dtype=bool)
    mask=mask&population
    result=reported_metrics(states[population,-1,:2],aligned['labels'][population],mask[population])
    for i,name in enumerate(['discharge','variable_depth']):
        e=states[mask,-1,i]-aligned['labels'][mask,i]
        result[name]['over_count']=int((e>0).sum());result[name]['under_count']=int((e<0).sum())
        result[name]['under_fraction']=float((e<0).mean()) if len(e) else None
    return result


def load_tail(folder):
    folder=Path(folder);report=json.loads((folder/'training_report.json').read_text())
    if report['model_type']!='six_segment_nonsaturating_tail_weighted':raise ValueError('Wrong model type')
    if digest(folder/'model.pt')!=report['saved_model_sha256']:raise ValueError('Checkpoint checksum mismatch')
    saved=torch.load(folder/'model.pt',map_location='cpu',weights_only=True);w=saved['network']
    model=TailChain(w['depths'],w['areas'],w['distances'],w['center'],w['scale'],float(w['q_scale']))
    model.load_state_dict(w);model.eval()
    return model,saved['route_logits'].numpy(),report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base',type=Path,default=BASE);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--epochs',type=int,default=150);parser.add_argument('--patience',type=int,default=25)
    args=parser.parse_args();folder=args.output.resolve();base=args.base.resolve()
    if min(args.epochs,args.patience)<1:raise ValueError('Finite positive run bounds required')
    if not folder.is_relative_to((DATA/'processed').resolve()) or not base.is_relative_to((DATA/'processed').resolve()):raise ValueError('Use local processed directories')
    if folder.exists():raise ValueError('Never overwrite an experiment')
    old,logits,previous=load_frozen(base)
    input_audit=json.loads((base/'input_audit.json').read_text());cache=(WORKSPACE/input_audit['cache']).resolve()
    if not cache.is_relative_to((DATA/'processed').resolve()):raise ValueError('Unexpected cache path')
    if digest(cache/'route_inputs.npz')!=input_audit['cache_sha256']:raise ValueError('Cache checksum mismatch')
    arrays=dict(np.load(cache/'route_inputs.npz',allow_pickle=False))
    seeds=np.concatenate([arrays[n] for n in ['train','validation','test']]);seeds=seeds[np.argsort(seeds[:,0])]
    if np.any(np.diff(seeds[:,0])<=0):raise ValueError('Repeated origins')
    bounds=[timestamp(x) for x in previous['boundaries_utc']]
    partitions={n:seeds[(seeds[:,0]>=bounds[i])&(seeds[:,0]<bounds[i+1])] for i,n in enumerate(['train','validation','test'])}
    policy=json.loads((WORKSPACE/'shared-resources/config/segment_ml_weather.json').read_text())
    provenance=audit_context(seeds,policy)
    manifest=json.loads((cache/'route_inputs.json').read_text())
    if provenance['weather_manifest_sha256']!=manifest['weather_manifest_sha256']:raise ValueError('Weather identity mismatch')
    protected=protected_inventory();folder.mkdir(exist_ok=False)
    write(folder/'previous_artifacts.json',protected)
    (folder/'training_source.py').write_text(Path(__file__).read_text(),encoding='utf-8')
    write(folder/'implementation_manifest.json',{str(p.relative_to(WORKSPACE)):digest(p) for p in
        [Path(__file__),Path(__file__).with_name('route_frozen.py'),Path(__file__).with_name('route_neural.py'),Path(__file__).with_name('neural.py')]})
    # Only training and validation are aligned before checkpoint selection.
    aligned={n:align_period(arrays,partitions[n],logits,bounds[i],bounds[i+1]) for i,n in enumerate(['train','validation'])}
    train=aligned['train'];valid=train['valid'];labels=train['labels'][valid]
    threshold=float(np.quantile(labels[:,0],.9));scales=np.maximum(labels.std(0),[1.,.1])
    raw=raw_context(train['context'][valid]);center=raw.mean(0);scale=np.maximum(raw.std(0),1e-3)
    torch.set_num_threads(2);torch.manual_seed(42);torch.use_deterministic_algorithms(True)
    model=TailChain(old.depths,old.areas,old.distances,center,scale,scales[0])
    protocol={'tail_threshold_training_Q90':threshold,'tail_weight':5.,'other_weight':1.,
        'scales_training_only':scales.tolist(),'learning_rate':.0005,'epochs_limit':args.epochs,'patience':args.patience,
        'route_fractions_frozen':previous['route_fractions'],'boundaries_utc':previous['boundaries_utc'],
        'selection':'validation weighted MSE, using threshold and scales fitted only on training',
        'base_validation_same_objective':objective(old,aligned['validation'],scales,threshold),
        'test_used_for_selection':False,'publication_time_verified':False}
    write(folder/'protocol_before_test.json',protocol)
    history,selected=train_tail(model,train,aligned['validation'],scales,threshold,args.epochs,args.patience)
    torch.save({'network':model.state_dict(),'route_logits':torch.tensor(logits)},folder/'model.pt')
    write(folder/'checkpoint_selection_before_test.json',{'selected_epoch':selected,'history':history,'model_sha256':digest(folder/'model.pt')})
    aligned['test']=align_period(arrays,partitions['test'],logits,bounds[2],bounds[3])
    results={};states={}
    for n,al in aligned.items():
        states[n]=predict(model,al);results[n]=metrics_with_baselines(arrays,al,states[n])
    test=aligned['test'];old_states=predict(old,test);v=test['valid'];comparison={}
    for name,population in [('all',np.ones(len(v),bool)),('Q_ge100',test['labels'][:,0]>=100),('Q_ge200',test['labels'][:,0]>=200)]:
        mask=v&population
        comparison[name]={'new':signed_metrics(states['test'],test,mask,population),'v1':signed_metrics(old_states,test,mask,population)}
    report={'model_type':'six_segment_nonsaturating_tail_weighted','created_at':datetime.now(timezone.utc).isoformat(),
        'architecture':'six SiLU residual blocks with explicit raw-flow linear skips and positive unbounded flow outputs; surveyed depth limits retained',
        'parameters':sum(p.numel() for p in model.parameters()),'epochs_completed':len(history)-1,'selected_epoch':selected,
        'protocol':protocol,'route_fractions':previous['route_fractions'],'metrics':results,'same_route_same_target_v1_comparison':comparison,
        'history':history,'saved_model_sha256':digest(folder/'model.pt'),'context_verification':provenance,
        'limitations':['Architecture is designed after prior retrospective test inspection; this is not a fresh blind test.',
            f'Train Q max is {labels[:,0].max():g} m3/s; validation Q max is {aligned["validation"]["labels"][aligned["validation"]["valid"],0].max():g}; larger flows are unsupported extrapolation.',
            'No future or endpoint-current observations were added as network inputs.',
            'Routes and unverified physical stage/area assumptions remain from v1.',
            'Tail weighting is symmetric, not a guaranteed removal of underprediction.',
            'No operational flood-warning validity or independent intermediate-section accuracy is established.']}
    if not all(digest(WORKSPACE/path)==sha for path,sha in protected.items()):raise AssertionError('Old artifacts changed')
    report['old_artifacts_unchanged']=True
    write(folder/'training_report.json',report)
    restored,rl,_=load_tail(folder)
    sample=align_period(arrays,partitions['train'][:10],logits,bounds[0],bounds[1])
    if not np.array_equal(predict(model,sample),predict(restored,sample)):raise AssertionError('Model reload differs')
    if not np.array_equal(rl,logits):raise AssertionError('Route reload differs')
    np.savez_compressed(folder/'test_predictions.npz',origins=test['origins'],label_times=test['label_times'],labels=test['labels'],
        valid=v,states=states['test'],source_times=test['source_rows'][:,:,0])
    write(folder/'verification.json',{'reload_exact':True,'old_artifacts_unchanged':True,'protected_count':len(protected),
        'checkpoint_saved_before_test_evaluation':True,'source_sha256':digest(Path(__file__))})
    print(json.dumps({'selected_epoch':selected,'epochs_completed':len(history)-1,'test':results['test']['model'],'comparison':comparison}),flush=True)


if __name__=='__main__':main()
