# Data coverage and archived validation report

## Current project status and follow-up checks

- The final goal is near-real-time water monitoring and potential overbank-risk estimation across the approximately 724 km mainstem and basin. This report updates existing archive evidence; it is not a new online validation.
- The user has received the government reply, data-use permission and download links. Four government survey ZIPs and extracted files are in `data/sources/alberta_flood_surveys/manual/`; use remains subject to the government terms.
- Archived ETL (2026-09-30T05:52:25.088102+00:00) contains 1,607 section lines, 91,967 points and 1,596 candidate profiles. Actual section risks remain indeterminate; having data does not establish verified hydraulic conditions.
- The newer source-timestamp snapshot dated 2026-10-04 contains 42 water stations with records within 48 hours, 4 with older records, 52 with historical daily values only and 4 returning no observations. These are snapshot statuses, not current online availability.
- Selected public interfaces do not explicitly expose actual station transmission time. Keep observation, provider processing and local receipt times separate. The summary is `data/processed/station_timestamps/Red_Deer_River_Station_Source_Timestamps.csv`.
- The four selected mainstem inputs are 05CA009, 05CC002, 05CE001 and 05CK004. Incorporate additional valid mainstem stations in upstream-to-downstream order after checking coordinates and network relationships; do not directly sum serial gauge flows.
- Acquisition code lives in `API/`, and each source has its own `data/sources/<source>/` directory. Eight completed migration and old document-editing utilities were removed; one-shot API scripts remain.
- HTTP acquisition and local ETL run separately; the complete automatically updating forecast workflow is not implemented. Address the AMQPS notification requirement before ongoing Datamart retrieval. This update starts no acquisition.
- See the [ETL reference](../../ETL_REFERENCE.md) and [manual survey review](manual_data_review.md).

Inventory/configuration snapshot below: 2026-09-29T03:03:04.418539+00:00 UTC. The corresponding one-time validation and static downloads did not start continuous collection. This is neither the documentation update time nor the latest observation time.

## Earlier archived inventory and validation results

- The WSC drainage index and GeoMet metadata were combined into 102 station records, including 12 mainstem stations and 2 dam or reservoir control points. Historical, inactive and observation-free stations remain in the catalogue.
- Validation found 43 stations with recent real-time records, 52 with historical records only, 3 with stale real-time records and 4 returning no observations. Recent means within 48 hours of validation, not that every station is continuously online.
- All 102 points have weather links that passed numerical precipitation checks, using 10 distinct ECCC stations. The maximum distance to a verified available weather station is 76.051 km; see weather_links.csv. These are not colocated observations. No precipitation was interpolated or fabricated.
- There are 112 named confluence records, including 44 direct mainstem connections and 28 matched same-river WSC gauges.
- The default configuration enables 42 distinct monitoring points across the mainstem, controls and matched tributaries. Of these, 26 have recent hydrometric and weather data, and 16 currently collect weather only. Historical hydrometric records are not repeatedly retrieved and presented as real-time observations.
- 11 federal NHN packages were downloaded once, covering 05CA through 05CK and the downstream Saskatchewan package 05CK002. Original ZIP files and coordinate definitions are retained.
- Alberta network features within or intersecting the basin comprise 8,591 permanent stream segments, 51,215 intermittent stream segments or related lines, and 5,104 waterbody polygons. Complete object-ID sets were queried before downloading and checked page by page to avoid silent truncation. Raw pages cover bounding boxes; processed outputs are filtered by basin boundaries.
- 13 official reports or amendments were downloaded, totalling 1715 pages. They cover Upper Red Deer, Red Deer, Markerville, Drumheller, Didsbury and Stettler.

## Evidence and limits of collection frequency

- Continuous hydrometric collection uses ECCC Datamart hourly CSV files, documented as updated hourly. GeoMet JSON was validated once, but DATETIME describes observation time and does not establish publication frequency.
- Continuous weather collection uses SWOB. Differences in processed_date_tm within a single response estimate the publication pattern, approximately 60 or 3,600 seconds in the samples. Observation and publication-processing timestamps are retained separately.
- **No official fixed station-specific SWOB publication SLA has been verified. These intervals are sample estimates, not officially confirmed values.** One-time validation cannot establish future publication behaviour; continuous polling was not started merely to determine frequency.
- Each water and weather source has an independent publication_interval_seconds schedule; shared sources are deduplicated. Calculation windows follow each water station publication interval and observation times without slowing weather collection. Legacy interval_seconds is retained for compatibility, not scheduling.
- Unknown intervals are not silently defaulted. Custom settings require an interval and evidence in config/stations.json. Shared weather sources are cached by source to avoid duplicate requests.
- Entering stop and pressing Enter, pressing Ctrl+C, or closing standard input stops new requests. In-flight HTTP requests finish or time out before exit. Connection and read timeouts are 15 and 20 seconds respectively; original responses are saved first.

## Incomplete coverage and actual data gaps

- **Complete numerical riverbed data, surveyed points for every cross-section and runnable HEC-RAS projects for the whole basin have not been obtained.** Public PDFs are not original survey or model files; planimetric river lines and polygons do not supply measured underwater elevations.
- Pages 170–171 of the earlier public Drumheller survey PDF name original datasets that were not provided by the public resource list or PDF attachments. Four survey packages were subsequently obtained through the government-provided access; use the saved packages and inspection reports for their actual filenames and layers.
- Full riverbed coverage along 724 km, or cross-sections at every tributary mouth, therefore cannot be claimed. Existing reports cover selected study reaches, not the entire river. DEMs and interpolation have not been presented as bathymetric surveys.
- Ungauged tributaries cannot produce measured observations. Where no same-river gauge exists, the association remains empty; another tributary or mainstem gauge is not substituted as that tributary’s gauge. Lake, reservoir and canal stations remain in the full catalogue.
- 5 confluence records use provisional straight-line selection because river-network connections are incomplete. selection_method marks these as provisional; they are not confirmed nearest-gauge results along the river.
- The older NHN network contains unknown flow directions, repeated watercourse names, unnamed reaches and branches, with unresolved records. See tributary_geometry_gaps.json and tributary_topology_gaps.json. The 550 unnamed mainstem inflow candidates are retained separately and are not equivalent to 550 confirmed tributaries.
- Scope is the public WSC/ECCC station network and the public GIS sources above. There is no evidence that all local, private or temporary monitoring facilities have been enumerated.

## Mainstem stations without recent hydrometric observations

| Station | Name | Validation result |
|---|---|---|
| 05CA004 | RED DEER RIVER ABOVE PANTHER RIVER | stale_realtime |
| 05CA008 | RED DEER RIVER AT FORESTRY ROAD | historical_only |
| 05CA001 | RED DEER RIVER NEAR SUNDRE | historical_only |
| 05CA010 | RED DEER RIVER AT SUNDRE | historical_only |
| 05CB003 | RED DEER RIVER AT GARRINGTON BRIDGE | no_observations |
| 05CD004 | RED DEER RIVER NEAR NEVIS | historical_only |
| 05CJ009 | RED DEER RIVER NEAR JENNER | historical_only |
| 05CK002 | RED DEER RIVER NEAR EMPRESS | historical_only |

## Sources and files

- [Complete WSC station index](https://wateroffice.ec.gc.ca/station_metadata/reference_index_download_e.html)
- [ECCC GeoMet hydrometric stations](https://api.weather.gc.ca/collections/hydrometric-stations)
- [ECCC SWOB real-time observations](https://api.weather.gc.ca/collections/swob-realtime)
- [Hydrometric hourly publication documentation](https://eccc-msc.github.io/open-data/msc-data/obs_hydrometric/readme_hydrometric-datamart_en/)
- [SWOB documentation](https://eccc-msc.github.io/open-data/msc-data/obs_station/readme_obs_insitu_swobdatamart_en/)
- [Alberta final flood studies](https://www.alberta.ca/final-flood-maps)
- [National Hydro Network](https://open.canada.ca/data/en/dataset/a4b190fe-e090-4e6d-881e-b87956c07977)

Public hydrometric, weather and GIS response sidecars record URL, UTC retrieval time, HTTP status, SHA-256 and byte count. These public interfaces use anonymous HTTPS. Satellite authentication uses .env credentials and run manifests; manual survey ZIP checksums are retained in archive inventories.

## Additional provincial weather checks and station matching review

- One latest public SWOB XML was checked for each of the 50 Alberta agricultural stations encountered during the original nearest-station search. 0 samples contained valid precipitation, so they did not replace the existing precipitation sources. This describes the samples only, not whether these stations ever measure precipitation.
- avg_wnd_spd_pcpn_gag_pst1hr is wind speed at precipitation-gauge height in km/h, not precipitation. Original XML, provider attribution and check results are retained under data.
- Spring Creek gauge 05CJ010 and Sylvan Creek gauge 05CC004 are more than 500 m from all mapped same-name river geometry and were not automatically selected as mouth substitutes. Their catalogue records and initial validation remain available; additional connectivity or location evidence is required.
- If a candidate’s verified river distance is shorter than the straight-line distance of every candidate with an unresolved route, the straight-line lower bound establishes the nearest gauge. Otherwise the selection remains provisional.
- Check script: API/check_partner_precipitation.py. Results: data/reports/partner_precipitation_check.json.


## Project Change History

### 2026-10-13 Scope reduction based on data coverage

The active project area is reduced from the approximately 724 km Red Deer River mainstem and its basin to the reach from the Gleniffer Lake outlet downstream of Dickson Dam to Joffre Bridge on Highway 11, approximately 96.3 km along the selected river network. Relevant tributary inflows entering this reach remain part of the analysis.

The original full-basin data are incomplete. Available, relatively reliable observations cannot support every relevant tributary inflow point. Filling these widespread gaps would require extensive estimation, increasing accumulated uncertainty and weakening model reliability. The project therefore focuses subsequent development on this reach, where hydrometric observations, tributary information and surveyed cross-sections are relatively more complete.

The goal remains a near-real-time monitoring system that uses available mainstem and tributary observations, river-network relationships and surveyed sections to estimate discharge, water level, travel time and potential overbank risk at selected locations. The smaller scope does not establish complete coverage or validated predictions; remaining gaps, assumptions and uncertainty must still be recorded and assessed.

Earlier text is retained as the original project record. This entry defines the revised geographic scope for subsequent work and supersedes earlier full-basin scope statements. It records a scope decision, not completion or validation of the model.
