# Section proximity sensitivity: Dickson Dam to 05CC002

**Decision:** Use the map to prioritize checking surveyed section records, not to select hydraulically valid sites.

Keep the active 05CC002 reach, the five mapped targets, network, section inventory and target-to-section associations fixed. Change only the inclusive limit on the absolute along-mainstem offset: **25 m** as a tight classroom screen and **50 m** to test the effect of doubling it. Neither threshold is a survey standard, a measure of mapping precision or a hydraulic acceptance criterion.

| Target | Linked section (short ID) | Section source | Along-river offset (m) | At 25 m | At 50 m |
| --- | --- | --- | ---: | --- | --- |
| P01 | RDR082 | County/Markerville, planned | 0.00 | Yes | Yes |
| P02 | RDR062A | County/Markerville, planned | 5.82 | Yes | Yes |
| P03 | RDR035A | County/Markerville, planned | 7.14 | Yes | Yes |
| P04 | R11 | Red Deer 2017, surveyed | 47.03 | No | Yes |
| P05 | R19 | Red Deer 2017, surveyed | 32.25 | No | Yes |

At 25 m, **3/5** pass and none is linked to a surveyed section. At 50 m, **5/5** pass: **P04 and P05** enter, both linked to surveyed sections, and no target leaves. Review survey metadata and the possible gauge-to-section transfer at P04/P05 first. Keep the other three marked as needing surveyed profiles. Do not infer that 50 m is more accurate, or that any of the five has a verified shared vertical datum, hydraulic transfer, bank elevation or observed model depth. Zero offset at P01 identifies a mapped crossing of a planned line, not a field measurement.

## Reproduce and check

1. Open the [existing QGIS project](../project/dickson_to_joffre.qgz). On the P01-P05 target layer use **Select by Expression** with `abs("nearest_section_along_river_offset_m") <= 25`, then make a new selection with the same expression and `50`. Compare the selected target IDs in the attribute table. There is no need to save the selections or edit the map.
2. From the AIDA-2362 folder run `python -B src/gis_tools/section_proximity_sensitivity.py`. It joins the saved [active target layer](../project/derived_prediction_targets/prediction_points.geojson) to the [County/Markerville](../project/alberta_flood_surveys/county_markerville/cross_section_lines.geojson) and [Red Deer](../project/alberta_flood_surveys/red_deer/cross_section_lines.geojson) line layers by section ID and reads their existing `line_status`. The [CSV](section-proximity-sensitivity.csv) preserves full IDs, exact distances and both selections.
3. The [target builder](../src/gis_tools/build_prediction_points.py) projects the selected mainstem and source section lines to EPSG:3400, measures chainage at usable point intersections and stores section chainage minus target chainage for the nearest intersection by absolute difference. Positive means downstream. The screen uses the unrounded absolute difference, not straight-line map distance. This reuses existing GIS geometry results and does not change or regenerate them.

Verification: reopened the current project in QGIS 3.44.14 and ran both selections without saving. The selected IDs matched the Python CSV in both cases.
