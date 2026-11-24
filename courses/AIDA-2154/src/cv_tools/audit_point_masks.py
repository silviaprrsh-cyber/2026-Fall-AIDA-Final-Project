"""Audit generated point masks and build a prioritized human-review queue."""
from collections import Counter
import csv
import json
from pathlib import Path
import numpy as np
import rasterio
from PIL import Image
from cv_tools.make_point_water_masks import OUT, WORKSPACE, points, sha

def main():
    manifest=json.loads((OUT/'full_manifest.json').read_text())
    rows=[]; flags=Counter(); checked=0
    ids={p['id'] for p in points()}
    for r in manifest['records']:
        assert r['point_id'] in ids
        with rasterio.open(OUT/r['mask']) as ds:
            a=ds.read(1)
            assert ds.shape==(61,61) and ds.res==(10,10)
            assert set(np.unique(a))<={0,1,255}
            assert int((a==1).sum())==r['water_pixels']
        reasons=[]
        if r['water_pixels']==0:reasons.append('no_water_detected')
        if r['unknown_pixels']/3721>0.10:reasons.append('unknown_over_10_percent')
        limit=0.15 if r['point_id'] in {'05CB001','05CC007'} else 0.50
        if r['water_pixels']/3721>limit:reasons.append('water_area_outlier_requires_visual_review')
        # These flags prioritize inspection, not an accuracy or safety certification.
        flags.update(reasons)
        rows.append(dict(id=r['id'],point_id=r['point_id'],date=r['date'],mask=r['mask'],preview=r['preview'],water_fraction=round(r['water_pixels']/3721,5),unknown_fraction=round(r['unknown_pixels']/3721,5),priority_reasons=';'.join(reasons),human_review_status='pending',training_ready=False))
        checked+=1
    with (OUT/'review_queue.csv').open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(sorted(rows,key=lambda r:(not bool(r['priority_reasons']),r['point_id'],r['date'])))
    summary=dict(verified_masks=checked,priority_review=sum(bool(r['priority_reasons']) for r in rows),priority_counts=dict(flags),human_approved=0,training_ready=0,distinct_point_dates=len({(r['point_id'],r['date'][:10]) for r in rows}),per_point={p:dict(masks=sum(r['point_id']==p for r in rows),dates=len({r['date'][:10] for r in rows if r['point_id']==p}),priority=sum(r['point_id']==p and bool(r['priority_reasons']) for r in rows)) for p in sorted(ids)})
    (OUT/'audit_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
    evidence=[]
    for point,day in [('P04','2026-10-12'),('05CC007','2026-10-30')]:
        candidates=[r for r in rows if r['point_id']==point and r['date'].startswith(day)]
        if candidates:evidence.append(candidates[0])
    if evidence:
        panel=Image.new('RGB',(750,310*len(evidence)),'white')
        for i,r in enumerate(evidence):panel.paste(Image.open(OUT/r['preview']),(0,i*310))
        panel.save(OUT/'seasonal_review_examples.png')
    print(json.dumps(summary,indent=2))

if __name__=='__main__':main()
