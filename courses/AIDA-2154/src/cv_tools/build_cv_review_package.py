"""Build a local allowlisted CV evidence candidate; never upload or commit it."""
import argparse
import hashlib
import json
import posixpath
import re
from pathlib import Path
import shutil
import urllib.parse
import zipfile
from project_paths import WORKSPACE

BASE=WORKSPACE/'courses/AIDA-2154'
REL=BASE/'data/processed/cv_release_20261113'
MD_LINK_RE = re.compile(r'(?<!!)\[([^\]]+)\]\(([^)]+)\)')


def sanitize_zip_md(rel_path: str, text: str, members: set[str]) -> str:
    dirs = set()
    for m in members:
        parts = m.split('/')
        for k in range(1, len(parts)):
            dirs.add('/'.join(parts[:k]))
    base = posixpath.dirname(rel_path)
    def repl(match: re.Match[str]) -> str:
        label, raw = match.group(1), match.group(2).strip()
        if raw.startswith(('http://', 'https://', '#', 'mailto:')):
            return match.group(0)
        tgt = urllib.parse.unquote(raw.split('#')[0]).rstrip('/')
        if not tgt:
            return match.group(0)
        norm = posixpath.normpath(posixpath.join(base, tgt)) if base else posixpath.normpath(tgt)
        if norm in members or norm in dirs:
            return match.group(0)
        return f"{label} (`{raw}` — see full repository; omitted from standalone ZIP)"
    return MD_LINK_RE.sub(repl, text)


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify(root):
    manifest=json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    expected={r['path'] for r in manifest['files']}
    actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='manifest.json'}
    assert actual==expected, (actual-expected,expected-actual)
    for r in manifest['files']:
        p=root/r['path'];assert p.stat().st_size==r['bytes'] and sha(p)==r['sha256'],r['path']
    return len(expected)


def build(name):
    assert name.replace('_','').replace('-','').isalnum()
    target=REL/name;archive=REL/(name+'.zip')
    if target.exists() or archive.exists():raise FileExistsError('Preserve candidate; choose a new release folder in code for a new version')
    names=['run.py','shared-resources/src/project_paths.py']
    names += ['courses/AIDA-2154/'+p.name for p in BASE.glob('*.md') if not p.name.endswith('CN.md')]
    names += ['courses/AIDA-2154/requirements-cv.lock.txt']
    names += [p.relative_to(WORKSPACE).as_posix() for p in (BASE/'docs').glob('*.md') if not p.name.endswith('CN.md')]
    for name in ['__init__.py','model.py','make_point_water_masks.py','train_point_cnn.py','validate_point_widths.py','summarize_point_widths.py','test_point_water_masks.py','test_point_cnn.py','test_point_widths.py','test_release_replay.py','replay_frozen_cnn.py','replay_frozen_training.py','build_cv_review_package.py','independent_manual_eval.py']:
        names.append('courses/AIDA-2154/src/cv_tools/'+name)
    for fname in ['blind_selection_manifest.json','manual_blind_annotations_9sites.json','manual_eval_summary.json','manual_eval_per_site.csv','independent_manual_comparison.png']:
        names.append('courses/AIDA-2154/outputs/independent_manual_eval_20261123/'+fname)
    for folder,files in {
        'point_cnn_20261113':['dataset.npz','dataset_manifest.json','best_model.pt','result.json','selection_summary.json','training_history.json','test_predictions.npz','test_examples.png','visual_selection_review.json'],
        'point_width_validation_20261113':['summary.json','test_width_hydrometry.csv','transects.json','hydrometry_width_scatter.png','transect_review.png'],
        'cv_release_20261113':['clean_run_v3.json'],
        'cv_release_20261113/evaluation':['evaluation.json','point_metrics.csv'],
        'cv_release_20261113/training_replay':['resources.json'],
    }.items():
        names.extend('courses/AIDA-2154/data/processed/'+folder+'/'+n for n in files)
    assert all((WORKSPACE/n).is_file() for n in names)
    target.mkdir(parents=True)
    for name in sorted(set(names)):
        dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(WORKSPACE/name,dest)
    shutil.copyfile(BASE/'docs/package-guide.md',target/'README.md')
    member_set = {p.relative_to(target).as_posix() for p in target.rglob('*') if p.is_file()}
    for p in sorted(target.rglob('*.md')):
        rel_md = p.relative_to(target).as_posix()
        p.write_text(sanitize_zip_md(rel_md, p.read_text(encoding='utf-8-sig'), member_set), encoding='utf-8')
    files=[]
    for p in sorted(target.rglob('*')):
        if not p.is_file():continue
        rel=p.relative_to(target).as_posix()
        assert p.suffix.lower() not in ['.key','.pem','.exe','.dll','.tar','.tif'] and '.env' not in p.name
        if p.suffix in ['.py','.md','.json','.csv','.txt']:
            text=p.read_text(encoding='utf-8-sig')
            assert ('C:'+chr(92)+'Users'+chr(92)) not in text and ('Bearer '+'eyJ') not in text,rel
        files.append(dict(path=rel,bytes=p.stat().st_size,sha256=sha(p)))
    manifest=dict(status='local D2L-ready candidate; AI declaration, retrospective, and 9-site blind manual audit included; real peer review and D2L upload pending',
        attribution='Contains modified Copernicus Sentinel data [2016-2026]',
        scope='frozen inference, original-config training replay, and independent 9-site blind manual scoring; not raw archive reconstruction',files=files)
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    verify(target)
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(target.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(target).as_posix())
    print(json.dumps(dict(files=len(files),bytes=archive.stat().st_size,zip_sha256=sha(archive)),indent=2))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--verify',type=Path);parser.add_argument('--name',default='AIDA2154_CV_review_candidate');args=parser.parse_args()
    print('Verified files:',verify(args.verify)) if args.verify else build(args.name)
