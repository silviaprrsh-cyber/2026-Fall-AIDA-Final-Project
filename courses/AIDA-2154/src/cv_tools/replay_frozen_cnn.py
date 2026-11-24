"""Offline replay of frozen CV inference and weak-label evaluation; no acquisition."""
import argparse
import ctypes
from ctypes import wintypes
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import time
import numpy as np
import torch
from cv_tools.train_point_cnn import SmallSegCNN, metrics, OUT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def peak_memory():
    if os.name == 'nt':
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)] + [(k, ctypes.c_size_t) for k in ['PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage']]
        c = Counters(); c.cb = ctypes.sizeof(c)
        kernel = ctypes.WinDLL('kernel32'); kernel.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL('psapi')
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb):
            raise OSError('Process memory query failed')
        return dict(peak_rss_bytes=int(c.PeakWorkingSetSize), method='Windows GetProcessMemoryInfo PeakWorkingSetSize; entire replay process')
    import resource
    value = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return dict(peak_rss_bytes=int(value if platform.system() == 'Darwin' else value * 1024), method='getrusage ru_maxrss; entire replay process')


def evaluate(data, output):
    if output.exists():
        raise FileExistsError('Use a new output directory; preserved evidence is never overwritten')
    start = time.perf_counter(); cpu = time.process_time()
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    manifest = json.loads((data/'dataset_manifest.json').read_text())
    expected = json.loads((data/'result.json').read_text())
    history = json.loads((data/'training_history.json').read_text())
    records = manifest['records']; arrays = np.load(data/'dataset.npz')
    x, y = arrays['x'], arrays['y']
    groups = {s: {r['date'][:10] for r in records if r['split'] == s} for s in ['train','validation','test']}
    assert all(not groups[a] & groups[b] for a,b in [('train','validation'),('validation','test'),('train','test')])
    assert len(records) == len({(r['point_id'], r['date'][:10]) for r in records})
    checkpoint = torch.load(data/'best_model.pt', map_location='cpu', weights_only=True)
    assert checkpoint['validation_loss'] == min(r['validation_loss'] for r in history)
    assert digest(data/'best_model.pt') == expected['model_sha256']
    model = SmallSegCNN(); model.load_state_dict(checkpoint['state_dict']); model.eval()
    ix = [i for i,r in enumerate(records) if r['split'] == 'test']
    truth = y[ix]; xx = (torch.from_numpy(x[ix])-checkpoint['mean'])/checkpoint['std']
    xx *= torch.from_numpy(truth != 255).unsqueeze(1)
    t = time.perf_counter()
    with torch.no_grad():
        prob = torch.cat([model(b).sigmoid() for b in xx.split(16)]).numpy()
    inference_seconds = time.perf_counter()-t
    saved = np.load(data/'test_predictions.npz')
    assert np.array_equal(saved['indices'], ix)
    assert np.allclose(prob, saved['probabilities'], atol=1e-6, rtol=1e-6)
    pred = prob >= .5; score = metrics(truth,pred)
    assert score == expected['test']
    baseline=[]
    for i in ix:
        tr=[j for j,r in enumerate(records) if r['split']=='train' and r['point_id']==records[i]['point_id']]
        baseline.append((np.sum(y[tr]==1,axis=0)/np.maximum(np.sum(y[tr]!=255,axis=0),1))>=.5)
    base=metrics(truth,np.stack(baseline)); assert base==expected['static_training_mask_baseline']
    score['Dice']=2*score['TP']/(2*score['TP']+score['FP']+score['FN'])
    slices=[]
    for point in sorted({records[i]['point_id'] for i in ix}):
        selected=[j for j,i in enumerate(ix) if records[i]['point_id']==point]
        slices.append(dict(point_id=point,images=len(selected),**metrics(truth[selected],pred[selected])))
    threshold_sensitivity={str(th):metrics(truth,prob>=th) for th in [.4,.5,.6]}
    result=dict(status='passed',purpose='frozen inference replay; not new accuracy validation',test=score,baseline=base,
        posthoc_threshold_sensitivity_not_model_selection=threshold_sensitivity,
        samples=len(ix),date_counts={k:len(v) for k,v in groups.items()},per_point=slices,
        max_probability_difference=float(np.max(np.abs(prob-saved['probabilities']))),
        selected_epoch=checkpoint['epoch'],inference_seconds=inference_seconds,wall_seconds=time.perf_counter()-start,
        cpu_seconds=time.process_time()-cpu,cpu_threads=torch.get_num_threads(),logical_cpus=os.cpu_count(),
        platform=platform.system(),processor=platform.processor(),python=platform.python_version(),torch=str(torch.__version__),
        memory=peak_memory(),input_sha256={f:digest(data/f) for f in ['best_model.pt','dataset.npz','dataset_manifest.json','result.json','test_predictions.npz','training_history.json']})
    output.mkdir(parents=True)
    (output/'evaluation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    with (output/'point_metrics.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(slices[0]));w.writeheader();w.writerows(slices)
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,default=OUT)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    evaluate(args.data,args.output)
