# Initial satellite CV material screening: 2026-11-11

Purpose: supporting water-extent interpretation for the Dickson Dam outlet to 05CC002 reach, not flood warning, bathymetry or safety decisions.

## Recorded result

775 active-scope overlapping images were checked pixel by pixel; zero SHA-256 mismatches. Screening produced 285 candidates from 71 overpass groups and a first 24-image shortlist spanning months and grids. These were not labelled training data. Independent ground-truth label count was zero.

Run `.venv/Scripts/python.exe -B run.py -m cv_tools.screen_cv_materials` from the project root. It reads existing imagery offline and updates local derived screening results, without downloads, training or model changes.

Historical strict thresholds: valid coverage >=95%; clear fraction in the 500 m corridor >=80%; clear fraction in the 20 m river-line neighbourhood >=90%; snow/ice <=1%; at least 100 corridor pixels and 20 line-neighbourhood pixels. Clear means provider SCL 4/5/6, shadow/cloud 3/8/9/10, snow/ice 11. The 20 m band tests obstruction near the mapped line; it is not water truth. River-line error, narrow-river mixed pixels and SCL error still require review. Hydrological matching within 150 seconds is auxiliary, not a mandatory water-CV eligibility condition or independent water truth.

## Files and interpretation

- all_image_screening.csv: complete imagery screening, quality, historical rejection reasons and time matching.
- eligible_label_review.csv: automated quality candidates awaiting human inspection/annotation.
- diverse_shortlist.csv: first multi-month/grid review list, not a frozen train/validation/test split.
- shortlist_contact_sheet.png: consistently stretched RGB previews; grey is outside the corridor or invalid. Thumbnails cannot establish boundary labels.
- catalog_pixel_availability.csv: 5,785 intersecting catalog products, including 5,500 without a source identity in the old downloaded archive. A crop does not imply acquisition of the whole product/current corridor.
- summary.json: thresholds, counts, input/script hashes and timing.

## Historical preview review

Among 24 RGB previews, 19 were prioritized in priority_annotation_19.csv and five initially held in held_after_preview_5.csv. Previews 11/12 showed whitening/thin-cloud-like features, 16 combined whitening and very small coverage, and 1/15 showed very little river. High SCL clarity cannot replace visual inspection. visual_review.json stores image/contact-sheet hashes, position and reasons. These were material-priority decisions only, without labels, cloud-type confirmation or frozen CV partitions.

Candidates by season: spring 30, summer 126, autumn 129, winter zero. This evidence cannot support winter/ice performance claims. [Current review rules](CURRENT_REVIEW.md) subsequently retained the difficult cases rather than treating historical hold/rejection flags as exclusions.

## Remaining evidence

Native-resolution independent water/non-water/uninterpretable masks need annotator/date/rule/disagreement records. Cloud, shadow, ice and invalid pixels must not be forced into land. Group by actual overpass event: neighbouring grids on the same date/orbit and reprocessing versions must stay together. Review temporal, spatial and seasonal coverage before splitting. Baselines, frozen validation, error analysis, CPU evidence and human takeover rules remain separate course requirements. Confirm Copernicus attribution and final-release permission against the project permission record.
