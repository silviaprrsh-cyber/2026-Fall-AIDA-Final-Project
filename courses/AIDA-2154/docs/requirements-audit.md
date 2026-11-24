# AIDA 2154 requirement-by-requirement audit
Technical audit date: 2026-11-13. Scheduling and submission update: 2026-11-21, from the latest supplied D2L assignment. All applicable course README files were inspected. Root and course teacher instructions are preserved; historical acquisition README counts are not current experiment counts.

## Approach and final deliverables
| Requirement | Evidence / disposition |
|---|---|
| One inspection decision, user, use/non-use, consequence | Current course README, model/data card, responsible-use review. False dry/wide predictions can mislead planning; outputs withheld. |
| Authorized source, identity, labels, compute limits | docs/data-permission-selection.md; Sentinel legal notice checked; source hashes and automatic-label status in frozen manifest. No independent labels. |
| Fixed split/leakage and metrics before tuning | Saved config/code, date groups, 7-day boundaries, training-only statistics; docs/evaluation-protocol.md. A separate prospective preregistration is not available; do not backdate one. |
| Transparent baseline and selected method | Train-only fixed-site mask and 6,113-parameter CNN; source, model and data identities preserved. |
| Reproducible CPU code, tested package | Offline replay scripts, dependency versions, 14 focused tests; clean package/extraction evidence retained locally. Raw acquisition regeneration explicitly excluded. |
| Metrics, error slices and representative failures | Original result.json, per-point CSV, first test scene per point, failure report and indirect width analysis (automatic-label agreement only), plus strictly separate 2026-11-23 9-site blind manual audit ([independent-manual-check.md](independent-manual-check.md): CNN clear IoU 79.26% vs. 79.80% static baseline; bounds 44.83%–83.31%). |
| Runtime, memory and CPU | docs/compute-reproduction.md; independent training and inference replay measurements. Original unmeasured memory remains unmeasured. |
| Bias/privacy/consent/authority/licence/accessibility/security/uncertainty | responsible-use-limitations.md and permission record; table equivalents, unknown pixels and local package allowlist. No flood or physical-width accuracy claim. |
| Human-review rule | Withhold all prediction-model use, not ask the owner to manually certify 2,322 inadequate images. Reconsider only with new suitable imagery and independent reference evidence. |
| Model/data card and enterprise recommendation | Current card and failure report: withhold; future redesign requires better evidence. |
| AI declaration and verification | Finalized in first person and personally reviewed by student on 2026-11-22 ([../ai-use-declaration.md](../ai-use-declaration.md)). |
| Retrospective | Finalized in first person and personally reviewed by student on 2026-11-22 ([retrospective.md](retrospective.md)). |
| Peer-review record and response | NOT COMPLETED; docs/peer-review-status.md records honest gap. Actual assigned review/template and response require real activity. |
| Manifest, release checklist, clean run | Local allowlisted candidate, SHA-256 manifest, replay and verification scripts; release-checklist.md. Latest D2L package, private-link and final-commit requirements are in [readiness notes](d2l-readiness.md); local CPU package replay has passed. |
| Presentation/demo and individual defence | docs/demo-notes.md prepared; in-class demonstration and defence NOT COMPLETED. |
| Versioning and submission | No commit/push/upload done in this task. Owner's requested final version can be committed later; D2L remains the actual submission route. |

## Root README and folder rules
The course question remains the approved river investigation, bounded to current sites and historical data. The supplied feedback explicitly makes operational integration future work and unvalidated CV optional to the main system. This does not erase the CV course's experimental evidence.
Every relevant data/src/docs/outputs README requires a short contents note and no restricted data/credentials; current folder guides are updated. Dated material-selection READMEs remain historical evidence and are not rewritten as new experiments.
Each course keeps its own evidence and assessment. This pass does not claim EDA/GIS completion. Latest supplied D2L: December 14, 2026 at 11:59 p.m. as displayed; Weeks 13–14 in class. The individual presentation slot and assigned peer activity are not verified.
No Week 16 project activity is invented.

## Honest completion boundary
Technical documentation and reproducible negative-result evidence are prepared. Final course submission is NOT COMPLETE until the owner checks disclosure and permitted scope, performs real peer review and demonstration, follows D2L packaging instructions and submits. No grade or instructor acceptance is guaranteed.


## Subsequent owner-requested engineering scope

Database audit/views and a separately packaged inference container are additional requested engineering work, not a reversal of the negative CV result. See postgres-cv-pipeline.md. Actual Windows Docker inference has now passed on 132 images with identical host masks and externally mounted read-only model/input files. The frozen CPU classroom package does not contain this separate Windows inference extension.
