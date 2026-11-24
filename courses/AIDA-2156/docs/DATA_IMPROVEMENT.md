# Later data treatment and coverage

[中文](DATA_IMPROVEMENTCN.md) · [Model experiments and final test](MODEL_EXPERIMENTS.md) · [Documentation index](README.md)

**Experimental only.** These checks explain which observations enter later experiments and where coverage or estimates fail. They do not change the active PostgreSQL View, any source archive, the selected original V4 60/20/20 model, or the project’s default behavior. Do not use these results for actual flood warnings, emergency response, or operations.

## What was changed, and what was kept separate

| Treatment tested | Definition / guard against leakage | Result or remaining limitation |
|---|---|---|
| Preserve legacy routed data | Original joined archive uses route-assigned arrivals and blends contributing parcels. The nine rain values are one airport’s rainfall queried at multiple source clocks and in overlapping 1/6/24h windows, not nine gauges. Original Dickson zero can represent no routed contribution, not measured zero release. | The original V4 data stay as they were. Matching may depend on terminal observations used in historical routing calibration, so the archive is not a live-ready as-of feature source. |
| Alternative weather inputs | Matched six-block A/B/C ablation used legacy rain / one terminal-clock rain set at block 6 / no rain. Later matched fits added terminal-clock temperature and RH to block 6; prior completed hour and assumed reporting delay, not future interpolation. A separate direct rise test shared weather-complete support across Q, Q+T and Q+T+RH; rain stratified the test but did not enter those forecasts. | Removing repeated rain features addressed specific artifacts, not both flood peaks. Weather improved some retrospective subsets but did not reliably improve strict-forward rise. Dry airport hours do not establish a dry watershed or evaporation. |
| Trailing water memory | Sum prior exact consecutive 5-min Q × 300 s for volume and compare the two half-window mean Qs for trend, using 1/3/6h and excluding the current row. Gaps or fold boundaries reset the requirement; missing history has neutral standardized effect, not imputed discharge. | The archived 27,256 predictions share the same evaluation indices; only 24,023/21,869/20,473 have complete 1/3/6h histories. More memory also produced more abrupt modeled jumps. |
| Reindex archived routes | Shift existing archived input bundles by branch only as a sensitivity check; exact donors required, absent donors excluded. The held 2025 analysis excluded crest rows and compared common rising rows. | June had 671/671 and July 546/671 common rising rows for the reindex comparison; whole-output oracle shifts that help June and July point in opposite directions. An oracle is not physical travel-time calibration. |
| Rebuild from original hydrometric observations | Later direct rise and six-MLP matching studies read local raw snapshots, exact UTC stage labels and fixed source clocks, without the legacy View’s target-conditioned parcel choice. These studies use documented observation timestamps; actual first-posted timestamps and historical revisions are unavailable. | An older measured value restores feature availability; it is not a measurement made at the originally requested time. The primary stress check imposes a simulated 30-minute delay, not an actual release log. |

Evidence: [Weather treatments](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/weather_once_20261119_ablation/README.md) · [Temperature/RH fits](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/six_mlp_weather_20261120/README.md) · [Trailing history](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/flow_memory_20261119_ablation/README.md) · [Branch reindex audit](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/travel_time_20261120/README.md). See [Data sources](DATA_SOURCES.md) and [Data pipeline notes](DATA_PIPELINE.md) for the project’s source and lineage documentation.

## Direct 1h and 3h rise experiment: denominators matter

Let t be the issue index and h the horizon. Labels are exact downstream stage at t and t+h on the five-minute UTC grid; neither downstream stage nor Q enters the upstream predictors. A known positive means an **observed increase of at least 5 cm over the specified horizon**, not an absolute water level or an official flood threshold. Persistence for the **change** target predicts zero change. The 2026 development freezes timing/modelling choices before the later E2 series; reused 2025 is a separate descriptive replay.

Two predeclared Dickson/Little/Medicine alternative lags (10.5/9/30h and 11/9/50h15m) were tested; both horizons selected **11/9/50h15m** on E1. Cutoffs and lag tuples belong to this experiment; the older 10.5/9/50h15m travel-time sensitivity example is not the chosen configuration. For a target-valid time v the requested measurement is v minus station lag. Under the primary availability proxy, a donor must be at/before the requested time and no later than t minus 30 minutes. Exact matching uses the requested timestamp. A 15/30-minute backward tolerance chooses the latest allowable earlier measured value if needed. Only Little/Medicine get the fallback; Dickson remains exact-only with existing zero policy if unavailable. A missing Little/Medicine feature after the rule gives no forecast, not zero flow.

The exact 3h cohort lost **208/288 known positives**: 77 Little-only, 123 Medicine-only, 8 both; zero losses due to weather among those positives. On all 3h origins the Q-only model had 34,756 rows before restricting to complete weather; 76 rows were lost to that common-weather comparison. Hypothetical coverage at 5 or 60 minutes was audited, not scored as a model. Omitting the prior-change feature was also a coverage probe, not a proven skill improvement. [Exact-coverage root-cause audit](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/causal_delta_20261120/coverage_audit_2026.json)

| Strict-forward 2026 3h Q-only, fixed fitted model | Exact | Backward ≤15 min | Backward ≤30 min |
|---|---:|---:|---:|
| Matched / 38,211 labeled origins | 34,680 | 36,200 | 36,531 |
| Covered / 288 observed positive origins | 80 | 192 | 226 |
| Positive origins with no forecast | 208 | 96 | 62 |
| Hits / all 288 observed positives | 18 (6.25%) | 41 (14.24%) | 56 (19.44%) |
| Row alert precision | 4.93% | 8.99% | 11.64% |
| Full-cohort false-positive rows | 347 | 415 | 425 |
| Routine Q20–40 false rows / episodes | 9 / 4 | 9 / 4 | 9 / 4 |
| Routine scored rows | 17,220 | 17,337 | 17,401 |
| Predicted runs with no overlap with truth (entire eval) | 56 | 41 | 43 |

The 15/30-minute results leave the exact common-support scores unchanged; they add rows, some with the most difficult observations. Across each arm's own support, 3h MAE increases from 0.560 to 0.665/0.678 cm. On newly covered rows only it is 3.07/2.89 cm. No-change baseline MAE on the weather-common exact comparison is 0.310 cm at 3h. Grouping adjacent positive five-minute slots into episodes can bridge gaps when coverage expands; fewer unmatched runs is not by itself a safety gain. The same two of five true 3h rise runs had a hit in all arms: June 24 was unchanged, June 27 first overlap changed from 125 to 35 to 0 minutes after the **observed label-run index began**. This is not measured real-world warning lead. At the 1h horizon no +5 cm rise was detected, even when all 45 positives were matchable. On the reused 2025 3h replay, matching rose 27,590 → 28,052 → 28,102 with **87 hits in all three**. [Direct rise and weather controls](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/causal_delta_20261120/README.md) · [Matching replay metrics](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/causal_match_20261120/forward_2026.json) · [Full-label episode audit](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/causal_match_20261120/full_label_episodes_2026.json) · [Reused 2025 direct replay](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/causal_match_20261120/historical_2025.json)

## Rebuild plus six-MLP training: a different denominator and target

A separate two-arm study compares exact versus ≤30-minute backward matching before training **all six numerical MLPs**; same configuration, fixed 12 epochs, train-only scaling, endpoint proxy-depth supervision. It measures a stage at the reconstruction timestamp, not the direct delta label above. It retains separate 1/6/24h airport rain contexts at each station’s accepted donor clock, using the preceding complete UTC hour, with missing rain encoded as zero by experiment rule. When Dickson has no exact observation, its requested clock is used for weather and zero for discharge. That zero is not new evidence of no release.

| Cohort | Labeled stages | Exact → backward predictions or training rows | Added |
|---|---:|---:|---:|
| 2026 final training | 85,392 | 83,341 → 84,264 | 923 |
| E2 strict-forward training | 45,094 | 45,072 → 45,092 | 20 |
| E2 strict-forward assessment, event + routine | 38,284 | 36,270 → 37,158 | 888 |
| E2 event-only assessment | 4,923 | 4,127 → 4,854 | 727 |
| 2025 reused raw snapshotted replay | 28,345 | 28,114 → 28,300 | 186 |

Strict-forward 888 recovered rows include 195 with positive Little donor age and 705 with positive Medicine donor age (some rows overlap). Medicine donor age median/P95/max among those 888, including zero ages, was 5/25/30 min. Recovered rows do not all have an observed Dickson input and are not equivalent to original View rows. The exact arm had **no estimate** at the June 29, 2026 05:30 UTC stage-proxy crest. The backward arm makes it scorable, but 92.93 cm versus observed 195.65 cm is −102.72 cm. The same recovered inputs with the exact-trained checkpoint are nearly as low (−102.59 cm). Read the paired score, separately from this newly scored timestamp, in [Model experiments](MODEL_EXPERIMENTS.md). [New run preflight with ages and coverage](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/six_mlp_match_20261120/preflight_2026.json) · [2026 fit freeze](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/six_mlp_match_20261120/frozen_2026.json) · [Historical replay receipt](../data/processed/segment_six_mlp_matched_early_stop_20261118T0108Z/v4_retrain/six_mlp_match_20261120/historical_receipt.json)

## Provenance boundaries

- Raw unit observations and airport records were already local. Source receipt timestamps in manifests document archive acquisition, not first public availability for each measurement. Archive-time freshness and the actual release at forecast issuance were not established. No missing gauge observation was recreated or independently verified by filling a gap.
- Stage minus the fixed 1.603545012324 m datum is a proxy in the final numerical comparisons, not surveyed channel depth. Missing or disallowed examples stay outside the relevant denominator and are reported as such. In the direct experiment, keeping abstentions in the all-positive denominator prevents apparent success on only easy complete rows.
- The links above point to generated local records. They are provenance and experiment evidence, not new datasets packaged with this documentation, a change to the live data path, or proof of an independent third-party rerun.

## Relation to the current package

None of the later weather or backward matching refits replaced the frozen V4 checkpoint. The deployment adapter uses its own source-only matching; missing and late live observations remain explicit and the demo does not substitute for them. [See the documentation index for release files and guides.](README.md)
