"""Plan and fetch nonduplicated CDSE CV corridor gaps within verified free quota."""
import argparse,csv,hashlib,io,json,math,re,tarfile,time
from collections import defaultdict,Counter
from datetime import datetime,timedelta,timezone
from pathlib import Path
import numpy as np,requests,rasterio
from rasterio.io import MemoryFile
from rasterio.features import geometry_mask
from pyproj import Transformer
from shapely.geometry import shape,mapping,box
from shapely.ops import transform,unary_union
from project_paths import WORKSPACE
from API.download_satellite_history import EVAL
BASE=WORKSPACE/'courses/AIDA-2154';ROOT=BASE/'data/sources/copernicus_sentinel2/raw/cv_gap_fill_20261111';BANDS=['B04','B03','B02','B08','SCL','dataMask']
def now():return datetime.now(timezone.utc).isoformat()
def save(p,x):
 p.parent.mkdir(parents=True,exist_ok=True);t=p.with_suffix(p.suffix+'.tmp');t.write_text(json.dumps(x,indent=None if p.name=='manifest.json' else 2,ensure_ascii=False)+'\n',encoding='utf-8')
 for attempt in range(20):
  try:t.replace(p);return
  except PermissionError:
   if attempt==19:raise
   time.sleep(.25)
def instant(x):return datetime.fromisoformat(x.replace('Z','+00:00'))
def obskey(s):
 a=s.removesuffix('.SAFE').split('_');return '_'.join([a[0],a[2],a[4],a[5]]) if len(a)>=7 else s

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--execute',action='store_true');parser.add_argument('--max-requests',type=int,default=120);parser.add_argument('--pu-cap',type=float,default=2000);args=parser.parse_args();assert 0<args.pu_cap<=13000
 ROOT.mkdir(parents=True,exist_ok=True);mp=ROOT/'manifest.json';forward=Transformer.from_crs(4326,32612,always_xy=True).transform
 riverpath=WORKSPACE/'courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson';rivers=unary_union([transform(forward,shape(f['geometry'])) for f in json.loads(riverpath.read_text())['features']]);corridor=rivers.buffer(500);core=rivers.buffer(20)
 if mp.exists():
  m=json.loads(mp.read_text());assert m['river_sha256']==hashlib.sha256(riverpath.read_bytes()).hexdigest()
 else:
  old=json.loads((BASE/'data/reports/satellite_history/20261103_history/manifest.json').read_text());assert old['bands']==BANDS and old['pixel_size_m']==10
  coverage=defaultdict(list)
  for j in old['jobs']:
   if j['status'] not in ['downloaded','no_data']:continue
   archive=BASE/'data/sources/copernicus_sentinel2/raw/history/20261103_history'/j['id']/j['archive_name'];assert archive.exists()
   for sid in j['scene_ids']:coverage[obskey(sid)].append(shape(j['geometry']))
  coverage={k:unary_union(v) for k,v in coverage.items()}
  # Include the retained one-shot validation footprint and its actual source product IDs.
  trial=BASE/'data/sources/copernicus_sentinel2/raw/satellite/20260930T035930356564Z'
  if (trial/'process_request.json').exists():
   req=json.loads((trial/'process_request.json').read_text());ud=json.loads((trial/'userdata.json').read_text());g=box(*req['input']['bounds']['bbox'])
   for tile in ud.get('tiles',[]):
    sid=tile.get('sentinel2ProductId',tile.get('productId',''))
    if sid:coverage[obskey(sid)]=unary_union([coverage.get(obskey(sid),g),g])
  cd=BASE/'data/sources/copernicus_sentinel2/raw/catalog_history/20261111_full_catalog';cm=json.loads((cd/'resume_manifest.json').read_text());features={}
  for pg in cm['pages']:
   for f in json.loads((cd/pg['path']).read_text())['features']:
    pr=f['properties'];d=instant(pr['datetime'])
    if pr.get('eo:cloud_cover',100)>20 or pr.get('eo:snow_cover',100)>1 or d.month not in range(4,12):continue
    key=obskey(f['id'])
    if key not in features or f['id']>features[key]['id']:features[key]=f
  cells=[]
  for x in range(math.floor(corridor.bounds[0]/10000)*10000,math.ceil(corridor.bounds[2]/10000)*10000,10000):
   for y in range(math.floor(corridor.bounds[1]/10000)*10000,math.ceil(corridor.bounds[3]/10000)*10000,10000):
    g=box(x,y,x+10000,y+10000).intersection(corridor)
    if not g.is_empty:cells.append((f'{x}_{y}',g))
  jobs=[];excluded=0
  for key,f in features.items():
   footprint=transform(forward,shape(f['geometry']));missing=corridor.intersection(footprint)
   if key in coverage:missing=missing.difference(coverage[key])
   if missing.is_empty:excluded+=1;continue
   for grid,g in cells:
    clip=g.intersection(missing)
    if clip.is_empty or clip.area<10000 or rivers.intersection(clip).length<300:continue
    ex=clip.bounds;bounds=[math.floor(ex[0]/10)*10,math.floor(ex[1]/10)*10,math.ceil(ex[2]/10)*10,math.ceil(ex[3]/10)*10];w=int((bounds[2]-bounds[0])/10);h=int((bounds[3]-bounds[1])/10)
    identity={'observation_key':key,'product_id':f['id'],'geometry':mapping(clip),'bounds':bounds,'bands':BANDS,'pixel_size_m':10,'crs':'EPSG:32612','scene_time':f['properties']['datetime']};digest=hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest()
    jobs.append({**identity,'id':digest[:24],'grid':grid,'width':w,'height':h,'cloud_cover':f['properties']['eo:cloud_cover'],'snow_cover':f['properties'].get('eo:snow_cover'),'estimated_pu':max(.01,w*h/262144*5/3*4),'status':'pending'})
  # Rotate through years and months before repeating a period, prefer low cloud and useful river length.
  groups=defaultdict(list)
  for j in jobs:groups[j['scene_time'][:7]].append(j)
  for v in groups.values():v.sort(key=lambda j:(j['cloud_cover'],j['estimated_pu'],j['scene_time'],j['id']))
  ordered=[]
  while any(groups.values()):
   for k in sorted(groups):
    if groups[k]:ordered.append(groups[k].pop(0))
  m={'started_at':now(),'river_sha256':hashlib.sha256(riverpath.read_bytes()).hexdigest(),'scope':'Current river corridor only; 500 m buffer, 10 m RGB/NIR/SCL/dataMask','free_pu_batch_cap':2000,'minimum_account_remaining_pu':5000,'deduplication':'Canonical platform/sensing time/orbit/tile plus same bands/resolution; subtract union of previously requested archived geometries including no-data to avoid repeating billed empty requests. Product reprocessing variants do not automatically trigger redownload.','excluded_empty_or_covered_observations':excluded,'pixel_cv_quality_unknown_until_download':True,'jobs':ordered,'pu_spent_this_run':0,'network_processing_started':False};save(mp,m)
 print('Plan jobs',len(m['jobs']),'empty or previously covered observations',m.get('excluded_empty_or_covered_observations'),flush=True)
 geometry_path=ROOT/'planned_geometries.json'
 if 'geometry' in m['jobs'][0]:
  assert not geometry_path.exists(), 'Existing geometry index requires inspection'
  geometries={j['id']:j.pop('geometry') for j in m['jobs']}
  save(geometry_path,geometries);m['geometry_index']='planned_geometries.json';m['geometry_index_sha256']=hashlib.sha256(geometry_path.read_bytes()).hexdigest();save(mp,m)
 else:
  raw=geometry_path.read_bytes();assert hashlib.sha256(raw).hexdigest()==m['geometry_index_sha256'];geometries=json.loads(raw)
 if not args.execute:return
 m.pop('stop_reason',None);m['free_pu_batch_cap']=args.pu_cap
 values={}
 for line in (WORKSPACE/'.env').read_text(encoding='utf-8-sig').splitlines():
  z=re.match(r'^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$',line)
  if z:values[z[1].upper()]=z[2].strip().strip(chr(34)).strip(chr(39))
 client=next(values[k] for k in ['CDSE_CLIENT_ID','SH_CLIENT_ID','CLIENT_ID'] if values.get(k));secret=next(values[k] for k in ['CDSE_CLIENT_SECRET','SH_CLIENT_SECRET','CLIENT_SECRET'] if values.get(k));session=requests.Session();access=None;expiry=0
 def headers():
  nonlocal access,expiry
  if time.monotonic()>expiry:
   r=session.post('https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token',data={'grant_type':'client_credentials','client_id':client,'client_secret':secret},timeout=30,allow_redirects=False);r.raise_for_status();o=r.json();access=o['access_token'];expiry=time.monotonic()+max(30,int(o.get('expires_in',300))-30)
  return {'Authorization':'Bearer '+access}
 def usage():
  r=session.get('https://sh.dataspace.copernicus.eu/api/v1/accounting/usage',headers=headers(),timeout=30,allow_redirects=False);r.raise_for_status();u=r.json();clean={k:u[k] for k in ['processingUnitsMonthly','processingUnitsOverage','requestsMonthly','requestsOverage']};assert float(clean['processingUnitsOverage']['configuration'])==0 and float(clean['requestsOverage']['configuration'])==0,'Unexpected overage configuration';return clean
 u=usage();save(ROOT/'quota_before.json',{'checked_at':now(),'quota':u});m['network_processing_started']=True;save(mp,m);count=0
 for job in m['jobs']:
  if job['status']!='pending':continue
  if count>=args.max_requests:break
  if count%5==0:u=usage()
  if float(u['processingUnitsMonthly']['remaining'])-job['estimated_pu']<5000 or float(u['requestsMonthly']['remaining'])<100: m['stop_reason']='quota_reserve';break
  if m['pu_spent_this_run']+job['estimated_pu']>args.pu_cap:m['stop_reason']='batch_pu_cap';break
  folder=ROOT/job['id'];folder.mkdir(exist_ok=True)
  if (folder/'response.tar').exists():raise RuntimeError('Unrecorded response exists; inspect before retry')
  t=instant(job['scene_time']);allowed=json.dumps([job['product_id']]);ev=EVAL+'\nfunction preProcessScenes(c){let allowed='+allowed+';c.scenes.tiles=c.scenes.tiles.filter(s=>allowed.indexOf((s.sentinel2ProductId||s.productId||" ").replace(/\\.SAFE$/,""))>=0);return c;}\n'
  payload={'input':{'bounds':{'bbox':job['bounds'],'geometry':geometries[job['id']],'properties':{'crs':'http://www.opengis.net/def/crs/EPSG/0/32612'}},'data':[{'type':'sentinel-2-l2a','dataFilter':{'timeRange':{'from':(t-timedelta(minutes=30)).isoformat(),'to':(t+timedelta(minutes=30)).isoformat()},'maxCloudCoverage':20},'processing':{'upsampling':'NEAREST','downsampling':'NEAREST'}}]},'output':{'width':job['width'],'height':job['height'],'responses':[{'identifier':'image','format':{'type':'image/tiff'}},{'identifier':'userdata','format':{'type':'application/json'}}]},'evalscript':ev}
  save(folder/'request.json',payload);job['status']='in_progress';save(mp,m)
  try:
   r=session.post('https://sh.dataspace.copernicus.eu/process/v1',json=payload,headers={**headers(),'Accept':'application/tar'},timeout=(20,180),allow_redirects=False)
   job['http_status']=r.status_code
   if r.status_code!=200:job['status']='stopped_http';m['stop_reason']='HTTP '+str(r.status_code);save(mp,m);break
   (folder/'response.tar').write_bytes(r.content);job['archive_sha256']=hashlib.sha256(r.content).hexdigest();job['bytes']=len(r.content)
   spent=r.headers.get('x-processingunits-spent');job['processing_units']=float(spent) if spent is not None else None
   if spent is not None:m['pu_spent_this_run']+=float(spent)
   with tarfile.open(fileobj=io.BytesIO(r.content)) as tar:
    assert set(tar.getnames())=={'image.tif','userdata.json'};data=tar.extractfile('image.tif').read();ud=json.load(tar.extractfile('userdata.json'))
   assert all(x.get('sentinel2ProductId',x.get('productId','')).removesuffix('.SAFE')==job['product_id'] for x in ud.get('tiles',[]))
   with MemoryFile(data) as mem,mem.open() as ds:
    assert ds.count==6 and ds.shape==(job['height'],job['width']) and ds.crs.to_epsg()==32612 and ds.res==(10,10) and np.allclose(ds.bounds,job['bounds'])
    a=ds.read();inside=geometry_mask([geometries[job['id']]],out_shape=ds.shape,transform=ds.transform,invert=True);near=geometry_mask([mapping(core.intersection(shape(geometries[job['id']])))],out_shape=ds.shape,transform=ds.transform,invert=True);valid=a[5]==1;clear=valid&np.isin(a[4],[4,5,6]);n=max(1,inside.sum());k=max(1,near.sum());q={'valid_fraction':float((inside&valid).sum()/n),'clear_fraction':float((inside&clear).sum()/n),'river_clear_fraction':float((near&clear).sum()/k),'snow_fraction':float((inside&valid&(a[4]==11)).sum()/n),'core_pixels':int(near.sum()),'signal':bool(np.any(a[:4,inside&valid]>0))}
   assert all(abs((instant(tile['date'])-t).total_seconds())<=1800 for tile in ud.get('tiles',[]))
   (folder/'image.tif').write_bytes(data);save(folder/'userdata.json',ud);job.update(status='downloaded',received_at=now(),image_sha256=hashlib.sha256(data).hexdigest(),quality=q,cv_candidate=q['signal'] and q['core_pixels']>=20 and q['valid_fraction']>=.95 and q['clear_fraction']>=.8 and q['river_clear_fraction']>=.9 and q['snow_fraction']<=.01,independent_labels=False)
   save(mp,m);count+=1;print('Downloaded',count,'PU',round(m['pu_spent_this_run'],2),'candidate',job['cv_candidate'],flush=True)
   if spent is None:m['stop_reason']='Missing processing unit receipt';break
   time.sleep(1)
  except Exception as exc:
   job['status']='needs_review';job['error_type']=type(exc).__name__;m['stop_reason']='Interrupted request or validation; inspect outcome before retry';save(mp,m);raise
 m['last_stopped_at']=now();m.setdefault('stop_reason','bounded_batch_finished');save(mp,m);save(ROOT/'quota_after.json',{'checked_at':now(),'quota':usage()});print('Statuses',dict(Counter(j['status'] for j in m['jobs'])),'PU',m['pu_spent_this_run'],flush=True)
if __name__=='__main__':main()
