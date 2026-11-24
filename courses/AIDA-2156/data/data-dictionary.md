# AIDA 2156 data dictionary

The [machine-readable dictionary](data-dictionary.csv) covers the frozen station observations, raw-audit source fields, and key derived diagnostics. Field spelling follows the archived files. Availability is quantified by explicit denominators; keep dates, absent timestamps, blank values, provider flags and reported zero distinct.

## Formal hydrology inputs

One record per ECCC WSC station and UTC observation timestamp; Q and level are paired only where available. The frozen files also retain the original single qualifier, source-reference path and acquisition receipt timestamp separately for each variable. The source-reference path and receipt establish archive lineage, **not** the first historical publication time. The minimized reproduction package excludes these non-analytical fields.

| Fields | Unit and meaning |
|---|---|
| `station_id`, `observed_at` | WSC identifier and ISO 8601 UTC observation time; key within a frozen snapshot. |
| `discharge_m3_s` | m³/s, reported stream discharge (provider parameter 47). |
| `level_m` | m, provider parameter 46. At river stations this is gauge stage relative to the station's datum; at Sylvan Lake it is a reported lake elevation. Do not compare raw absolute levels between stations or infer riverbed-relative depth. |
| `level_symbol`, `level_qualifiers`, `discharge_symbol`, `discharge_qualifiers` | Retained provider text. Historical analysis policy uses positive finite on-grid values with blank symbol and plural qualifiers. A blank flag is not evidence of verified quality. |
| `level_approval`, `discharge_approval` | Provider approval label. The historical screen does not require approval; stricter sensitivity requires the exact retained label `Final/Finales` on every included value. |
| `level_grade`, `discharge_grade` | Retained provider grade text; analyzed as categories, not an ordered accuracy score. |

Final EDA compares local complete-case schedules rather than filling holes. Grid coverage counts time slots within the fixed analysis window; a gap does not identify the cause. In the lag summary, an upstream value precedes or coincides with the terminal value by the declared lag. Correlations are observational, not causal or calibrated travel times. A missing estimate or an empty strict joint cohort is not zero correlation.

## Raw audit

| Data | Grain, relevant fields and missingness |
|---|---|
| Water Office CSV | One station, observed time and reported parameter per archived response row; repeated across download batches. `ID`, `Date`, `Parameter/Paramètre`, `Value/Valeur`; preserve `Qualifier`, `Symbol`, `Approval`, `Grade`, `Qualifiers`. An absent UTC slot, a blank value and a measured zero are not interchangeable. |
| GeoMet climate-hourly | One station and `UTC_DATE` per archived GeoJSON feature (`ID`, `CLIMATE_IDENTIFIER`). `PRECIP_AMOUNT` is mm, `TEMP` is °C, `RELATIVE_HUMIDITY` is %. Preserve companion `*_FLAG`; some fields may be null while others at the same hour are observed. |
| Sentinel-2 raster | One saved processing-grid GeoTIFF, not one independent event. Four raw digital spectral bands (B04/B03/B02/B08), then SCL and dataMask. SCL originates at 20 m; the pixel grid is 10 m. `dataMask=0` is unavailable; SCL cloud, shadow and snow differ from clear land/water. Source tiles can share sensing days. Catalogue records, pixel files, scope-QA eligibility and point crops are distinct counts. |
| Alberta GIS | Feature in a specific geodatabase and layer. Original cross-section keys differ: `CS_ID`, `NodeName` or `NAME`. Preserve source FID, surveyed/planned status, source river, original elevation field (`Elevation` or `ELEV`) and CRS/datum. Missing or unverified derived profile/bank/datum fields are not physical zeros or validation. |

See [provenance and hashes](provenance.md), [raw source evidence](../output/raw_data_eda/README.md) and [governance](../governance-and-release.md).
