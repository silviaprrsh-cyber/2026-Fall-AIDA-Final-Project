# data

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

## Current contents
Source imagery remains unchanged in sources/copernicus_sentinel2. Derived point masks, frozen CNN data/model and width checks remain in processed/point_water_masks_20261113, point_cnn_20261113 and point_width_validation_20261113. Supplementary reproducibility evidence and a local candidate ZIP are in processed/cv_release_20261113. These directories are Git-ignored. Only the allowlisted derived Sentinel data needed for the candidate replay are copied into its package; original acquisition archives, credentials and unrelated survey inputs are excluded. See ../docs/data-permission-selection.md.


## Database replay artifacts

Generated masks, view-derived training tensors and run reports are in processed/cv_pipeline_20261113, which is Git-ignored. PostgreSQL stores managed relative file references and hashes, not raster blobs. Existing raw imagery and retained experiments remain unchanged.
