# Dickson to 05CC002: text and table equivalent

[Existing map PDF](Overhead%20view.pdf) | [All 246 local feature records](map-feature-equivalent.csv)

## Map purpose and scale

The 8 November 2026 map shows the selected Red Deer River reach from the Dickson Dam outlet below Gleniffer Lake to Red Deer station 05CC002. The mainstem is 55,995.47 m along the mapped centerline. The geographic scope includes Little Red Deer River and Medicine River from their observation inputs to the mainstem, and a mapped Sylvan Creek connection without an active flow input. This is a regional overview; use the 0–20 km scale bar on the map, not the resized page, and do not measure property or channel widths from it. The scale bar is not the source of the metre-level threshold comparison below.

## Layers in words

| Map layer | Units or key entries | Meaning |
|---|---|---|
| River network | 4 lines: Red Deer River mainstem, Little Red Deer River, Medicine River and Sylvan Creek | Selected geometry, not verified flow direction or hydraulic transfer. |
| Water stations with qualifying recent data at the archive review | 05CB007 Dickson Dam Tunnel Outlet; 05CB001 Little Red Deer River near the mouth; 05CC007 Medicine River near Eckville; 05CC002 Red Deer River at Red Deer | Availability evaluated on 13 October 2026, local date. The official 05CC002 station marker remains about 69.4 m from the projected centerline endpoint. The dam tunnel outlet is not verified total dam release. |
| Historical / lake references | 05CC003 Sylvan Lake at Sylvan Lake; 05CC012 Tindastoll Creek near Markerville | 05CC003 is a lake-level reference, not an outlet-flow gauge; 05CC012 is shown as a historical reference. Neither is a prediction target. |
| Weather | 3025484 Red Deer Regional, plus one drawn association corridor | A single archive-linked station. The corridor is schematic; it is neither a watershed nor a rainfall-coverage boundary. |
| Cross-section lines | 38 Red Deer surveyed and 191 County/Markerville proposed; 229 total (146 mainstem, 83 tributary) | Lines with differing evidence, not 229 verified surveyed profiles. The Red Deer surveys date from 2017; County fieldwork was in 2022. One near-route mapped mainstem line, RDR087, does not supply a mainstem crossing. |
| Target locations | Five individually identified locations below | Project-selected review locations, not water-level stations, verified calibration sites or hazard locations. |
| OpenStreetMap | Context tiles; no feature records in this equivalent | Roads, settlements and other background context. © OpenStreetMap contributors. Optional to the analysis. |

## Exact decision equivalent: one changed threshold

Keep the same five points, nearest section association, mainstem and CRS. Select on the unrounded absolute along-river offset. Both limits include the boundary; the displayed figures are rounded, and the [source result table](section-proximity-sensitivity.csv) preserves full IDs and exact offsets.

| Target | Location (km from Dickson, rounded) | Nearest section and type | Along-river offset | ≤25 m | ≤50 m |
|---|---|---|---:|---|---|
| P01 | Mainstem below Little Red Deer/Medicine confluences (13.0) | RDR082, County proposed | 0.00 m | Yes | Yes |
| P02 | Highway 54 (23.0) | RDR062A, County proposed | 5.82 m | Yes | Yes |
| P03 | Township Road 370 (33.2) | RDR035A, County proposed | 7.14 m | Yes | Yes |
| P04 | Mainstem at the mapped Sylvan Creek mouth (48.7) | R11, Red Deer surveyed | 47.03 m | No | Yes |
| P05 | Highway 2 crossings (50.8) | R19, Red Deer surveyed | 32.25 m | No | Yes |

**Result:** 3/5 at 25 m and 5/5 at 50 m. Only P04 and P05 enter; no site leaves. Check the surveyed sections for P04/P05 first; keep P01–P03 flagged for missing verified survey profiles. P01's zero offset means a mapped coincident crossing with a proposed line, not field validation. None of the five has verified gauge-to-section vertical datum, hydraulic transfer, bank-spill elevation or observed target depth. The review recommendation is unchanged by colour, format, or basemap availability.

The [246-row feature equivalent](map-feature-equivalent.csv) lists every local vector feature by layer and stable identifier, with a role, feature bounds, exact point coordinates where applicable, and the active decision result for the five targets. Bounds describe geometry extent but are not a replacement for the analytical line/polygon coordinates in QGIS. Data sources and controls: [inventory](../data/layer-inventory.md), [validation](current-qgis-validation.json), [reanalysis instructions](section-proximity-sensitivity.md). Not for property-level inundation, emergency response, flood warnings or other operational decisions.
