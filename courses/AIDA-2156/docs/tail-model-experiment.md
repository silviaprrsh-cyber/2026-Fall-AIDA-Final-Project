# Non-saturating high-flow model experiment

This independent v2 experiment does NOT replace frozen-route v1 or the project's default model.

## Motivation and protocol

Training/validation inspection found no rows above the old flow multiplier's theoretical maximum. The v1 model's top-decile flow MAE was approximately 3.21 m3/s in training and 3.54 m3/s in validation. Matched training flow peaks at 129 m3/s and validation at 99.1 m3/s, so much larger test peaks are an extrapolation problem, not an established output-cap bug.

The v2 design was motivated by previously inspected test failures. It is retrospective, not a fresh blind experiment. Test values did not enter new fitting, threshold/scaling estimation, or checkpoint selection.

Changes in `analysis/rdr_ml/route_tail.py`:

- Six fresh SiLU residual blocks and explicit raw-flow linear skip paths.
- Raw discharge/stage/precipitation inputs replace their log-compressed representations where applicable; no fixed standardized-feature clipping.
- Positive softplus flow outputs without the old bounded exponential multiplier.
- Existing surveyed depth bounds and Q/A consistency are retained.
- Symmetric weight 5 for labels at/above the training-only 90th flow percentile (74 m3/s), weight 1 otherwise. This is not an arbitrary upward offset or asymmetric reward for overprediction.
- Frozen v1 route fractions and the same chronological boundaries, observations, weather and lake rules. No endpoint-current observation was added as a network input.
- Validation selects a checkpoint using the same training-defined weighted loss. Maximum 150 epochs, patience 25. The checkpoint and selection record are written before test evaluation.

## Completed run and negative result

Output: `courses/AIDA-2156/data/processed/segment_nn_weather_tail_v2_20261110/`.

Training stopped after 32 epochs; validation selected epoch 7. The same 35,306 test predictions were valid (95.10% of prepared candidates).

| Metric, identical target rows | v1 | v2 |
|---|---:|---:|
| Overall Q MAE (m3/s) | 6.0213 | 6.1351 |
| Overall Q bias, prediction minus observation (m3/s) | -3.7986 | -4.8727 |
| Q >=100 MAE / negative bias magnitude (m3/s) | 42.9291 | 43.0420 |
| Q >=200 MAE / negative bias magnitude (m3/s) | 137.6114 | 137.7900 |
| Overall experimental-depth MAE (m) | 0.036431 | 0.033723 |

All 3,161 predictions with observed Q >=100 m3/s remain underestimates. The 61 rows at/above 200 m3/s also remain underestimates. Thus this architecture/loss change did NOT solve severe high-flow underprediction. Small stage-error improvement is not a successful flood-prediction result. v2 is retained as a documented unsuccessful experiment and is not promoted over v1.

Persistence baselines, seasonal/event breakdowns, signed-error counts and coverage are saved in the report. The persistence baseline has access to current endpoint measurements, unlike the neural model. Stage values remain experimental and not verified physical depth. Historical propagation assumptions, input coverage and the scarcity of high-flow training support still need investigation. Repeated test-guided tuning would not establish independent performance.

## Reproduction and verification

Run tests from the repository root:

    .\.venv\Scripts\python.exe -B run.py -m rdr_ml.test_route_frozen
    .\.venv\Scripts\python.exe -B run.py -m rdr_ml.test_route_tail

Use a new output directory for a bounded new run:

    .\.venv\Scripts\python.exe -B run.py -m rdr_ml.route_tail --epochs 150 --patience 25 --output courses/AIDA-2156/data/processed/segment_nn_weather_tail_new_run

Existing destinations are rejected. No network, database or API acquisition is required. Source archives, previous experiment files, saved weights, reload consistency, input chronology and Q/A are verified. These commands do not replace default model settings.

`training_source.py` preserves the actual source used to train this run. A subsequent reporting-only correction fixed high-flow comparison coverage denominators and clarified retrospective disclosure. The pre-correction report is retained in `training_report.before_reporting_fix.json`; `reporting_source.py`, report revision metadata and `reporting_verification.json` identify the correction. Weights, predictions, selected epoch and all error values were unchanged. High-flow coverage now uses the high-flow candidate denominator rather than all test origins. No retraining followed this correction.

## Relation to the current package

This page preserves the named offline experiment. The tail-model candidate is not part of the deployed package; see the course documentation index for the separate V4 release. [See the documentation index for release files and guides.](README.md)
