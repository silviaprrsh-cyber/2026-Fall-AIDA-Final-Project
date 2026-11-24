# Gap-fill inventory and current review rules

Historical report, 2026-11-11. Only downloaded requests enter the image inventory using actual metadata. request_status_inventory.csv lists every request. needs_review and pending results have unknown pixel quality, sensing time and eligibility; they are not confirmed downloads and are not automatically retried. Local file existence alone does not establish successful server execution. Unknown actual costs remain blank, not zero. Abnormal status or missing files requires separate checking.

cv_candidate and new_cv_candidates.csv retain the historical strict-clear-quality subset. False, held or a failed old clarity threshold does not mean current exclusion. Keep clear imagery and challenging haze/partial-cloud imagery where the river remains discernible. Review at native resolution, ignore confirmed uninterpretable areas, and always ignore invalid pixels. Provider cloud/shadow/snow/ice flags are review aids, never water/non-water truth.

Use the completed diversity inventory [20261111T092336634170Z](../cv_material_diversity_20261111/20261111T092336634170Z/README.md), rather than this strict-subset CSV. A usable snapshot contains both summary.json and README.md; it does not automatically incorporate later downloads. Refresh from the project root with `.venv/Scripts/python.exe -B run.py -m cv_tools.retain_challenge_materials`. See [current review](CURRENT_REVIEW.md). Original imagery and historical screening evidence remain identifiable; this reporting stage trained no model.

## Recorded strict-screening totals

2,751 planned requests; 2,749 downloaded images; 1,149 strict-clear candidates. summary.json records status counts. needs_review is neither success nor failure nor free execution.

Recorded receipts total 4,525.755 processing units. This does not establish the costs of unknown requests or the live account balance; use the official account page and time-matched quota_after.json.

all_downloaded_images.csv lists downloaded images; new_cv_candidates.csv is only the strict subset; new_candidates_contact_sheet.png shows its first 24. None replaces the diversity inventory or independent labels. Original 10 m six-band imagery and request/response evidence remain retained.

Reproduce local summary generation with `.venv/Scripts/python.exe -B run.py -m cv_tools.summarize_cv_gaps`. That command summarizes existing local evidence without acquisition API calls, request retries or model training.
