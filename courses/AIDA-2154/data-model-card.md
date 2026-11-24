# Computer vision data and model card

Updated 2026-11-13 against the current course README. This describes the retained experiment, not operational readiness.

## Decision, user and scope

A municipal river-infrastructure reviewer asks whether archived satellite segmentation can supply reliable point-width information for a prediction model. **Withhold current CV output from that model.** The obtainable imagery is not sufficiently clear at its native 10 m scale for this target-width task. Mixed bank/water pixels, narrow channels, cloud/shadow and bridge occlusion limit boundary detail. Resolution is not proven to be the sole cause of every error; this is not a claim that all satellite methods fail.

Scope: P01-P05 and discharge stations 05CB001, 05CB007, 05CC002, 05CC007. Exclude 05CC003/05CC012 from this CV task. Non-use: flood warnings, physical depth, safety decisions, live monitoring, new-river generalization, downstream model features or labels. A false detection can invent a wide channel; a miss can suggest dry or safe land. Neither interpretation is accepted.

## Data identity and selection

Source: CDSE Sentinel-2 L2A historical and gap-fill archives. Original TIFFs remain unchanged. EPSG:32612, native 10 m RGB/NIR, 61 x 61 pixel windows (610 m square); source reflectance is multiplied by 10000. Provider SCL originates at 20 m and is not independent 10 m truth. Exact sources/hashes are in data/processed/point_water_masks_20261113/full_manifest.json.

Candidate masks use NDWI/NDVI, reflectance, river-line seeds/connectivity and one 3 x 3 cross-shaped water closing (dilation then erosion), not opening. Values: 1 water candidate, 0 visible background, 255 unknown. There are 2,322 masks and 1,436 point/date combinations. 607 priority-review candidates have overlapping reasons; unflagged does not mean correct.

Training excludes those 607 candidates, over-10%-unreliable scenes, empty water and two visually identified 05CC007 false expansions. Same-point/date products are deduplicated, exact cross-split duplicate crops rejected, and boundary samples purged. Limited cloud/thin haze does not automatically reject a whole scene; unreliable pixels do not enter normalization, loss or scoring. The final dataset ignores 13,413 targets.

The 1,009 samples use automatic labels. Visual checks identified errors, but image detail was insufficient to reliably trace water boundaries and verify masks for independent reference labels. Membership is in data/processed/point_cnn_20261113/dataset_manifest.json. Old corridor counts are acquisition history, not final CNN counts. See [permission and selection](docs/data-permission-selection.md).

## Fixed split and methods

| Split | Samples | Dates | Range |
|---|---:|---:|---|
| Train | 708 | 204 | 2016-05-02 to 2024-09-07 |
| Validation | 169 | 41 | 2024-09-22 to 2025-10-05 |
| Test | 132 | 40 | 2025-10-22 to 2026-10-20 |

All points from a date stay together, with a seven-day boundary exclusion. Fixed-site temporal holdout is not spatial generalization and does not remove shared-label bias or all temporal dependence.

Baseline: each point's average training-label mask. CNN: 6,113-parameter RGB/NIR encoder/decoder with convolutions, ReLU, pooling, upsampling and a high-resolution skip connection. This tests image responsiveness against static site shape using course CNN concepts.

Seed 42, Adam learning rate 0.001, batch 16, four CPU threads, maximum 40 epochs, patience 10, training-only normalization, paired flips, weighted BCE with training-derived positive weight capped at 10. Save whenever validation loss is strictly lower; threshold fixed at 0.5. Epoch 40 selected, validation loss 0.081287. Test scores did not select the checkpoint. A four-epoch preliminary run was interrupted for label rejection before test scoring, then restarted from seed 42. Retained code/configuration reconstruct the protocol; this closure does not invent a preregistration date.

## Results and resources

| Method | TP | FP | FN | TN | IoU | Precision | Recall |
|---|---:|---:|---:|---:|---:|---:|---:|
| CNN | 58,327 | 9,096 | 1,025 | 420,985 | 85.2136% | 86.5091% | 98.2730% |
| Static mask | 53,628 | 4,182 | 5,724 | 425,899 | 84.4083% | 92.7660% | 90.3558% |

These are held-out automatic-label agreement, not independent segmentation/physical-width accuracy. IoU gain is 0.8052 percentage points, with more FP. Narrow-site IoU: 05CB001 62.28%, 05CC007 53.74%. The first test image per site is retained, not selected by score.

Original train/evaluate runtime was 93.57 seconds, four CPU threads, PyTorch 2.15.0+cpu. Original training peak memory was not measured. Any supplementary resource replay is a separate measurement: data/processed/cv_release_20261113/evaluation/evaluation.json; verified status is in release-checklist.md.

Frozen indirect validation found 124/132 complete three-transect widths; 70 station scenes matched preceding observations within 300 seconds, 68 with complete widths. Five 05CC007 scenes predicted zero width with positive flow. Correlation alone neither proves segmentation error nor provides missing truth. P01-P05 do not inherit a nearby gauge as local truth. See [failure report](docs/cv-width-failure-report.md).

## Identity, authority and disposition

The experiment directory retains arrays, manifests, weights, training history, scores and predictions. Weight SHA-256: 57659d1f5acfe621b81996b5745d4d3d92c9c6c782f9facab71bd7db3d369b32. The failure report has a 19-file preservation ledger. Reproduction is documented in the course README and release instructions; source is in src/cv_tools/. Supplementary work must not overwrite the experiment.

Teacher README records proposal approval; feedback supports bounded historical study and keeping unvalidated CV outside the core model. Source permission, attribution and redistribution are separate from proposal approval; exclude credentials/private correspondence.

**Withhold downstream and operational use; retain the reproducible negative-result classroom experiment.** Reconsider only with clearer suitable imagery and independent references followed by evaluation. See responsible-use-limitations.md, ai-use-declaration.md, docs/retrospective.md and release-checklist.md.

## Supplementary reproducibility measurements - 2026-11-13

A separate unchanged-configuration training replay recorded 78.0578 seconds wall time, 224.1094 seconds process CPU time, four threads and 560,390,144 bytes peak working set (534.43 MiB). Its selected epoch and test counts match the original; its resource record reports original evidence unchanged. This is a replay, not another model-selection experiment. Evidence: data/processed/cv_release_20261113/training_replay/resources.json.

Frozen inference replay recorded 6.0094 seconds total wall time, 0.3309 seconds model inference, four threads and 440,422,400 bytes peak working set (420.02 MiB), using Windows GetProcessMemoryInfo PeakWorkingSetSize over the whole process. Recomputed probabilities have maximum difference 0.0 from the stored predictions; confusion counts match and derived Dice is 0.920166. These are reproducibility/resource checks, not new independent accuracy evidence. A separately labelled post-hoc threshold sensitivity compares 0.4/0.5/0.6 without changing the selected 0.5 threshold or using the test set to choose a replacement model.


## Engineering pipeline extension (2026-11-13)

The original scientific results and withholding decision are unchanged. A separate PostgreSQL/view-driven replay regenerates masks and trains a new artifact from the retained frozen selection. File references, hashes, SQL audit and run identities provide lineage. This is not independent truth validation. Container packaging is an isolated inference demonstration; Windows Docker inference was verified on 132 images, with identical masks and zero valid-pixel probability difference. Model weights and inputs remain external read-only mounts.
