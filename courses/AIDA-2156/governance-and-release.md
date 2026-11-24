# Governance and release decision

**Withhold operational prediction, flood warning and emergency-response use.** Permit clearly labelled course evaluation only. Historical associations do not validate travel times, establish an operational trigger or show that a gauge reports riverbed-relative depth. See [provenance](data/provenance.txt) for the sources and [the dictionary](data/data-dictionary.csv) for observed and derived fields.

## Attribution and clean package boundary

| Source | Documented authority and treatment |
|---|---|
| **Water Survey of Canada, Environment and Climate Change Canada** | The repository's dated Water Office terms record (`courses/AIDA-2154/docs/data-permission-selection.md`) records that the [Water Office disclaimer](https://wateroffice.ec.gc.ca/disclaimer_info_e.html) permits copying/distribution with attribution, prohibits resale of bundled raw information, and warns that near-real-time observations are preliminary. The local station archive matches that product; no conflicting source-specific terms were identified in the selected acquisition records. Credit WSC/ECCC, identify this as derived student work, retain quality/approval metadata in the selected projection and do not imply Government of Canada endorsement. |
| **ECCC GeoMet Climate Hourly** | Credit ECCC and identify the station and archive in analytical results. The recorded Water Office disclaimer does not by itself govern unrelated providers or products. Include aggregate coverage/quality findings, not minute/hour-level climate rows or GeoMet response archives in the clean package. |
| **Copernicus Sentinel-2 L2A / CDSE** | The 2026-11-13 source record (`courses/AIDA-2154/docs/data-permission-selection.md`) identifies [CDSE terms](https://dataspace.copernicus.eu/terms-and-conditions) and attribution for Sentinel imagery. Credit “Contains modified Copernicus Sentinel data [2016–2026]” for applicable derived imagery/figures. This does not cover portal graphics, credentials or unrelated sources. The package includes aggregate evidence only; do not bundle imagery, per-file provider responses or authenticated receipts. |
| **Government of Alberta Flood Survey; NRCan if geometry is reused** | Credit agencies and named study areas; include aggregate inventory/verification findings only. The local repository's `shared-resources/provenance-and-permissions.md` records permission reported by the project author for data use; it does not establish permission to redistribute original surveys, reports, GIS layers, or private correspondence. Public data or a government reply does not establish Indigenous, community or instructor endorsement. |

Keep the formal EDA code, tables, documentation and [input provenance](data/provenance.md) in the coursework repository. Reproduce the raw-source audit only where the local archival inputs are authorized. Do not distribute credentials, connection strings, request receipts, private correspondence, restricted surveys, PostgreSQL dumps, model weights or virtual environments with the EDA evidence.

The teacher-authored root README records the proposals as “Approved as submitted.” That is recorded project-topic approval, not a separate sign-off for all external data, release contents or the later reduced geographic scope. D2L submission, authorship/AI disclosure, peer-review claims and final course compliance remain the student's responsibility. A local clean-room run or package scan, when recorded in the package, is evidence of that check only, not a substitute for them. No public deployment or D2L submission is implied.

## Separate Windows prototype

The full repository's course README documents a separate Windows server ZIP and client EXE; neither ships here. Keep the private server archive and checkpoint outside this EDA package. Local synthetic demo mode is not real observation or flood-readiness evidence. No cloud deployment or public endpoint publication is authorized by this governance record.
