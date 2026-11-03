# `core.py`

Training first intersects exact valid observation timestamps across all five stations and partitions them chronologically into 60/20/20 training, validation and test sets. Endpoint targets use propagation arrival times. Validation chooses the joint checkpoint and the test set provides final evaluation. Insufficient matches raise InsufficientSplit with an audit report. Lake normalization uses training origins only.

Reads scoped ETL SQLite through Dataset and calls ObservationIndex and section_geometry. Chain recursively produces Q, experimental depth, area, velocity and arrival times. fit calibrates six parameter blocks against the endpoint and returns the model, reports and holdout predictions to the CLI. Source inputs, lake features, geometry gaps and temporal purging are explicit. This module performs no direct file writes. See README.md for equations and assumptions.

PostgreSQL datasets use their view-provided partition memberships and snapshot identifier. Model geometry is cached by section and depth while velocity remains Q/A for each prediction. SQLite remains an explicit legacy source.

Supports validation_fraction=0 for chronological train/test experiments. Without validation, checkpoint selection uses training loss only. Records selection_basis and completed iteration budget.
