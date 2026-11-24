# CV project overview: from satellite imagery to a Windows container

Updated: 2026-11-13. Scope: AIDA 2154, Red Deer River CV component.

## 1. Project introduction and intended outcome

The CV component was designed to extract water-surface width at selected Red Deer River locations from satellite images. Its intended users were municipal river-infrastructure and emergency-planning reviewers. The selected locations are P01-P05 and the discharge stations 05CB001, 05CB007, 05CC002 and 05CC007, located using the project GIS layers.

The intended product was a dated width value in metres at each point, supported by a water mask and quality information. These measurements were intended to support the larger river prediction model. The completed course work instead delivers an independent, reproducible water-segmentation experiment with database lineage and Windows-container inference.

The latest course README requires a bounded CPU prototype, a baseline, a fixed evaluation split, error analysis, responsible-use documentation and a reproducible package. This report summarizes the technical work; the [requirements audit](requirements-audit.md) and [release checklist](../release-checklist.md) track the remaining submission activities.

## 2. Original overall workflow

The original proposal/design combines archived observations and offline ETL with a static reach database; recorded outputs used JSON, CSV and SQLite. Hydrological estimates support educational risk displays, not operational warnings. Independently segmented CV masks yield width, area and expansion through GIS postprocessing, then support comparisons at matching locations and acquisition times and validated bias feedback. Source: Scope Proposal pp. 2 and 4; Project Design pp. 5, 8 and 24.

```text
[Water/weather APIs] -> [Raw archive + offline ETL] --+
                                                    v
[Networks + surveys] -> [Verified static database] -> [Section flow/level/routing]
                                                    |                 ^
                                                    v                 |
                                     [Educational risk display]       |
                                                                      |
[Satellite imagery] -> [Independent segmentation] -> [GIS width/area]  |
                                                    |                 |
[Section estimates at matching location/time] ------+                 |
                                                    v                 |
                                      [Compare + validate bias] ------+
```

The later independent CV engineering workflow uses PostgreSQL:

```text
[Existing API image files + GIS-selected samples]
    -> [PostgreSQL source references/metadata + SQL audit]
    -> [v_raw_images] -> [Generate versioned local mask files]
    -> [PostgreSQL mask references/versions + SQL audit]
    -> [v_training_pairs] -> [CNN training + versioned checkpoint]
    -> [Local Windows Docker inference + parity test]
```

Views supply records and file references; Python performs raster processing and CNN computation. Raster binaries remain in managed files. This independent pipeline ends at packaged inference and is not connected to the river prediction model.

## 3. Data acquisition and processing

### Source and selection

Sentinel-2 L2A imagery was obtained through the authenticated Copernicus Data Space Ecosystem processing API. The database workflow registers the existing downloaded products, preserving their acquisition metadata and SHA-256 identities. This migration made **zero new satellite API requests**.

The registered inventory contains 1,442 source image files and 2,322 point samples, acquired from 2016-05-02 to 2026-11-04 with irregular coverage. Each point crop is 61 x 61 pixels on the native 10 m grid. Inputs are red, green, blue and near-infrared reflectance, divided by 10,000 and clipped to [0,1]. The SCL quality layer originates at 20 m and is resampled for the crop.

Catalogue discovery uses `https://stac.dataspace.copernicus.eu/v1/search`; image processing uses `https://sh.dataspace.copernicus.eu/process/v1`. Returned bands are B04, B03, B02, B08, SCL and dataMask on an EPSG:32612 grid.

### Masks and training

Green/NIR and red/NIR spectral rules, narrow-channel seeds and water closing (dilation followed by erosion) produce the automatic candidate masks. A three-pixel halo is processed before the final crop; closing uses a 3 x 3 cross. Water is 1, non-water is 0, and excluded pixels are 255. Cloud, shadow and snow areas remain unknown rather than becoming land labels.

Selection removes unsuitable samples, duplicate point/date samples and split-boundary dates. The retained 1,009 samples are grouped by acquisition date, with a seven-day exclusion gap at split boundaries:

| Split | Samples | Acquisition-date range (UTC) |
|---|---:|---|
| Training | 708 | 2016-05-02 to 2024-09-07 |
| Validation | 169 | 2024-09-22 to 2025-10-05 |
| Test | 132 | 2025-10-22 to 2026-10-20 |

Normalization uses training data only. The baseline is a fixed per-point mask derived from training labels. The selected CNN has four input channels and 6,113 parameters; seed 42, four CPU threads, batch size 16, Adam learning rate 0.001 and 40 epochs. A checkpoint is saved whenever validation loss strictly decreases. The selected checkpoint is epoch 40; inference threshold is 0.5.

The PostgreSQL replay regenerated all 2,322 masks with identical pixels and assembled the 1,009 training pairs through the view. It saved a new training run instead of overwriting the original experiment. The resulting checkpoint SHA-256 matches the retained model.

Source attribution: Contains modified Copernicus Sentinel data [2016-2026]. See [data authority and selection](data-permission-selection.md). Raw satellite/hydrological archives, GIS originals and credentials remain outside this report and the container image.

## 4. SQL structure, fields and auditing

PostgreSQL 18.6 uses the separate `cv_pipeline` schema. Raster content stays in managed local files; SQL stores identities, references, relationships and execution records. The authoritative definition is [cv_pipeline.sql](../sql/cv_pipeline.sql).

| Table | Fields and purpose |
|---|---|
| `runs` | `run_id` text primary key; `stage` text; `started_at` and `finished_at` timestamptz; `status` running/complete/failed; `details` JSONB for counts, metrics and artifacts. |
| `scenes` | `scene_id` text primary key; unique `source_path`; 64-character `sha256`; `acquired_at` timestamptz; `provenance` text; `imported_at` timestamptz. |
| `samples` | `sample_id` text primary key; `scene_id` foreign key; `point_id`; `coordinates` JSONB; nullable `split` train/validation/test; `original_record` JSONB; `selection_manifest_sha256`. |
| `masks` | Composite primary key (`sample_id`, `method_id`); sample foreign key; artifact `path` and `sha256`; `water_pixels`, `unknown_pixels` integers; `run_id` foreign key. Method identity distinguishes mask versions. |
| `audit` | Identity `event_id`; `occurred_at` timestamptz; database `actor`; `transaction_id`; `table_name`, `operation`, `row_key`; `old_row` and `new_row` JSONB. |

Relationships: one scene can supply several point samples; each sample can have mask records under different method identities; every mask belongs to a generation run.

- **`v_raw_images`** joins samples to scenes, providing point coordinates, split/selection metadata, source path/hash, acquisition time and provenance.
- **`v_training_pairs`** adds mask path/hash, method and run identity. It admits selected split members only from completed mask runs. Training reads paired records in a repeatable-read snapshot, then checks frozen membership, dates, hashes and grids before assembling tensors.
- **Audit triggers** run after INSERT, UPDATE or DELETE on `runs`, `scenes`, `samples` and `masks`. They preserve old/new row values in the same transaction; rolled-back changes do not leave committed audit rows. This is a reproducibility ledger, editable by a database owner.

The verification snapshot at **2026-11-13 17:13:02 UTC** recorded 1,442 scenes, 2,322 samples, 2,322 masks, 1,009 training pairs and 6,094 committed audit events. Repeated registration preserved the scene/sample counts.

The unified entry point is `python -B run.py cv`, with `init`, `register`, `masks`, `train`, `verify` and `all` stages. Existing shared connection, path and atomic-write modules are reused. Hydrological schemas are unchanged. Credentials are read from the existing ignored configuration, not embedded in code or documents.

## 5. Difficulties, failed objective and evidence

The fundamental limitation was **insufficiently clear satellite imagery at the available spatial resolution**. With native 10 m pixels, narrow channels and mixed water/bank edges are difficult to resolve; cloud, shadow and bridges add ambiguity. Visual checks identified errors, but image detail was insufficient to reliably trace water boundaries and verify masks for independent reference labels. The labels remain automatically generated candidates. Consequently, segmentation agreement alone did not establish reliable physical width.

| Held-out pixel result | CNN | Fixed training-mask baseline |
|---|---:|---:|
| TP | 58,327 | 53,628 |
| FP | 9,096 | 4,182 |
| FN | 1,025 | 5,724 |
| IoU | 0.852136 | 0.844083 |

An indirect check measured water along 500 m GIS-oriented transects, with parallel offsets of +/-50 m. It produced 124 complete three-transect measurements from 132 test images. All 70 station images matched an earlier hydrological observation within 300 seconds; 68 had complete widths. Matching uses acquisition timestamps, not filenames.

Key failure cases:

- At 05CC007, five test dates produced median width zero while observations still recorded discharge. For example, 2026-08-21 had 0.780 m3/s. The output missed a usable flowing-channel width.
- At P04, width ranged from 85.0 to 195.5 m. MAE against automatic-mask width was 29.69 m, worse than the fixed baseline's 14.93 m.
- Narrow-station candidate-label IoU was 0.622829 at 05CB001 and 0.537389 at 05CC007. Width/discharge rank correlations across the four stations were 0.080, -0.619, -0.148 and 0.251.

These errors and the lack of independent width measurements led to withholding CV width from downstream prediction. Correlation is a consistency check, and automatic-mask MAE is not a surveyed width error. P01-P05 also lack local observed hydrometry and verified arrival alignment. Detailed figures, exact match times, sensitivity checks and file hashes are in the [failure report](cv-width-failure-report.md) and retained local evidence.

## 6. Completed engineering outcome

**The intended reliable-width input was not achieved; the independent data-to-model workflow and Windows container were completed.**

| Verified outcome | Evidence |
|---|---|
| SQL views -> masks -> CNN | 2,322 regenerated masks, 1,009 paired samples; checkpoint matches the retained model. |
| CPU training | Training function 106.8 s; enclosing train-call interval 109.060 s; whole database training stage including materialization/checks 535.658 s. Mask generation stage: 222.695 s. Entire replay-process peak working set: 664,870,912 bytes. These are separate measurements, not an acquisition-to-container total. |
| Windows image | `aida2154-cv:windows-local`, Windows/amd64, 5,983,068,037 bytes; image ID starts `6357eafb81bc`. |
| Actual container run | 2026-11-13, exit code 0; Hyper-V isolation, `ContainerUser`, network disabled, four CPUs, 4 GiB limit. Inference routine: 10.656 s. |
| Output comparison | All 132 masks identical to host output; maximum valid-pixel probability difference 0; 1,739 unknown pixels preserved. |
| Preservation and checks | Eight container/context tests passed; 19 original experiment files retained their hashes. |

The image packages the runtime, shared model architecture and inference entry point. The checkpoint and input arrays are supplied through external read-only mounts, with a separate output mount. There is no main-model integration, registry push or image tar export. WSL and Virtual Machine Platform remain disabled.

Use the [container guide](../container/README.md) for build/run commands and the [PostgreSQL pipeline guide](postgres-cv-pipeline.md) for staged replay. Docker packaging establishes a usable execution artifact while the course recommendation remains to withhold the current CV width from river prediction.

### Evidence index

Paths below are relative to `courses/AIDA-2154/`; data folders are local and Git-ignored.

- `data/processed/point_cnn_20261113/`: frozen split, checkpoint, metrics and test predictions.
- `data/processed/point_width_validation_20261113/`: width comparisons, transects and diagnostic figures.
- `data/processed/cv_pipeline_20261113/database_verification.json`: database snapshot and completed runs.
- `data/processed/cv_pipeline_20261113/train_from_view_096165fbab2e440f8f8dd3a3dae78b0d/pipeline_result.json`: training replay and resource evidence.
- `data/processed/cv_container_20261113/windows_container_verification/`: build/run logs, image inventory, verification and predictions.

This report adds documentation only; it does not rerun training or modify retained results.
