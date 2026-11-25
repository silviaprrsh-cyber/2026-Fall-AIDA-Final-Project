# AIDA 2154 Final Professional Project — Computer Vision

**Individual assessment · 25% of the AIDA 2154 course grade**

## Quick-Start Offline Reproduction (Reviewer & Self-Check Guide)

> **Everything needed to reproduce the CV results is already tracked in this repository** inside [`D2L_SUBMISSION_READY/AIDA2154_CV_D2L_ready_20261123.zip`](../../D2L_SUBMISSION_READY/AIDA2154_CV_D2L_ready_20261123.zip) (~30.8 MB; bundles all 1,009 frozen Sentinel-2 RGB/NIR arrays `dataset.npz`, frozen CNN weights `best_model.pt`, `transects.json`, the 9-site blind manual audit JSON, and all replay/test scripts). **No raw 20 GB GeoTIFFs, network, PostgreSQL, or QGIS are required.**

```powershell
# 1. From the repository root, extract the tracked standalone CV package
Expand-Archive -Path D2L_SUBMISSION_READY\AIDA2154_CV_D2L_ready_20261123.zip -DestinationPath cv_replay_unpack -Force
cd cv_replay_unpack

# 2. Install Python 3.13 CPU dependencies (skip if already installed)
pip install -r courses\AIDA-2154\requirements-cv.lock.txt

# 3. Run full 132-image CPU inference replay, 14 portable tests, and 9-site blind manual audit (~10-15 s)
python -B run.py -m cv_tools.replay_frozen_cnn --output cv_replay_NEW
python -B run.py -m cv_tools.test_release_replay
python -B run.py -m cv_tools.independent_manual_eval --score courses\AIDA-2154\outputs\independent_manual_eval_20261123\manual_blind_annotations_9sites.json
```

- **Expected verified result:** `0.0` valid-pixel probability difference across all 132 held-out images (`85.21%` CNN vs. `84.41%` static baseline), 14/14 portable tests pass, and the 9-site blind manual check reproduces `79.26%` CNN vs. `79.80%` static baseline (`44.83%–83.31%` uncertainty bounds), supporting **WITHHOLD**. Optional 40-epoch CPU training replay (~2 min): `python -B run.py -m cv_tools.replay_frozen_training --output cv_training_NEW`.
- **Key files to inspect:** [Failure Report](docs/cv-width-failure-report.md) · [9-Site Blind Manual Check](docs/independent-manual-check.md) · [Model/Data Card](data-model-card.md) · [Peer Review Record](docs/peer-review-status.md).

---

## Purpose and boundary

Develop a bounded, reproducible computer-vision inspection prototype for a facilities-maintenance question. Use only supplied or explicitly approved data and keep the implementation CPU-bounded. This is a teaching prototype, not a deployed product. A personal recording is never required. Do not connect to a live employer system or claim operational readiness.

## How to approach the work

1. **Frame one inspection decision.** Name the user, decision, object/task, intended use and non-use, and the consequence of an incorrect result.
2. **Confirm data authority and feasibility.** Document dataset source, permission/licence, consent/privacy, file identity, labels, and compute limits before substantive analysis.
3. **Plan validation before tuning.** Fix a defensible train/validation/test split and leakage controls; state metrics and error slices before comparing approaches.
4. **Build a simple baseline.** Implement a transparent baseline and the chosen approach; use repeatable commands, fixed seeds where applicable, and record code/data/model identities.
5. **Inspect performance and failure.** Report suitable metrics, meaningful slices, representative failures, runtime/memory/CPU evidence, and the conditions where the system should defer to a person.
6. **Review responsible use.** Address bias, privacy, consent/authority, licensing, accessibility, security, uncertainty, limitations, and a human-review rule.
7. **Make a bounded enterprise recommendation.** State whether to release, redesign, or withhold the prototype, the conditions for any pilot, and what further evidence is required.

## Required final deliverables

Keep these items under `courses/AIDA-2154/` and use the clean project package required by D2L:

- authorized data documentation, provenance, and a data-selection/permission record;
- reproducible computer-vision code and CPU-bounded run instructions;
- a simple baseline and selected approach, with reason for the choice;
- fixed split and explicit leakage controls; predeclared metrics and evaluation protocol;
- evaluation results, error/slice analysis, compute/performance evidence, and representative failures;
- limitations, bias/privacy/consent/authority/licensing/accessibility/security review, and a human-review rule;
- model/data card, bounded enterprise recommendation, AI-use declaration and verification, and retrospective;
- peer-review record and response; release checklist, clean package manifest, and presentation/demo notes.

The published course rubric totals 25 marks: problem framing/data authority/evidence plan (4), implementation/baseline/selected approach and tested package (7), validation/leakage/metrics/errors/performance (6), responsible-use/model/data documentation/human review/recommendation (5), demonstration/defence/AI declaration/retrospective/release (3). Formative project gates do not add a separate grade.

## How progress is checked

Use `project-progress.md` to show evidence and the next action at each formative gate. These checks measure whether the project is becoming more bounded, reproducible, validated, and safe to interpret; they do not create extra graded weights.

- **Week 6 — scope/data permission:** decision, boundary, authorized data, licence/privacy/consent, compute limits.
- **Week 8 — evidence plan/design:** baseline, chosen approach, split/leakage controls, metrics, slices, experiment plan, safe-failure rule.
- **Week 10 — prototype:** clean command, environment/seed, data/model identities, first baseline and approach output.
- **Week 12 — validation/responsibility:** validation plan/results, error slices, runtime, risks, limits, human review.
- **Week 14 — release candidate:** frozen candidate manifest, model/data card, peer review and response, unresolved-risk list.
- **Week 15 — release readiness:** clean extraction/run, checksums, final recommendation, and retrospective. The latest D2L presentation schedule below supersedes earlier presentation-week guidance.

## Submission and presentation

Submit the separate clean, reproducible CV package through the AIDA 2154 D2L Final Professional Project assignment. Include the private GitHub repository link and the relevant final commit identifier. In class in Weeks 13–14, show the CPU workflow, a result and validation evidence, a limitation and the human-review decision. Weekly graded labs remain separate. See the [D2L readiness notes](docs/d2l-readiness.md).

## Shared project dates and class activities

The latest supplied D2L assignment shows **December 14, 2026, 11:59 p.m.** (as displayed), with in-class presentations in **Weeks 13–14**. Verify the individual assigned slot separately. Each student reviews at least one assigned classmate's repository or code plan using the actual D2L peer-review process and records their response to feedback.

---

This separately preserved AIDA 2154 experiment is a negative result for satellite-derived width validation. No CV width, mask or proxy was used to validate the [AIDA 2156 V4 hydrology study](../AIDA-2156/README.md). V4 is separate research evidence, not an operational flood-warning product or part of the CV package.

## Current CV implementation and reproduction
Updated 2026-11-13. The teacher requirements above are unchanged. Earlier acquisition-stage READMEs remain dated historical records, not current model status.

### Decision, scope and downstream use
The current CV output is not suitable for input to the prediction model. The obtainable satellite imagery is not sufficiently clear at its available spatial resolution for reliable width identification in the selected reaches. Native 10 m pixels, mixed bank/water pixels and occlusion limit boundaries. This is a failed CV downstream-use approach, not failure of the whole river project or all satellite methods.
The intended audience is a hypothetical municipal river-infrastructure reviewer. The bounded inspection question is whether historical images at P01-P05 and 05CB001/05CB007/05CC002/05CC007 support usable water-width evidence. No live monitoring, warning, physical-depth inference or unvalidated MLP labels are supplied.

### Evidence map
| Requirement | Current artifact |
|---|---|
| Source, permission, labels, identities | [Data selection/permission](docs/data-permission-selection.md); frozen dataset_manifest.json |
| Baseline, approach, fixed protocol | [Evaluation protocol](docs/evaluation-protocol.md); src/cv_tools/train_point_cnn.py |
| Results, slices, performance and failures | [Failure report](docs/cv-width-failure-report.md); [replay resources](docs/compute-reproduction.md); [supplementary 9-site blind manual check](docs/independent-manual-check.md) |
| Card, risks, human-review rule | [Model/data card](data-model-card.md); [responsible use](responsible-use-limitations.md) |
| AI verification, retrospective | [Declaration](ai-use-declaration.md); [technical retrospective](docs/retrospective.md) |
| Clean manifest/run and demo | [Package guide](docs/package-guide.md); [demo notes](docs/demo-notes.md) |
| Exact requirement audit and remaining work | [Requirements audit](docs/requirements-audit.md); [release checklist](release-checklist.md); [peer-review status](docs/peer-review-status.md) |

### Data and methods
2,322 automatic point masks were made from previously downloaded imagery. Each crop uses its verified GIS point and native 61 x 61 grid. Green/NIR and red/NIR rules plus narrow-channel seeds and WATER closing (dilate then erode, not opening) produce candidate labels. Unknown/cloud/shadow/snow pixels are excluded, not dry land. Visual checks identified errors, but image detail was insufficient to reliably trace water boundaries and verify masks for independent reference labels.
The retained 1,009 unique point-date samples are split 708/169/132, with all points of the same date together and a seven-day boundary gap. Training-only normalization and static per-point training-mask baseline prevent test fitting. Four input bands feed a 6,113-parameter CPU CNN; seed 42, 4 threads, batch 16, Adam 0.001, up to 40 epochs. Every strictly lower validation loss saves a checkpoint. Threshold 0.5 remains fixed.
The saved protocol covers 2016-05-02 to 2026-10-20; the previous 955/775-image and 485/389-candidate inventories describe older acquisition stages, not the current frozen dataset.

### Results and limitations
| Test measure | CNN | Static training-mask baseline |
|---|---:|---:|
| TP | 58,327 | 53,628 |
| FP | 9,096 | 4,182 |
| FN | 1,025 | 5,724 |
| TN | 420,985 | 425,899 |
| IoU | 85.2136% | 84.4083% |
| Precision | 86.5091% | 92.7660% |
| Recall | 98.2730% | 90.3558% |

These are automatic-label agreement scores, not independent physical-width accuracy. Final selected epoch is 40, validation loss 0.081287. Narrow-site IoU is only 62.28% at 05CB001 and 53.74% at 05CC007. Each point's first test image is shown, not the best image.
Indirect width checks use the frozen predictions: 124/132 have complete three-line widths; 70 station images match prior observations within 300 seconds, with 68 complete widths. Width/discharge correlations are 0.080, -0.619, -0.148 and 0.251 for the four stations. Correlation alone cannot diagnose segmentation accuracy. Five 05CC007 zero-width predictions occur during positive flow. P04 weak-label width error exceeds the static baseline. See the failure report and exact per-image CSV for dates and quantities.
No winter test scenes or independent physical widths exist. P01-P05 lack corresponding local hydrometry; nearby station observations were not substituted. Withhold all CV outputs from downstream prediction and operational decisions.

#### Supplementary independent blind manual check (2026-11-23, reported separately)
Following Formative Feedback 1, a strictly separate blind manual check was completed on nine predeclared chronological-median held-out crops (one per site, June–July 2026, disjoint from `test_examples.png`, annotated with zero model or mask visibility across `clear land`, `clear water`, and `uncertain/mixed`). On clear pixels (`30,342` px), the frozen CNN scored **79.26% IoU** — slightly **below** the static training-mask baseline (**79.80%**) and automatic weak mask (**82.18%**) — with **`3,147` uncertain pixels** (`45.24%` of the combined water+uncertain channel zone) producing a **44.83%–83.31%** IoU uncertainty band (`05CC007` CNN IoU `23.53%`; `P03` side-channel omission `41.25%`; `P04` off-channel FP drop `87.09%` vs. `98.71%` baseline). This supplementary audit does not alter the original 132-image evaluation and further reinforces the **WITHHOLD** disposition. See [independent-manual-check.md](docs/independent-manual-check.md) and [`outputs/independent_manual_eval_20261123/`](outputs/independent_manual_eval_20261123/).

### Safe offline replay (reviewer / classmate quick-start — no raw GeoTIFFs needed)
Although the original 20 GB Sentinel-2 GeoTIFF archive and local `courses/AIDA-2154/data/` folder are Git-ignored, the **complete frozen offline replay package is tracked directly in this repository** at [`D2L_SUBMISSION_READY/AIDA2154_CV_D2L_ready_20261123.zip`](../../D2L_SUBMISSION_READY/AIDA2154_CV_D2L_ready_20261123.zip) (~30.8 MB). It bundles all 1,009 frozen Sentinel-2 RGB/NIR crops and weak labels (`dataset.npz`, 708/169/132 split), the frozen CNN checkpoint (`best_model.pt`), transect width tables/geometry (`transects.json`, `test_width_hydrometry.csv`), the 9-site blind manual audit JSON, and all replay/test scripts.

To independently reproduce the full held-out evaluation on CPU directly from a GitHub clone (no network, PostgreSQL, QGIS, or raw GeoTIFFs required):

1. **Extract the standalone replay ZIP** from the repository root and enter the unpacked folder:
   ```powershell
   Expand-Archive -Path D2L_SUBMISSION_READY\AIDA2154_CV_D2L_ready_20261123.zip -DestinationPath cv_replay_unpack -Force
   cd cv_replay_unpack
   ```
2. **Install Python 3.13 CPU dependencies** (skip if already installed in your environment):
   ```powershell
   pip install -r courses\AIDA-2154\requirements-cv.lock.txt
   ```
3. **Run the frozen 132-image CPU inference replay, 14 portable unit/identity tests, and 9-site blind manual audit scorer** (~10–15 s total on CPU; the `--output` folder must be new):
   ```powershell
   python -B run.py -m cv_tools.replay_frozen_cnn --output cv_replay_NEW
   python -B run.py -m cv_tools.test_release_replay
   python -B run.py -m cv_tools.independent_manual_eval --score courses\AIDA-2154\outputs\independent_manual_eval_20261123\manual_blind_annotations_9sites.json
   ```
   - `replay_frozen_cnn` reloads `best_model.pt` and `dataset.npz`, recomputes predictions for all 132 held-out images plus the static baseline, verifies `0.0` valid-pixel probability difference, and writes `cv_replay_NEW/evaluation.json` and `point_metrics.csv`.
   - `test_release_replay` runs 14 portable checks (5 morphology, 4 CNN, 4 geometry/width statistics, and 1 frozen-site identity check).
   - `independent_manual_eval --score` reproduces the separate 9-site blind manual IoU comparison (`79.26%` CNN vs. `79.80%` static baseline; `44.83%–83.31%` uncertainty bounds) and refreshes `courses/AIDA-2154/outputs/independent_manual_eval_20261123/`.
4. **Optional unchanged 40-epoch CPU training replay** (~2 min on CPU; never overwrites the original saved model):
   ```powershell
   python -B run.py -m cv_tools.replay_frozen_training --output cv_training_NEW
   ```

Original local workspace artifacts remain under the Git-ignored `data/processed/point_cnn_20261113`, `point_water_masks_20261113`, `point_width_validation_20261113`, and `cv_release_20261113`. Only upstream raw-GeoTIFF-to-crop regeneration and full-workspace GIS scope tests require the excluded local source archives. See the [package guide](docs/package-guide.md) and [D2L readiness notes](docs/d2l-readiness.md) for replay boundaries and verification hashes.


## Database and container workflow extension (2026-11-13)

The owner requested a separate CV engineering pipeline, not another width-accuracy improvement. Existing API archives feed an isolated PostgreSQL schema and SQL audit, raw-image and training-pair views, regenerated masks, and a new CNN training run. See [pipeline instructions](docs/postgres-cv-pipeline.md) and [container handoff](container/README.md). The earlier frozen review ZIP is a prior snapshot and does not include this extension. Actual Windows Server Core LTSC2022 build and Hyper-V container inference passed on 132 images; see container/README.md and the recorded image/base digests. Host and container masks match exactly. Outputs remain withheld from river prediction.

## Two-part Windows container delivery

Obtain both binary parts from the course `outputs` directory: `AIDA2154-CV-Windows-20261113.zip.part001` (1,321,342,227 bytes) and `AIDA2154-CV-Windows-20261113.zip.part002` (1,321,342,226 bytes). Each is strictly below 2,000,000,000 bytes; neither can be extracted independently. Follow the [two-part delivery and startup guide](outputs/README.md): verify the part hashes, join them in order using streaming PowerShell, verify the reconstructed ZIP against the original SHA-256, then extract it and run `./run.ps1` from the package folder. The guide contains the canonical commands and hashes.

The reconstructed package contains the full saved image, external model weights, scripts and two synthetic smoke-test samples, not real source imagery. It requires a compatible licensed Windows host, Docker Windows container mode and Server Core LTSC2022 Hyper-V isolation; no host Python/PostgreSQL is required. The earlier extracted-package test passed on the same development computer, not a second clean machine. The original full ZIP is retained locally and Git-ignored; the two delivery parts are not ignored. Nothing has been uploaded or submitted. This handoff remains separate from the historical review package and pending formal course submission.
