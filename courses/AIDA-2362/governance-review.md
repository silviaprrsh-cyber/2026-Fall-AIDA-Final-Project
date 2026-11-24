# GIS privacy and governance review

Updated 2026-11-22 (initial working review 2026-11-11), covering privacy, bias, community impacts, distinctions-based Indigenous authority and licensing required by [the GIS brief](README.md). This records current limits and release conditions; it does not certify legal clearance or community engagement.

## Data authority and provenance

The [shared permission record](../../shared-resources/provenance-and-permissions.md) and [active per-layer inventory](data/layer-inventory.md) (`data/layer-inventory.csv`) document external environmental inputs rather than fictional/synthetic data. The teacher-authored root README records the course proposal as "Approved as submitted," and this review preserves that approval while tracking explicit instructor acknowledgement of the reduced `05CC002` reach.

| Source or component | Existing basis | Remaining release condition |
|---|---|---|
| Alberta flood surveys (`county_markerville`, `red_deer`) | Provided by Alberta Environment and Protected Areas (EPA) on 2026-09-30 for RDP academic use. On **2026-11-23**, Alberta EPA confirmed in writing that the provided survey data is publicly available information and that EPA has no concerns with using the clipped derived layers in the course submission provided EPA is credited. | Include explicit Alberta EPA attribution in the package and README; keep private email correspondence (`Protected A`) and raw original geodatabases strictly out of Git and the D2L ZIP. |
| NRCan river geometry (`nrcan_nhn`) | Public Open Government Licence – Canada; archive metadata, CRS and attribution recorded in `data/layer-inventory.md`. | Preserve required OGL-Canada attribution in the final portable ZIP. |
| ECCC station/weather layers (`eccc_*`) | Public federal catalogue / ECCC Data Servers End-use Licence; per-layer CRS, fields and attribution recorded in `data/layer-inventory.md`. On 2026-11-17, ECCC (NHS Hydrological AB) also confirmed that most stations use an assumed vertical datum. | Preserve ECCC / MSC / WSC attribution; do not bundle private ECCC correspondence or personal contact details. |
| OpenStreetMap basemap | Live QGIS XYZ source (`© OpenStreetMap contributors`); requires network access. | Preserve attribution; do not bundle cached raster tiles in the ZIP; distinguish live tiles from the eight offline vector layers. |
| Derived target/weather layers | Derived locally in `EPSG:4326` / `EPSG:3400`; full geometry, CRS, field and count validation recorded in `outputs/current-qgis-validation.json`. | Keep relative paths and regenerate `submission-manifest.txt` after final ZIP assembly and clean extraction test. |

The per-layer inventory (`data/layer-inventory.csv`, `data/layer-inventory.md`) and local preflight manifest (`submission-manifest.txt`) are now complete. Public access, academic provision, or technical validity do not by themselves establish unrestricted redistribution permission.

## Privacy and security

Current selected records concern environmental stations, cross-section lines and river geometry, not personal-record datasets. Private emails (including the `Protected A` Alberta EPA reply and ECCC inquiry containing student contact details), credentials, connection strings, original geodatabases and unrelated historical archives must remain excluded from the private repository and any D2L submission ZIP.

## Bias and community effects

Monitoring locations, survey coverage and historical availability are uneven. Missing data do not show absence of flood exposure or community need. The reduced reach and `P01–P05` are evidence boundaries, not a priority ranking. Schematic weather associations are not watersheds; assigning them as actual catchments would misrepresent affected places. Do not use this classroom map to allocate resources, assess property safety or imply protection of unobserved locations.

## Indigenous authority

First Nations, Métis and Inuit have distinct rights, authorities and governance expectations; one generic government data licence is not evidence of their consent or endorsement. This review has not identified or consulted relevant rights-holders for the reach and does not claim authority to speak for them. It has not established whether particular source data carry community-specific restrictions.

Before any proposed community-facing or operational use, identify the relevant rights-holders and data stewards, establish the appropriate distinctions-based engagement and data-governance process, and verify permitted purposes, representation, attribution, access and any restricted locations with those authorities. Do not label this classroom exercise as Indigenous consultation or apply a single governance rule to all communities.

## Release decision

Withhold operational and public flood-risk release. For private course submission only, Alberta EPA confirmed permission with attribution on 2026-11-23; `AIDA2362_FinalProject_Miles_Zhang.zip` is assembled with all eight permitted relative vector layers, required agency attributions (NRCan, ECCC, Alberta EPA, OSM), and clean-extraction QGIS verification recorded in `outputs/zip-extraction-validation.json`. Preserve all scientific and governance unknowns explicitly in the [decision brief](decision-brief.md).
