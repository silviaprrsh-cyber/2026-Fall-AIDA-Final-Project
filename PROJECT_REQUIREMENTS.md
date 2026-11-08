# User-confirmed scope

## Final deliverable

The final goal is a continuously operating near-real-time Red Deer River monitoring and potential overbank-risk assessment system. It will automatically acquire new hydrometric, precipitation and available imagery data; update discharge, water level, travel time and potential overbank risk at cross-section locations; and use CV water segmentation, width and extent comparisons for validation and bias feedback. Historical data support model development, calibration and independent evaluation; a historical analysis alone is not the final deliverable. The active scope is now the Gleniffer Lake outlet / Dickson Dam downstream to the Joffre Bridge / Highway 11. This replaces the previous 724 km/full-basin scope, including the Blindman River input-to-mouth segment and ending at Joffre Bridge. Tributaries entering this reach are retained from the nearest usable same-river station to the mouth; where no usable station exists, retain available river geometry and the gap without an empty station marker.

Operational mainstem inputs use gauges with available real-time observations, adjusted with available tributary measurements according to confluence locations and propagation relationships, without double-counting upstream flows already included downstream. The central question for Jomis is whether these available real-time mainstem gauges, tributary inputs and surveyed sections can reasonably support discharge estimates at every section when only some mainstem gauges supply real-time data. This goal does not imply that reliable calculation conditions already exist at every section; observations, estimates and gaps must remain distinct.

The items below record implementation scope and stage-specific authorization. Features deferred at a particular stage remain part of the final system goal.

1. Maintain public API access for usable stations within the selected Dickson outlet–Joffre Bridge mainstem segment. Bounded validation and one-time snapshots do not start continuous collection.
2. Cover tributary mouths entering this segment. If no mouth gauge exists, select the nearest usable gauge on that same tributary, retaining the station-to-mouth reach. Do not invent observations or substitute another river when no gauge exists. Preserve gaps and available ungauged river geometry.
3. Use available original riverbed, cross-section and channel geometry for the selected reach. Preserve previously acquired broader archives. Distinguish planimetric geometry, reports, surveyed elevation points and model projects; never describe missing data as acquired.
4. Link a weather interface to every hydrometric point in items 1 and 2, with numerical precipitation data required. Validate the schema and data once; do not collect continuously.
5. First create an environment dedicated to this folder, with additional libraries installable as needed.
6. Store all downloaded original data in this folder's `data` directory.
7. Items 1, 2 and 4 must support continuous collection stopped with terminal `stop`. Under the latest request, each water and weather source uses its own publication interval. Each water station defines its calculation interval and observation-time windows. Sum nonoverlapping precipitation depths and duration-weight mean intensities; retain both. Explicitly label unknown publication frequencies; observation resolution is not publication frequency.
8. Station identifiers, counts and API availability mentioned in the original conversation are not verified facts; check them during implementation.
9. Current authorization covers implementation, one-time validation and static downloads. Do not independently start unattended continuous collection.

The latest authorization adds stages 1–4: normalize four survey packages; link cross-sections, rivers, gauges and datums; implement observation-time ETL; and implement basic hydraulics and risk screening. Unverified spatial transfers, bank elevations and datum conversions are not automatically approved. Bounded retrieval for ETL validation is allowed; unattended continuous acquisition is not started. CV training, joint CV feedback, dashboards and deployment remain outside this stage.

## Latest confirmed adjustments

- Keep broader historical tributary archives for later ML reference, but apply the current map exclusions in `config/map_station_selection.json`. Display each station once: blue for a numeric observation within the preceding three calendar months, yellow when no recent observation is found in the checked sources. Use observation dates, not download times; preserve query-failure and coverage caveats. Never overlay historical yellow and recent blue markers at the same station. Uncertain historical positions retain official coordinates and an explicit approximate-location label until a better location is verified. Lake-level references remain separate from river discharge targets. This does not expand the operational reach, enable live sources or start model training. Sylvan Lake 05CC003 is an explicit yellow lake-level reference on the current map, replacing Sylvan Creek 05CC004 on display only; its unqueried recent availability remains unknown. Keep prediction targets in a separate red point layer, identified upstream to downstream and linked to archived landmark/section evidence. Red denotes a requested estimation location, never an observed station or a computed risk category.

- The 2026-10-12 selection uses 05CB007 (Dickson tunnel outlet) and 05CC002 (Red Deer), with 05CB001, 05CC007, 05CC011 and 05CC001 as tributary inputs. Verify total dam release separately from tunnel discharge. Incorporate additional valid in-scope inputs only after coordinate and connectivity checks; do not sum serial gauge flows. `config/active_scope.json` and the new QGIS verification report record the scope; disabled catalogue entries and original full-basin archives are retained.
- The government reply, data-use permission and download links have been received, and four survey packages are saved. Datums, effective banks, spatial transfers and basin-wide coverage still need validation.
- Acquisition code lives in `API/`; originals are separated under `data/sources/<source>/`, with government manual downloads in `data/sources/alberta_flood_surveys/manual/`. Configuration and `.env` remain in the root; integrated derived outputs live in `data/processed/`.
- Eight completed migration and old document utilities were removed; one-shot API scripts remain. Markdown uses the original filename for English and `*CN.md` for Chinese; all Chinese copies are Git-ignored.
- HTTP retrieval, ETL and hydraulic screening have baseline implementations. CV training, joint feedback, a complete automatic forecast workflow, dashboards and deployment remain future goals. On 2026-10-10 the user authorized one three-hour collection, preserving one-shot/manual material and existing filenames. Datamart AMQPS notifications and finite-duration stop controls were added for this run; future runs still require authorization.


## Project Change History

### 2026-10-13 Scope reduction based on data coverage

The active project area is reduced from the approximately 724 km Red Deer River mainstem and its basin to the reach from the Gleniffer Lake outlet downstream of Dickson Dam to Joffre Bridge on Highway 11, approximately 96.3 km along the selected river network. Relevant tributary inflows entering this reach remain part of the analysis.

The original full-basin data are incomplete. Available, relatively reliable observations cannot support every relevant tributary inflow point. Filling these widespread gaps would require extensive estimation, increasing accumulated uncertainty and weakening model reliability. The project therefore focuses subsequent development on this reach, where hydrometric observations, tributary information and surveyed cross-sections are relatively more complete.

The goal remains a near-real-time monitoring system that uses available mainstem and tributary observations, river-network relationships and surveyed sections to estimate discharge, water level, travel time and potential overbank risk at selected locations. The smaller scope does not establish complete coverage or validated predictions; remaining gaps, assumptions and uncertainty must still be recorded and assessed.

Earlier text is retained as the original project record. This entry defines the revised geographic scope for subsequent work and supersedes earlier full-basin scope statements. It records a scope decision, not completion or validation of the model.

## Project modification history — 2026-11-04 (verified 2026-11-05)

The active movetest reach now ends at Red Deer station 05CC002. Retain P01–P05; remove P06–P11 and downstream Blindman/Waskasoo map inputs. The selected project data provide no comparable downstream observation constraint to validate the continuation to P11. This reduction limits unsupported extrapolation; it does not establish accuracy at retained targets. The filename `dickson_to_joffre.qgz` is retained for compatibility, but its layers and displayed endpoint now use 05CC002.

Source archives, previous model results and satellite acquisitions are retained. Existing `Overhead view.pdf`, `map_overview.png` and earlier validation reports are historical Joffre snapshots, not updated exports. Current GIS checks are `courses/AIDA-2362/data/reports/scope_05CC002.json` and `qgis_scope_05CC002.json`. The model already ends at 05CC002: its M06 link from P05 to the validation station remains; M06 is not prediction point P06. This map update does not retrain the model or replace PostgreSQL snapshots.
