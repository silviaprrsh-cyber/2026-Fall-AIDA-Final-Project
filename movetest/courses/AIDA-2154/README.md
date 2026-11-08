# AIDA 2154 — Computer Vision

Purpose: inspect satellite water extent for the selected river reach as supporting evidence, not an hourly flood-warning product.

Code: `src/cv_tools/`. Inputs: `data/sources/copernicus_sentinel2/`, with acquisition metadata and provider quality masks. Run from the project root: `python -B run.py inspect-imagery`. Output: `outputs/archive_inspection.json`.

Current evidence covers raster shape, CRS, valid pixels and cloud/shadow counts. Provider masks are not a trained model. Still required: approved input/permission record, CPU-bounded baseline and model, fixed event/time/space splits, metrics and failure analysis, responsible-use/human-review decision, peer review and final package. AI assisted restructuring; no CV training or accuracy claim is made.

## Historical image acquisition

`API.download_satellite_history` queries all Sentinel-2 L2A products with tile cloud cover <=20% across the common hydrometric dataset period. The archived 20261103_history run used the former Dickson-to-Joffre river network with a 500 m buffer, native 10 m RGB/NIR spacing and exact source-product filtering. SCL is resampled from 20 m. Archive originals are in `data/sources/copernicus_sentinel2/raw/history/`; manifests are in `data/reports/satellite_history/`. Actual sensing timestamps are matched to station observations within 150 seconds. Unmatched periods, clouds, shadows and snow/ice remain explicit gaps.

Run from `movetest`. The acquisition command below starts a NEW run for the current selected geometry; provide credentials through an existing environment file. Do not resume `20261103_history` against the changed river geometry. The second command only indexes the retained historical run:

```powershell
..\.venv\Scripts\python.exe -B run.py -m API.download_satellite_history --run-id dickson_05CC002_NEW_RUN --credential-file ../.env --workers 4
..\.venv\Scripts\python.exe -B run.py -m cv_tools.index_satellite_history --run-id 20261103_history
```

The indexer extracts original GeoTIFF pixels without resampling into `data/processed/satellite_history/20261103_history/` and writes `image_index.json`. Bands 1–4 are red, green, blue and NIR, stored as reflectance x 10000; bands 5–6 are SCL and dataMask. Use the index completion flag and quality fractions before analysis. A low-cloud source tile does not guarantee a clear river corridor. Multiple grids from one overpass belong to the same event for CV splitting. CV training has not started.

Verified on 2026-11-04: all 989 planned requests resolved into 955 downloaded images and 34 no-data responses, covering 104 acquisition groups. The complete index contains 485 clear, time-matched candidates and flags one signal-free image. See [image inventory and band guide](data/processed/satellite_history/20261103_history/README.md). No CV model was trained.

## Scope of the retained archive

The 955-image inventory describes the former Joffre corridor. The 2026-11-04 map reduction did not crop or re-index these images. Active-scope selection has now produced 775 overlapping images and 389 candidates; 485 remains the old-corridor candidate count. Apply the new mask before training. Keep original pixels and provenance.

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

The first two commands rebuild local derived selections; the import commands write a versioned PostgreSQL schema/configuration. They do not fetch new observations or train a model. The satellite archive, normalized surveys and QGIS layers must accompany the code. For a new machine, create a local Python 3.13 environment and install `requirements.lock.txt`; configure `.env` from the blank `.env.example` using that machine's PostgreSQL account. Satellite credentials are needed only for new acquisition. In this workspace the existing parent `.venv` can be used explicitly; no credentials were copied and no second environment was created. QGIS remains a separately installed dependency. This is reproduction from supplied data, not an automatic reconstruction of every source archive from an empty checkout.
