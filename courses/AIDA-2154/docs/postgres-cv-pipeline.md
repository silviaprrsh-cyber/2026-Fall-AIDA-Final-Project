# PostgreSQL CV pipeline

This is an additive engineering workflow, not a new claim of river-width accuracy. Archived API imagery is registered by relative path and SHA-256, then read through a PostgreSQL view to regenerate masks. Images and masks remain managed files; PostgreSQL stores provenance, associations, versions, splits and audit records, not raster blobs. No raw library is duplicated into Git or a Docker image.

## Structure
- `cv_pipeline.scenes`: source identity, acquisition timestamp, archive provenance.
- `cv_pipeline.samples`: GIS point, coordinates, frozen selection and split, source relation.
- `cv_pipeline.masks`: generated artifact hash/path, method identity and generation run.
- `cv_pipeline.runs`: started/completed/failed execution records.
- `cv_pipeline.audit`: SQL triggers record inserts, updates and deletes with old/new rows.
- `v_raw_images`: source-to-point input for the mask worker.
- `v_training_pairs`: joins raw input to a completed mask run; selects frozen split members.

This audit is for reproducibility, not a tamper-proof security ledger. Database owners can modify it. Credentials stay in the existing ignored `.env` or runtime PG environment variables (the shared existing .env precedence is retained) and are never copied into reports. This schema does not modify hydrological schemas or account permissions.

## Commands from the project root
Use the existing project environment with psycopg 3.3.7 and the CV dependency versions. PostgreSQL must already be available and local PG settings configured.

```powershell
python -B run.py cv init
python -B run.py cv register
python -B run.py cv masks
python -B run.py cv train
python -B run.py cv verify
```

`register` imports already-downloaded API products referenced by the retained point-mask inventory. It does not issue a new API request or claim that historic acquisition events were audited when they happened. Repeating it is idempotent; modified source bytes or a changed frozen selection are rejected. The existing API downloader remains the acquisition component. Newly downloaded images require a new reviewed selection/version; they are not silently admitted into this frozen experiment.

`masks` reads `v_raw_images`, regenerates candidate labels with the original spectral rules and WATER closing, writes a new run directory and audited database references. It verifies pixel equality with the retained masks. `train` reads a repeatable-read snapshot of `v_training_pairs`, checks paths/hashes/grids/date groups and exact frozen membership, assembles tensors from those files, then invokes the unchanged CNN training function. It does not load the old dataset as its training input; the old dataset is only a parity check. Strictly lower validation loss saves the new checkpoint. Test labels remain automatic candidates.

Outputs are under the Git-ignored `data/processed/cv_pipeline_20261113/`. Existing image, mask and model artifacts are preserved. Mask files generated during a failed run can remain as diagnostic artifacts, but the training view excludes incomplete runs. A rerun creates a fresh directory. The last successful training location is in `latest_training.json`.

A sequential replay is available with `python -B run.py cv all`. It creates new mask and training runs rather than overwriting the earlier experiments.

## Container boundary
See `../container/README.md`. The independent CPU inference container consumes a trusted new checkpoint and explicit reflectance/quality arrays. It is not integrated into flood prediction. Docker availability and actual build/run are reported separately from host-Python parity. Local Windows container deployment and inference were verified; registry publication and operational river-system deployment are outside this workflow.

## Interpretation
The existing 10 m imagery does not reliably resolve the target river boundaries. Engineering traceability does not improve this physical limitation. CV output remains unsuitable for input into the prediction model. This addition demonstrates acquisition provenance, SQL audit, views, mask processing, training lineage and packaging only.

## Shared-module boundaries
The root run.py dispatches the CV command. project_tools.database is extracted from the existing EDA connection code with compatible imports and unchanged credential precedence; CV and EDA now use it. project_paths handles root boundaries, rdr.storage.save_json performs atomic JSON writes, and the original mask and training functions are reused. CV schema/triggers remain domain-specific because no existing generic SQL audit component was present; hydrological tables are not migrated. The model architecture is shared by training and packaged inference rather than copied.

## Executed verification (2026-11-13)
- PostgreSQL 18.6: 1,442 referenced API source scenes, 2,322 point samples/masks and 1,009 frozen training pairs. Repeated import preserved scene/sample counts. SQL audit contained 6,094 committed events after these runs.
- 2,322 masks regenerated from v_raw_images matched the retained label pixels exactly.
- v_training_pairs produced the 708/169/132 split. A new 40-epoch training run selected epoch 40; TP 58,327, FP 9,096, FN 1,025, TN 420,985 and IoU 0.85213592800374. New model SHA equals the original, proving a workflow migration rather than changed predictive performance.
- Training function wall time was 106.8 seconds; entire training-process peak working set was 664,870,912 bytes. These do not measure total archive import/mask generation elapsed time.
- Nine PostgreSQL/shared-connection/path/audit/rollback tests, four CNN tests, six mask tests and seven inference-entry tests passed. The shared EDA connection remained compatible and 32 existing hydrology views remained queryable.
- All 19 retained experiment files kept their prior SHA-256 values. Generated outputs remain Git-ignored. During the database migration, no new source imagery was downloaded and no Git commit/push or downstream integration occurred. The later authorized Windows image build downloaded official runtime/dependency components, not new satellite data.
- At the earlier database-only checkpoint, Docker was unavailable. After the owner-authorized Windows Docker setup and restart, the Windows Server Core LTSC2022 build and Hyper-V inference passed. No Linux/WSL workflow was used. ContainerUser, no network, read-only external checkpoint/input and a dedicated output mount were verified. All 132 masks matched host output and valid-pixel probability difference was 0. See container/README.md and data/processed/cv_container_20261113/windows_container_verification/verification.json. No registry push or image tar export was performed.

Evidence: data/processed/cv_pipeline_20261113/database_verification.json, verification_summary.json, preservation.json and latest_training.json. New inference material is under data/processed/cv_container_20261113/database_model_verification. The original offline review ZIP was not overwritten.
