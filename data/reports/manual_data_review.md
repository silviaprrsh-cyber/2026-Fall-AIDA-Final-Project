# Manual survey review

Government data-use permission and download links have been received. Original ZIPs and geodatabases remain unchanged in their source directory. Baseline ETL contains 1,607 lines, 91,967 points and 1,596 candidate profiles, with candidate links, banks and datum transfers still requiring verification. Package counts below describe the initial layer review and use different filters from ETL counts.

All four ZIP archives were extracted into their corresponding directories under `data/sources/alberta_flood_surveys/manual/`; the original archives are retained. ZIP CRC checks passed during extraction. SHA-256 hashes, file counts and sizes are recorded in `manual_archive_inventory.json`. The initial review inspected data and relationship fields only. Baseline ETL and candidate spatial links were subsequently implemented; see the status update below. This documentation update starts no acquisition or ETL rebuild.

| Package | Data read | Main coverage |
| --- | --- | --- |
| Drumheller | 27,228 cross-section survey points; 435 planned section lines | Red Deer, Rosebud, Kneehills, Michichi, Willow |
| Red Deer | 594 surveyed section lines; 34,979 survey points, including 28,936 classified as Cross Section | Red Deer, Waskasoo, Piper |
| Upper Red Deer | 318 surveyed section lines; 18,899 survey points, including 17,881 classified as Cross Section | Red Deer, Bearberry and Fishway |
| Red Deer County and Markerville | 10,861 section topographic survey points; 260 proposed section lines | Red Deer, Little Red Deer, Medicine |

These datasets cover individual study reaches. They do not establish complete coverage of the 724 km mainstem or all tributaries. Planned line counts must not be presented as verified surveyed section counts.

## Confirmed value and relationship fields

- All four principal survey-point layers contain `Elevation` or `ELEV`, with no nonfinite elevation values found in this read. This does not validate survey accuracy or fitness for use.
- Drumheller section points include 11,279 `BATHY`, 5,233 `BED`, 3,367 `BNK`, 884 `TOB` and 749 `BOB` records. The report defines TOB as top of bank. Some submerged-bed and bank-top measurements are available, but effective left/right spill elevations have not yet been established for every target section.
- County/Markerville point types include 5,970 `UNDERWATER`, 3,976 `GROUND`, 678 `WATERLINE`, 232 `ROCK` and 5 null values.
- All 28,936 Red Deer Cross Section points match the 594 section lines by `CS_ID`; all 594 lines have matching points.
- For Upper Red Deer, 17,840 Cross Section points match 316 lines by `CS_ID`. The other 41 points use `N/A`, `R3 to R4` or `R4 to R5`. Two lines have no directly matching points under this filter and need separate review.
- Section identifiers such as `R1` recur across packages. Future joins should use a package/study-area namespace, river and `CS_ID`, rather than a globally assumed unique `CS_ID`.
- Drumheller's `WSC_Stations.DESCRIP` contains `05CE001` and `05CE020`; both match identifiers in the project station catalogue. Other section-to-live-station relationships still need river-name, coordinate and river-network checks; one-to-one correspondence must not be assumed.
- The initial review made no automatic nearest-line assignments. Subsequent ETL created distance- and ambiguity-constrained spatial candidates for Drumheller and County/Markerville; spatial relationships and source codes remain subject to verification.

## Datums and unresolved questions

The main survey layers use NAD83(CSRS) / Alberta 3TM 114 (EPSG:3780). All four accompanying main reports describe CGVD28 survey elevations and HTv2.0. Auxiliary layers can use other systems; photo locations, for example, use WGS84. A single CRS must not be applied indiscriminately to every layer. Gauge-zero elevations and datum consistency must still be checked before comparing live gauge readings with survey elevations.

Drumheller report Table 3, PDF page 13 (printed page 5), reports 444 surveyed sections, while `XS_Planned` contains 435 planned lines. Their meanings and counts differ; individual reconciliation has not been performed. Report publication dates are not survey dates: Red Deer includes 2017 point observations, while Upper Red Deer section lines include 2013 and 2017 records.

The previous blanket statement that section and bank data had not been obtained is now outdated for some study areas. The accurate status is that surveyed section points and bed/bank elevations have been obtained for some reaches; complete coverage, section reconstruction, effective bank-top extraction and hydrometric-station linkage remain unverified. The user has explicitly confirmed receipt of the government reply, data-use permission and download links; the reply and attachments determine the permitted uses.

## Evidence

Layer, field and relationship checks are stored in `manual_gdb_layers.json`, `manual_gdb_field_checks.json` and `manual_relationship_checks.json`. The four databases expose 33 layers/tables. The reader warned that some M dimensions are unsupported; no source database was converted or overwritten.

The linked source reports above were checked at these PDF pages: Drumheller 11 and 13; Drumheller spatial metadata 1–2; Red Deer 8; Upper Red Deer 8; County and Markerville 14. Download links have since been received according to the user. Exact URLs, original download dates and licence terms are not inferred from filenames.

## Source report links

- [Drumheller report](../sources/alberta_flood_surveys/manual/Drumheller/ep-draft-drumheller-survey-base-data-report-mar-2020.pdf): PDF pages 11 and 13.
- [Drumheller spatial metadata](../sources/alberta_flood_surveys/manual/Drumheller/Geodatabase_v104/DrumhellerRHS_Survey_SpatialDataMetadata.pdf): PDF pages 1–2.
- [Red Deer report](<../sources/alberta_flood_surveys/manual/Red Deer/ep-draft-red-deer-survey-base-data-report-mar-2021.pdf>): PDF page 8.
- [Upper Red Deer report](<../sources/alberta_flood_surveys/manual/Upper Red Deer/ep-draft-upper-red-deer-survey-base-data-report-jun-2022.pdf>): PDF page 8.
- [County and Markerville report](<../sources/alberta_flood_surveys/manual/Red Deer County and Markerville/epa-draft-red-deer-county-markerville-main-report-mar-2024.pdf>): PDF page 14.
