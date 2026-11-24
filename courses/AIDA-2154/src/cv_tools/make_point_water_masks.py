"""Offline, GIS-point-centred candidate water masks; never human ground truth."""
import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import time
import zipfile
import xml.etree.ElementTree as ET
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import shape, mapping
from shapely.ops import transform, unary_union
from PIL import Image, ImageDraw, ImageFont
from project_paths import WORKSPACE

BASE = WORKSPACE / 'courses/AIDA-2154'
GIS = WORKSPACE / 'courses/AIDA-2362/project'
OUT = BASE / 'data/processed/point_water_masks_20261113'
PARAMS = dict(window_pixels=61, halo_pixels=3, seed_distance_m=60,
              seed_ndwi=0.0, grow_ndwi=-0.10, max_ndvi=0.40, max_nir=0.18,
              narrow_max_nir=0.12, narrow_max_ndvi=0.30, narrow_min_ndwi=-0.45,
              min_valid_fraction=0.99, closing_kernel='3x3 cross',
              closing_iterations=1, water=1, background=0, unknown=255)

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
    return h.hexdigest()

def morph(a, dilate):
    p=np.pad(a,1,constant_values=False)
    parts=[p[1:-1,1:-1],p[:-2,1:-1],p[2:,1:-1],p[1:-1,:-2],p[1:-1,2:]]
    return np.logical_or.reduce(parts) if dilate else np.logical_and.reduce(parts)

def closing(a):
    return morph(morph(a,True),False)

def connected(mask,seeds):
    out=np.zeros_like(mask); queue=deque(map(tuple,np.argwhere(seeds&mask)))
    for y,x in queue:out[y,x]=True
    while queue:
        y,x=queue.popleft()
        for dy in (-1,0,1):
            for dx in (-1,0,1):
                yy,xx=y+dy,x+dx
                if 0<=yy<mask.shape[0] and 0<=xx<mask.shape[1] and mask[yy,xx] and not out[yy,xx]:
                    out[yy,xx]=True;queue.append((yy,xx))
    return out

def segment(a,near):
    red,green,blue,nir=a[:4].astype(float)/10000
    ndwi=(green-nir)/np.maximum(green+nir,1e-8)
    ndvi=(nir-red)/np.maximum(nir+red,1e-8)
    valid=(a[5]==1)&np.any(a[:4]>0,axis=0)
    # Low-confidence, cloud/shadow/snow pixels are unknown, never background.
    known=valid&np.isin(a[4],[2,4,5,6,7])
    spectral=known&(ndvi<PARAMS['max_ndvi'])&(nir<PARAMS['max_nir'])
    narrow=(nir<PARAMS['narrow_max_nir'])&(ndvi<PARAMS['narrow_max_ndvi'])&(ndwi>PARAMS['narrow_min_ndwi'])
    permissive=spectral&((ndwi>PARAMS['grow_ndwi'])|narrow)
    seeds=permissive&near&((ndwi>PARAMS['seed_ndwi'])|narrow)
    initial=connected(permissive,seeds)
    # Close WATER foreground (dilation then erosion) on a halo, no opening.
    water=connected(closing(permissive)&spectral,seeds)
    labels=np.zeros(a.shape[1:],dtype='uint8');labels[~known]=255;labels[water]=1
    return labels,initial

def points():
    with zipfile.ZipFile(GIS/'dickson_to_joffre.qgz') as z:
        root=ET.fromstring(z.read(next(n for n in z.namelist() if n.endswith('.qgs'))))
    sources={x.findtext('datasource') for x in root.findall('.//projectlayers/maplayer')}
    result=[]
    for source,kind in [('derived_prediction_targets/prediction_points.geojson','prediction'),('eccc_hydrometric_geomet/stations.geojson','discharge_station')]:
        if './'+source not in sources:raise ValueError('Layer not referenced by QGIS: '+source)
        data=json.loads((GIS/source).read_text(encoding='utf-8-sig'))
        for f in data['features']:
            p=f['properties']; ident=p.get('target_id',p.get('station_id'))
            if kind=='discharge_station' and not (p.get('discharge_m3_s') is not None or p.get('discharge_m3_s_count',0)>0):continue
            result.append(dict(id=ident,kind=kind,coordinates=f['geometry']['coordinates'],source=source))
    assert {p['id'] for p in result}=={'P01','P02','P03','P04','P05','05CB001','05CB007','05CC002','05CC007'}
    return result

def inputs():
    old=BASE/'data/processed/satellite_history/20261103_history/image_index.json'
    idx=json.loads(old.read_text())
    records={str((WORKSPACE/r['image']).resolve()):min([t['sensing_at'] for t in r.get('time_matches',[])] or ['']) for r in idx['images']}
    for path in sorted((BASE/'data/sources/copernicus_sentinel2/raw/cv_gap_fill_20261111').rglob('image.tif')):
        meta=json.loads(path.with_name('userdata.json').read_text())
        records[str(path.resolve())]=min([r['date'] for r in meta.get('tiles',[])] or [''])
    return sorted(records.items())

def read_crop(ds,p):
    x,y=Transformer.from_crs(4326,ds.crs,always_xy=True).transform(*p['coordinates'])
    row,col=ds.index(x,y)
    if not(0<=row<ds.height and 0<=col<ds.width):return None
    w=Window(col-33,row-33,67,67)
    a=ds.read(window=w,boundless=True,fill_value=0)
    return a,ds.window_transform(w),Window(col-30,row-30,61,61),[x,y]

def preview(a,label,p,date,path):
    rgb=(np.clip(np.moveaxis(a[:3],0,-1)/3000,0,1)**(1/1.8)*255).astype('uint8')
    overlay=rgb.copy();overlay[label==1]=(0.45*rgb[label==1]+0.55*np.array([0,175,255])).astype('uint8');overlay[label==255]=[190,80,190]
    binary=np.zeros_like(rgb);binary[label==1]=[255,255,255];binary[label==255]=[190,80,190]
    panel=Image.new('RGB',(750,310),'white');d=ImageDraw.Draw(panel)
    for i,(arr,title) in enumerate([(rgb,'RGB'),(binary,'Candidate mask'),(overlay,'Overlay')]):
        im=Image.fromarray(arr).resize((244,244),Image.Resampling.NEAREST);panel.paste(im,(i*250,45));d.text((i*250+5,28),title,fill='black')
    d.text((5,5),f"{p['id']}  {date[:10]}  610 m square / native 10 m",fill='black')
    d.text((5,294),'White/blue: water candidate | purple: unknown | NOT human-reviewed truth',fill='black')
    for i in [0,2]:d.ellipse((i*250+117,162,i*250+127,172),outline='yellow',width=1)
    panel.save(path)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--preview-only',action='store_true');parser.add_argument('--preview-selection',type=__import__('pathlib').Path);args=parser.parse_args()
    if args.preview_only and args.preview_selection is None:parser.error('--preview-only requires --preview-selection JSON')
    started=time.perf_counter();OUT.mkdir(parents=True,exist_ok=True)
    pts=points(); forward=Transformer.from_crs(4326,32612,always_xy=True).transform
    features=json.loads((GIS/'nrcan_nhn/selected_rivers.geojson').read_text())['features']
    river=unary_union([transform(forward,shape(f['geometry'])) for f in features]).buffer(PARAMS['seed_distance_m'])
    all_inputs=inputs(); accepted=[];reject=Counter();errors=[]
    if args.preview_only:
        select=json.loads(args.preview_selection.read_text(encoding='utf-8'))
        selection={(r['id'],str((WORKSPACE/r['image']).resolve())) for r in select}
        paths={path for _,path in selection};all_inputs=[r for r in all_inputs if r[0] in paths]
    for path,date in all_inputs:
        try:
            with rasterio.open(path) as ds:
                if ds.count!=6 or ds.crs.to_epsg()!=32612 or ds.res!=(10,10):raise ValueError('Unexpected raster grid/bands')
                for p in pts:
                    if args.preview_only and (p['id'],path) not in selection:continue
                    crop=read_crop(ds,p)
                    if crop is None:continue
                    a,t,w,xy=crop; center=a[:,3:-3,3:-3]
                    valid=(center[5]==1)&np.any(center[:4]>0,axis=0)
                    if not valid[30,30] or valid.mean()<PARAMS['min_valid_fraction']:
                        reject[p['id']+'_incomplete_window']+=1;continue
                    near=geometry_mask([mapping(river)],out_shape=(67,67),transform=t,invert=True)
                    labels,initial=segment(a,near);labels=labels[3:-3,3:-3];initial=initial[3:-3,3:-3]
                    ident=p['id']+'_'+date[:10]+'_'+hashlib.sha256(path.encode()).hexdigest()[:12]
                    folder=OUT/p['id'];folder.mkdir(exist_ok=True)
                    maskpath=folder/(ident+'_mask.tif');profile=ds.profile.copy();profile.update(width=61,height=61,count=1,dtype='uint8',nodata=255,transform=ds.window_transform(w),compress='deflate')
                    with rasterio.open(maskpath,'w',**profile) as out:
                        out.write(labels,1);out.update_tags(label_status='automatic_candidate_not_ground_truth',point_id=p['id'])
                    review=folder/(ident+'_review.png');preview(center,labels,p,date,review)
                    with rasterio.open(maskpath) as out:
                        assert out.crs==ds.crs and out.transform==ds.window_transform(w)
                        assert np.array_equal(out.read(1),labels)
                        rr,cc=out.index(*xy);assert (rr,cc)==(30,30)
                    rec=dict(id=ident,point_id=p['id'],date=date,source=Path(path).relative_to(WORKSPACE).as_posix(),source_sha256=sha(Path(path)),mask=maskpath.relative_to(OUT).as_posix(),preview=review.relative_to(OUT).as_posix(),water_pixels=int((labels==1).sum()),unknown_pixels=int((labels==255).sum()),closing_added=int(((labels==1)&~initial).sum()),label_status='automatic_candidate_pending_review')
                    accepted.append(rec)
        except Exception as exc:errors.append(dict(source=path,error=str(exc)))
    name='preview' if args.preview_only else 'full'
    (OUT/(name+'_manifest.json')).write_text(json.dumps(dict(points=pts,parameters=PARAMS,script_sha256=sha(Path(__file__)),qgis_sha256=sha(GIS/'dickson_to_joffre.qgz'),records=accepted,errors=errors,rejected=dict(reject)),indent=2)+'\n',encoding='utf-8')
    summary=dict(mode=name,count=len(accepted),points=dict(Counter(r['point_id'] for r in accepted)),empty_water=sum(r['water_pixels']==0 for r in accepted),mostly_unknown=sum(r['unknown_pixels']>1860 for r in accepted),errors=len(errors),seconds=round(time.perf_counter()-started,2),training=False,network_requests=0)
    (OUT/(name+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    if args.preview_only:
        canvas=Image.new('RGB',(1500,1550),'white')
        for i,r in enumerate(accepted):canvas.paste(Image.open(OUT/r['preview']),((i%2)*750,(i//2)*310))
        canvas.save(OUT/'nine_point_review.png')
    print(json.dumps(summary,indent=2),flush=True)

if __name__=='__main__':main()
