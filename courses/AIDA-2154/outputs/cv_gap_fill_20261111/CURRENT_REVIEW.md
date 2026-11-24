# Current material-retention rules: correction of 2026-11-11

The latest complete [coverage verification](../cv_material_diversity_20261111/20261111T092336634170Z/COVERAGE_VALIDATION.md) includes 2,749 new and 775 historical images; two unknown requests are listed separately. The earlier 616-new-image snapshot remains historical evidence only.

new_cv_candidates.csv, cv_candidate=False and held records describe earlier strict clarity screening or preview decisions, not current exclusions. The strict candidate CSV is not the master inventory of retained CV material.

Retain clear material and haze/partial-cloud cases with discernible river regions. Failing an old SCL threshold calls for regional inspection, not whole-image rejection. Ignore confirmed uninterpretable regions and all invalid pixels. Provider cloud/shadow/snow/ice labels are not water/non-water labels and do not establish total invisibility.

Use the latest completed directory under [diversity snapshots](../cv_material_diversity_20261111/) containing summary.json and README.md. The earlier verified 20261111T073754499301Z snapshot contained the 616 new downloads available then and never updated itself as downloading continued. Refresh with `.venv/Scripts/python.exe -B run.py -m cv_tools.retain_challenge_materials` from the root.

New previews 8/9/13 are retained as challenge cases. All candidates still need native-resolution regional review and independent annotation. This policy note did not alter historical CSVs, source images, download status or models.
