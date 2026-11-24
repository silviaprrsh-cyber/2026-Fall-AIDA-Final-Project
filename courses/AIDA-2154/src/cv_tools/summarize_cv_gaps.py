"""Summarize completed CV gap archives without networking or model training."""
import csv,hashlib,json,math
from collections import Counter
from pathlib import Path
import numpy as np,rasterio
from rasterio.features import geometry_mask
from PIL import Image,ImageDraw
from project_paths import WORKSPACE

def inventory_rows(jobs, root):
 rows=[]
 for j in jobs:
  f=root/j['id'];downloaded=j['status']=='downloaded';image_exists=(f/'image.tif').is_file();metadata_exists=(f/'userdata.json').is_file()
  q=j.get('quality',{}) if downloaded else {}
  times=''
  if downloaded and metadata_exists:
   times=';'.join(sorted({t['date'] for t in json.loads((f/'userdata.json').read_text()).get('tiles',[])}))
  rows.append({'request_id':j['id'],'product_id':j.get('product_id',''),'observation_key':j.get('observation_key',''),'scene_time':j.get('scene_time',''),'actual_sensing_times':times,'grid':j.get('grid',''),'status':j['status'],'cv_candidate':j.get('cv_candidate',False) if downloaded else None,'image':str((f/'image.tif').relative_to(WORKSPACE)).replace('\\','/') if downloaded and image_exists else '', 'image_sha256':j.get('image_sha256','') if downloaded else '', 'image_file_exists':image_exists,'userdata_file_exists':metadata_exists,'pixel_material_status':('downloaded_files_present' if image_exists and metadata_exists else 'downloaded_files_missing') if downloaded else 'not_confirmed_downloaded_pixels_unknown','actual_PU':j.get('processing_units'),'valid_fraction':q.get('valid_fraction'),'clear_fraction':q.get('clear_fraction'),'river_clear_fraction':q.get('river_clear_fraction'),'snow_fraction':q.get('snow_fraction'),'independent_labels':False,'visual_review':'pending_full_resolution_review' if downloaded else 'no_verified_material_to_review'})
 return rows

def main():
 root=WORKSPACE/'courses/AIDA-2154/data/sources/copernicus_sentinel2/raw/cv_gap_fill_20261111';out=WORKSPACE/'courses/AIDA-2154/outputs/cv_gap_fill_20261111';out.mkdir(parents=True,exist_ok=True);m=json.loads((root/'manifest.json').read_text());geometries=json.loads((root/'planned_geometries.json').read_text());rows=[]
 inventory=inventory_rows(m['jobs'],root);rows=[r for r in inventory if r['status']=='downloaded']
 good=[r for r in rows if r['cv_candidate'] and r['pixel_material_status']=='downloaded_files_present']
 for name,data in [('request_status_inventory.csv',inventory),('all_downloaded_images.csv',rows),('new_cv_candidates.csv',good)]:
  with (out/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=list(inventory[0]));w.writeheader();w.writerows(data)
 sample=good[:24];sheet=Image.new('RGB',(4*360,max(1,math.ceil(len(sample)/4))*300),'white');draw=ImageDraw.Draw(sheet);lookup={j['id']:j for j in m['jobs']}
 for i,r in enumerate(sample):
  j=lookup[r['request_id']]
  with rasterio.open(WORKSPACE/r['image']) as ds:
   a=ds.read();inside=geometry_mask([geometries[j['id']]],out_shape=ds.shape,transform=ds.transform,invert=True)&(a[5]==1);rgb=(np.clip(np.moveaxis(a[:3],0,-1).astype(float)/3000,0,1)**(1/1.8)*255).astype('uint8');rgb[~inside]=65;im=Image.fromarray(rgb);im.thumbnail((350,240));x=i%4*360;y=i//4*300;sheet.paste(im,(x+(350-im.width)//2,y));draw.text((x+5,y+244),f'{i+1:02} {r["scene_time"][:10]} {r["grid"]}',fill='black');draw.text((x+5,y+260),f'river clear {r["river_clear_fraction"]:.1%}, label pending',fill='black')
 sheet.save(out/'new_candidates_contact_sheet.png')
 qa=json.loads((root/'quota_after.json').read_text()) if (root/'quota_after.json').exists() else None
 summary={'planned_missing_requests':len(m['jobs']),'status_counts':dict(Counter(j['status'] for j in m['jobs'])),'new_downloaded_archives':len(rows),'new_cv_candidates':len(good),'pu_used_this_run':m['pu_spent_this_run'],'quota_after':qa,'training_started':False,'independent_labels':0,'archive_bytes':sum((root/j['id']/'response.tar').stat().st_size for j in m['jobs'] if (root/j['id']/'response.tar').exists()),'candidate_years':dict(Counter(r['scene_time'][:4] for r in good))}
 (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 text=f'''本次清单包含 {len(m['jobs'])} 个计划请求，已下载 {len(rows)} 张，严格清晰指标候选 {len(good)} 张。请求状态计数见 summary.json，全部请求及本地文件状态见 request_status_inventory.csv。needs_review 表示结果待核查，不等于成功、失败或免费，不自动重试。

已记录处理单位回执合计 {m['pu_spent_this_run']:.3f} PU。这不是未知请求费用确认，也不是账户实时余额；配额应核对官方页面及对应时间的 quota_after.json。

all_downloaded_images.csv 列已下载影像；new_cv_candidates.csv 仅列严格指标子集；new_candidates_contact_sheet.png 仅显示该子集前24张。它们不能代替多样性主清单或独立水体标签。

原始10m六波段影像、请求和响应证据均保留。本次只生成本地派生汇总，不调用下载API、不重试请求、不训练模型。复现：`.venv\\Scripts\\python.exe -B run.py -m cv_tools.summarize_cv_gaps`。
'''
 diversity=out.parent/'cv_material_diversity_20261111'
 completed=sorted(p for p in diversity.glob('*') if p.is_dir() and (p/'summary.json').exists() and (p/'README_CN.md').exists())
 latest=f'[最新已完成快照 {completed[-1].name}](../cv_material_diversity_20261111/{completed[-1].name}/README_CN.md)' if completed else '尚无完整快照，请先运行素材多样性筛选命令。'
 current=f'''# 当前规则：保留薄雾与局部云素材

request_status_inventory.csv 单列所有请求状态。只有 downloaded 读取实际元数据并进入影像清单；needs_review、pending 等非完成状态的像素质量、实际过境时间和候选资格均未知，不计作下载成功，也不自动重试。文件是否存在只表示本地文件状态，不证明请求成功。实际费用未知保持为空，不能当作零。下载状态异常或缺文件需另外核对。

本报告中的 cv_candidate 和 new_cv_candidates.csv 仍表示历史严格清晰度指标子集，不是全部可用素材。cv_candidate=False、held 或清晰率未达旧阈值，不等同于当前排除或不能标注。

清晰素材与河道仍可辨认的薄雾、局部云素材均保留。需要逐区域原分辨率复核；真正不可辨认的区域确认后忽略，无效像素必须忽略。供应商云影/雪冰标记只是复核建议，不能用作水体或非水体标签。

当前主清单在 [多样性时间戳快照目录](../cv_material_diversity_20261111/)，不在本目录的严格候选 CSV。{latest}。只采用同时包含 summary.json 与 README_CN.md 的完整快照。该快照可能早于本次下载汇总，不会自动纳入之后完成的下载。

刷新主清单：`.venv\\Scripts\\python.exe -B run.py -m cv_tools.retain_challenge_materials`。更多解释见 [CURRENT_REVIEW_CN.md](CURRENT_REVIEW_CN.md)。原始影像和旧筛选证据保留，未训练模型。

## 历史严格指标汇总

'''
 (out/'README_CN.md').write_text(current+text,encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
