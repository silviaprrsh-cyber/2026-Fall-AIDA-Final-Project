"""Replay frozen visual-review decisions; never invent labels or run training."""
import csv,hashlib,json
from project_paths import WORKSPACE

def main():
 p=WORKSPACE/'courses/AIDA-2154/outputs/cv_material_screening_20261111'
 rows=list(csv.DictReader((p/'diverse_shortlist.csv').open(encoding='utf-8-sig')))
 review=json.loads((p/'visual_review.json').read_text(encoding='utf-8'))
 if hashlib.sha256((p/'shortlist_contact_sheet.png').read_bytes()).hexdigest()!=review['contact_sheet_sha256']:raise ValueError('Contact sheet changed; visual re-review required')
 lookup={r['id']:r for r in review['reviews']}
 if set(lookup)!={r['id'] for r in rows}:raise ValueError('Shortlist changed; review required')
 for r in rows:
  v=lookup[r['id']]
  if r['image_sha256']!=v['image_sha256']:raise ValueError('Image identity changed')
  r['visual_review_status']=v['decision'];r['visual_review_note_cn']=v['note_cn']
 for filename,decision in [('priority_annotation_19.csv','prioritize_annotation'),('held_after_preview_5.csv','hold')]:
  with (p/filename).open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(r for r in rows if r['visual_review_status']==decision)
 print('Verified frozen review identities and reproduced review lists.')
if __name__=='__main__':main()
