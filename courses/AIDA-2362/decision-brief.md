# GIS decision brief

Reviewed 2026-11-23 (initial working draft 2026-11-11), addressing the bounded decision, uncertainty, limitations, implementation/no-go conditions and next-evidence requirements in [the course brief](README.md). **Recommendation: release this bounded GIS package for classroom evidence review only (Alberta EPA confirmed submission use with attribution on 2026-11-23); withhold operational flood, maintenance or public-safety recommendations.**

## Decision and boundary

The intended spatial reviewer needs to locate monitoring inputs, section associations, prediction targets and evidence gaps between the Dickson Dam outlet and station `05CC002`. The immediate action is to review coverage and identify where further validation is needed, not to authorize flood warnings, maintenance or public-safety decisions. An incorrect coverage interpretation could imply that an unobserved location is validated or that a missing observation means low risk.

The selected mainstem is approximately 55,995 m long. The [scope report](data/reports/scope_05CC002.json) retains `P01–P05` and removes `P06–P11`, Blindman River and Waskasoo Creek from the active map because the selected data lack a comparable downstream observation constraint beyond `05CC002`. This change limits unsupported extrapolation; it does not establish accuracy at `P01–P05`. The official `05CC002` coordinate is unchanged; its projected centerline endpoint is about 69.4 m away.

The map is a dated development snapshot, not live station status. The exported PDF (`Overhead view.pdf`, reviewed 2026-11-08) uses a printed 0–20 km scale bar for regional review and is not intended for parcel- or structure-level measurement. Per-layer sources, licences, dates, CRS and coordinate units are now documented in [data/layer-inventory.md](data/layer-inventory.md) and [data/layer-inventory.csv](data/layer-inventory.csv). The teacher-authored root README records AIDA 2362 as "Approved as submitted." That approval is preserved; explicit instructor acknowledgement of the reduced `05CC002` reach remains a confirmation item.

## Existing evidence

The [current QGIS validation](outputs/current-qgis-validation.json) and [reopening/demo guide](outputs/qgis-reopen-and-demo.md) verify offline reopening of an independent relative-path copy in QGIS 3.44.14 with all eight local vector layers, 246 features, valid geometries, documented CRS/units and two saved layouts (`Simple OSM overview` and `Overhead view`). The active inventory comprises 5 targets, 4 river gauges, 2 historical/lake references, 1 weather station, 38 Red Deer surveyed section lines, 191 County/Markerville planned section lines, 4 river features and 1 schematic weather-association area.

The working project is [dickson_to_joffre.qgz](project/dickson_to_joffre.qgz); its legacy filename does not change the active `05CC002` endpoint. The current presentation output is [Overhead view.pdf](outputs/Overhead%20view.pdf). Blue/yellow indicate archived observation availability, red indicates estimation targets and green indicates schematic weather associations (not watershed boundaries). Non-colour text and table equivalents are provided in [outputs/map-text-equivalent.md](outputs/map-text-equivalent.md) and [outputs/map-feature-equivalent.csv](outputs/map-feature-equivalent.csv).

The [fixed-target proximity screen](outputs/section-proximity-sensitivity.md) adds `P04` and `P05` when the along-river cutoff changes from 25 m (`3/5`) to 50 m (`5/5`). They are the only two targets linked to surveyed sections in this screen. Prioritize verifying their survey records; keep the three planned-only targets (`P01–P03`) flagged for new field surveys.

## Uncertainty and no-go conditions

Proximity does not prove network connectivity, hydraulic transfer or a valid prediction. Vertical datum separation remains unresolved: Alberta survey profiles reference CGVD28 (`EPSG:3780`), whereas Environment and Climate Change Canada (NHS Hydrological AB, 2026-11-17) confirmed in response to a student datum inquiry that most hydrometric stations operate in an assumed datum and that conversion factors may not exist or remain contiguous across gauge moves. The map cannot validate water depth, travel time, CV output or unobserved intermediate model estimates.

Do not use the map outside the reviewed extent/time/scale, to rank real communities or properties, or for flood/safety decisions. The historical scope reduction is not presented as the required controlled baseline/changed-variable sensitivity test.

## Next evidence and implementation conditions

Alberta Environment and Protected Areas confirmed on 2026-11-23 that the provided survey data is publicly available information and may be used in the course submission with EPA attribution (private email correspondence and original GDBs remain excluded). Assemble and clean-extract test `AIDA2362_FinalProject_Miles_Zhang.zip`, complete classmate peer review (two projects, Dec 1–11), demonstrate the live QGIS workflow in Week 15, and upload the final ZIP to D2L by December 14. Review [governance](governance-review.md) and [release conditions](release-checklist.md) alongside this brief.
