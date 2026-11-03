# `__main__.py`

Defaults to --source postgres and the snapshot selected by shared-resources/config/postgres_dataset.json. Loads training data through read-only SQL views and writes new model artifacts under data/processed/segment_ml_postgres. Use --source sqlite for the older local snapshot.

Implements run.py ml inspect/train/evaluate/predict. Calls rdr_ml.core, rdr_eda.postgres and the ETL companion writer. Reads the selected data source and JSON policy. Writes model and prediction artifacts under course data/processed/segment_ml_postgres and readiness/error/evaluation reports under data/reports. Model loading checks graph, policy and geometry compatibility. See README.md for command examples.

Training also saves training_report.json next to each model for comparisons across output directories.
