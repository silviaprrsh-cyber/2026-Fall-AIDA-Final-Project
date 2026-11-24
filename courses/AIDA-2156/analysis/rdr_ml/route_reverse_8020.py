"""Retrospective reverse-time 80/20 experiment on an isolated matched population."""
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


def refit(model,a,scales,epochs):
    rng=np.random.default_rng(42);opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=1e-4)
    ids=np.flatnonzero(a['valid']);history=[]
    for epoch in range(1,epochs+1):
        model.train();order=rng.permutation(ids);total=0.
        for i in range(0,len(order),512):
            ix=order[i:i+512];states,delta=model(torch.tensor(a['initial'][ix],dtype=torch.float32),torch.tensor(a['context'][ix],dtype=torch.float32))
            loss=((states[:,-1,:2]-torch.tensor(a['labels'][ix],dtype=torch.float32))/torch.tensor(scales,dtype=torch.float32)).square().mean()+.001*delta.square().mean()
            opt.zero_grad();loss.backward();torch.nn.utils.clip_grad_norm_(model.parameters(),5.);opt.step();total+=float(loss.detach())*len(ix)
        history.append({'epoch':epoch,'training_objective':total/len(ids)})
        if epoch==1 or epoch%5==0:print('Full80 refit',epoch,flush=True)
    model.eval();return history


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();folder=args.output.resolve()
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
    a=strict_align(arrays,seeds,logits,float(arrays['boundaries'][0]),float(arrays['boundaries'][-1]))
    tm,em,split=isolated_split(a);train=subset(a,tm);test=subset(a,em)
    if train['labels'][:,0].max()!=284:raise ValueError('Training peak absent')
    cut=float(train['origins'][int(.8*len(train['valid']))]);fm=(train['origins']<cut)&(train['label_times']<cut)&(train['common_arrivals']<cut);vm=(train['origins']>=cut)&(train['label_times']>=cut)
    fit=subset(train,fm);val=subset(train,vm)
    if min(len(fit['valid']),len(val['valid']))<30:raise ValueError('Too few inner samples')
    protected=protected_inventory();folder.mkdir();write(folder/'previous_artifacts.json',protected)
    protocol={'split':split,'route_fractions':fs.tolist(),'architecture':'fresh original V1 WeatherChain',
        'inner_fit':population_summary(fit),'inner_validation':population_summary(val),'inner_boundary_utc':iso(cut),
        'inner_boundary_purged':int(len(train['valid'])-fm.sum()-vm.sum()),
        'final_train':population_summary(train),'final_test':population_summary(test),
        'selection':'max100 epochs/patience20 on internal validation; fresh refit full80 for selected epoch count; test prediction errors evaluated once afterward; population ranges inspected before fitting',
        'limitations':['Retrospective reverse-time transfer, not future forecasting. Historical test previously inspected.',
            '80/20 is the final isolated matched population, not all raw observations. Source windows can exclude many rows.',
            'The route is reused from a later training-only calibration; no new test labels select route or stopping epoch.',
            'Internal validation is used for epoch tuning, not independent performance evidence: the reused route was selected on overlapping development-period labels.',
            'Current endpoint persistence uses an extra input unavailable to the network.']}
    write(folder/'protocol_before_test.json',protocol);(folder/'training_source.py').write_text(Path(__file__).read_text(),encoding='utf-8')
    print('Protocol',json.dumps(protocol),flush=True);torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    geometry=torch.load(DEFAULT_CACHE/'model.pt',map_location='cpu',weights_only=True)['network'];model=new_model(geometry,fit)
    history,chosen=fit_network(model,fit,val,np.maximum(fit['labels'].std(0),[1.,.1]),100,20)
    write(folder/'epoch_selection_before_test.json',{'selected_epoch':chosen,'history':history})
    model=new_model(geometry,train);refit_history=refit(model,train,np.maximum(train['labels'].std(0),[1.,.1]),chosen)
    torch.save({'network':model.state_dict(),'route_logits':torch.tensor(logits)},folder/'model.pt')
    write(folder/'checkpoint_before_test.json',{'sha256':digest(folder/'model.pt'),'selected_epoch':chosen})
    results={};peak_rows={}
    for name,part in [('train',train),('test',test)]:
        states=predict(model,part);results[name]=metrics_with_baselines(arrays,part,states);q=part['labels'][:,0];err=states[:,-1,0]-q
        results[name]['signed_high_flow']={str(t):{'n':int((q>=t).sum()),'bias':float(err[q>=t].mean()) if (q>=t).any() else None,'mae':float(abs(err[q>=t]).mean()) if (q>=t).any() else None,'under_fraction':float((err[q>=t]<0).mean()) if (q>=t).any() else None} for t in [100,140,200]}
        ix=np.flatnonzero(q==q.max());peak_rows[name]=[{'time':iso(part['label_times'][i]),'observed':part['labels'][i].tolist(),'predicted':states[i,-1,:2].tolist()} for i in ix]
        np.savez_compressed(folder/(name+'_predictions.npz'),origins=part['origins'],label_times=part['label_times'],labels=part['labels'],states=states,source_times=part['source_rows'][:,:,0])
    ck=torch.load(folder/'model.pt',map_location='cpu',weights_only=True);restored=new_model(geometry,train);restored.load_state_dict(ck['network']);restored.eval()
    sample=subset(train,np.arange(len(train['valid']))<32);assert np.array_equal(predict(model,sample),predict(restored,sample))
    assert all(digest(WORKSPACE/k)==sha for k,sha in protected.items())
    report={'model_type':'reverse_v1_matched_80_20','created_at':datetime.now(timezone.utc).isoformat(),'protocol':protocol,'selected_epoch':chosen,'selection_history':history,'refit_history':refit_history,'metrics':results,'peak_rows':peak_rows,'saved_model_sha256':digest(folder/'model.pt'),'context_verification':provenance}
    write(folder/'training_report.json',report);write(folder/'verification.json',{'reload_exact':True,'old_artifacts_unchanged':True,'protected_count':len(protected),'achieved_development_fraction':len(train['valid'])/(len(train['valid'])+len(test['valid'])),'source_sha256':digest(Path(__file__))})
    print(json.dumps({'selected_epoch':chosen,'metrics':{n:x['model'] for n,x in results.items()},'high_flow':{n:x['signed_high_flow'] for n,x in results.items()},'peak_rows':peak_rows}),flush=True)

if __name__=='__main__':main()
