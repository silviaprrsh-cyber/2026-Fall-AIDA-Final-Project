# User-confirmed scope

## Final deliverable

The final goal is a continuously operating near-real-time Red Deer River monitoring and potential overbank-risk assessment system. It will automatically acquire new hydrometric, precipitation and available imagery data; update discharge, water level, travel time and potential overbank risk at cross-section locations; and use CV water segmentation, width and extent comparisons for validation and bias feedback. Historical data support model development, calibration and independent evaluation; a historical analysis alone is not the final deliverable. The approximately 724 km mainstem and full-basin spatial scope remain unchanged.

Operational mainstem inputs use gauges with available real-time observations, adjusted with available tributary measurements according to confluence locations and propagation relationships, without double-counting upstream flows already included downstream. The central question for Jomis is whether these available real-time mainstem gauges, tributary inputs and surveyed sections can reasonably support discharge estimates at every section when only some mainstem gauges supply real-time data. This goal does not imply that reliable calculation conditions already exist at every section; observations, estimates and gaps must remain distinct.

The items below record implementation scope and stage-specific authorization. Features deferred at a particular stage remain part of the final system goal.

1. Build a public API access layer for public monitoring stations along the approximately 724 km Red Deer River mainstem. During implementation, validate the current schema once; do not collect continuously.
2. Cover all tributary mouths. If no mouth gauge exists, select the nearest gauge on that same tributary. Do not invent observations or substitute another river when no gauge exists. Preserve gaps.
3. Acquire available original riverbed, cross-section and channel geometry material across the basin once. Distinguish planimetric geometry, reports, surveyed elevation points and model projects; never describe missing data as acquired.
4. Link a weather interface to every hydrometric point in items 1 and 2, with numerical precipitation data required. Validate the schema and data once; do not collect continuously.
5. First create an environment dedicated to this folder, with additional libraries installable as needed.
6. Store all downloaded original data in this folder's `data` directory.
7. Items 1, 2 and 4 must support continuous collection stopped with terminal `stop`. Under the latest request, each water and weather source uses its own publication interval. Each water station defines its calculation interval and observation-time windows. Sum nonoverlapping precipitation depths and duration-weight mean intensities; retain both. Explicitly label unknown publication frequencies; observation resolution is not publication frequency.
8. Station identifiers, counts and API availability mentioned in the original conversation are not verified facts; check them during implementation.
9. Current authorization covers implementation, one-time validation and static downloads. Do not independently start unattended continuous collection.

The latest authorization adds stages 1–4: normalize four survey packages; link cross-sections, rivers, gauges and datums; implement observation-time ETL; and implement basic hydraulics and risk screening. Unverified spatial transfers, bank elevations and datum conversions are not automatically approved. Bounded retrieval for ETL validation is allowed; unattended continuous acquisition is not started. CV training, joint CV feedback, dashboards and deployment remain outside this stage.

## Latest confirmed adjustments

- The four currently selected mainstem gauges are 05CA009, 05CC002, 05CE001 and 05CK004. Incorporate valid data from additional mainstem stations according to coordinates, connectivity, flow direction, along-river distance and upstream-to-downstream order. Inputs are not fixed to four stations; do not sum serial gauge flows.
- The government reply, data-use permission and download links have been received, and four survey packages are saved. Datums, effective banks, spatial transfers and basin-wide coverage still need validation.
- Acquisition code lives in `API/`; originals are separated under `data/sources/<source>/`, with government manual downloads in `data/sources/alberta_flood_surveys/manual/`. Configuration and `.env` remain in the root; integrated derived outputs live in `data/processed/`.
- Eight completed migration and old document utilities were removed; one-shot API scripts remain. Markdown uses the original filename for English and `*CN.md` for Chinese; all Chinese copies are Git-ignored.
- HTTP retrieval, ETL and hydraulic screening have baseline implementations. CV training, joint feedback, a complete automatic forecast workflow, dashboards and deployment remain future goals. Address AMQPS notifications before ongoing Datamart retrieval. This reorganization starts no continuous collection.
