# Final-project progress record

**Current D2L deadlines:** December 14, 2026, 11:59 p.m., separately by course. 2154/2156 present in Weeks 13–14; 2362 presents in Week 15. Check the assigned slot in D2L.

Use this file to keep a short record of the evidence you have produced and the next task to complete. Update it at each feedback checkpoint. It is a planning aid, not an additional graded submission. The course rubric and D2L assignment determine the final assessment.

For each row, choose one status: **Not started**, **In progress**, **Ready for feedback**, **Feedback received**, or **Complete**. Link a file, folder, commit, or D2L item as evidence. A commit count alone does not show project quality; reviewers look for a working, checked, well-explained result.

| Week / checkpoint | Evidence to prepare | Status | Evidence path or commit | Feedback / next action |
|---|---|---|---|---|
| 6 — scope and feasibility | Approved or reviewed question; intended user/decision; scope boundary; course contribution; data source/permission; feasibility question. | Complete | `project-charter.md`; `scope-matrix.md`; `shared-resources/Miles-project-plan.md` | Proposals approved as submitted; Alberta EPA written attribution clearance received 2026-11-23; 05CC002 scope reduction documented in charter and contribution map. |
| 8 — data and evidence plan | Data inventory/sample; permission/provenance; method/pipeline plan; baseline; success and quality checks. | Complete | `shared-resources/Miles-data-sources.md`; `courses/AIDA-2156/data/data-dictionary.csv`; `courses/AIDA-2362/data/layer-inventory.csv` | Data dictionary, API/DB docs, 12 testable functional requirements (`FR-01`–`FR-12`), ECCC assumed-datum confirmation (2026-11-17), and Alberta EPA credit clearance (2026-11-23) are recorded. |
| 10 — working prototype | One repeatable end-to-end run or spatial/vision/analysis workflow with an initial output and short run note. | Complete | `courses/AIDA-2154/docs/d2l-readiness.md`; `courses/AIDA-2156/output/clean-copy-replay.txt`; `courses/AIDA-2362/outputs/Overhead view.pdf` | Clean CPU CV replay, standard-library formal EDA replay, and offline QGIS project reopen (8 layers, 246 features) all passed. |
| 12 — validation and revision | Validation/check results; sensitivity or changed-setting comparison; error/limitation; revisions and what changed. | Complete | `courses/AIDA-2154/docs/cv-width-failure-report.md`; `courses/AIDA-2156/output/sensitivity-results.csv`; `courses/AIDA-2362/outputs/section-proximity-sensitivity.md` | CV negative-result closure, EDA P-S1/P-S2 sensitivities with 7-day block intervals, and GIS 25 m vs. 50 m sensitivity (`3/5`→`5/5`) are complete. |
| 14 — release candidate | Organized course folders; evidence index; clean-run/release checks; peer review and response; presentation practice. | Feedback received | `shared-resources/submission-readiness.md`; `presentation/README.md`; `courses/AIDA-2154/docs/independent-manual-check.md`; `courses/AIDA-2362/outputs/zip-extraction-validation.json` | **2026-11-23 Formative Feedback 1 & 2026-11-24 Peer Review 1 actioned:** (1) 2154 blind 9-site manual audit completed separately (CNN 79.26% vs. 79.80% baseline; bounds 44.83%–83.31%, reinforcing WITHHOLD); (2) 2362 Alberta EPA written attribution clearance received & portable QGIS ZIP verified; (3) **Peer Review 1 received from Chen Liu across all three courses** (2154: 22/25, 2156: 23/25, 2362: 20/25 `Yes 100%`; **0 `No`** across all 75 checks) and actioned via top-of-README offline ZIP reproduction guides, 2362 optional Hydro-GIS companion note, and synced D2L ZIPs ahead of **Nov 29** final formative review & **Dec 3** Review 2. |
| 15 — final handoff | Final course packages; submission manifest; D2L submission evidence; in-class presentation; final limitation and next step. | Not started | No final handoff evidence. | Complete Weeks 13–15 presentations, run any supplied validator, record final manifests/commit SHA, and upload separately to D2L by Dec 14. |

## How to ask for feedback

Email the instructor before a scheduled checkpoint if you need guidance. Include the repository link, exact course folder and file or commit to review, what you have already tried, and one or two specific questions. Do not send credentials or restricted data.

## Completion rule

Follow the current course-specific D2L presentation slots and submission deadlines above.

Review date: 2026-11-22 (originally 2026-11-08). Status reflects actual checked evidence, not the calendar week.

## CV outcome - 2026-11-13

The fundamental practical limitation is that the satellite imagery obtainable for this project is not sufficiently clear, at its available spatial resolution, to support reliable width identification in the target river reaches. The current imagery has native 10 m pixels; mixed bank/water pixels and cloud, shadow or bridge occlusion further limit usable boundary detail, particularly in narrow channels. The experiment results below are concrete evidence of inadequate output fitness and remaining uncertainty, not proof that resolution alone caused every error. This conclusion concerns the available imagery and current CV approach, not all satellite imagery. The current CV output is not suitable for input to the prediction model.

The current CV river-width experiment is closed as a failed approach for use in the prediction model, with evidence retained in [the CV failure report](courses/AIDA-2154/docs/cv-width-failure-report.md). Its baseline, CNN, frozen weak-label test and indirect checks are complete; independent physical-width validation was not achieved. Documentation, responsible-use review and reproducibility resources have been updated. Package assembly/checks are tracked in [the CV release checklist](courses/AIDA-2154/release-checklist.md). Real peer review, student verification/reflection, demonstration and D2L submission remain pending. This does not change other-course completion statuses or claim course completion. Original experiments remain preserved; the later unchanged-configuration resource replay is a separate run.


## CV engineering extension (2026-11-13)

The owner subsequently requested an independent API-archive/PostgreSQL audit/view/mask/CNN/container workflow. See courses/AIDA-2154/docs/postgres-cv-pipeline.md. This is not an operational river-model integration. Original CV failure evidence is retained; the prior CV review ZIP is a historical snapshot. Actual Windows Docker build/run passed (132 images, zero valid-pixel probability difference); refreshed final packaging remains pending. See courses/AIDA-2154/container/README.md for exact evidence. EDA and GIS completion is not changed by this extension.

## AIDA 2156 research package (2026-11-20)

Frozen V4 60/20/20 is the retained academic baseline. The local private Windows server ZIP and separate single-file receiver are listed in the [2156 README](courses/AIDA-2156/README.md). This is a packaged prototype, not evidence of a public deployment, managed database in operation, operational accuracy, formal handoff or D2L submission. The original final test does not support real-world flood warning or emergency response.
