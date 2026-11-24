# AIDA 2154 D2L readiness

The latest supplied D2L assignment displays **December 14, 2026, 11:59 p.m.**, with in-class presentations in **Weeks 13–14**. This replaces the earlier scheduling text. The personal presentation slot and assigned peer are not verified here.

## Submission

1. Upload the **clean, reproducible CV package separately** in the AIDA 2154 Final Professional Project assignment. The [CPU package guide](package-guide.md) describes the frozen experiment. It is not the two-part Windows engineering handoff, the EDA/GIS work or the full development repository.
2. Include the private GitHub repository URL and the relevant final commit identifier. The repository URL is recorded locally in `repo_link.txt` at project root; verify assessor access and enter the actual final commit after the final version is saved. Neither action has been performed by this check.
3. Record actual assigned peer review, received feedback and a response linked to the evidence, or truthfully record what has not yet been received. Use the real D2L template. Review the [AI declaration](../ai-use-declaration.md) personally and verify it matches what you can reproduce and defend. Do not claim that the classroom presentation, peer review, personal verification or upload happened.

## Verifiable CPU path

The earlier frozen candidate `AIDA2154_CV_submission_review_20261113.zip` was rechecked on 2026-11-21 UTC in a new extraction on the existing local Python 3.13 CPU environment. All 49 manifest-listed payloads, 132 test images and 14 portable tests passed. The [local rerun record](../data/processed/cv_release_20261113/d2l_readiness_clean_run_20261121.json) preserves exit codes, timing and metrics. This does not mean a fresh OS/dependency install, new accuracy validation or a D2L submission.

For the [classroom demo](demo-notes.md), run the frozen replay from an extracted package, point to the annotated examples and per-site table, and compare IoU **0.8521** with the static baseline **0.8441**. Both are agreement against automatic masks. Use 05CC007 as the failure example: five outputs report zero measured width while contemporaneous observed flows are positive. The photos cannot validate river width; CV output is withheld from the wider prediction model and operational use. See the [failure report](cv-width-failure-report.md).

## Current verified package

Use the local **`AIDA2154_CV_D2L_ready_20261123.zip`** under `data/processed/cv_release_20261113/` for the clean CV upload. Size: `32,304,365` bytes (`30.81 MB`). SHA-256: `370f181f53d2429dd22b2396b957adb1501a227b592344daba234fea22a4308e`. It bundles the frozen scientific data, model, code, 2026-11-22 finalized first-person AI declaration & retrospective, and the strictly separate 2026-11-23 9-site blind manual audit (`docs/independent-manual-check.md` + `outputs/independent_manual_eval_20261123/`). Earlier 20261113 and 20261121 snapshots remain preserved locally.

In a fresh extraction on Windows with Python 3.13.11 and the existing CPU environment, **60 payload files** verified in **0.542 s**; **132 test images** reproduced the original metrics in **11.671 s**; **14 portable tests** passed in **4.004 s**; and the **9-site blind manual audit** re-scored identically in **0.802 s** (all four commands exited `0`). Tracked verification record: [`../outputs/zip-extraction-validation.json`](../outputs/zip-extraction-validation.json). No retraining, upload or Git write was performed.
