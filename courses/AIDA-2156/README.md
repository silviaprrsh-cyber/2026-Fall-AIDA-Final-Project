# AIDA 2156 Final Professional Project — EDA Decision Study

## Formal 2156 EDA decision study

**Standalone course report (Word):** [English](docs/eda-project-report.docx) · [中文版](docs/eda-project-reportCN.docx)

Start with the [decision report](app-or-report/final-eda-report.md), [claim-to-evidence index](claim-evidence-index.csv), [formal sensitivity results](output/sensitivity-results.csv) and [source-context audit](app-or-report/source-context.md). From this course folder, run `python -B analysis/analysis.py` with the frozen normalized inputs; see [analysis instructions](analysis/README.md). This is a historical observed-station comparison, independent of the V4 model and Windows demonstration below.

Reproduce the EDA with the [analysis instructions](analysis/README.md) and [runtime record](requirements-eda.lock.txt). The [clean-copy replay](output/clean-copy-replay.txt) passed the formal assertions and reproduced all seven saved files byte-for-byte. The [submission manifest](submission-manifest.txt) inventories local evidence and remaining submission checks. The Windows demo is separate.

## Final Red Deer River study: V4

**Course research only. The final historical test does not support using V4 for real flood forecasting, alerts, emergency response or other safety decisions.** The retained course checkpoint is the frozen **V4 60/20/20 six-MLP** (`model_60_20_20.pt`), not the later optional Dickson jump guard or a retrained matching/weather variant. Selection makes it the project reference, not an operational flood system. V4 predicts a terminal depth proxy at a historical arrival time, not surveyed water depth, inundation or lead time.

Start in the [bilingual documentation index](docs/README.md): [data sources and formats](docs/DATA_SOURCES.md), [data splits and pipeline](docs/DATA_PIPELINE.md), [model experiments and decision](docs/MODEL_EXPERIMENTS.md), and [later data-improvement trials](docs/DATA_IMPROVEMENT.md). The notes below preserve earlier course and experiment context; earlier metrics and commands refer to their named snapshots, not this final V4 checkpoint.


### Windows service and desktop receiver

The local release files are the [private Windows server ZIP](deployment/dist/RedDeerRiver-Server-Windows-Private.zip) and the [single-file Windows client EXE](deployment/dist/RedDeerRiver.exe). See the [server operator guide](deployment/server/README.md), [client guide](deployment/client/README.md) and [v1 HTTP contract](deployment/server/WIRE.md). These are local build artifacts, not publicly hosted downloads. The server and a dedicated managed PostgreSQL database are **prepared for cloud deployment, not deployed**. Keep the server ZIP private; it contains the pinned model.

The server starts collecting on its own. It fetches official ECCC observations, writes to its isolated PostgreSQL schema, and publishes a read-only `/api/v1/snapshot` (initial 84-hour fetch, then 3-hour overlap every 10 minutes by default). The client opens by double-click without Python or a terminal; enter a server **base URL** in its UI, without recompiling. The internal HTTP listener defaults to `127.0.0.1:8765` (`--port` or `RDR_PORT`); the external HTTPS proxy and the database have independent ports. Only the server connects to PostgreSQL.

The viewer distinguishes four observed station flows and the airport rain observation from modeled depths at the current target bin, +3 h and +9 h. P01–P05 are unverified internal model outputs; P06 is a terminal water-depth proxy. +9 h requires the exact Little Red Deer observation for the current five-minute grid slot to have been received at issuance; a late or missing input means unavailable, not an estimated upstream discharge. Synthetic demo mode is separate from live observations. The package uses frozen V4 weights with a source-only adapter, not the historical training View, and is **not for real flood warning, response or safety decisions**.

**Individual assessment · 25% of the AIDA 2156 course grade**

## Purpose and project case

Complete an individual, evidence-led exploratory data analysis for a bounded facilities-maintenance decision. The supplied space-comfort service-event data are fictional and synthetic. The starter proves the package can run and helps you inspect data-quality choices; it is not a solution path or an approved project question. Propose a student-selected decision question and obtain the required formative scope check before treating it as your project. Do not make causal claims unless your design supports them.

## How to approach the work

1. **Define the decision and unit.** Name the audience, decision, population, period, observation unit, denominator, practical criterion, and stop rules. Keep a dated change record.
2. **Establish data authority and quality.** Record source, permission, grain, units, missing codes, provenance, privacy review, and data dictionary. Validate keys, ranges, missingness, and transformations.
3. **Plan claims before writing conclusions.** Link each decision-bearing claim to its source fields, checks, method, output, uncertainty, sensitivity, and limitation.
4. **Explore before deciding.** Examine distributions, relationships, subgroups, unusual cases, missingness, and reasonable alternatives. Record why each view answers the decision question.
5. **Quantify uncertainty and practical meaning.** Report estimates, intervals/uncertainty, effect sizes, sample structure, assumptions, dependence/multiplicity or selection concerns where relevant, and non-causal limits. A p-value alone is not sufficient.
6. **Test whether the decision changes.** Compare at least two consequential changed specifications, including one concerning missingness, outliers, dependence, measurement, or inclusion. State whether the takeaway changes or remains stable.
7. **Communicate accessibly and govern release.** Provide a report or app plus equivalent values in a table and text/static access notes; document governance, privacy, limitations, AI use, and release/redesign/withhold decision.

## Required final deliverables

Keep the evidence in `courses/AIDA-2156/`. The current D2L clean, reproducible EDA package must cover:

- `analysis-plan.md`: bounded question/decision, audience, unit, period, denominator, practical criterion, claim plan, stop rules, and dated changes;
- `data/data-dictionary.csv` and `data/provenance.txt`: authorized input, grain, units, missing codes, source/version, permission, privacy review, synthetic/external status, and checksum;
- `analysis/analysis.py` or a documented notebook with reproducible cleaning and EDA, plus `analysis/tests_or_assertions.py` or equivalent checks;
- `claim-evidence-index.csv`: each decision claim linked to fields, quality checks, method, output, uncertainty, sensitivity, limitation, and release status;
- `output/`: labelled figures/tables, validation evidence, clean-run log, and `sensitivity-results.csv` with at least two changed specifications and decision impact;
- `app-or-report/`: explanatory report or local app, equivalent values in a table, and accessibility notes for keyboard/non-colour/static access and text alternatives;
- `governance-and-release.md`, `limitations-and-next-evidence.md`, `ai-use-declaration.md`, `retrospective.md`, and `peer-review.md`;
- exact environment lock(s), `submission-manifest.txt`, README/run instructions, and all permitted supporting files.

A fresh copy must run using permitted inputs and leave a dated log without secrets or machine-specific paths. Exclude virtual environments, caches, credentials, connection strings, restricted/raw data, nested ZIPs, and unrelated files. Run any package checks the instructor supplies before submitting; a structural check does not verify the reasoning.

The D2L rubric totals 25% across decision framing (2.5), data quality (3.5), exploration (4), statistical reasoning (4), sensitivity (2.5), accessible communication (2.5), governance/ethics/privacy/disclosure (2), reproducibility/repository/submission hygiene (2), and individual demonstration/defence (2).

## How progress is checked

Use the shared formative checkpoints; they do not change the project weight. Bring evidence that the project is moving from a bounded question to a clean, checked, defensible decision artifact.

- **Week 6 — question/access:** plan, unit/denominator, practical criterion, data permission, and stop rules.
- **Week 8 — data/quality:** inventory, dictionary, provenance, validation, and initial exploration design.
- **Week 10 — exploration/claim map:** repeatable initial analysis, first output, and claim-evidence links.
- **Week 12 — sensitivity/limitations:** two consequential alternative specifications, decision impact, uncertainty, limitations.
- **Weeks 13–14:** demonstrate the working EDA and complete the assigned peer review.
- **Before final upload:** use the feedback to improve the work and verify the clean package.

## Submission and presentation

**Current D2L deadline: Monday, December 14, 2026 at 11:59 p.m.** In-class presentations are planned in **Weeks 13–14**, as scheduled by the instructor. Complete the assigned peer review and record the genuine feedback and response, including what you accepted, adapted or declined and why.

Demonstrate the working EDA: station, parameter and UTC time unit; the denominator; one traceable claim; a sensitivity or limitation; and the recommended next step. The Word report shows the evidence sequence. The synthetic V4 viewer is optional context.

The `AIDA 2156 Final Project: Presentation, Peer Review, and Submission` D2L activity requires an uploadable, reproducible clean project package and the private repository link in the submission information or manifest. The supplied page does not specify an extension; verify the actual files from a clean location before submitting and use any official validation checks made available. A Git link does not replace upload. **No EDA submission package was made or uploaded for this check.**

---

## Project implementation and reproduction

The course requirements above are preserved. The following section describes the implemented Red Deer River project and its current limitations.

## AIDA 2156 — EDA

The active [unit-value history analysis](data/processed/model_unit_history/20261103T070414Z/README.md) contains 95,053 common screened observation timestamps over the requested 18-month window. The candidate 60/20/20 split is by record count and time order. Daily-history files remain backups and are excluded from this analysis. Source grades, approvals, missingness and provenance are preserved.

The experimental recursive ML entry point is `python -B run.py ml inspect`. Training, evaluation and prediction commands are described in [the ML README](analysis/rdr_ml/README.md). It uses minimum surveyed elevation as experimental section zero and derives velocity from Q/A. 05CC007 supplies independent Q, stage and trend features with a learned lag. All parameters train jointly on the 05CC002 endpoint. The active unit-value dataset is stored in PostgreSQL. Training reads versioned views and reports effective arrival-aligned sample counts for each partition.

Question: are hydrometric and precipitation observations sufficiently complete and temporally compatible to support the selected reach analysis? Observation units are station records and station-specific calculation windows.

The integrated submodel table is `data/processed/project_etl/segment_training.csv`: M01–M06 run from the source inputs (05CB007 + 05CB001 flows, with independent 05CC007 features) through P01–P05 to validation station 05CC002. Sylvan Lake elevation is a separate feature only for P03→P04. Future submodel velocities determine cumulative L/V arrival times and nearest-time endpoint labels; no same-time fallback is used. Missing model states remain null. The data README documents optional `--segment-states` input and PostgreSQL SQL export; local training artifacts are retained separately; credentials and ignored data are not included in a code-only checkout.

Code: `analysis/`; inputs and normalized tables: `data/`. Sources remain separated under `data/sources/`. Run from the project root: `python -B run.py etl`. The current reduced-scope dataset is in [data/processed/project_etl/](data/processed/project_etl/README.md), with CSV and SQLite versions and a build report at `data/reports/project_etl_validation.json`. The final GIS selection and normalized profiles are explicit prerequisites; raw data are retained.

The former 2026-11-02 ETL snapshot is backed up. Current ETL and GIS retain P01-P05, 229 sections and validation endpoint 05CC002, with synchronized PostgreSQL views. Experimental depth assumptions, missing-precipitation handling and EDA reporting work remain; endpoint supervision does not validate intermediate states.

The PostgreSQL importer is `python -B run.py -m eda_tools.import_unit_postgres`. It creates a versioned snapshot with source hashes. Training uses `v_train`, `v_validation` and `v_test`, plus separate lagged input, lake, endpoint and geometry views. Newly acquired data require a new import before training can use them.

The 60/20/20 and 80/20 training experiments both selected the zero-parameter baseline, without demonstrated learned improvement. Reports are `data/reports/segment_ml_training_60_20_20.json` and `data/reports/segment_ml_training_80_20.json`; map updates do not retrain these experiments.

### Scope synchronization — 2026-11-08

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

## Submission evidence organization — 2026-11-08

Keep the instructor brief above as the requirement. See [the course-by-course gap register](../../shared-resources/submission-readiness.md) and [scope matrix](../../scope-matrix.md) for the current evidence and unfinished work. Refer to the current D2L assignment for submission instructions. Do not submit environments, credentials, scratch files or unrelated historical archives. Preserve permitted inputs needed to reproduce the selected result.

Weather update (2026-11-09): the finite `API.download_weather_history` module archives official station 3025484 hourly records by month. `rdr_ml.weather_experiment` trains and tests paired weather/control joint chains using the existing PostgreSQL hydrometric views and a local weather join. Full commands, metrics, missingness rules and limitations are in the root README weather section; comparison: courses/AIDA-2156/data/reports/segment_ml_weather_comparison_60_20_20.json.

Neural main model (2026-11-10): the weather-aware six-block MLP has been jointly trained and evaluated. See the root README neural section for exact metrics, cohort guards, limitations and reproduction commands. This does not complete the EDA course deliverables.

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

Run from the repository root with the existing PostgreSQL views and permitted local archives. Existing model directories are never overwritten. `--speed-search initial-cohort` retains the first trial algorithm for reproducibility. `load_trained(folder)` reloads the network and fitted route fractions. Inference uses `align` with these fractions and independent observed-stage caps, then the six-block network; the legacy `WeatherChain` cumulative local delays are not this version's timing output. Reported node times use the anchor path's distance/speed progression. This historical experiment is separate from the standalone V4 research service and does not establish operational warning performance.

All three selected fractions are at the highest tested candidate (0.75). This does not establish a continuous optimum or validate the inferred travel times. The full matched-test speed audit is recorded in `verification.json`.

## Current supporting model evidence

The five retained protocols and identical-test comparisons are summarized in the [experimental evidence report](app-or-report/experimental-evidence-report.md). These model results support exploratory comparison; they are not the formal EDA or its sensitivity checks. The formal evidence is linked at the top of this README.
