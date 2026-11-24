# AIDA 2154: frozen CV experiment review package
Disposition: WITHHOLD CV outputs from the prediction model. This is a classroom evidence package, not a flood-warning product.
Contains modified Copernicus Sentinel data [2016-2026].

These instructions describe the retained frozen Python review package, not the later [Windows inference handoff](../container/README.md), the separate AIDA 2156 V4 study, or an official D2L submission.

## What is included
Frozen derived RGB/NIR arrays and automatic labels (1,009 samples), model, split/source hashes, selected results/figures, implementation and tests, current course documents. No credentials, original acquisition archive, database, unrelated GIS inputs, environments or logs are included. The mask-generation source is retained for method inspection, but regenerating raw-image masks and GIS/hydrometry joins requires the original local archives not included here.

## Offline replay
Use Python 3.13 with the locked packages in courses/AIDA-2154/requirements-cv.lock.txt. The tested computer already had these packages installed; a fresh dependency installation on another OS is not claimed.
From the extracted package root:
```powershell
python -B run.py -m cv_tools.replay_frozen_cnn --output replay_result
python -B run.py -m cv_tools.test_release_replay
```
The output directory must be new. This loads the frozen model and recomputes test probabilities, baseline and metrics without network, PostgreSQL, QGIS or source TIFFs.
Optional unchanged training replay:
```powershell
python -B run.py -m cv_tools.replay_frozen_training --output training_repeat
```
This retains the frozen input split and original hyperparameters; it never replaces the supplied model. Forty CPU epochs were about two minutes on the development computer, not a universal runtime promise.

## Review order
Read courses/AIDA-2154/README.md, data-model-card.md, docs/cv-width-failure-report.md, docs/evaluation-protocol.md, docs/requirements-audit.md and release-checklist.md.
Numeric image equivalents are in data/processed/cv_release_20261113/evaluation/point_metrics.csv under that course.
The original CNN folder has first-per-point test_examples.png, result.json and training_history.json. Width evidence is in point_width_validation_20261113. Its derived analysis is retained, but full raw-source regeneration is outside this minimal package.

## Integrity and submission
manifest.json lists each included payload file, byte count and SHA-256. The manifest itself is excluded from its own list. Compare hashes before execution; a matching hash proves identity, not scientific validity.
The local package was extracted to a new directory and replayed using the existing Python environment. This does not prove a clean OS installation.
Peer review, owner verification of the AI declaration/technical retrospective, the actual presentation and D2L upload remain pending. Confirm exact D2L format/time; do not treat this candidate ZIP as already submitted or approved.

Portable tests run five morphology, four CNN, four geometry/statistics and one frozen-site identity check. The original GIS-file scope test remains a full-workspace test and requires the excluded GIS project; it is not represented as a package test.
