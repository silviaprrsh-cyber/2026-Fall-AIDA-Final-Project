# Submission readiness against teacher instructions

Review date: 2026-11-08. Source: local teacher repository commit `8abd56ea80ac703e565661d53be754f450829020`, root README and all three course briefs. The original review did not access D2L. The November 21 supplement uses the current course briefs supplied by Miles. This is not a submission receipt.

## Shared requirements

- Charter, scope matrix, data inventory and provenance are now populated from existing evidence. Proposal/data-scope alignment with the generic facilities-maintenance wording remains to be confirmed.
- Keep three separate D2L submissions. All three activities display December 14, 2026 at 11:59 p.m. 2154/2156 present in Weeks 13–14; 2362 presents in Week 15. Git does not replace a D2L upload.
- Keep the repository private. Do not submit credentials, virtual environments, caches or restricted/raw archives with the coursework.
- Include permitted inputs needed for reproduction, especially the portable GIS package. Live APIs alone cannot reconstruct a frozen historical training dataset or government surveys.
- Genuine peer review and response, actual demonstrations, and final D2L uploads remain pending. AI declarations and retrospectives for all three courses were personally reviewed and finalized on 2026-11-22, and clean-extraction verification of all three course D2L ZIPs (`2154`, `2156`, `2362`) passed on 2026-11-23. No instructor email or submission has been sent by this task.

## AIDA 2154 - Computer Vision

Updated 2026-11-13 against the current teacher README. The nine-point mask/CNN experiment and failure decision are now retained, not pending implementation. Available 10 m imagery is insufficiently clear for reliable target width; **do not input current CV outputs to the prediction model**.

| Requirement | Current evidence / remaining action |
|---|---|
| Data selection, provenance and authority | Source/sample hashes and selection are retained; current scope and permitted package inputs are described in the course data permission record and model/data card. Do not bundle private replies, credentials or unrelated archives. |
| Baseline, approach, split and reproducibility | Static training-mask baseline, 6,113-parameter CNN, 708/169/132 date-grouped samples, seven-day boundary exclusion and code/configuration are retained. Original training result is preserved. |
| Metrics, slices, failures and compute | Test TP/FP/FN/IoU and site failures are recorded; unchanged-configuration training and frozen inference replay provide separate runtime/CPU/peak-memory evidence. Weak-label agreement is not independent truth. |
| Independent width evidence and decision | Physical-width ground truth not achieved; indirect hydrometric checks do not supply true width. On 2026-11-23, a strictly separate [9-site blind manual audit](../courses/AIDA-2154/docs/independent-manual-check.md) found CNN clear-pixel IoU 79.26% vs. 79.80% static baseline (44.83%–83.31% uncertainty bounds), reinforcing the WITHHOLD decision. |
| Responsible use, card, AI declaration, retrospective | Updated current-state documents exist; [AI declaration](../courses/AIDA-2154/ai-use-declaration.md) and [personal retrospective](../courses/AIDA-2154/docs/retrospective.md) were finalized in first person on 2026-11-22. |
| Manifest, clean package and demo | **`AIDA2154_CV_D2L_ready_20261123.zip`** (60 files, 30.81 MB, bundling 2026-11-22 declaration/retrospective & 2026-11-23 9-site blind manual audit) passed clean-extraction manifest verification, 132-image CPU replay, 14 portable tests, and blind manual re-scoring ([zip-extraction-validation.json](../courses/AIDA-2154/outputs/zip-extraction-validation.json)). Demo/defence evidence preserves the WITHHOLD decision. |
| Peer review and final actions | Actual assigned review, feedback response, presentation/defence, final commit recording and D2L submission remain pending. |

See [CV release checklist](../courses/AIDA-2154/release-checklist.md) for current detailed status. This CV evidence is separate from the EDA and GIS evidence below.

## AIDA 2156 — EDA Decision Study

| Teacher deliverable | Current evidence / action |
|---|---|
| `analysis-plan.md` | The [bounded plan](../courses/AIDA-2156/analysis-plan.md) is present. The dated plan separates completed observation-based sensitivity work from historical model experiments and flags original-proposal alignment for review. |
| `data/data-dictionary.csv`, `data/provenance.txt` | Both [the dictionary](../courses/AIDA-2156/data/data-dictionary.csv) and [the provenance record](../courses/AIDA-2156/data/provenance.txt) exist. Check them against the exact permitted analysis input selected for submission. The [V4 source and units guide](../courses/AIDA-2156/docs/DATA_SOURCES.md) documents a separate model cohort. |
| `analysis/analysis.py` or documented notebook; assertions | The final `analysis.py` and `tests_or_assertions.py` were independently replayed on the frozen hydrometric fields. They do not need ETL, V4 or a database. |
| `claim-evidence-index.csv` | The [working claim/evidence index](../courses/AIDA-2156/claim-evidence-index.csv) exists. Verify the stated evidence, inference limits and final dispositions before submitting. |
| `output/` figures/tables, validation, clean-run log, `sensitivity-results.csv` | [Both formal sensitivities](../courses/AIDA-2156/output/sensitivity-results.csv) and reproducible tables exist. The [isolated local replay](../courses/AIDA-2156/output/clean-copy-replay.txt) reproduced all seven outputs from the five frozen station tables. The [submission manifest](../courses/AIDA-2156/submission-manifest.txt) identifies evidence and separates local input dependencies. |
| `app-or-report/` report or app, equivalent table, accessibility notes | The [decision report](../courses/AIDA-2156/app-or-report/final-eda-report.md) provides static numeric and text equivalents; see [accessibility notes](../courses/AIDA-2156/app-or-report/accessibility-notes.md). The separate Windows viewer is not evidence of course or accessibility approval. |
| Governance, limitations, AI declaration, retrospective, peer review | [AI declaration](../courses/AIDA-2156/ai-use-declaration.md) and [retrospective](../courses/AIDA-2156/retrospective.md) were finalized in first person on 2026-11-22, and [limitations](../courses/AIDA-2156/limitations-and-next-evidence.md) now records the 2026-11-17 ECCC assumed-datum confirmation. Actual peer feedback, final uploadable clean ZIP packaging, presentation and D2L upload remain pending. |
| Reproduction | [Analysis instructions](../courses/AIDA-2156/analysis/README.md) document the Python version, commands and frozen inputs. See the [input checksum ledger](../courses/AIDA-2156/data/eda-input-checksums.csv) to identify the source files. |

Current disposition: formal EDA replay, personal AI/retrospective sign-off, and clean-extraction verification of **`AIDA2156_EDA_D2L_ready_20261123.zip`** (41 files, 3.72 MB, `python -B -E -S`, 7 tables + 4 SVGs byte-matched, 0 mismatches — see [zip-extraction-validation.json](../courses/AIDA-2156/output/zip-extraction-validation.json)) are complete; actual peer feedback, presentation and D2L upload remain pending. [V4 experiment findings](../courses/AIDA-2156/docs/MODEL_EXPERIMENTS.md) explicitly withhold real flood use. Do not confuse the locally verified [research deployment package](../courses/AIDA-2156/deployment/server/README.md) with a passed D2L submission, cloud uptime or a flood warning system.

## AIDA 2362 — GIS Decision Package

Existing: the current 05CC002 QGIS project and layers, map PDF, spatial processing code and reopening/count reports. [Decision brief](../courses/AIDA-2362/decision-brief.md), [governance review](../courses/AIDA-2362/governance-review.md), [AI declaration](../courses/AIDA-2362/ai-use-declaration.md) (finalized 2026-11-22) and [release checklist](../courses/AIDA-2362/release-checklist.md) are updated. On **2026-11-23**, Alberta Environment and Protected Areas (EPA) confirmed in writing that the provided survey data is publicly available information and may be used in the course submission with EPA credit (`Protected A` correspondence and original raw GDBs remain excluded). The portable submission archive `AIDA2362_FinalProject_Miles_Zhang.zip` (under Git-ignored `data/processed/gis_release_20261123/`) passed clean extraction and QGIS 3.44.14 reopening with all eight local relative vector layers (246 valid features, 0 invalid geometries, matching 25/50 m selections); see [zip-extraction-validation.json](../courses/AIDA-2362/outputs/zip-extraction-validation.json) and [submission-manifest.txt](../courses/AIDA-2362/submission-manifest.txt). Actual classmate peer review (two projects, Dec 1–11), Week 15 live QGIS demonstration, and D2L upload remain open. No flood hazard or property decisions are supported.

Current disposition: portable GIS submission ZIP assembled and verified from clean extraction; pending peer review, Week 15 live QGIS demo, and D2L upload. Current `dickson_to_joffre.qgz` is intentionally named for compatibility but ends at 05CC002.

## Engineering evidence update 2026-11-13

The independent CV PostgreSQL audit, two views, mask generation and CNN training have run. Windows Docker verification reproduced all 132 host masks with externally mounted read-only model/input files; see the [pipeline guide](../courses/AIDA-2154/docs/postgres-cv-pipeline.md). Visual diagnosis identified errors, but imagery detail is insufficient for reliable boundary verification. The intended independent width-comparison and bias-feedback channel remains disconnected from the river model.

EDA has [five supporting model experiments](../courses/AIDA-2156/app-or-report/experimental-evidence-report.md); the later formal EDA sensitivities and reproducible outputs are documented above. This evidence does not change GIS or student-owned submission requirements.
