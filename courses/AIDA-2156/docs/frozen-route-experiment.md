# Frozen-route experimental workflow

This is an additional offline experiment. Existing route modules, models and results are unchanged. It does not replace the project's default model or start API acquisition.

## What changed

`analysis/rdr_ml/route_frozen.py` selects a route using training data only, freezes the three route fractions, and then matches each chronological partition independently. A forecast origin no longer has to be valid under every one of the 27 candidate routes.

The default dates are UTC:

- Training: source archive start through 2026-04-01, exclusive.
- Validation: 2026-04-01 through 2026-06-01, exclusive.
- Test: 2026-06-01 through the cached archive's end.

Past source observations may precede a partition boundary: they are valid historical warm-up, not future information. Sources must never be later than forecast origin. Endpoint labels and arrivals must stay before the partition's upper boundary; endpoint labels must be at or after its lower boundary and the forecast origin. Weather and lake cache values are recomputed from local archives and checked for past-only source times. This is observation-time replay; historical publication-time availability remains unverified.

## Route calibration

The first 75% of training origins fit a small ridge regression proxy; the remaining chronological training origins are an inner calibration holdout. Fit labels cannot cross the inner boundary. The proxy uses source state and contextual features, with scaling fitted only on the inner fit rows. The ridge penalty is fixed at 1. Each route is scored on the same inner holdout origin population:

- Valid row: normalized squared error / (1 + normalized squared error).
- Invalid row: loss 1.

This makes missing predictions visible in a fixed denominator instead of silently dropping hard rows. The normalization scale comes only from inner-fit-period endpoint observations. All 27 predetermined fractions are assessed; objective, matched counts and proxy errors are saved in `route_calibration.json`. No outer validation/test observations are used to select routes. Routes are not revised during neural training.

This is a statistical proxy for choosing route settings, not a physical velocity calibration or a guarantee of optimal neural-network performance. Its bounded objective trades coverage against error and can underweight extreme errors; raw errors and coverage are reported separately. Different routes can match different target times. Never interpret their calibration score difference as a controlled same-label physical experiment.

## Neural training and evaluation

All six neural blocks are newly initialized. The historical checkpoint provides only static depth/area/distance buffers; its learned layers and normalization are not reused. Normalization and loss scales are fitted on new training matches. Validation selects the neural checkpoint. Runs have finite epochs and early stopping.

Reports include:

- Candidate counts, matched counts, coverage, distinct dates, unique target times, flow range and invalid reasons.
- Full-period errors and high-flow (100/200 m3/s diagnostic thresholds), early-June, late-June/July, summer and autumn subsets. These thresholds are not official flood thresholds. Subset coverage uses its own candidate denominator.
- Persistence baseline using the latest endpoint observation at/before origin, no more than one hour old, compared on identical rows and labels. This baseline has endpoint-current information not provided to the neural model.
- Historical checkpoint comparison only on common origins with identical observed target timestamps. The old checkpoint has already seen portions of the newly designated test period; this comparison is descriptive, not independent evidence.
- Complete test arrays, including unmatched candidate masks, in `test_predictions.npz`.
- Weight reload verification, source/dependency hashes and checksums confirming listed previous experiment and report files are unchanged.

Empty subsets report null coverage/errors rather than zero error. Repeated target timestamps are not deduplicated because the unit of evaluation is a forecast origin; distinct target counts are reported. Subsets are conditional on the route's aligned target time/value, not an independently fixed complete event population.

## Commands from the repository root

Run regression tests:

    .\.venv\Scripts\python.exe -B run.py -m rdr_ml.test_route_frozen

Run a fresh bounded experiment, using a NEW output directory:

    .\.venv\Scripts\python.exe -B run.py -m rdr_ml.route_frozen --epochs 100 --patience 20 --output courses/AIDA-2156/data/processed/segment_nn_weather_frozen_new_run

Use `--prepare-only` to calibrate and audit matches without training. The destination must not exist; even an incomplete experiment is never overwritten. The source cache and outputs must remain under the local processed-data directory. No database service or internet access is used. Saved weights are loaded with `weights_only=True`; `load_frozen(folder)` verifies checkpoint identity before loading.

## Remaining limitations

This uses an existing prepared cache, not a full re-extraction of every original source. Earlier weather/lake exclusions remain. The stage-to-depth datum and unchanged-depth transfer to cross-sections remain experimental. Q/minimum valid area is an unvalidated path-speed constraint, not a measured flood-wave speed. Intermediate locations have no independent observed labels. Route selection cannot manufacture missing events, guarantee validation coverage or replace physical validation.

All historical periods have been examined during development. Revised splits are retrospective assessments, not a fresh untouched blind test. The two-epoch smoke run is a workflow check, not a final model result.

## Relation to the current package

This page preserves the named offline experiment. The standalone cloud-prepared release uses the retained V4 weights with a separate source-only adapter; do not transfer the results on this page to the receiver. [See the documentation index for release files and guides.](README.md)
