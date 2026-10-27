# AIDA 2154 — Computer Vision

Purpose: inspect satellite water extent for the selected river reach as supporting evidence, not an hourly flood-warning product.

Code: `src/cv_tools/`. Inputs: `data/sources/copernicus_sentinel2/`, with acquisition metadata and provider quality masks. Run from the workspace root: `python -B run.py cv-check`. Output: `outputs/archive_inspection.json`.

Current evidence covers raster shape, CRS, valid pixels and cloud/shadow counts. Provider masks are not a trained model. Still required: approved input/permission record, CPU-bounded baseline and model, fixed event/time/space splits, metrics and failure analysis, responsible-use/human-review decision, peer review and final package. AI assisted restructuring; no CV training or accuracy claim is made.
