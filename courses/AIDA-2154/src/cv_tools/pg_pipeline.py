"""PostgreSQL/view-driven CV replay with audited, versioned file references."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import uuid
import numpy as np
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import rasterio
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union
from cv_tools import make_point_water_masks as masks
from cv_tools import train_point_cnn as training
from project_tools.database import connect as shared_connect
from project_paths import require_local
from rdr.storage import save_json

ROOT=masks.WORKSPACE
BASE=masks.BASE
FROZEN=BASE/'data/processed/point_cnn_20261113'
OUTPUT=BASE/'data/processed/cv_pipeline_20261113'


def local(relative):
    return require_local(ROOT/relative)


def contained(base, value):
    p=(base/value).resolve()
    if not p.is_relative_to(base.resolve()):raise ValueError('Artifact path escapes intended directory')
    return p


def relative(path):return Path(path).resolve().relative_to(ROOT).as_posix()


def connect():
    return shared_connect(application_name="cv_pipeline")


def save(path,value):
    save_json(path,json.loads(json.dumps(value,default=str,allow_nan=False)))


@contextmanager
def stage(name):
    ident=name+'_'+uuid.uuid4().hex
    with connect() as db:db.execute('INSERT INTO cv_pipeline.runs(run_id,stage,status) VALUES(%s,%s,%s)',(ident,name,'running'))
    try:
        yield ident
    except Exception as exc:
        with connect() as db:db.execute("UPDATE cv_pipeline.runs SET status='failed',finished_at=now(),details=%s WHERE run_id=%s AND status='running'",(Jsonb({'error_type':type(exc).__name__}),ident))
        raise


def finish(ident,details):
    with connect() as db:db.execute("UPDATE cv_pipeline.runs SET status='complete',finished_at=now(),details=%s WHERE run_id=%s",(Jsonb(details),ident))


def initialize():
    with connect() as db:db.execute((BASE/'sql/cv_pipeline.sql').read_text(encoding='utf-8-sig'))
    print('Isolated cv_pipeline schema and views ready')


def register():
    """Register archived API responses, not a new API acquisition."""
    full=json.loads((masks.OUT/'full_manifest.json').read_text())
    selected=json.loads((FROZEN/'dataset_manifest.json').read_text())
    selection_hash=masks.sha(FROZEN/'dataset_manifest.json')
    frozen={r['id']:r['split'] for r in selected['records']}
    points={p['id']:p for p in masks.points()}
    scenes={r['source']:r for r in full['records']}
    with stage('register_archive') as run:
        with connect() as db:
            for source,r in sorted(scenes.items()):
                digest=masks.sha(local(source))
                if digest!=r['source_sha256']:raise ValueError('Archived source hash changed: '+source)
                scene_id=hashlib.sha256(source.encode()).hexdigest()
                prior=db.execute('SELECT * FROM cv_pipeline.scenes WHERE scene_id=%s',(scene_id,)).fetchone()
                if prior and (prior['sha256']!=digest or prior['source_path']!=source or prior['acquired_at'].astimezone(timezone.utc)!=datetime.fromisoformat(r['date'].replace('Z','+00:00'))):raise ValueError('Scene identity conflict')
                db.execute('INSERT INTO cv_pipeline.scenes(scene_id,source_path,sha256,acquired_at,provenance) VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(scene_id,source,digest,r['date'],'existing Copernicus API archive; imported now, not newly fetched'))
            for r in full['records']:
                prior=db.execute('SELECT * FROM cv_pipeline.samples WHERE sample_id=%s',(r['id'],)).fetchone()
                if prior and (prior['selection_manifest_sha256']!=selection_hash or prior['original_record']!=r or prior['point_id']!=r['point_id'] or prior['coordinates']!=points[r['point_id']]['coordinates'] or prior['split']!=frozen.get(r['id']) or prior['scene_id']!=hashlib.sha256(r['source'].encode()).hexdigest()):raise ValueError('Frozen sample identity changed; use a new dataset version')
                db.execute('INSERT INTO cv_pipeline.samples(sample_id,scene_id,point_id,coordinates,split,original_record,selection_manifest_sha256) VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',(r['id'],hashlib.sha256(r['source'].encode()).hexdigest(),r['point_id'],Jsonb(points[r['point_id']]['coordinates']),frozen.get(r['id']),Jsonb(r),selection_hash))
        result={'scenes':len(scenes),'candidate_samples':len(full['records']),'frozen_selected':len(frozen),'selection_sha256':selection_hash,'new_api_requests':0}
        finish(run,result);print(json.dumps(result))


def method_id():
    return hashlib.sha256((json.dumps(masks.PARAMS,sort_keys=True)+masks.sha(Path(masks.__file__))+masks.sha(masks.GIS/'nrcan_nhn/selected_rivers.geojson')).encode()).hexdigest()


def promote_masks(records,run,report):
    with connect() as db:
        # A complete regenerated version replaces references, never old files.
        for row in records:
            db.execute('INSERT INTO cv_pipeline.masks VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(sample_id,method_id) DO UPDATE SET path=EXCLUDED.path,sha256=EXCLUDED.sha256,water_pixels=EXCLUDED.water_pixels,unknown_pixels=EXCLUDED.unknown_pixels,run_id=EXCLUDED.run_id',row)
        db.execute("UPDATE cv_pipeline.runs SET status='complete',finished_at=now(),details=%s WHERE run_id=%s",(Jsonb(report),run))


def make_masks():
    method=method_id()
    forward=Transformer.from_crs(4326,32612,always_xy=True).transform
    features=json.loads((masks.GIS/'nrcan_nhn/selected_rivers.geojson').read_text())['features']
    river=unary_union([transform(forward,shape(f['geometry'])) for f in features]).buffer(masks.PARAMS['seed_distance_m'])
    with stage('generate_masks_from_view') as run:
        dest=OUTPUT/run;dest.mkdir(parents=True)
        with connect() as db:
            rows=db.execute('SELECT * FROM cv_pipeline.v_raw_images ORDER BY source_path,sample_id').fetchall()
        checked=set(); count=0; records=[]
        for r in rows:
            path=local(r['source_path'])
            if path not in checked:
                if masks.sha(path)!=r['source_sha256']:raise ValueError('Source hash mismatch')
                checked.add(path)
            p={'id':r['point_id'],'coordinates':r['coordinates']}
            with rasterio.open(path) as ds:
                if ds.count!=6 or ds.crs.to_epsg()!=32612 or ds.res!=(10,10):raise ValueError('Unexpected image format')
                crop=masks.read_crop(ds,p)
                if crop is None:raise ValueError('GIS point not inside image')
                a,t,w,xy=crop
                near=geometry_mask([mapping(river)],out_shape=(67,67),transform=t,invert=True)
                labels,_=masks.segment(a,near);labels=labels[3:-3,3:-3]
                out=contained(dest,r['sample_id']+'.tif')
                profile=ds.profile.copy();profile.update(width=61,height=61,count=1,dtype='uint8',nodata=255,transform=ds.window_transform(w),compress='deflate')
                with rasterio.open(out,'w',**profile) as target:target.write(labels,1)
            original=contained(masks.OUT,r['original_record']['mask'])
            with rasterio.open(original) as old:
                if not np.array_equal(old.read(1),labels):raise ValueError('Regenerated mask differs from retained experiment')
            row=(r['sample_id'],method,relative(out),masks.sha(out),int((labels==1).sum()),int((labels==255).sum()),run)
            records.append(row);count+=1
            if count%200==0:print('Masks from view:',count,flush=True)
        report={'run_id':run,'masks':count,'method_id':method,'all_equal_to_original_labels':True,'source_view':'cv_pipeline.v_raw_images'}
        save(dest/'generation.json',report)
        promote_masks(records,run,report)
        print(json.dumps(report))


def train_from_view():
    with stage('train_from_view') as run:
        dest=OUTPUT/run;dest.mkdir(parents=True)
        with connect() as db:
            db.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            db.execute("SET LOCAL TIME ZONE 'UTC'")
            rows=db.execute('SELECT * FROM cv_pipeline.v_training_pairs WHERE method_id=%s ORDER BY acquired_at,point_id,sample_id',(method_id(),)).fetchall()
        if not rows:raise ValueError('No completed masks in training view')
        records=[];xs=[];ys=[];days={};hash_groups={};checked=set()
        for r in rows:
            path=local(r['source_path']);mask=local(r['mask_path'])
            if path not in checked:
                if masks.sha(path)!=r['source_sha256']:raise ValueError('Source modified')
                checked.add(path)
            if masks.sha(mask)!=r['mask_sha256']:raise ValueError('Mask modified')
            with rasterio.open(path) as src,rasterio.open(mask) as lab:
                win=rasterio.windows.from_bounds(*lab.bounds,transform=src.transform).round_offsets().round_lengths()
                a=src.read(window=win);y=lab.read(1)
                if a.shape!=(6,61,61) or lab.transform!=src.window_transform(win):raise ValueError('Image-mask grid mismatch')
            bad=np.isin(a[4],[0,1,3,8,9,10,11])|(a[5]!=1)|(y==255)
            y[bad]=255;x=np.clip(a[:4].astype('float32')/10000,0,1)
            day=r['acquired_at'].date().isoformat();split=r['split'];digest=hashlib.sha256(x.tobytes()).hexdigest()
            if day in days and days[day]!=split:raise ValueError('Date leakage')
            if digest in hash_groups and hash_groups[digest]!=split:raise ValueError('Identical-pixel leakage')
            days[day]=split;hash_groups[digest]=split
            rec=dict(r['original_record'],split=split,crop_sha256=digest,mask_sha256=r['mask_sha256'],database_mask_path=r['mask_path'],mask_run_id=r['mask_run_id'])
            records.append(rec);xs.append(x);ys.append(y.astype('float32'))
        np.savez_compressed(dest/'dataset.npz',x=np.stack(xs),y=np.stack(ys))
        save(dest/'dataset_manifest.json',{'records':records,'config':training.CONFIG,'read_source':'cv_pipeline.v_training_pairs','method_id':method_id(),'run_id':run,'snapshot_sha256':masks.sha(dest/'dataset.npz')})
        expected=json.loads((FROZEN/'dataset_manifest.json').read_text())['records']
        old=np.load(FROZEN/'dataset.npz');old_x=old['x'];old_y=old['y'];index={r['id']:i for i,r in enumerate(expected)}
        if set(index)!={r['id'] for r in records}:raise ValueError('Frozen selection membership changed')
        for i,r in enumerate(records):
            j=index[r['id']]
            if not np.array_equal(xs[i],old_x[j]) or not np.array_equal(ys[i],old_y[j]) or r['split']!=expected[j]['split']:raise ValueError('Frozen sample content changed')
        training.OUT=dest
        start=time.perf_counter();training.train()
        result=json.loads((dest/'result.json').read_text())
        report={'run_id':run,'model':relative(dest/'best_model.pt'),'model_sha256':masks.sha(dest/'best_model.pt'),'input_view':'cv_pipeline.v_training_pairs','samples':len(records),'seconds':time.perf_counter()-start,'test':result['test'],'source_data_and_labels_equal_to_frozen':True,'read_only_snapshot':True}
        from cv_tools.replay_frozen_cnn import peak_memory
        report['memory']=peak_memory()
        report['pipeline_script_sha256']=masks.sha(Path(__file__))
        save(dest/'pipeline_result.json',report);finish(run,report)
        save(OUTPUT/'latest_training.json',report);print(json.dumps(report,indent=2))


def verify():
    with connect() as db:
        counts={t:db.execute('SELECT count(*) AS n FROM cv_pipeline.'+t).fetchone()['n'] for t in ['scenes','samples','masks','audit','v_raw_images','v_training_pairs']}
        stages=db.execute('SELECT run_id,stage,status,details FROM cv_pipeline.runs ORDER BY started_at').fetchall()
    report={'counts':counts,'runs':stages,'verified_at':datetime.now(timezone.utc).isoformat()}
    OUTPUT.mkdir(parents=True,exist_ok=True);save(OUTPUT/'database_verification.json',report);print(json.dumps(report,default=str,indent=2))


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['init','register','masks','train','verify','all']);a=p.parse_args()
    actions={'init':initialize,'register':register,'masks':make_masks,'train':train_from_view,'verify':verify}
    if a.action=='all':
        for action in actions.values():action()
    else:actions[a.action]()


if __name__=='__main__':main()
