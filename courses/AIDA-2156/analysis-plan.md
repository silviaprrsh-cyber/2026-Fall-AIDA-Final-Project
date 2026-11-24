# EDA analysis plan

Draft recorded 2026-11-08 from the existing project; this is not a preregistration of the earlier ML experiments.

- **Audience and decision:** A hypothetical municipal river-infrastructure analyst decides which observations and assumptions are adequate for further experimental estimation and where results must be withheld.
- **Question:** How do temporal coverage, quality filtering, lake-data gaps and the experimental stage/depth assumption affect the usable evidence and downstream comparison in Dickson–05CC002?
- **Population / period:** Available records for 05CB007, 05CB001, 05CC007, 05CC003 and validation station 05CC002 requested for 2025-05-03–2026-11-03 UTC. Do not generalize to all river conditions, excluded downstream reaches or future floods.
- **Unit / denominator:** Raw unit is station–observation-time–parameter. Descriptive coverage uses station-specific expected slots inferred from observed cadence and labels that denominator as inferred. Model-origin cohort is a separate common timestamp unit; 95,053 screened candidates are not independent events or final arrival-matched labels. Report both included and excluded counts by station/month/quality class.
- **Inputs:** Frozen unit-value observations and provenance; scoped section/routing tables where needed; rainfall and lake levels only with explicit coverage. Daily means remain backup, not active substitutes. See the shared inventory and source reports.
- **Practical criterion / stop rules:** Withhold operational recommendations. Missing required flow/level/geometry, invalid area, unmatched arrival labels, unverified datum transfer or insufficient evidence produce unknown/excluded-with-reason results. Never fill missing rain with zero or represent lake elevation as discharge. Numerical operational thresholds remain unset until justified.
- **Claim plan:** (1) Coverage and exclusions: counts, missingness and quality by station/time, with source denominators. (2) Relationships: distribution and lagged upstream/endpoint comparisons without causal claims. (3) Sensitivity: whether interpretation changes under quality/inclusion and measurement assumptions. Each completed claim must enter `claim-evidence-index.csv` with its actual output and uncertainty.
- **Uncertainty:** Account for repeated/autocorrelated observations; assess by time/event blocks rather than treating five-minute rows as independent. State provisional records, selection effects, seasonal gaps and original publication-time uncertainty.
- **Planned sensitivity:** Compare existing quality filtering with a justified stricter grade/approval policy; compare lake-complete versus broader river-only cohorts with explicit missing-lake handling. Separately examine experimental depth-reference assumptions where justified. Record changed counts, estimates and decisions; no outcomes claimed yet.
- **Existing ML context:** Historical 60/20/20 and 80/20 reports are exploratory comparisons, not two completed EDA sensitivities or independent new tests. Five later supporting model experiments have saved results; formal EDA sensitivities were still pending at that checkpoint. Do not tune against test results or claim intermediate-point accuracy from endpoint agreement.
- **Reproduction / output:** Existing ETL and audit entry points are in `analysis/README.md`. Final EDA must add labelled tables/figures, claim index, sensitivity results, accessible report, clean-run log and course governance/release documents. Keep credentials and restricted source archives out of coursework handoffs; use an authorized reproducible input route.
- **Dated changes:** 2026-11-04 endpoint reduced to 05CC002; 2026-11-08 teacher-format planning added. Check approved-proposal alignment before changing the main question or promised result.


## Evidence update on 11 November 2026

Five later experiments have saved results for supporting ML work. See output/model-experiment-metrics.csv, output/identical-test-comparison.csv and app-or-report/experimental-evidence-report.md. At that date, formal quality/inclusion and lake-missingness sensitivities were still pending. This documentation update is retrospective and does not preregister past experiments. No training or final package run was performed.

## Current release boundary

The historical observation plan above is unchanged. The V4 data rules, including its modeled Dickson zero and prior-hour rainfall treatment, are separate from the descriptive EDA stop rules; see `docs/DATA_PIPELINE.md` in the full workspace. The separate Windows prototype is not an input to the formal EDA and does not establish any new observational claim.

## 2026-11-20 implemented comparison and scope record

The [decision report](app-or-report/final-eda-report.md) answers the historical observational-adequacy question, not the incremental predictive gain of rainfall or tributary data over persistence. It does not alter the approved proposal or imply approval of the later scope. Check alignment with the teacher before presenting it as answering the original predictive question.

The denominator is 158,112 inferred five-minute UTC grid slots per parameter over the common request window, consistent with each station's modal cadence. Missing, rejected and off-grid values are counted separately. Join only exact timestamps, without imputation. Use river-only comparisons for historical description; identify when values are provisional or conditional on lake coverage. Stop short of depth estimates without verified vertical transfer or operational claims without independent event validation.

P-S1 requires explicitly final approval beyond historical screening. P-S2 compares lake-complete and river-only on the same dates and reports whole-window coverage separately. Where supported, estimates use seven-day UTC block resampling. No all-final joint effect can be estimated, and no arbitrary vertical shift was used. See [formal sensitivity results](output/sensitivity-results.csv) and the [claim index](claim-evidence-index.csv).
