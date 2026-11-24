# data

Use this folder only for the evidence described in the current D2L instructions for this course. Add a short note here when you place files in the folder. Do not add restricted data or credentials.

---

## Project implementation and reproduction

The course requirements above are preserved. The following section describes the implemented Red Deer River project and its current limitations.

## data

Water, weather and historical-series inputs are separated by provider under `sources/`; ETL tables are under `processed/`, and validation records under `reports/`. Survey inputs are referenced from AIDA 2362 through the shared path resolver. Preserve observation times, units, missingness and provenance. Data remain local and ignored by Git.

Weather update (2026-11-09): the finite `API.download_weather_history` module archives official station 3025484 hourly records by month. `rdr_ml.weather_experiment` trains and tests paired weather/control joint chains using the existing PostgreSQL hydrometric views and a local weather join. Full commands, metrics, missingness rules and limitations are in the root README weather section; comparison: courses/AIDA-2156/data/reports/segment_ml_weather_comparison_60_20_20.json.

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

Run from the repository root with the existing PostgreSQL views and permitted local archives. Existing model directories are never overwritten. `--speed-search initial-cohort` retains the first trial algorithm for reproducibility. `load_trained(folder)` reloads the network and fitted route fractions. Inference uses `align` with these fractions and independent observed-stage caps, then the six-block network; the legacy `WeatherChain` cumulative local delays are not this version's timing output. Reported node times use the anchor path's distance/speed progression. This retrospective experiment is separate from the packaged service and does not prove operational warning accuracy.

All three selected fractions are at the highest tested candidate (0.75). This does not establish a continuous optimum or validate the inferred travel times. The full matched-test speed audit is recorded in `verification.json`.

## Current release boundary

The archived outputs described here are not copied into the live service. See [data sources](../docs/DATA_SOURCES.md) for the frozen V4 evidence and [deployment](../README.md) for the standalone ECCC → dedicated PostgreSQL adapter. Live/demo records are kept separate.
