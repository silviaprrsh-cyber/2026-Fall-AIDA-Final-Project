# Satellite CV material: retain haze and partial-cloud diversity

This is a historical material-review snapshot, not a labelled training set. The count is recorded in summary.json. It includes only completed imagery present when the manifests were read; later downloads require a new timestamped snapshot. Original reports, imagery and download status were not changed by this review stage.

## Revised criteria

Haze, local clouds or unusual brightness alone do not justify rejecting a whole image. Where river boundaries remain reliably discernible, regions may be candidates for independent annotation alongside clear cases. Human confirmation is required before ignoring uninterpretable regions. Never guess water boundaries or label cloud/invalid pixels as land.

- clear_proxy_label_review.csv: passes old strict pixel metrics and lacks an existing preview hold. clear_proxy is only an SCL-based proxy, not proof of clear, usable or labelled imagery.
- challenge_region_review.csv: retains haze, cloud/shadow, snow/ice, low coverage, other failed old SCL thresholds and preview concerns. Inspect individual regions. This is not an all-haze or all-trainable group; snow/ice needs separate treatment for unfrozen-water use.
- unreliable_input_review.csv: hash failures, no valid pixels or no reflectance signal. Original files remain retained.
- region_quality_inventory.csv and region_review_masks/: review aids only. Codes: 0 outside-scope ignore; 1 valid/unlabelled; 2 invalid/must ignore; 3 provider cloud/shadow review suggestion; 4 provider snow/ice review suggestion; 5 other SCL review. Codes 3/4/5 do not confirm obstruction or require whole-region exclusion; code 1 does not guarantee visibility. Never train water/non-water classes directly from these masks.

## Previous previews

previous_holds_retained.csv preserves all eight previous holds. Historical 11/12/16 and new 8/9/13 enter challenge review; historical 1/15 remain small-coverage suitability cases. New 8/9/13 retain visible river form and merit native-resolution inspection. Historical 11/12 are visibly whitened, so thumbnails cannot establish usability everywhere; historical 16 has little coverage. This changes material disposition only, without creating human labels or approving training. No visual conclusion is made for images outside the reviewed contact sheets.

## Reproduction and limits

Run `.venv/Scripts/python.exe -B run.py -m cv_tools.retain_challenge_materials`. By default it creates a new UTC-stamped output directory. Exact replay uses `--snapshot <this input_snapshot.json> --output <new course outputs directory>`. The snapshot records completed tasks, geometry and previous metrics/previews. Reproduction rechecks image SHA-256, six bands, 10 m and EPSG:32612 and recalculates pixel metrics; in-progress files are not read.

The 500 m corridor is the study area; the 20 m line neighbourhood assesses coverage, not water truth. Native 20 m SCL resampled to 10 m cannot supply 10 m ground-truth precision. Candidates still require independent labels, grouped splits, leakage controls, error slices and licensing checks. The archives use different event-key formats, so unify real overpass time/orbit and spatial proximity before splitting; do not split directly on event_group_hint. This stage neither trained/tuned a model, froze the final split nor claimed accuracy.
