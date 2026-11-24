# Recursive segment ML

Run commands from `aida-final-project-miles-zhang` using its configured Python environment. In the current workspace, the environment is in this repository root at .venv.

```powershell
.\.venv\Scripts\python.exe -B run.py ml inspect
.\.venv\Scripts\python.exe -B run.py ml train --iterations 120
.\.venv\Scripts\python.exe -B run.py ml evaluate
.\.venv\Scripts\python.exe -B run.py ml predict --origin "2026-11-02T12:00:00Z"
```

The prediction timestamp is an example. Supply an origin covered by source observations and later than the fitted model's training cutoff. `evaluate` and `predict` require a successful training artifact. A separately installed environment inside `aida-final-project-miles-zhang` uses `.\.venv\Scripts\python.exe` instead.

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

Use `run.py -m eda_tools.import_unit_postgres --split 80-20` to create `v_8020_train`, an empty `v_8020_validation`, and `v_8020_test` in the same snapshot schema. The 95,053 chronological origins split into 76,042 training and 19,011 test rows. This two-way run selects parameters using training loss only. It does not use test errors for checkpoint selection. Run from `aida-final-project-miles-zhang`:

```powershell
.\.venv\Scripts\python.exe -B run.py ml train --iterations 120 --config shared-resources/config/segment_ml_8020.json --pg-config shared-resources/config/postgres_dataset_8020.json --output courses/AIDA-2156/data/processed/segment_ml_05CC002_8020
```

Each model output directory now receives `training_report.json`. The previous 60/20/20 report is retained with its model. The 80/20 test boundary differs by one origin because of integer rounding. This is a follow-up comparison on a previously inspected test period, not a new untouched evaluation set.

The 2026-11-03 80/20 run completed all 120 iterations and selected iteration 0 using training loss. It matched 15,863 test origins, with variable-depth Bias -1.227800 m, MAE 1.227800 m and RMSE 1.228352 m. Both split experiments retained the same zero-parameter baseline. The comparison is saved under `data/processed/segment_ml_05CC002_8020/comparison_602020.json` relative to the course directory.

## Scope synchronization — 2026-11-08

API configuration, current GIS and rebuilt ETL now use Dickson Dam outlet → 05CC002: four enabled river gauges, a separate lake reference, one weather station, P01–P05 and 229 sections. The ETL satellite table now indexes 775 overlapping archived rasters; recalculated quality/time checks select 389 candidates. Original images are unchanged. Use the active-scope mask before CV; neither selection nor provider masks are a trained CV model.

The current PostgreSQL snapshot is `rdr_unit_0f36881e431d0966`. Both default 60/20/20 views (57,031 / 19,010 / 19,012 candidates) and 80/20 views (76,042 / 0 / 19,011) were verified. These are candidate counts before travel-time alignment. Training still reads the unit-value dataset, not the 6,572 instantaneous rows in the separate scoped ETL archive.

The previous PostgreSQL snapshot and both trained models remain historical. Changed geometry/graph rejects old model reuse. New default artifacts go to `courses/AIDA-2156/data/processed/segment_ml_05CC002/`; no new model has been trained. Use a separate output directory for an 80/20 run. Previous ETL and configuration are preserved in `courses/AIDA-2156/data/processed/scope_history/before_05CC002_sync_20261108.zip`.

Reproduction from the movetest directory, using its installed Python environment:

```powershell
python -B run.py -m cv_tools.select_scope_history
python -B run.py etl
python -B run.py -m eda_tools.import_unit_postgres
python -B run.py -m eda_tools.import_unit_postgres --split 80-20
python -B run.py ml inspect
```

The first two commands rebuild local derived selections; the import commands write a versioned PostgreSQL schema/configuration. They do not fetch new observations or train a model. The satellite archive, normalized surveys and QGIS layers must accompany the code. For a new machine, create a local Python 3.13 environment and install `requirements.lock.txt`; configure `.env` from the blank `.env.example` using that machine's PostgreSQL account. Satellite credentials are needed only for new acquisition. In this workspace the destination-local `.venv` is installed and can be used explicitly; credentials remain in the local ignored .env, and the pre-existing destination environment was updated from the lock file. QGIS remains a separately installed dependency. This is reproduction from supplied data, not an automatic reconstruction of every source archive from an empty checkout.

## Weather model experiment — 2026-11-09

Historical weather from the already associated Red Deer Regional A station (3025484) now enters the joint recursive model. Official ECCC climate-hourly responses were downloaded by local calendar month, with raw bytes, query parameters, receipt times and hashes retained in a separate `eccc_climate_hourly` source directory. The initial long-range query was truncated despite its returned count; it is excluded from this experiment. Monthly archives contain 13,334 records, of which 13,208 fall inside the requested UTC feature period (2025-05-01 through 2026-11-04 exclusive).

Features are past 1/6/24-hour accumulated precipitation and temperature. Mean precipitation intensities are retained in prediction provenance. A conservative one-hour delay excludes unfinished hourly periods. All 24 hourly precipitation values and the latest temperature must be numeric and unflagged; missing, trace, estimated or flagged precipitation is not filled with zero. These are nearby point observations, not catchment-average rainfall. Features are frozen at forecast origin for the whole chain; no later weather observations are fed into downstream predictions. This is retrospective observation-time analysis, not proof of historical publication-time availability.

Each segment has four weather weights for Q and four for experimental depth: 48 additional weights, 71 total parameters. Both weather and 23-parameter control models use the same PostgreSQL 60/20/20 views and complete-weather requirement. Fixed physical feature scales (10, 30, 60 mm and 20 degrees C) use no test statistics. Both run 120 joint random-search proposals; validation selects the checkpoint, and final metrics use the test partition. Both arms preserve the original geometry/depth assumptions and optimizer. The previously inspected test period is exploratory, not a new untouched test.

| Model | Matched test origins | Depth bias (m) | Depth MAE (m) | Depth RMSE (m) | Q RMSE (m3/s) |
|---|---:|---:|---:|---:|---:|
| No-weather control | 15864 | -1.227794 | 1.227794 | 1.228346 | 1.508748 |
| Weather features | 15864 | -1.227794 | 1.227794 | 1.228346 | 1.508748 |

Selected iterations: control 0; weather 0. Full results and coverage are in `courses/AIDA-2156/data/reports/segment_ml_weather_comparison_60_20_20.json`. The comparison uses common matched forecast origins; arrival labels follow each model's predicted travel time. No claim of improvement is made solely because weather inputs were added. Intermediate P01–P05 estimates remain unvalidated.

From this repository root:

```powershell
python -B run.py -m API.download_weather_history
python -B run.py -m rdr_ml.weather_checks
python -B run.py -m rdr_ml.weather_experiment
```

The first command is a finite cached monthly download. The last trains/tests both arms and writes new directories `segment_ml_weather_control_60_20_20` and `segment_ml_weather_60_20_20` under `courses/AIDA-2156/data/processed/`. Reports use corresponding suffixes in `data/reports/`. The original default model policy and historical artifacts remain unchanged. To evaluate the weather model separately use `python -B run.py ml evaluate --config shared-resources/config/segment_ml_weather.json --output courses/AIDA-2156/data/processed/segment_ml_weather_60_20_20`. PostgreSQL supplies hydrometric training views; weather is joined from the checksum-verified local API archive. It is not yet a weather table/view in PostgreSQL or an automatic live-weather inference workflow.

Source documentation: https://api.weather.gc.ca/collections/climate-hourly and https://climate.weather.gc.ca/glossary_e.html .

## Weather-aware segmented neural main model — 2026-11-10

The main-model experiment uses six independent small MLPs (15→16→8→2, Tanh), chained through P01–P05 to 05CC002 and trained jointly by Adam on the downstream endpoint. The 2,460 trainable parameters are updated together; no intermediate observed targets are fabricated. This task trained only the weather-aware neural main model. Previous random-search models remain historical and their default configuration is unchanged.

Every block receives origin-available 1/6/24-hour precipitation and temperature. The first block also uses 05CC007 flow/stage/trends; lake level enters only the P04 block. Inputs are standardized using training inputs only, with log1p rainfall and normalized-feature clipping at ±8. Training uses the existing PostgreSQL hydrometric views and checksum-verified local weather archive. Branch source alignment and the 24-hour 05CC007 feature lag are fixed preprocessing assumptions in this experiment, not learned lags.

Each block predicts a bounded positive flow adjustment and experimental depth within its surveyed profile limits. Differentiable interpolation of 1,024 area samples per section gives A(h), V=Q/A and successive L/V arrival offsets. Checked area approximation errors are in the report. The existing minimum-survey-elevation zero is experimental, not a validated conversion from gauge stage to physical depth. No overbank-risk class is produced.

Nearest-arrival observed labels are reassigned outside the gradient calculation. No simultaneous-time labels are forced. This is stop-gradient alternating label matching, not a fully differentiable travel-time objective. The chronological 60/20/20 source boundaries are preserved; a seven-day maximum-transit plus 30-minute tolerance guard removes origins near each upper boundary. Fixed initial-model eligible cohorts prevent comparisons from silently dropping difficult cases; invalid subsequent labels receive a large fixed-denominator penalty. The resulting cohort sizes are train 43,680, validation 12,329, test 14,669. Their counts are no longer exactly 60/20/20 after coverage/guard exclusions.

CPU training: PyTorch 2.15.0+cpu, seed 42, two threads, batch 512, learning rate 0.001, maximum 100 epochs, patience 15. Completed 36 epochs; validation selected epoch 21. Test values were not used for parameter updates or checkpoint selection. The test period was inspected in earlier experiments, so this is exploratory evaluation rather than a fresh untouched test.

| Metric | Test result |
|---|---:|
| Matched origins | 14669 |
| Experimental depth bias (m) | 0.004782 |
| Experimental depth MAE (m) | 0.017889 |
| Experimental depth RMSE (m) | 0.025059 |
| Discharge MAE (m3/s) | 2.004652 |
| Discharge RMSE (m3/s) | 3.108108 |

These results do not establish intermediate-point accuracy, weather's incremental benefit or operational readiness. Cohort guards and model geometry handling differ from the old random-search experiment; raw errors are not a controlled like-for-like comparison. Model, histories and test predictions are in `courses/AIDA-2156/data/processed/segment_nn_weather_60_20_20/`; the named report is `courses/AIDA-2156/data/reports/segment_nn_weather_training_60_20_20.json`.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
.\.venv\Scripts\python.exe -B run.py -m rdr_ml.train_neural --checks-only
.\.venv\Scripts\python.exe -B run.py -m rdr_ml.train_neural --output courses/AIDA-2156/data/processed/segment_nn_weather_repeat_60_20_20
```

The CPU wheel source is recorded in the dependency files. Use a new output directory for a fresh run; existing model artifacts are not overwritten. Commands require the PostgreSQL service, local credentials and permitted archived inputs described above, and do not start API acquisition. Runtime assertions cover gradients through all six blocks, weather sensitivity, Q/A, chronological arrival order and nearest-label boundaries. Saved weights were reloaded with `weights_only=True` and reproduced ten training-input predictions exactly. The final end-to-end API/dashboard integration remains future work.

## Bounded route-speed neural training

The new weather-aware model uses total source-to-05CC002 river distances (05CB007: 55,995.47 m; 05CB001: 54,271.19 m; 05CC007: 115,001.37 m). A source observation arrives at its observation time plus distance divided by estimated representative path speed. The 05CB007 arrival anchors the other two sources; match the nearest eligible past-source arrival and the nearest endpoint observation, selecting the later observation on an exact tie, within 30 minutes. The old fixed 24-hour feature lag and fixed seven-day transit cutoff are not used. All source, trend, lake and endpoint timestamps must remain within their chronological partition. Weather retains past-only complete 1/6/24-hour precipitation and temperature.

Each speed is `fitted_fraction * Q / minimum_valid_pre_confluence_area`. The area is computed independently from observed experimental stage, transferred unchanged to the available same-river profiles before the confluence. It is not controlled by the neural depth prediction. There are 21 dam-path, 15 Little Red Deer and 68 Medicine River candidate profiles. Invalid or truncated profiles are excluded for each observation; no valid area means no estimate. Every trajectory records its controlling section, valid profile count, area, Q, speed cap and estimated speed. This is an experimental constraint, not a verified physical speed limit.

The first bounded-route trial is preserved in `segment_nn_weather_route_bounded_60_20_20/`. Its fixed-cohort penalty rejected every speed proposal, leaving all fractions at 0.5; that trial does not demonstrate calibrated speeds. The corrected calibration uses a common cohort valid under all 27 combinations of predeclared fractions 0.25, 0.5 and 0.75. Training-only coordinate search alternates with joint Adam updates to all six neural blocks, supervised only at 05CC002. This is a discrete, interpretable speed calibration, not a continuous unconstrained speed network. Original PostgreSQL 60/20/20 date boundaries remain; exclusions mean final counts are not exactly those proportions. Common cohort sizes: train 11703, validation 7073, test 676.

Completed 100 epochs; validation selected epoch 82. Selected fractions: 05CB007=0.75, 05CB001=0.75, 05CC007=0.75. No test labels selected parameters or checkpoints. The previously inspected test period remains exploratory.

| Test evaluation | Matched / candidates | Q MAE (m3/s) | Q RMSE (m3/s) | Experimental depth MAE (m) | Experimental depth RMSE (m) |
|---|---:|---:|---:|---:|---:|
| Common calibration-comparable cohort | 676/676 | 2.507232 | 2.631778 | 0.008429 | 0.009716 |
| All weather/lake-prepared test origins, selected speeds | 13231/19012 | 2.318317 | 2.490262 | 0.010300 | 0.013710 |

Errors in the second row apply only to matched rows; missing matches are not zero-error predictions. The common subset is small and does not establish event-wide accuracy. Different arrival labels/cohorts prevent a controlled headline comparison with the older neural model. Experimental stage-to-depth and unchanged-depth section transfer are unverified. Long inferred travel times, especially on Medicine River, require hydrological review and must not be presented as validated water or flood-wave travel times. Intermediate P01-P05 outputs remain unobserved estimates.

New files are under `courses/AIDA-2156/data/processed/segment_nn_weather_route_bounded_60_20_20_grid/`; the named JSON report is `courses/AIDA-2156/data/reports/segment_nn_weather_training_route_bounded_60_20_20_grid.json`. The previous neural model and first bounded trial are checksum-preserved. `verification.json` checks every saved test trajectory for the hard speed cap, past-only sources, distance/speed timing, nearest endpoint labels and local Q/A consistency; all passed.

```powershell
.\.venv\Scripts\python.exe -B run.py -m rdr_ml.route_neural --checks-only
.\.venv\Scripts\python.exe -B run.py -m rdr_ml.route_neural --output courses/AIDA-2156/data/processed/segment_nn_weather_route_repeat_60_20_20
```

Run from the repository root with the existing PostgreSQL views and permitted local archives. Existing model directories are never overwritten. `--speed-search initial-cohort` retains the first trial algorithm for reproducibility. `load_trained(folder)` reloads the network and fitted route fractions. Inference uses `align` with these fractions and independent observed-stage caps, then the six-block network; the legacy `WeatherChain` cumulative local delays are not this version's timing output. Reported node times use the anchor path's distance/speed progression. This offline experiment is separate from the packaged V4 research service and does not establish operational warning performance.

All three selected fractions are at the highest tested candidate (0.75). This does not establish a continuous optimum or validate the inferred travel times. The full matched-test speed audit is recorded in `verification.json`.


## Approximate-depth frozen-route sensitivity — 2026-11-17

Completed an opt-in run in `courses/AIDA-2156/data/processed/segment_nn_weather_depth_weighted_v1_20261117/`, reusing `rdr_ml.route_weighted_v1` rather than adding a new model module. It reads the reviewed proxy-depth PostgreSQL bundle locally, in a read-only transaction, and keeps the legacy stage-based propagation matches fixed. Defaults, old models, raw observations, CV and database readiness flags are unchanged. This is a feature/target coordinate experiment, **not** a physically recalibrated depth-routing model.

The same isolated reverse-time cohort contains 49,380 later training origins and 12,350 earlier test origins. This is 61,730 retained of 92,912 weather/lake-prepared origins; 73,714 were globally propagation matched before 11,984 temporal-boundary exclusions. The within-cohort 100% match rate is conditional, not coverage of all observations. Training includes the 284 m³/s peak on 2026-06-29; test includes a separate 148 m³/s peak on 2025-06-21. The inner high-flow validation maximum is 161 m³/s. The historical test was already inspected and does not represent prospective forecasting. Frozen-route calibration also limits the independence of internal validation.

Epoch selection stopped after 22 epochs and selected epoch 2 using only the existing internal validation objective. A fresh network was refit for two epochs on the full development set. All test comparisons below use identical source/origin/arrival/target rows, and the archived stage predictions and labels are translated once to the same endpoint proxy-depth coordinate.

| Same 12,350 test origins | Stage control | Approximate-depth experiment |
|---|---:|---:|
| Endpoint depth/stage MAE (m) | 0.124380 | 0.086357 |
| Endpoint depth/stage bias (m) | -0.007250 | -0.008227 |
| Q MAE (m³/s) | 9.427686 | 11.800840 |
| Q bias (m³/s) | 7.289783 | 9.993308 |
| Q ≥100 MAE (m³/s), 310 origins | 17.360280 | 27.022361 |
| Q ≥140 bias (m³/s), 46 origins | -43.960334 | -43.076873 |
| Q ≥140 underprediction fraction | 100% | 100% |

Overall depth MAE improved about 30.6%, but Q MAE worsened about 25.2%; the severe upper-tail underprediction remains. The 46 upper-tail rows are not independent events, and some share endpoint timestamps. No test target reaches 200 m³/s. This experiment is **not** an overall replacement for the historical stage model, and no default was promoted. Do not tune further choices against these test errors.

Per-station proxy depth is reported stage plus a constant, so no new time-varying information was introduced. Intermediate same-depth transfer is still unvalidated. The trained model has 921/12,350 test inputs above the P02 geometry grid and 937 P02 outputs within 1% of its upper bound (training: 2,530 and 2,870 respectively). These numerical constraints prevent interpreting endpoint improvement as physical geometry validation. The natural next diagnostic is training-only source-to-section depth transfer and routing calibration, not simply increasing epochs against the inspected test.

Verification: 32 focused protocol/depth tests passed; 7 local-connection helper cases passed. Model reload reproduces saved predictions; 243 prior artifacts remain hash-identical. `protocol_before_test.json`, `training_report.json`, `verification.json` and `post_training_audit.json` retain the protocol, metrics, hashes and full-test reload check. Command/options and caveats are in `route_weighted_v1.py.md` and its Chinese companion. All generated inputs/checkpoints/logs stay in ignored local paths.


## Fixed-arrival six-MLP depth experiment

The opt-in PostgreSQL depth chain is separate from the legacy commands above. Run `.venv\Scripts\python.exe -B run.py -m rdr_ml.train_routing_depth --checks-only` for synthetic checks. See `train_routing_depth.py.md` for the 60/20/20 and 80/20 read-only preflight and explicit training command. Routing is fixed before the model; intermediate depth outputs are not independently supervised.

## Current packaging boundary

The commands and archived experiment metrics here concern earlier analysis and the offline model chain, not the packaged service. For the retained V4 and separate deployment adapter with server ZIP and Windows receiver, see the [course README](../../README.md). Do not reuse these analysis commands or their results as a live forecast.
