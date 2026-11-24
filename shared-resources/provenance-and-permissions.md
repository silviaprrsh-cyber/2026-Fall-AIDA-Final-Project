# Shared data provenance and permissions

Reviewed 2026-11-08 from local project records; this is not a new legal or provider-terms verification. All selected environmental inputs are external, not fictional/synthetic. No credentials or private correspondence belong in Git.

| Input / owner | Authority recorded | Version / grain / preparation | Remaining release check |
|---|---|---|---|
| Hydrometry and weather / ECCC | Public anonymous interfaces recorded in acquisition code and metadata. | Unit-history request 2025-05-03–2026-11-03; source-specific station/time/parameter records; UTC normalization, revision handling, quality flags and window coverage. | Attach the applicable licence/attribution and frozen input checksums to the final package. Public access alone is not proof of unrestricted redistribution. |
| River geometry / NRCan | Public source archives retained. | Download metadata preserved per archive; selected reach derived using river geometry and station associations. | Record exact source licence/version, layer CRS and attribution in the GIS release inventory. |
| Flood surveys / Government of Alberta (EPA) | Provided 2026-09-30 for RDP academic use; on **2026-11-23**, Alberta EPA confirmed in writing that the provided Red Deer River survey data is publicly available information and may be used in the course submission provided EPA is credited. | Original manual packages preserved locally; 229 clipped active lines in GIS package with explicit Alberta EPA attribution. | Preserve Alberta EPA attribution; keep private email correspondence (`Protected A`) and raw full geodatabases out of Git and submission ZIPs. |
| Sentinel-2 / Copernicus via CDSE | Authenticated acquisition using local credentials, archived product metadata and checksums. | 2025-05-03–2026-11-01 image window; RGB/NIR with provider quality products; scoped mask and acquisition-time association. | Include applicable attribution and redistribution terms; exclude tokens. Provider classifications are not project ground truth. |

Privacy review: selected records describe environmental stations, not personal records. Raw responses and manual packages still require a content and licence review before release. Exact source identity/checksums reside in acquisition sidecars/manifests and course reports. Do not imply Indigenous community approval or authority from government data access. Community impacts and Indigenous-authority considerations remain part of the GIS release review.

The teacher records proposal approval, but this review has not inspected D2L or independently verified that approval against each external input or the reduced scope. Record that confirmation before making a final compliance claim.

## CV inventory update 2026-11-13

The dated archive windows above remain stage records. The current independent CV database registers 1,442 source image files and 2,322 point samples dated 2016-05-02 through 2026-11-04, with irregular coverage. The frozen train/validation/test counts are 708/169/132; the final test acquisition is 2026-10-20. Source identity and permissions are documented in the [CV data record](../courses/AIDA-2154/docs/data-permission-selection.md). The database replay made no new satellite API requests.
