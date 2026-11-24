"""Offline CV input screening; no download, training, or fabricated labels."""
import csv, hashlib, io, json, math, time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import rasterio
from rasterio.features import geometry_mask
from shapely.geometry import shape, mapping, box
from shapely.ops import transform, unary_union
from pyproj import Transformer
from PIL import Image, ImageDraw
from project_paths import WORKSPACE

def main():
    started=time.perf_counter()
    base=WORKSPACE/'courses/AIDA-2154'
    out=base/'outputs/cv_material_screening_20261111'
    out.mkdir(parents=True,exist_ok=True)
    source=base/'data/processed/satellite_history/dickson_to_05CC002/image_index.json'
    riverpath=WORKSPACE/'courses/AIDA-2362/project/nrcan_nhn/selected_rivers.geojson'
    index=json.loads(source.read_text()); forward=Transformer.from_crs(4326,32612,always_xy=True).transform
    rivers=unary_union([transform(forward,shape(f['geometry'])) for f in json.loads(riverpath.read_text())['features']])
    corridor=rivers.buffer(500); core=rivers.buffer(20)
    records=[]; failures=[]
    def frac(n,d): return float(n/max(d,1))
    for original in index['images']:
        path=(WORKSPACE/original['image']).resolve()
        if not path.is_relative_to(WORKSPACE):raise ValueError('Outside workspace')
        actual_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        with rasterio.open(path) as ds:
            if ds.count!=6 or ds.crs.to_epsg()!=32612 or ds.res!=(10,10):raise ValueError('Unexpected raster format')
            a=ds.read();inside=geometry_mask([mapping(corridor)],out_shape=ds.shape,transform=ds.transform,invert=True)
            near=geometry_mask([mapping(core)],out_shape=ds.shape,transform=ds.transform,invert=True)
            valid=(a[5]==1); clear=valid&np.isin(a[4],[4,5,6]); cloud=valid&np.isin(a[4],[3,8,9,10]); snow=valid&(a[4]==11)
            n=int(inside.sum());k=int(near.sum());signal=bool(np.any(a[:4,inside&valid]>0)); dates=[t['sensing_at'] for t in original.get('time_matches',[])]
            when=min(dates) if dates else '';month=when[:7];season={12:'winter',1:'winter',2:'winter',3:'spring',4:'spring',5:'spring',6:'summer',7:'summer',8:'summer',9:'autumn',10:'autumn',11:'autumn'}.get(int(when[5:7]) if when else 0,'unknown')
            key=path.stem;parts=key.split('_'); event='_'.join(parts[:2]); grid='_'.join(parts[-2:]); reasons=[]
            vf=frac((inside&valid).sum(),n);cf=frac((inside&clear).sum(),n);rf=frac((near&clear).sum(),k);sf=frac((inside&snow).sum(),n);cl=frac((inside&cloud).sum(),n)
            if actual_hash!=original['image_sha256']:reasons.append('hash_mismatch')
            if not signal:reasons.append('no_reflectance_signal')
            if n<100:reasons.append('too_little_corridor')
            if k<20:reasons.append('too_little_river_core')
            if vf<.95:reasons.append('valid_coverage_below_95pct')
            if cf<.80:reasons.append('clear_corridor_below_80pct')
            if rf<.90:reasons.append('clear_river_core_below_90pct')
            if sf>.01:reasons.append('snow_ice_above_1pct')
            time_match=bool(dates) and all(t['common_origin']['within_150_seconds'] for t in original.get('time_matches',[]))
            records.append({'id':key,'image':str(path.relative_to(WORKSPACE)).replace('\\','/'),'image_sha256':actual_hash,'source_archive':original['source_archive'],'event_group':event,'grid':grid,'sensing_at':when,'month':month,'season':season,'corridor_pixels':n,'river_core_pixels':k,'valid_corridor_fraction':vf,'clear_corridor_fraction':cf,'cloud_shadow_corridor_fraction':cl,'snow_ice_corridor_fraction':sf,'clear_river_core_fraction':rf,'river_line_in_raster_m':float(rivers.intersection(box(*ds.bounds)).length),'signal_present':signal,'hash_verified':actual_hash==original['image_sha256'],'hydrometry_matched_150s':time_match,'eligible_for_label_review':not reasons,'rejection_reasons':';'.join(reasons),'independent_label_status':'not_available_requires_annotation','visual_review_status':'pending','split_status':'unassigned_keep_event_group_together'})
    eligible=[r for r in records if r['eligible_for_label_review']]
    # First select the best candidate per month/grid, then balance months and cap event repetition.
    score=lambda r:(r['clear_river_core_fraction'],r['clear_corridor_fraction'],r['valid_corridor_fraction'],r['river_core_pixels'])
    buckets=defaultdict(list)
    for r in eligible:buckets[(r['month'],r['grid'])].append(r)
    pool=[max(v,key=score) for v in buckets.values()];by_month=defaultdict(list)
    for r in pool:by_month[r['month']].append(r)
    for v in by_month.values():v.sort(key=score,reverse=True)
    shortlist=[];event_use=Counter();grid_use=Counter()
    for round_no in range(12):
        for month in sorted(by_month):
            options=[r for r in by_month[month] if r not in shortlist and event_use[r['event_group']]<2]
            if options and len(shortlist)<24:
                r=min(options,key=lambda r:(grid_use[r['grid']],-score(r)[0],-score(r)[1]));shortlist.append(r);event_use[r['event_group']]+=1;grid_use[r['grid']]+=1
    def write_csv(name,rows):
        with (out/name).open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(rows)
    write_csv('all_image_screening.csv',records);write_csv('eligible_label_review.csv',eligible);write_csv('diverse_shortlist.csv',shortlist)
    # Display only; no resampling or changes to source rasters. Gray is outside current corridor.
    canvas=Image.new('RGB',(4*360,math.ceil(len(shortlist)/4)*300),'white');draw=ImageDraw.Draw(canvas)
    for i,r in enumerate(shortlist):
        with rasterio.open(WORKSPACE/r['image']) as ds:
            a=ds.read();mask=geometry_mask([mapping(corridor)],out_shape=ds.shape,transform=ds.transform,invert=True)&(a[5]==1)
            rgb=np.moveaxis(a[:3].astype(float)/10000,0,-1);rgb=np.clip(rgb/0.30,0,1)**(1/1.8);rgb=(rgb*255).astype('uint8');rgb[~mask]=[65,65,65]
            im=Image.fromarray(rgb);im.thumbnail((350,240));x=(i%4)*360;y=(i//4)*300;canvas.paste(im,(x+(350-im.width)//2,y))
            draw.text((x+5,y+242),f'{i+1:02} {r["sensing_at"][:10]} grid {r["grid"]}',fill='black');draw.text((x+5,y+258),f'clear {r["clear_corridor_fraction"]:.1%} river {r["clear_river_core_fraction"]:.1%}',fill='black');draw.text((x+5,y+274),'LABEL PENDING / NOT TRAINING DATA',fill='black')
    canvas.save(out/'shortlist_contact_sheet.png')
    catalogdir=base/'data/sources/copernicus_sentinel2/raw/catalog_history/20261111_full_catalog';cm=json.loads((catalogdir/'resume_manifest.json').read_text());ci=json.loads((catalogdir/'scene_index.json').read_text());scoped={r['id'] for r in ci if r['intersects_corridor']};hm=json.loads((base/'data/reports/satellite_history/20261103_history/manifest.json').read_text());represented={sid for j in hm['jobs'] if j['status']=='downloaded' for sid in j['scene_ids']};cat=[]
    for pg in cm['pages']:
        for f in json.loads((catalogdir/pg['path']).read_text())['features']:
            if f['id'] not in scoped:continue
            prop=f['properties'];cat.append({'scene_id':f['id'],'datetime':prop['datetime'],'tile_cloud_percent':prop.get('eo:cloud_cover'),'historical_cropped_download_source':f['id'] in represented,'pixel_quality_verified_for_current_corridor':False,'label_available':False,'status':'historical_partial_crops_exist' if f['id'] in represented else 'catalog_only_not_downloaded'})
    with (out/'catalog_pixel_availability.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(cat[0]));w.writeheader();w.writerows(cat)
    summary={'created_utc':datetime.now(timezone.utc).isoformat(),'input_index_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'river_sha256':hashlib.sha256(riverpath.read_bytes()).hexdigest(),'source_script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'thresholds':{'buffer_m':500,'river_proximity_buffer_m':20,'minimum_corridor_pixels':100,'minimum_core_pixels':20,'valid_fraction':.95,'clear_corridor_fraction':.8,'clear_core_fraction':.9,'max_snow_fraction':.01},'images_audited':len(records),'hash_failures':sum(not r['hash_verified'] for r in records),'eligible_for_label_review':len(eligible),'eligible_events':len({r['event_group'] for r in eligible}),'shortlist_count':len(shortlist),'shortlist_events':len(event_use),'eligible_seasons':dict(Counter(r['season'] for r in eligible)),'shortlist_months':dict(Counter(r['month'] for r in shortlist)),'rejection_counts':dict(Counter(x for r in records for x in r['rejection_reasons'].split(';') if x)),'catalog_scope_scenes':len(cat),'catalog_only_scenes':sum(r['status']=='catalog_only_not_downloaded' for r in cat),'independent_labels':0,'training_started':False,'network_requests':0,'elapsed_seconds':time.perf_counter()-started}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    cn=f'''# 卫星CV素材初筛（2026-11-11）\n\n当前目标：Dickson Dam出口至05CC002河段的水面范围辅助判读；不是洪水预警、测深或安全决策。\n\n## 结果\n\n本轮逐像元重算{len(records)}张当前范围相交影像，SHA-256不一致{summary['hash_failures']}张。自动筛出{len(eligible)}张可进入人工检查/标注的候选，来自{summary['eligible_events']}次过境组；另选{len(shortlist)}张兼顾月份和网格的首批复核素材。它们尚不是已标注训练集。独立真值标签数量为0。\n\n## 可复现条件\n\n从项目根目录运行：`.venv\\Scripts\\python.exe -B run.py -m cv_tools.screen_cv_materials`。本程序只读现有原始影像，不联网、不训练、不改模型；只更新本目录派生结果。\n\n有效覆盖≥95%；500米河道走廊清晰比例≥80%；河线两侧20米邻近带清晰比例≥90%；雪冰≤1%；至少100个走廊像元和20个河线邻近像元。清晰使用提供方SCL类别4/5/6，阴影/云为3/8/9/10，雪冰为11。20米邻近带仅用于检查实际河线附近的遮挡，不是水面真值；河道线位置误差、窄河混合像元和SCL本身误差仍需人工复核。\n\n水文±150秒匹配只保留为辅助字段，不作为水面CV必须条件。不要把水位或SCL标签当作独立的水面真值。\n\n## 文件\n\n- all_image_screening.csv：所有已下载当前范围影像及质量、拒绝原因、时间匹配。\n- eligible_label_review.csv：自动质量合格但待人工检查/标注的候选。\n- diverse_shortlist.csv：首批多月份/网格复核清单（不是固定训练/验证/测试划分）。\n- shortlist_contact_sheet.png：RGB接触表，统一显示拉伸，灰色为走廊外或无效像元；不能仅凭缩略图判定边界标签。\n- catalog_pixel_availability.csv：{len(cat)}个相交目录产品，其中{summary['catalog_only_scenes']}个仅有目录、未在旧影像下载来源中出现；旧裁剪存在也不代表全产品/全当前走廊已下载。\n- summary.json：阈值、数量、输入和脚本哈希、耗时。\n\n## 下一步与课程证据\n\n人工审核首批原分辨率影像并标注独立水/非水/不可判读掩膜，记录标注人、日期、规则和复核分歧；云、阴影、雪冰和无效像元不应强制标成陆地。按过境事件分组控制泄漏，相同日期/轨道的相邻网格及重处理版本不能跨数据划分。时间、空间、季节覆盖需在确定划分前审核。课程要求还包括基线、固定验证协议、错误分析、CPU性能证据和人工接管规则，本次仅完成素材准备，不声称已完成模型评价。Copernicus归属声明及最终发布许可仍按项目permission record核实。\n'''
    (out/'README_CN.md').write_text(cn,encoding='utf-8')
    (out/'README.md').write_text('# CV material screening\n\nOffline audit of existing current-scope imagery, with pixel-quality screening and a month/grid-diverse review shortlist. See README_CN.md for the full Chinese explanation. All candidates require visual review and independent labels; provider SCL is not ground truth. No downloads, training or model changes. Reproduce: `.venv/Scripts/python.exe -B run.py -m cv_tools.screen_cv_materials`.\n',encoding='utf-8')
    print(json.dumps(summary,indent=2),flush=True)
if __name__=='__main__':main()
