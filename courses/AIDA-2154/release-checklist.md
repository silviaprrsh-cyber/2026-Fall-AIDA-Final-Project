# CV release checklist
Updated 2026-11-21 against the supplied D2L assignment; presentation window and deadline supersede prior schedule notes.
Operational disposition: WITHHOLD. Current CV outputs are unsuitable for the prediction model because the available imagery lacks sufficient clarity/resolution; preserve the failed experiment.

| Check | Status / evidence |
|---|---|
| Decision, nine-point scope, use/non-use | Prepared: course README and data-model card |
| Data selection, provenance and licence | Prepared: docs/data-permission-selection.md; Sentinel attribution and source hashes |
| Baseline, trained CNN and frozen split | Verified: 708/169/132, date-grouped, original model hash retained |
| Metrics, slices and failure analysis | Verified computationally; not independent truth: result.json, failure report, point CSV. Supplementary 9-site blind manual audit completed 2026-11-23 ([docs/independent-manual-check.md](docs/independent-manual-check.md)): CNN clear-pixel IoU 79.26% vs. 79.80% static baseline (uncertainty bounds 44.83%–83.31%), reinforcing WITHHOLD. |
| CPU, runtime, memory | Measured in separate unchanged training/inference replays; docs/compute-reproduction.md |
| Responsible use, accessibility, human rule | Prepared; withhold all downstream use, not pretend manual approval exists |
| AI declaration and retrospective | Finalized in first person and personally reviewed by student on 2026-11-22 ([ai-use-declaration.md](ai-use-declaration.md), [docs/retrospective.md](docs/retrospective.md)) |
| Clean candidate, manifest and extraction | Fresh extraction of **`AIDA2154_CV_D2L_ready_20261123.zip`** (60 files, 30.81 MB, bundling 2026-11-22 finalized declaration/retrospective + 2026-11-23 blind manual audit) passed payload verification, 132-image CPU replay, 14 portable tests, and 9-site blind manual scoring ([outputs/zip-extraction-validation.json](outputs/zip-extraction-validation.json); [readiness notes](docs/d2l-readiness.md)); refresh once Dec 1–11 peer review is added |
| Real peer review and response | Review 1 received from Chen Liu on 2026-11-24 (22/25 Yes 100%, 0 No, 3 Not observed: #8, #11, #23) and actioned via explicit GitHub-clone offline replay instructions in [README.md](README.md) and [docs/peer-review-status.md](docs/peer-review-status.md); Review 2 (Dec 3) and outbound D2L peer-review submissions remain pending |
| Demo notes | Prepared for Weeks 13–14; assigned slot and actual in-class demonstration/defence not verified |
| D2L package requirements and submission | Due Dec 14, 2026 at 11:59 p.m. as displayed. Attach clean CV package separately and include private GitHub URL and real final commit. NOT SUBMITTED. |
| Commit/push | Not performed by this task |

Read docs/requirements-audit.md for each requirement and limitation. A successful replay does not validate width accuracy, licensing of excluded third-party archives, or final course acceptance.


## New engineering candidate boundary

The frozen offline classroom CPU package is distinct from the Windows inference handoff. The PostgreSQL/container extension is described in docs/postgres-cv-pipeline.md and container/README.md. Do not submit the earlier ZIP as if it contains this extension. Actual Windows Docker build/run passed with external read-only model/input mounts. The [two-part Windows inference handoff](outputs/README.md) is preserved separately from the earlier Python review ZIP. Local CPU reproduction is verified; that does not verify an assigned class presentation, peer response, student sign-off, private GitHub access/commit or D2L submission.
