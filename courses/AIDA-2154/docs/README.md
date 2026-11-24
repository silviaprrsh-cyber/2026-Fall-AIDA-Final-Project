# docs

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

## Current contents
The CV failure report, source/permission record, evaluation protocol, compute replay report, requirement audit, finalized first-person retrospective (2026-11-22), supplementary 9-site blind manual audit (2026-11-23), demo notes, package guide and honest peer-review status are here. These documents preserve the negative finding: current satellite-derived widths are not suitable for the prediction model. Actual peer review, demonstration and D2L submission remain pending.


This separately preserved AIDA 2154 experiment is a negative result for satellite-derived width validation. No CV width, mask or proxy was used to validate the [AIDA 2156 V4 hydrology study](../../AIDA-2156/README.md). V4 is separate research evidence, not an operational flood-warning product or part of the CV package.

## Database workflow

postgres-cv-pipeline.md describes the isolated PostgreSQL schema, audited image/mask references, two views and training replay. The container guide is in ../container/README.md. These are separate from the retained original experimental evidence.

## Formal report

The [English Word report](cv-project-report.docx) and [Chinese version](cv-project-reportCN.docx) cover the original design, implemented independent workflow, data, SQL audit, experimental limitations and Windows container outcome in six sections. The [Markdown overview](cv-project-overview.md) preserves the same distinction between the two workflows.

## Two-part Windows container delivery

Obtain both binary parts from the course `outputs` directory: `AIDA2154-CV-Windows-20261113.zip.part001` (1,321,342,227 bytes) and `AIDA2154-CV-Windows-20261113.zip.part002` (1,321,342,226 bytes). Each is strictly below 2,000,000,000 bytes; neither can be extracted independently. Follow the [two-part delivery and startup guide](../outputs/README.md): verify the part hashes, join them in order using streaming PowerShell, verify the reconstructed ZIP against the original SHA-256, then extract it and run `./run.ps1` from the package folder. The guide contains the canonical commands and hashes.

The reconstructed package contains the full saved image, external model weights, scripts and two synthetic smoke-test samples, not real source imagery. It requires a compatible licensed Windows host, Docker Windows container mode and Server Core LTSC2022 Hyper-V isolation; no host Python/PostgreSQL is required. The earlier extracted-package test passed on the same development computer, not a second clean machine. The original full ZIP is retained locally and Git-ignored; the two delivery parts are not ignored. Nothing has been uploaded or submitted. This handoff remains separate from the historical review package and pending formal course submission.

## D2L delivery and demonstration

[D2L readiness](d2l-readiness.md) records the local candidate ZIP, SHA-256, 132-image CPU replay and 14 portable tests. See [live-demo notes](demo-notes.md), the [English Word report](cv-project-report.docx) and its [Chinese companion](cv-project-reportCN.docx).
