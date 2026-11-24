# Frozen experiment protocol and evidence chronology
This document consolidates the implemented protocol on 2026-11-13. It does not backdate a new preregistration.

## Decision and comparison
Can a small CPU CNN improve fixed-site water masks enough to provide useful river widths? The simple comparator is the per-point mean training mask thresholded at 0.5. It is interpretable and tests whether learning imagery adds value beyond memorizing persistent river shape. The selected small encoder/decoder has 6,113 parameters; it uses the taught convolution, ReLU and pooling concepts while retaining pixel outputs.

The original training source and saved config freeze seed 42, 4 CPU threads, 40 maximum epochs, batch 16, Adam 0.001, positive BCE class weighting capped at 10, validation patience 10 and checkpoint saving at every strictly lower validation loss. Paired flips are training-only. The inference threshold is 0.5. All model selection uses validation; frozen test predictions were subsequently examined, so future reuse is exploratory.

## Data and leakage
Dataset: 1,009 point-date samples, 708 train / 169 validation / 132 test, 204/41/40 unique dates. Train 2016-05-02 to 2024-09-07; validation 2024-09-22 to 2025-10-05; test 2025-10-22 to 2026-10-20. All points from the same date are kept together; seven-day boundary gaps and exact duplicate pixel checks apply. Normalization and static baseline use training only. Cloud/shadow/snow/unknown labels (255) do not enter loss or metrics. 13,413 ignored pixels are retained across the full dataset.
This tests future dates at known sites, not new locations. Automatic-label errors are shared between training and test; the scores are weak-label agreement, not independent ground truth.

## Metrics and inspection
Original code computes TP, FP, FN, TN, IoU, precision, recall, baseline and per-point slices. Formula: IoU=TP/(TP+FP+FN); precision=TP/(TP+FP); recall=TP/(TP+FN). Dice=2TP/(2TP+FP+FN) was added in the release replay as a derived descriptive score, not a selection criterion.
First test image per point is shown without choosing by score. Narrow-tributary slices, zero-width examples, centre/parallel/orientation transects, seasons, brightness and quality checks describe failures. Hydrometric associations are retrospective and are not width truth.
The release replay also reports thresholds 0.4/0.5/0.6 as POST-HOC sensitivity only. It does not replace the original threshold or choose a new model from test performance.

## Evidence identity
Original code hash and model hash: data/processed/point_cnn_20261113/result.json.
Data/source identities and splits: dataset_manifest.json and selection_summary.json in that directory.
Original retained experiment hashes: docs/cv-width-failure-report.md.
Release replay: data/processed/cv_release_20261113/evaluation/evaluation.json.
A separate dated preregistration before all exploratory labeling decisions is not available; do not claim one. Protocol consolidation and computational replay do not repair the absence of independent labels.
