# Recursive segment ML

Run commands from `movetest` using its configured Python environment. In the current workspace, the existing environment is one directory above this folder's project root.

```powershell
..\.venv\Scripts\python.exe -B run.py ml inspect
..\.venv\Scripts\python.exe -B run.py ml train --iterations 120
..\.venv\Scripts\python.exe -B run.py ml evaluate
..\.venv\Scripts\python.exe -B run.py ml predict --origin "2026-11-02T12:00:00Z"
```

The prediction timestamp is an example. Supply an origin covered by source observations and later than the fitted model's training cutoff. `evaluate` and `predict` require a successful training artifact. A separately installed environment inside `movetest` uses `.\.venv\Scripts\python.exe` instead.

## Implemented model

Two time-aligned source flows and independent 05CC007 features feed P01. Six parameter blocks propagate P01 → P02 → P03 → P04 → P05 → 05CC002 under one joint training objective. Each block predicts discharge and experimental variable depth. For each selected section, the lowest measured elevation defines experimental zero. Integration follows the wetted component connected to that lowest point. This channel-selection assumption is explicit in the configuration. Piecewise-linear integration gives A(h), and V = Q/A gives the outgoing velocity used for the next leg's L/V arrival estimate.

For each segment, Q_out = Q_in × exp(a), and h_out = h_in × exp(b) × (Q_out/Q_in)^p. The initial depth seed is discharge-weighted source depth. The exponent p defaults to 0.3 as an adjustable model prior. Only M04 adds two coefficients multiplied by standardized Sylvan Lake elevation. Lake centering and scaling use the training period. Missing instantaneous lake input leaves the trajectory pending. Rainfall features remain available in ETL for subsequent model extensions.

All 23 parameters are learned jointly from the downstream endpoint through bounded, seeded NumPy parameter-vector search and a zero-centered coefficient penalty. Each proposal updates the complete parameter vector and evaluates one endpoint loss. The loss scales Q and depth by their respective calibration-label mean magnitudes. Twelve segment coefficients, two lake coefficients, eight Medicine River feature coefficients and one lag parameter are fitted together. Intermediate states have no observed training labels, so endpoint supervision cannot uniquely identify every block. Reported intermediate values retain their experimental interpretation. The zero-coefficient baseline uses the same timing and geometry workflow.

Source velocity initialization for 05CB007 and 05CB001 uses explicit nearby proxy sections and observed Q and experimental depth through geometry adapters. 05CC007 contributes log1p(Q), log1p(stage), Q change per hour and stage change per hour to the P01 discharge and depth heads, each with learned coefficients. Its lag is learned jointly with the chain. The initial 24-hour lag and adjustable search range are experimental optimizer settings. A lag selects the station observation at or before the required departure and its earlier trend record. Future, stale and missing inputs leave a pending trajectory. The station's empty section mapping is intentional. The model requires its Q and stage records without computing station velocity.

## Time and validation

The dam branch defines the P01 arrival anchor. Other branches look up previous observations at their required departures, iterating with the selected record's geometry. The model rejects future required inputs, stale observations, nonconvergent lookups and excessive branch arrival spread. Later legs use the preceding predicted velocity. The endpoint target is the nearest observed timestamp within the configured tolerance. Receipt times remain separate.

Forecast origins are first restricted to timestamps with valid numeric records at all five stations, including lake 05CC003 and endpoint 05CC002. Earlier source departures and downstream targets still follow propagation timing. Chronological training, validation and test proportions are 60/20/20. Training fits the complete parameter vector through one endpoint loss. Validation selects among improving training checkpoints. Test errors are evaluated after that selection. Forecast origins and downstream targets must remain in their assigned partition. Earlier source and lake history may cross the lower partition boundary when available at forecast time. Insufficient samples stop the run and produce segment_ml_split.json. The partition remains fixed.

Lake normalization uses only the selected calibration origins. Eligible calibration origins are frozen before optimization, and losing a matched pair invalidates that candidate. Reports include MAE, RMSE, bias, coverage, failure counts and baseline comparisons on common origins. Because model-dependent arrival times select labels, the report compares each model's arrival-aligned errors. Archived revision and receipt-time availability have yet to be validated for operational replay. Prediction intervals and intermediate-point accuracy remain unestablished. The report's overlap_selection records exact common timestamps, station coverage, proposed split counts and baseline matched origin/target ranges. The PostgreSQL unit-value snapshot has 95,053 screened common timestamps. Effective counts after propagation checks are reported for each run.

## Inputs and outputs

The default source is PostgreSQL database `red_deer_river`, selected through `shared-resources/config/postgres_dataset.json`. The loader reads only views in a read-only repeatable-read transaction. `v_train`, `v_validation` and `v_test` supply the fixed origin partitions. Input and lake histories support lagged features. The separate endpoint observation view supplies arrival-aligned supervision. Section and routing views supply geometry. `shared-resources/config/segment_ml.json` controls model assumptions. The older local snapshot is available explicitly through `--source sqlite`. Daily means remain backup data.

Successful training writes `model.json`, `holdout_predictions.json` and `holdout_states.csv` under `courses/AIDA-2156/data/processed/segment_ml_postgres/`. The model includes configuration, input and geometry hashes, individual submodel parameters, training cutoff and version. Prediction and evaluation write named JSON/CSV files in the same directory. CSV rows include trajectory status and distinguish source geometry adapters from model predictions. The ETL `--segment-states` interface has a separate format.

Readiness, errors, training and evaluation reports go to `courses/AIDA-2156/data/reports/segment_ml_*.json`. Generated files receive bilingual companion notes. Survey-edge exceedance, invalid selected wetted components, missing inputs and insufficient matched samples produce explicit failure states. Risk remains indeterminate. The PostgreSQL origin views contain 57,031 training, 19,010 validation and 19,012 test rows. Each run applies propagation-time matching and boundary checks before fitting and records effective counts. Model artifacts keep the database schema, dataset identifier, source hashes and model-selection cutoff.

## PostgreSQL run checked on 2026-11-03

The 120-iteration joint run completed using PostgreSQL views. The iteration-88 candidate reduced training loss but failed the requirement to retain every eligible validation match, so selection retained iteration 0, the zero-coefficient baseline. Test coverage was 15,864/19,012 (83.44%), discharge MAE 0.973 m3/s and experimental variable-depth MAE 1.228 m. These results do not establish reliable water-level predictions. See `data/reports/postgresql_training_verification.json` relative to the course folder for the run record.

## Optional 80/20 comparison

Use `run.py -m eda_tools.import_unit_postgres --split 80-20` to create `v_8020_train`, an empty `v_8020_validation`, and `v_8020_test` in the same snapshot schema. The 95,053 chronological origins split into 76,042 training and 19,011 test rows. This two-way run selects parameters using training loss only. It does not use test errors for checkpoint selection. Run from `movetest`:

```powershell
..\.venv\Scripts\python.exe -B run.py ml train --iterations 120 --config shared-resources/config/segment_ml_8020.json --pg-config shared-resources/config/postgres_dataset_8020.json --output courses/AIDA-2156/data/processed/segment_ml_postgres_8020
```

Each model output directory now receives `training_report.json`. The previous 60/20/20 report is retained with its model. The 80/20 test boundary differs by one origin because of integer rounding. This is a follow-up comparison on a previously inspected test period, not a new untouched evaluation set.

The 2026-11-03 80/20 run completed all 120 iterations and selected iteration 0 using training loss. It matched 15,863 test origins, with variable-depth Bias -1.227800 m, MAE 1.227800 m and RMSE 1.228352 m. Both split experiments retained the same zero-parameter baseline. The comparison is saved under `data/processed/segment_ml_postgres_8020/comparison_602020.json` relative to the course directory.
