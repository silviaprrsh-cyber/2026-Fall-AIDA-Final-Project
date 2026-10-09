# Data directory

All acquired originals are separated by source under `sources/<source>/`. Within each source, `raw/` holds API responses, `static/` holds static downloads and `manual/` holds user downloads. Acquisition batches, station files and original metadata are preserved.

| Source directory | Contents |
| --- | --- |
| `sources/eccc_hydrometric_geomet/` | GeoMet water observations, history and station metadata |
| `sources/eccc_hydrometric_datamart/` | Datamart hourly hydrometric CSV |
| `sources/eccc_weather_geomet/` | GeoMet weather, precipitation and weather station metadata |
| `sources/eccc_weather_datamart/` | Partner weather XML and discovery responses |
| `sources/eccc_wateroffice/` | WSC station indexes and datum evidence |
| `sources/eccc_geomet_catalog/` | GeoMet collection catalog |
| `sources/eccc_documentation/` | Archived official ECCC documentation |
| `sources/alberta_geospatial/` | Alberta GIS rivers, waterbodies and watersheds |
| `sources/alberta_flood_studies/` | Alberta flood-study pages and reports |
| `sources/alberta_flood_surveys/manual/` | Four government survey ZIPs and extracted study folders |
| `sources/nrcan_nhn/` | NRCan National Hydro Network |
| `sources/copernicus_sentinel2/` | Copernicus satellite responses and imagery |

Keep separate station files, acquisition batches and survey-study subdirectories within each source. Put additional government survey downloads in `sources/alberta_flood_surveys/manual/`, preserving original ZIP names by study. Give other sources their own directories instead of mixing unidentified downloads.

`processed/` contains derived and cross-source associations. `processed/etl/` is an integrated snapshot of sections, hydrometry and precipitation, not original data from one provider. `reports/` holds validation reports and document QA artifacts; `logs/` and `state/` hold audit trails and runtime state.

`processed/source_normalized/eccc_wateroffice/station_index_all.csv` is the strict 18-column station-index copy used by the catalogue builder. `rdr/station_index.py` preserves literal quotes in provider station names, removes empty surplus columns and pads blank/footer rows; it rejects nonempty surplus fields and incomplete station rows. The adjacent `.meta.json` records source/output SHA-256 hashes and corrected source line numbers. The original `sources/eccc_wateroffice/raw/discovery/station_index_all.csv` remains unchanged. Catalogue rebuilds regenerate this derived copy before strict parsing.

Station source timestamp CSV: `processed/station_timestamps/Red_Deer_River_Station_Source_Timestamps.csv`.

This CSV is an archived query export, not a live status feed. Observation time, provider processing time and actual station transmission time have different meanings. Where the interfaces do not expose actual transmission time, that field remains empty. A new `API/query_station_timestamps.py` run updates its JSON results but does not automatically regenerate this CSV.

The relocation manifest and per-file SHA-256 hashes are in `reports/layout_migration/manifest.json`. Original responses and metadata remain byte-identical, so archived metadata may retain old paths. Resolve them using `rdr.paths.resolve_archived_path()` or the manifest. Active configuration and derived record paths are updated; the manifest also traces historical references in older reports and rendered documents.

Project Markdown has separate language copies: English keeps the original name; Chinese adds `CN`, such as `READMECN.md`, and is Git-ignored. Source/derived data, logs and machine reports remain ignored. This English README and the two English human-readable reports may be versioned.
