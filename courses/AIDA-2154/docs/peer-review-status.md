# Peer-review record and response

Status: **REVIEW 1 RECEIVED & ACTIONED (2026-11-24); Review 2 (Dec 3, 2026) and outbound classmate peer-review D2L submissions pending.**

## Received Peer Review 1 (AIDA 2154)
- **Reviewer:** Chen Liu (assigned classmate)
- **Review date:** 2026-11-24 (`AIDA2154_Chen_Liu_Review1.docx`, kept locally outside Git per privacy/no-other-student-work rule)
- **Summary of 25 progress checks:** **22 / 25 `Yes (100%)`**, **0 `No`**, and **3 `Not observed`** (Check #8: inspect/run workflow; Check #11: permitted sample & rerun steps; Check #23: live in-class demonstration, scheduled later).
- **Specific action requested (Written Feedback Q5):** Provide clear reproducible sample/rerun instructions (or live demonstration) so a reviewer cloning the GitHub repository can independently reproduce the workflow and verify Check #8 and Check #11 in Review 2 (December 3, 2026), noting that the full raw satellite image archive is too large for GitHub.

## Evidence-linked response (2026-11-24)
- **Root cause identified:** The full frozen offline replay package (`D2L_SUBMISSION_READY/AIDA2154_CV_D2L_ready_20261123.zip`, ~30.8 MB, containing all 1,009 frozen Sentinel-2 RGB/NIR crops in `dataset.npz`, `best_model.pt`, `transects.json`, the 9-site blind manual audit, and all replay/test scripts) was already committed to the repository, but `courses/AIDA-2154/README.md` previously referred only to the Git-ignored local `data/processed/cv_release_20261113` path, making it appear unavailable from a GitHub clone.
- **Change made:** Updated the **`Safe offline replay`** section in [`courses/AIDA-2154/README.md`](../README.md) with explicit step-by-step reviewer instructions:
  1. `Expand-Archive` of the repository-tracked `D2L_SUBMISSION_READY/AIDA2154_CV_D2L_ready_20261123.zip` into a clean folder (no raw 20 GB GeoTIFFs, PostgreSQL, or network required).
  2. `pip install -r courses\AIDA-2154\requirements-cv.lock.txt` (Python 3.13 CPU dependencies).
  3. Three exact one-line commands to independently reproduce the full 132-image held-out CPU inference + static baseline comparison (`replay_frozen_cnn`), 14 portable tests (`test_release_replay`), and 9-site blind manual audit scoring (`independent_manual_eval --score`), plus optional 40-epoch CPU training replay (`replay_frozen_training`).
- **Remaining peer-review items:** Follow-up verification in **Review 2 (Thursday, December 3, 2026)**, live in-class demonstration (Check #23), and owner's outbound peer reviews of assigned classmate projects submitted separately in D2L.
