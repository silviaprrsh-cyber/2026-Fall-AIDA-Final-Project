"""CPU CNN segmentation experiment using screened automatic point-mask labels."""
import argparse
from collections import Counter
import csv
from datetime import date
import hashlib
import json
import random
import time
import numpy as np
import rasterio
import torch
from torch import nn
from PIL import Image, ImageDraw
from cv_tools.make_point_water_masks import OUT as MASKS, WORKSPACE, BASE, sha

OUT=BASE/'data/processed/point_cnn_20261113'
CONFIG=dict(seed=42,epochs=40,batch_size=16,learning_rate=0.001,patience=10,cpu_threads=4,
            checkpoint='strictly_lower_validation_loss',threshold=0.5,
            split='chronological_acquisition_dates_70_15_15_with_7_day_boundary_gap',
            labels='screened_automatic_candidates_not_human_ground_truth',channels=['red','green','blue','nir'])

def save(name,data):
    (OUT/name).write_text(json.dumps(data,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    source=json.loads((MASKS/'full_manifest.json').read_text())
    queue={r['id']:r for r in csv.DictReader((MASKS/'review_queue.csv').open())}
    retained={}; rejected=Counter(); cache={}
    for r in source['records']:
        if queue[r['id']]['priority_reasons']:rejected['priority_review']+=1;continue
        path=WORKSPACE/r['source']
        with rasterio.open(MASKS/r['mask']) as m, rasterio.open(path) as ds:
            win=rasterio.windows.from_bounds(*m.bounds,transform=ds.transform).round_offsets().round_lengths()
            a=ds.read(window=win);y=m.read(1)
            assert a.shape==(6,61,61) and m.transform==ds.window_transform(win)
        unreliable=np.isin(a[4],[0,1,3,8,9,10,11])|(a[5]!=1)|(y==255)
        y[unreliable]=255
        if unreliable.mean()>0.10:rejected['unreliable_pixels_over_10_percent']+=1;continue
        if not (y==1).any():rejected['empty_water']+=1;continue
        key=(r['point_id'],r['date'][:10]);x=np.clip(a[:4].astype('float32')/10000,0,1)
        crop_hash=hashlib.sha256(x.tobytes()).hexdigest()
        item=dict(r,crop_sha256=crop_hash,mask_sha256=sha(MASKS/r['mask']))
        if key not in retained or r['source']<retained[key][0]['source']:retained[key]=(item,x,y.astype('float32'))
    data=sorted(retained.values(),key=lambda a:(a[0]['date'],a[0]['point_id']))
    days=sorted({r[0]['date'][:10] for r in data}); n=len(days)
    if n<20:raise ValueError('Too few independent acquisition dates')
    b1=days[int(n*.70)];b2=days[int(n*.85)]
    records=[];xs=[];ys=[];hash_splits={};purged=0
    for r,x,y in data:
        day=r['date'][:10]
        if any(abs((date.fromisoformat(day)-date.fromisoformat(b)).days)<7 for b in [b1,b2]):purged+=1;continue
        split='train' if day<b1 else 'validation' if day<b2 else 'test'
        if r['crop_sha256'] in hash_splits and hash_splits[r['crop_sha256']]!=split:
            rejected['identical_pixels_across_splits']+=1;continue
        if (r['point_id'],day) in {('05CC007','2026-11-04'),('05CC007','2026-10-30')}:
            rejected['visually_confirmed_false_expansion']+=1;continue
        hash_splits[r['crop_sha256']]=split
        records.append(dict(r,split=split));xs.append(x);ys.append(y)
    x=np.stack(xs);y=np.stack(ys)
    for s in ['train','validation','test']:
        if sum(r['split']==s for r in records)<10:raise ValueError('Insufficient split '+s)
    groups={s:{r['date'][:10] for r in records if r['split']==s} for s in ['train','validation','test']}
    assert not(groups['train']&groups['validation'] or groups['train']&groups['test'] or groups['test']&groups['validation'])
    np.savez_compressed(OUT/'dataset.npz',x=x,y=y)
    save('dataset_manifest.json',dict(records=records,config=CONFIG,rejected=dict(rejected),purged_boundary_samples=purged,input_manifest_sha256=sha(MASKS/'full_manifest.json'),boundaries=[b1,b2]))
    summary=dict(samples=len(records),before_date_dedup=sum(1 for r in source['records'] if not queue[r['id']]['priority_reasons']),split_counts=dict(Counter(r['split'] for r in records)),date_counts={s:len(g) for s,g in groups.items()},date_ranges={s:[min(g),max(g)] for s,g in groups.items()},point_counts=dict(Counter(r['point_id'] for r in records)),rejected=dict(rejected),purged_boundary_samples=purged,label_type=CONFIG['labels'],ignored_pixel_count=int((y==255).sum()))
    save('selection_summary.json',summary)
    chosen=[]
    for point in sorted({r['point_id'] for r in records}):
        ids=[i for i,r in enumerate(records) if r['point_id']==point]
        chosen.extend([ids[0],ids[-1]])
    sheet=Image.new('RGB',(1500,310*((len(chosen)+1)//2)),'white')
    for k,i in enumerate(chosen):sheet.paste(Image.open(MASKS/records[i]['preview']),((k%2)*750,(k//2)*310))
    sheet.save(OUT/'selection_review.png')
    print(json.dumps(summary,indent=2),flush=True)

# Compatibility export: all existing callers share the canonical model.
from cv_tools.model import SmallSegCNN


def metrics(y,p):
    tp=int(((y==1)&p).sum());fp=int(((y==0)&p).sum());fn=int(((y==1)&~p).sum());tn=int(((y==0)&~p).sum())
    return dict(TP=tp,FP=fp,FN=fn,TN=tn,IoU=tp/max(tp+fp+fn,1),precision=tp/max(tp+fp,1),recall=tp/max(tp+fn,1))

def train():
    start=time.perf_counter();torch.set_num_threads(CONFIG['cpu_threads']);torch.manual_seed(CONFIG['seed']);random.seed(CONFIG['seed']);np.random.seed(CONFIG['seed']);torch.use_deterministic_algorithms(True)
    manifest=json.loads((OUT/'dataset_manifest.json').read_text());records=manifest['records'];d=np.load(OUT/'dataset.npz');x=torch.from_numpy(d['x']);y=torch.from_numpy(d['y'])
    indices={s:torch.tensor([i for i,r in enumerate(records) if r['split']==s]) for s in ['train','validation','test']}
    train_pixels=x[indices['train']].permute(0,2,3,1)[y[indices['train']]!=255]
    mean=train_pixels.mean(dim=0).view(1,4,1,1);std=train_pixels.std(dim=0).clamp_min(.01).view(1,4,1,1);x=(x-mean)/std
    x=x*(y!=255).unsqueeze(1)
    positives=(y[indices['train']]==1).sum();negatives=(y[indices['train']]==0).sum();weight=(negatives/positives).clamp(1,10)
    criterion=nn.BCEWithLogitsLoss(pos_weight=weight,reduction='none')
    def lossfn(logits,target):
        valid=target!=255
        return (criterion(logits,target.clamp(0,1))*valid).sum()/valid.sum().clamp_min(1)
    model=SmallSegCNN();optimizer=torch.optim.Adam(model.parameters(),lr=CONFIG['learning_rate'])
    best=float('inf');best_epoch=0;history=[]
    for epoch in range(1,CONFIG['epochs']+1):
        model.train();order=indices['train'][torch.randperm(len(indices['train']))];total=0
        for batch in order.split(CONFIG['batch_size']):
            xx=x[batch];yy=y[batch]
            if random.random()<.5:xx=xx.flip(-1);yy=yy.flip(-1)
            if random.random()<.5:xx=xx.flip(-2);yy=yy.flip(-2)
            optimizer.zero_grad();loss=lossfn(model(xx),yy);loss.backward();optimizer.step();total+=float(loss.detach())*len(batch)
        model.eval();v=0
        with torch.no_grad():
            for batch in indices['validation'].split(CONFIG['batch_size']):v+=float(lossfn(model(x[batch]),y[batch]))*len(batch)
        v/=len(indices['validation']);improved=v<best
        if improved:
            best=v;best_epoch=epoch;torch.save(dict(state_dict=model.state_dict(),mean=mean,std=std,config=CONFIG,epoch=epoch,validation_loss=v),OUT/'best_model.pt')
        history.append(dict(epoch=epoch,train_loss=total/len(order),validation_loss=v,saved=improved));save('training_history.json',history)
        print(json.dumps(history[-1]),flush=True)
        if epoch-best_epoch>=CONFIG['patience']:break
    checkpoint=torch.load(OUT/'best_model.pt',weights_only=True);model.load_state_dict(checkpoint['state_dict']);model.eval()
    with torch.no_grad():prob=torch.cat([model(x[b]).sigmoid() for b in indices['test'].split(CONFIG['batch_size'])]).numpy()
    test_idx=indices['test'].tolist();truth=d['y'][test_idx];pred=prob>=CONFIG['threshold'];scores=metrics(truth,pred)
    slices={p:metrics(truth[[j for j,i in enumerate(test_idx) if records[i]['point_id']==p]],pred[[j for j,i in enumerate(test_idx) if records[i]['point_id']==p]]) for p in sorted({records[i]['point_id'] for i in test_idx})}
    static=[]
    for i in test_idx:
        tr=[j for j in indices['train'].tolist() if records[j]['point_id']==records[i]['point_id']]
        static.append(((d['y'][tr]==1).sum(axis=0)/np.maximum((d['y'][tr]!=255).sum(axis=0),1))>=.5 if tr else np.zeros((61,61),bool))
    result=dict(test=scores,per_point=slices,static_training_mask_baseline=metrics(truth,np.stack(static)),selected_epoch=best_epoch,validation_loss=best,epochs_completed=len(history),sample_counts={s:len(v) for s,v in indices.items()},parameters=sum(p.numel() for p in model.parameters()),cpu_threads=CONFIG['cpu_threads'],seconds=round(time.perf_counter()-start,2),torch_version=str(torch.__version__),model_sha256=sha(OUT/'best_model.pt'),script_sha256=sha(__import__('pathlib').Path(__file__)),label_type=CONFIG['labels'],independent_human_ground_truth=False,test_used_for_selection=False,config=CONFIG)
    save('result.json',result);np.savez_compressed(OUT/'test_predictions.npz',probabilities=prob,indices=np.array(test_idx))
    # One fixed first test example per point; no cherry-picking by score.
    selected=[next(j for j,i in enumerate(test_idx) if records[i]['point_id']==p) for p in sorted(slices)]
    sheet=Image.new('RGB',(750,240*len(selected)),'white');draw=ImageDraw.Draw(sheet)
    for row,j in enumerate(selected):
        i=test_idx[j];rgb=(np.clip(np.moveaxis(d['x'][i,:3],0,-1)/.3,0,1)**(1/1.8)*255).astype('uint8');label=np.repeat(((truth[j]==1)*255).astype('uint8')[...,None],3,axis=-1);prediction=np.repeat((pred[j]*255).astype('uint8')[...,None],3,axis=-1)
        label[truth[j]==255]=[190,80,190];prediction[truth[j]==255]=[190,80,190]
        for col,a in enumerate([rgb,label,prediction]):sheet.paste(Image.fromarray(a).resize((220,220),Image.Resampling.NEAREST),(col*250,row*240+20))
        draw.text((5,row*240),records[i]['point_id']+' '+records[i]['date'][:10]+' | RGB / automatic target / CNN',fill='black')
    sheet.save(OUT/'test_examples.png');print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','train']);args=parser.parse_args()
    prepare() if args.action=='prepare' else train()
