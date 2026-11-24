# CV river-width experiment: failure decision

Decision date: 2026-11-13

## Decision and scope

The fundamental practical limitation is that the satellite imagery obtainable for this project is not sufficiently clear, at its available spatial resolution, to support reliable width identification in the target river reaches. The current imagery has native 10 m pixels; mixed bank/water pixels and cloud, shadow or bridge occlusion further limit usable boundary detail, particularly in narrow channels. The experiment results below are concrete evidence of inadequate output fitness and remaining uncertainty, not proof that resolution alone caused every error. This conclusion concerns the available imagery and current CV approach, not all satellite imagery. The current CV output is not suitable for input to the prediction model.

**The current CV output is not suitable for use in the prediction model.** The attempted objective was to turn satellite water segmentation at P01-P05 and four discharge stations into useful point-width data for the downstream prediction model. This CV approach has failed to establish that fitness for purpose. This conclusion is confined to the current CV project/implementation, not the entire flood-prediction project, all CNN architectures, or all satellite methods. Preserve the experiment as negative-result evidence; do not promote its outputs to model features or training labels.

## Method and held-out results

The small four-channel RGB/NIR CNN was trained on automatic candidate masks, not independently verified human ground truth. Date-grouped chronological splitting with a seven-day gap used 708 training, 169 validation and 132 test samples (1,009 total). Checkpoints were saved whenever validation loss decreased. Frozen test predictions gave TP=58,327, FP=9,096, FN=1,025, IoU=0.852136; the fixed train-only mask baseline gave IoU=0.844083. These are agreement scores against held-out automatic labels, not physical-width accuracy or independent segmentation accuracy.

The indirect check retained the frozen model and 0.5 threshold. GIS-oriented 500 m transects pass through each target, with parallel offsets of +/-50 m; their median is a neighbourhood proxy, while exact-centre results are separately retained. Native 10 m pixel intersections define water length, with unknown pixels excluded and +/-10 degree direction sensitivity reported. There are 124 complete three-transect measurements among 132 images. All 70 station images match the most recent earlier observation within 300 seconds using acquisition metadata rather than filename time; 68 have complete widths.

| Station | Complete widths | Width/Q Spearman | Width/stage Spearman |
|---|---:|---:|---:|
| 05CB001 | 9 | 0.080 | -0.050 |
| 05CB007 | 23 | -0.619 | -0.610 |
| 05CC002 | 16 | -0.148 | -0.147 |
| 05CC007 | 20 | 0.251 | 0.514 |

The constant-width baseline has undefined correlation, not zero correlation. Seasonal, clear-only, brightness, quality-code and exact-centre sensitivity results are retained. The lack of consistent positive hydrometric correlation alone does not prove segmentation errors: local channel geometry, stage/discharge behaviour, sampling and confounding also matter. It does not supply the missing independent width validation.

## Concrete failure evidence

At 05CC007, the median CNN width is zero on 2025-10-22, 2026-08-21, 2026-08-26, 2026-09-17 and 2026-09-20 despite respective observed discharge of 0.107, 0.780, 0.399, 0.174 and 0.137 m3/s. These are failures of this output to provide a usable flowing-channel width, not proof that the channel was dry or identification of a single cause. Exact acquisition/observation times and quality fields are retained in the per-image CSV.

P04 widths range from 85.0 to 195.5 m. MAE against automatic-mask width is 29.69 m versus 14.93 m for the fixed baseline. This discrepancy is a warning, not measured physical error or observed flooding. Narrow-station weak-label IoU is 0.622829 at 05CB001 and 0.537389 at 05CC007.

## Limits and disposition

No independent physical-width measurements are available. Visual checks identified errors, but image detail was insufficient for reliable boundary verification and independent reference masks. P01-P05 lack local observed hydrometry and verified arrival alignment; no neighbouring-station substitution was made. Gauge stage is not water depth. There are no winter test scenes; seasonal subsets are small. Cloud/shadow, bridges, mixed pixels, translated/planned transects and native 10 m resolution constrain interpretation. Archived matches include 65 provisional and five final records, all received after image acquisition: this is retrospective consistency, not historical live availability.

The decision is a fitness-for-purpose rejection, not an invented numerical acceptance threshold or an inference that all masks are wrong. Independent width/reference validation and a revised method would be needed before reconsidering use in the prediction model. No further training or integration is authorized by this record.

## Retained evidence and reproduction

Paths are relative to the repository root; local data remain Git-ignored, not removed:

- `courses/AIDA-2154/data/processed/point_water_masks_20261113/`: automatic masks, source manifests and review imagery.
- `courses/AIDA-2154/data/processed/point_cnn_20261113/`: dataset manifest, arrays, best_model.pt, training history, result.json and frozen test predictions.
- `courses/AIDA-2154/data/processed/point_width_validation_20261113/`: transects.json, test_width_hydrometry.csv, summary.json, transect_review.png and hydrometry_width_scatter.png.
- `courses/AIDA-2154/src/cv_tools/`: training and validation implementations, tests and CN explanations.

From the repository root, reproduce the indirect evaluation with `python -B run.py -m cv_tools.validate_point_widths` then `python -B run.py -m cv_tools.summarize_point_widths`. Four width geometry/statistics tests previously passed. This documentation-only closure does not rerun or overwrite experiments. The preservation ledger below hashes the existing experiment files and verifies they are unchanged by closure documentation; it is not a new scientific validation.

| File | SHA-256 |
|---|---|
| `courses/AIDA-2154/data/processed/point_cnn_20261113/best_model.pt` | `57659d1f5acfe621b81996b5745d4d3d92c9c6c782f9facab71bd7db3d369b32` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/dataset.npz` | `472e5b3d5e0938d1fe2ea35127e036b0904dac0335e5b1263a312ab0db1a98f5` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/dataset_manifest.json` | `b93bfd1789b8e3079daef6fc1630c379dd1c1bac26170dfa205d67159bc94c44` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/README.md` | `a787e3215e16e7231ffb844b618436c5390b5aaf2370accc27b0e788b92660b5` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/READMECN.md` | `230a605332faf4faaebd13085d9ae37faad67037f43f431c20c7d2a788d1940f` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/result.json` | `0bc6522ebf1140158f864e1ea729c049950fd4091ea79f0578f4eeb7e9b61b2b` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/selection_review.png` | `f660a7caa28a1fec881fb0c6d6b5a3d93bf5de86feb49a13775dba5d6f6d4bad` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/selection_summary.json` | `228c067fcd27656f2d926f2c006462f436a52f4822ce4dad3159ef63f9c200ee` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/test_examples.png` | `449b303df3a4276233d5c63f7c0332e5ca477ed45b3bd1e124c8af5062021fdc` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/test_predictions.npz` | `87030836872819bc4cf93ef8e1b73629a4571c97bb1884c375df88cb243ee444` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/training_history.json` | `a5b606c65026ea4798fc9e33a0db9a8298271480daecc88d296f5a36e7f68d34` |
| `courses/AIDA-2154/data/processed/point_cnn_20261113/visual_selection_review.json` | `853910bd323595d67c5b5ffbce997c411e58c4867a8262b155a95c82423be34a` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/hydrometry_width_scatter.png` | `ce1952fff7e83b4cfa6783d3c2fa3fbf22b306db3521e72d1f133d122ad4feb4` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/README.md` | `a32b078114b89396a16122049a0f27aa9bf79694efd87af598dc6407dd0e24c5` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/READMECN.md` | `57e75f19d9b0dea10366b86559be87a2a6e6756fffe26c375e228afec4b3548d` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/summary.json` | `a7cb2f354c403e1641b71267da0bde21e2ca6d8eea3c5b213098555df48f1a48` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/test_width_hydrometry.csv` | `9789ccbc9f44f531205a05648602ad2099271269bf4dcdc0e4fc1083a4cc8fa1` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/transect_review.png` | `fcf340859b757e583dd7e92141599061669186cc3c3693b6862203377124f144` |
| `courses/AIDA-2154/data/processed/point_width_validation_20261113/transects.json` | `e5143e1e36bfc8130346db75308c2cdd7d0d898899bd0e625d893b4d2d07a011` |
