# src

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

## Current contents
cv_tools contains candidate-mask processing, the small CNN and static baseline, width analysis and focused tests. replay_frozen_cnn rechecks the retained model and metrics; replay_frozen_training repeats the unchanged configuration into a new folder; build_cv_review_package constructs a local allowlisted candidate. Use the course README and package guide, not historical acquisition commands, for final offline replay. No script in the final replay requires a live API.


## PostgreSQL-driven CV replay

cv_tools.pg_pipeline provides init/register/masks/train/verify/all stages. cv_tools.test_pg_pipeline checks paths, audit, constraints, date groups and atomic rollback. It reuses the existing segmentation and CNN functions without changing their scientific method.
