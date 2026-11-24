# Raw data EDA evidence

This is a local, offline source audit for the Red Deer River course project. It does not read V4 predictions, change ETL, fill observations, train models, or establish operational flood readiness.

## Reproduce

From the repository root on the project Windows machine:

```powershell
& .\.venv\Scripts\python.exe -B courses\AIDA-2156\analysis\raw_data_eda.py
```

Pass `--output-dir <folder>` for an independent rerun; use `--only hydro`, `--only cv`, or `--only gis` to run one component. The CV raster spot check uses Rasterio. The GIS audit uses GDAL with OpenFileGDB (on Windows the launcher can find installed QGIS, or take `--gis-python`). The presenter needs authorized access to the actual source archives; this evidence folder does not redistribute them. A fresh checkout without local archives or historical CV audit inputs cannot run the full check.

## Results and interpretation

| Evidence | What it measures |
| --- | --- |
| [Hydrometric and weather series](hydro_series_summary.csv), [monthly coverage](hydro_monthly_coverage.csv), [gap inventory](hydro_gap_inventory.csv) | Four flow stations, two observed stage series, and airport hourly weather. Counts use inferred in-span 5-minute or hourly slots, not a claim that every missing slot is an instrument fault. No imputation. |
| [Provider flags](hydro_provider_flags.csv), [overlapping values that changed](hydro_value_revisions.csv) | Source quality status and repeated timestamps tracked separately from missing values or measured zeros. |
| [CV inventory and summary](cv_summary.json), [date coverage](cv_acquisition_coverage.csv), [quality screen](cv_scoped_quality.csv) | Local source GeoTIFFs and sensing days, with separately identified historical screening and derived point crops. The screen is not independent width validation. |
| [GIS layer and linkage audit](gis_summary.json), [source layers](gis_source_layers.csv), [scoped section links](gis_scope_cross_sections.csv), [prediction targets](gis_scope_targets.csv) | Original survey and proposed lines, their relation to working layers, and limits of gauge-to-survey comparison. P01–P05 are not independent observed water-depth stations. |

Raw-source findings explain what the evidence can support; they do not validate travel times, explain V4 errors, or replace final EDA sensitivity comparisons.


## Verified run

On 2026-11-20, the complete run succeeded in the repository and then from outside the repository with an empty alternate output folder on the same Windows machine. All 16 generated CSV/JSON files were byte-identical across the two runs. Four Python scripts parsed, evidence links resolved, and representative source counts matched. This verifies the local authorized-input workflow, not portability to a machine without the archives.
