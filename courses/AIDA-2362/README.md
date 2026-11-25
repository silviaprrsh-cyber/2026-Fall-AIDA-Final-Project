# AIDA 2362 Final Professional Project — GIS Decision Package

**Current D2L schedule:** December 14, 2026, 11:59 p.m. Week 15 live QGIS presentation and peer review. Submit one complete QGIS ZIP and record the clean-extraction reopening test.

**Individual assessment · 25% of the AIDA 2362 course grade**

## Quick-Start Offline Reproduction (Reviewer & Self-Check Guide)

> **Everything needed to open and verify the portable QGIS project is already tracked in this repository** inside [`D2L_SUBMISSION_READY/AIDA2362_FinalProject_Miles_Zhang.zip`](../../D2L_SUBMISSION_READY/AIDA2362_FinalProject_Miles_Zhang.zip) (~9.1 MB; bundles the relative-path QGIS project `project/dickson_to_joffre.qgz`, all 8 local GeoJSON layers / 246 valid features, all 3 scope comparison PDFs, and validation scripts). **No raw government geodatabases, online basemap, or PostgreSQL are required.**

```powershell
# 1. From the repository root, extract the tracked standalone GIS package
Expand-Archive -Path D2L_SUBMISSION_READY\AIDA2362_FinalProject_Miles_Zhang.zip -DestinationPath gis_replay_unpack -Force
```

2. **Open offline in QGIS 3.44.14 LTR**: double-click `gis_replay_unpack\project\dickson_to_joffre.qgz` (active ~56.0 km Dickson Dam to `05CC002` reach; 8 local relative vector layers, 2 print layouts).
3. **Reproduce the `25 m` vs. `50 m` sensitivity live in QGIS**: select layer `prediction_points` → **Select by Expression**:
   - Baseline (`<= 25 m`, selects 3 targets `P01–P03`): `abs("nearest_section_along_river_offset_m") <= 25`
   - Sensitivity (`<= 50 m`, selects 5 targets `P01–P05`, adding surveyed `P04`/`P05`): `abs("nearest_section_along_river_offset_m") <= 50`
4. **Optional headless QGIS package check** (from `gis_replay_unpack` with QGIS 3.44.14 installed):
   ```powershell
   "C:\Program Files\QGIS 3.44.14\bin\python-qgis-ltr.bat" src\gis_tools\validate_course_package.py --check-only
   ```

- **Expected verified result:** 8/8 local vector layers load with 0 broken links, 246 features pass GEOS validity (`0` invalid geometries), and `<= 25 m` (`3/5`) vs. `<= 50 m` (`5/5`) highlights `P04`/`P05` as the sole surveyed targets.
- **Optional companion Hydro-GIS viewer (Check #25):** QGIS 3.44.14 remains the required primary tool for AIDA 2362. As an optional read-only visualization companion, the Windows Hydro-GIS receiver ([`courses/AIDA-2156/deployment/dist/RedDeerRiver.exe`](../AIDA-2156/deployment/dist/RedDeerRiver.exe); guide in [`client/README.md`](../AIDA-2156/deployment/client/README.md)) embeds all 8 active AIDA 2362 GeoJSON layers (246 features) alongside the `<= 25 m` vs. `<= 50 m` sensitivity toggle and NRCan OGL-Canada offline basemap without replacing the QGIS evidence chain.
- **Key files to inspect:** [Decision Brief](decision-brief.md) · [25 m vs. 50 m Sensitivity](outputs/section-proximity-sensitivity.md) · [Active 56 km Map PDF](outputs/Overhead%20view.pdf) · [Layer Inventory](data/layer-inventory.csv).

---

## Purpose and tool boundary

Build one fictional facilities-maintenance spatial decision package around a bounded question. Name the decision-maker, action, unit, geographic extent, time period, map scale, and consequences of error. QGIS is the core tool. Python may extend the work, but it cannot replace the QGIS evidence chain. Do not use real sensitive locations or claim operational readiness. Paid services, specialized hardware, mandatory Docker, or deployment are not required.

## How to approach the work

1. **Set the spatial decision.** Define user/action, features and area/time included, map scale, decision threshold if appropriate, uncertainty, and no-go conditions.
2. **Check every layer.** Record source, licence/permission, date/version, CRS, coordinate units, scale, fields, and limitations. Keep data within the approved fictional/supplied boundary.
3. **Build a reproducible QGIS chain.** Use documented processing history/model and/or code. Use stable identifiers and test joins/cardinality, geometry validity, missingness, CRS transformations, units, and output counts.
4. **Compare a baseline and changed setting.** Preserve a simple baseline and at least one changed-variable sensitivity test. Report which locations/IDs/counts move and whether the decision changes.
5. **Communicate the result accessibly.** Provide a readable decision map and an exact text/table equivalent; explain symbology, scale, uncertainty, and who should use the result.
6. **Review responsibility and release.** Address privacy, bias, community impacts, distinctions-based Indigenous authority, data licensing, limitations, implementation conditions, and what evidence would change the recommendation.
7. **Prepare the portable handoff.** Use relative paths, verify the project opens after extraction, and document the clean run and release decision.

## Required final deliverables

The course final submission is a complete, portable QGIS project package through D2L. Include:

- QGIS project file with relative/portable paths and all permitted required inputs;
- data inventory with sources, licences/permissions, metadata, CRS, units, dates, and limits;
- derived layers and a documented Processing history/model and/or code;
- checks for CRS/transformation, area of use, units, geometry validity, stable IDs/cardinality, missingness, output counts, and a clean run;
- a baseline plus at least one changed-variable sensitivity test, including changed IDs/counts and decision impact;
- accessible decision map and exact text/table equivalent;
- bounded decision brief with uncertainty, scale, limitations, implementation and no-go conditions, and next evidence;
- privacy, bias, community-impact and Indigenous-authority review; manifest, release checklist, README, and AI declaration.

The published 25-point rubric covers decision context (3), authorized data/provenance/governance (3), reproducible QGIS workflow/validation (5), spatial analysis/sensitivity (5), accessible map/equivalent (3), uncertainty/privacy/community/authority (3), and recommendation/ZIP/AI/presentation (3). A successful processing run by itself is not sufficient release evidence.

## How progress is checked

At each checkpoint, record the evidence path and the next action in `project-progress.md`. The gates are formative and add no separate weight. Your work should show visible steps from a scoped proposal to validated spatial evidence and a portable package.

- **Week 6 — proposal/scope:** decision, unit, extent/time, scale, source permission, feasibility.
- **Week 8 — evidence plan:** layer inventory, metadata/CRS plan, processing chain, baseline and validation plan.
- **Week 10 — prototype:** working QGIS project with one initial derived layer and a reproducible process note.
- **Week 12 — validation:** geometry/CRS/ID/output checks, sensitivity comparison, limitations and corrected errors.
- **Week 14 — release candidate:** portable project, map and equivalent, metadata, privacy/governance review, peer feedback and response.
- **Week 15 — release readiness:** clean extracted package, manifest, recommendation, presentation and final handoff. Finish all work by end Week 15; there is no Week 16 project or final-exam activity.

## Submission and presentation

Submit the complete GIS ZIP through AIDA 2362 D2L. A repository link is optional for a GIS-only project and never replaces the ZIP upload. In Week 15, demonstrate the working QGIS project from the clean extraction or the same verified copy as directed.

## Shared project dates and class activities

Final submission is due **December 14, 2026 at 11:59 p.m.** The presentation and in-class peer review are in Week 15, according to the D2L schedule. Record genuine peer feedback and your response.

---

## Project implementation and reproduction

The course requirements above are preserved. The following section describes the implemented Red Deer River project and its current limitations.

## AIDA 2362 — GIS

**Standalone course report (Word):** [English](docs/gis-project-report.docx) · [中文版](docs/gis-project-reportCN.docx)

Purpose: map monitoring coverage and requested estimation locations from Dickson Dam to validation station 05CC002. QGIS is the core tool.

Code: `src/`; survey, river-network and derived spatial inputs: `data/`. The working QGIS project is `project/dickson_to_joffre.qgz`; the reviewed map is `outputs/Overhead view.pdf`. Hydrometric/weather inputs owned by AIDA 2156 are referenced through the shared resolver. Source metadata and CRS checks remain in data records; permissions do not imply unrestricted redistribution.

Open the project in QGIS. Blue/yellow indicate archived observation availability, red indicates prediction targets, and green areas are schematic weather associations, not watershed boundaries. The [25 m vs 50 m section-proximity sensitivity](outputs/section-proximity-sensitivity.md), [per-layer inventory](data/layer-inventory.md), [exact map text/table equivalents](outputs/map-text-equivalent.md), [246-feature QGIS validation](outputs/current-qgis-validation.json), [governance review](governance-review.md), and [clean-extracted ZIP verification](outputs/zip-extraction-validation.json) are complete (Alberta EPA confirmed public-information submission use with attribution on 2026-11-23); remaining items are classmate peer review (two projects, Dec 1–11), Week 15 live QGIS demonstration, and D2L upload. AI assisted code organization and documentation; the map alone does not establish valid flood estimates.

### Three map extents and the reasons for reducing scope

The [bilingual map index](outputs/README.md) explains the original full project (~724 km and basin), the first Dickson–Joffre reduction (~96.3 km), and the current Dickson–05CC002 reach (~56.0 km). It links the presentation PDFs, explains inventory and datum limits, and distinguishes historical GIS P06 from the V4 terminal output. The maps support study-design review, not flood risk or operational prediction.

### Current map inventory and use

Sylvan Creek is shown as ungauged mapped tributary geometry only. Sylvan Lake (05CC003) is a lake-level reference, not an outlet-discharge input or validation station. The historical Sylvan Creek gauge (05CC004) is archived and not shown as an active observation point; its published coordinate was not moved to the mapped creek. The map supports classroom coverage review, not live monitoring, flood warnings, property-level risk or emergency decisions.

The 2026-11-05 check confirms 5 prediction points (P01–P05), 4 river gauges (05CB007, 05CB001, 05CC007, 05CC002), 2 historical/lake references (05CC003, 05CC012), 1 weather station, 229 section lines and 4 river features. Blue/yellow status refers to the archived availability review, not a fresh station query. The centerline endpoint is projected from the official 05CC002 coordinate, about 69 m away; the station coordinate itself is unchanged.

Open [the working project](project/dickson_to_joffre.qgz) in QGIS 3.44.14. Both `Simple OSM overview` and `Overhead view` layouts remain. OSM tiles need network access. The [presentation PDF](outputs/Overhead%20view.pdf) and [PNG preview](project/map_overview.png) were updated and visually checked on 2026-11-08, showing P01–P05 and endpoint 05CC002. The [prior Joffre PDF](data/processed/scope_history/Overhead_view_Joffre.pdf) is retained separately.

Reproduce the current map by opening `project/dickson_to_joffre.qgz` in QGIS, or run `src/gis_tools/export_scope_layout.py` with QGIS python-qgis-ltr.bat to export the saved layout. `build_prediction_points.py` regenerates P01-P05 from current configuration. Five retired legacy builders, one-time clipping and layout-refresh scripts and their notes are archived in `data/processed/scope_history/retired_gis_tools_20261108.zip`. Current reproduction requires the supplied QGIS project and layers; this is not a new one-command GIS rebuild from raw sources. Previous scope backups and validation reports remain available.

### Project modification history — 2026-11-04 (verified 2026-11-05)

The active movetest reach now ends at Red Deer station 05CC002. Retain P01–P05; remove P06–P11 and downstream Blindman/Waskasoo map inputs. The selected project data provide no comparable downstream observation constraint to validate the continuation to P11. This reduction limits unsupported extrapolation; it does not establish accuracy at retained targets. The filename `dickson_to_joffre.qgz` is retained for compatibility, but its layers and displayed endpoint now use 05CC002.

Source archives, previous model results and satellite acquisitions are retained. At the 2026-11-04 scope change, the map exports still showed the prior Joffre extent. The 2026-11-08 [presentation PDF](outputs/Overhead%20view.pdf) and [PNG preview](project/map_overview.png) show the current 05CC002 scope; the [prior Joffre PDF](data/processed/scope_history/Overhead_view_Joffre.pdf) and earlier checks remain historical evidence. Current GIS checks are `courses/AIDA-2362/data/reports/scope_05CC002.json` and `qgis_scope_05CC002.json`. The model already ends at 05CC002: its M06 link from P05 to the validation station remains; M06 is not prediction point P06. This map update does not retrain the model or replace PostgreSQL snapshots.

## Submission evidence organization — 2026-11-08

Keep the instructor brief above as the requirement. See [the course-by-course gap register](../../shared-resources/submission-readiness.md) and [scope matrix](../../scope-matrix.md) for the current evidence and unfinished work. This folder is a development workspace, not a final clean submission package. Use the required course-specific D2L package; do not bundle environments, credentials, scratch files or unrelated historical archives. Preserve permitted inputs needed to reproduce the selected result.

## Current technical readiness and Week 15 QGIS demonstration

See the [active layer inventory](data/layer-inventory.md), [current QGIS validation](outputs/current-qgis-validation.json), [clean-extracted ZIP audit](outputs/zip-extraction-validation.json), [map text/table equivalent](outputs/map-text-equivalent.md), and [actual QGIS demo steps](outputs/qgis-reopen-and-demo.md). On 2026-11-23, Alberta Environment and Protected Areas (EPA) confirmed in writing that the provided survey data is publicly available information and may be used in the course submission with EPA credit (private correspondence and original GDBs remain excluded). The portable submission archive `AIDA2362_FinalProject_Miles_Zhang.zip` (built under Git-ignored `data/processed/gis_release_20261123/`) passed clean extraction and QGIS 3.44.14 reopening with all eight local relative vector layers, 246 valid features, both layouts, and matching 25/50 m selections (`3/5` to `5/5`). See [submission-manifest.txt](submission-manifest.txt) for exact member SHA-256 hashes.

[Course Word reports and evidence index](docs/README.md). The [active layer CSV](data/layer-inventory.csv) and [246-feature table](outputs/map-feature-equivalent.csv) complement the inventory and map explanations.
