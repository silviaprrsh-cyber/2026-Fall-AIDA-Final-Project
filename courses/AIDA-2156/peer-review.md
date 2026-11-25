# Peer-review record and response

Status: **REVIEW 1 RECEIVED & ACTIONED (2026-11-24); Review 2 (Dec 3, 2026) and outbound classmate peer-review D2L submissions pending.**

## Received Peer Review 1 (AIDA 2156)
- **Reviewer:** Chen Liu (assigned classmate)
- **Review date:** 2026-11-24 (`AIDA2156_Chen_Liu_Review1.docx`, kept locally outside Git per privacy/no-other-student-work rule)
- **Summary of 25 progress checks:** **23 / 25 `Yes (100%)`**, **0 `No`**, and **2 `Not observed`** (Check #18: permitted inputs, environment, and clean-run steps independently verified; Check #21: student independently traces a claim through a live rerun).
- **Specific action requested (Written Feedback Q5):** Provide a clean-run path or small reproducible input so a reviewer can trace one complete claim-to-evidence path from an input table to a final table/figure and verify Checks #18 and #21 during Review 2 (December 3, 2026), noting that the full raw archive appeared too large for GitHub.

## Evidence-linked response (2026-11-24)
- **Root cause identified:** The complete standalone EDA package (`D2L_SUBMISSION_READY/AIDA2156_EDA_D2L_ready_20261123.zip`, 3.72 MB, 41 files — bundling all five frozen 18-month station CSV inputs, pure Python 3.13 standard-library scripts, 7 tables, and 4 SVGs) was already tracked in the repository, but was not surfaced at the top of `courses/AIDA-2156/README.md`.
- **Change made:** Added a **`Quick-Start Offline Reproduction`** block at the very top of [`courses/AIDA-2156/README.md`](README.md) with exact `Expand-Archive` instructions and three zero-dependency Python 3.13 standard-library (`-B -E -S`) commands (`analysis.py`, `tests_or_assertions.py`, `make_eda_figures.py`) that reproduce all 7 output tables and 4 SVGs byte-for-byte in ~25 seconds with no `pip install`, database, or network access.
- **Remaining peer-review items:** Live claim-to-evidence walkthrough and verification in **Review 2 (Thursday, December 3, 2026)** (Checks #18 and #21), plus owner's outbound peer reviews of assigned classmate projects submitted separately in D2L.
