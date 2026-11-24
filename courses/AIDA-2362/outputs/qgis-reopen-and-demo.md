# Current QGIS validation and Week 15 demonstration

This is local D2L preparation, not a submission receipt. The exact fingerprinted inputs are in [the local preflight manifest](../submission-manifest.txt). The [QGIS audit](current-qgis-validation.json) used an isolated copy of the saved project and eight permitted-for-local-use vector layers with their relative hierarchy. It reopened in QGIS 3.44.14 and ran the checks below. No release ZIP was assembled, extracted, or uploaded; this test is not the course's final extraction check.

## Reproduce the local technical check

From the repository root in PowerShell, use the installed matching QGIS Python launcher:

```powershell
& 'C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat' -B courses/AIDA-2362/src/gis_tools/validate_course_package.py --check-only
```

Omit `--check-only` to regenerate the audit JSON and the per-feature CSV. The temporary QGIS profile and copied files are removed after the run; the original project, layers and map are not saved over. The OSM tiles were not rendered or fetched. Running this uses QGIS and its bundled GDAL/GEOS/PROJ, not the separate project virtual environment.

| Check | Current local result |
|---|---|
| Relative-path reopen | Both saved layouts and all eight vector sources reopened from the independent copy; the saved project had no absolute vector file dependency. The ninth layer is the optional network-dependent OSM basemap. |
| Geometry, fields, IDs and counts | 246 vector features in eight layers, with zero empty or GEOS-invalid geometries, no wrong geometry types, no blank or duplicate layer IDs, and no missing required decision fields. Optional null counts are retained by field. |
| CRS/units and spatial join | EPSG:4326 vector storage, EPSG:3857 map display, EPSG:3400 metre-based route measurement; all vertices checked against the appropriate recorded Alberta areas of use. All five section links matched the recomputed nearest point intersections. |
| Documented exceptions | Proposed lines have no row-level survey date; 05CC012 lacks an optional map label/display role; P-series water-level/flow/risk placeholders are intentionally blank. Of 146 mapped mainstem section lines, 145 yield usable centerline point intersections; RDR087 does not. None of the section profiles or bank elevation pairs are marked verified. |
| Sensitivity reproducibility | In QGIS, 25 m selected P01–P03; 50 m selected P01–P05. Only P04 and P05 entered. The selected IDs match the exact CSV. |

## Demonstrate in actual QGIS

1. Open [the active QGIS project](../project/dickson_to_joffre.qgz). The legacy filename says Joffre, but the live reach in the project stops at 05CC002. Locate the Dickson outlet, the 05CC002 station marker, and the saved **Overhead view**. If the basemap is inaccessible, turn its visibility off without saving and use the local vector layers.
2. Show the **Prediction targets – P01 to P05** attribute table. Point out the stable target ID, nearest section ID and signed along-river offset; positive means the section is downstream of the target. Use **Select by Expression**:

   ```qgis
   abs("nearest_section_along_river_offset_m") <= 25
   ```

3. Record P01, P02 and P03. Make a new selection with 50 instead of 25. Confirm that only P04/R11 (47.03 m) and P05/R19 (32.25 m) enter. Use the [exact non-colour table](map-text-equivalent.md) to state why these two surveyed records are worth reviewing first. Compare the surveyed vs proposed line layers and say why P01's zero offset is not a verified profile.
4. Close without saving selection/visibility changes. Explain why the map does not verify datum transfer, hydraulic behaviour or real flood decisions. The original PDF and the table are a visual/accessibility fallback, not a replacement for the required live QGIS demonstration.

## Release ZIP assembly and clean-extraction verification (2026-11-23)

On 2026-11-23, Alberta Environment and Protected Areas (EPA) confirmed in writing that the provided Red Deer River survey data is publicly available information and may be used in this course submission provided EPA is credited (private email correspondence and original raw geodatabases remain excluded).

To rebuild `courses/AIDA-2362/data/processed/gis_release_20261123/AIDA2362_FinalProject_Miles_Zhang.zip` and verify clean extraction in QGIS 3.44.14:

```powershell
& 'C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat' -B courses/AIDA-2362/src/gis_tools/build_and_verify_release_zip.py
```

The clean-extraction audit is recorded in [zip-extraction-validation.json](zip-extraction-validation.json) and member SHA-256 hashes are in [submission-manifest.txt](../submission-manifest.txt). Actual in-class demonstration (Week 15), classmate peer review (two projects, Dec 1–11), and D2L upload (due Dec 14 at 11:59 p.m.) remain tracked in [release-checklist.md](../release-checklist.md).
