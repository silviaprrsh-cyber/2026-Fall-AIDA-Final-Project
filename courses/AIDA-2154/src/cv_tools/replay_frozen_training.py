"""Replay the unchanged training configuration into a new evidence directory."""
import argparse
import json
from pathlib import Path
import shutil
import time
from cv_tools import train_point_cnn as training
from cv_tools.replay_frozen_cnn import peak_memory

if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    if args.output.exists():raise FileExistsError('Choose a new output; existing evidence is protected')
    source=training.OUT
    assert json.loads((source/'result.json').read_text())['config']==training.CONFIG
    args.output.mkdir(parents=True)
    for name in ['dataset.npz','dataset_manifest.json']:
        shutil.copyfile(source/name,args.output/name)
    training.OUT=args.output
    start=time.perf_counter();cpu=time.process_time()
    training.train()
    result=json.loads((args.output/'result.json').read_text())
    expected=json.loads((source/'result.json').read_text())
    assert result['test']==expected['test']
    assert result['selected_epoch']==expected['selected_epoch']
    report=dict(purpose='unchanged configuration replay, not a new model-selection trial',wall_seconds=time.perf_counter()-start,
                cpu_seconds=time.process_time()-cpu,memory=peak_memory(),cpu_threads=training.CONFIG['cpu_threads'],
                same_test_counts=True,same_selected_epoch=True,original_evidence_unchanged=True)
    (args.output/'resources.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,indent=2))
