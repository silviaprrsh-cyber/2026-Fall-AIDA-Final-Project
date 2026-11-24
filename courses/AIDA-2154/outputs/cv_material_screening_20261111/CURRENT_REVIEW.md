# Current material-retention rules: correction of 2026-11-11

The latest complete [coverage verification](../cv_material_diversity_20261111/20261111T092336634170Z/COVERAGE_VALIDATION.md) covers 3,524 images: 1,426 clear-proxy and 2,098 challenge-review images, with two unknown requests separate. Earlier snapshot links remain historical only.

This directory retains strict clarity screening and preview records. Old eligible/cv_candidate=False, rejection_reasons or held fields are not current exclusions or proof that CV use is impossible.

Retain clear imagery and discernible haze/partial-cloud cases. Low SCL clarity requires regional review, not whole-image rejection. Ignore confirmed uninterpretable regions and invalid pixels. Provider cloud/shadow/snow/ice flags are review suggestions, not water/non-water truth.

Use the newest complete [diversity snapshot](../cv_material_diversity_20261111/) containing summary.json and README.md. The early 20261111T073754499301Z snapshot was verified at that time; later downloads require a new snapshot. Run `.venv/Scripts/python.exe -B run.py -m cv_tools.retain_challenge_materials`.

Historical previews 11/12/16 and new 8/9/13 are retained as challenging cases; historical 1/15 remain regional-suitability cases because coverage is small. All need independent labels and native-resolution review. This note did not modify old CSVs, original imagery, request status or models.
