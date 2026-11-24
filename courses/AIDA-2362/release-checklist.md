# GIS release evidence checklist

Updated 2026-11-23 against [the course brief, current D2L schedule, and Formative Feedback 1](README.md). **Current disposition: `AIDA2362_FinalProject_Miles_Zhang.zip` is assembled and passed clean-extraction QGIS 3.44.14 verification after Alberta EPA confirmed public-information use with attribution on 2026-11-23.** Remaining actions: classmate peer review (two projects, Dec 1–11), Week 15 live QGIS demonstration, and D2L upload by Dec 14.

| Required evidence | Current status and next evidence |
|---|---|
| Bounded decision, scale, uncertainty and no-go conditions | [Decision brief](decision-brief.md) and [regional map interpretation](outputs/map-text-equivalent.md) distinguish monitoring review from flood decisions, state the mapped reach, note the 2026-11-17 ECCC assumed-datum reply and explain scale limits. |
| QGIS project and permitted inputs | [Project](project/dickson_to_joffre.qgz) packaged into `AIDA2362_FinalProject_Miles_Zhang.zip` and verified by clean extraction into an empty folder with all eight relative local vector layers ([zip-extraction-validation.json](outputs/zip-extraction-validation.json)). |
| Sources, licences, metadata, CRS, units, dates and limits | [Per-layer inventory](data/layer-inventory.md) records NRCan (OGL-Canada), ECCC (Open/End-use), OSM attribution, and Alberta EPA's 2026-11-23 confirmation permitting submission use with EPA attribution (`Protected A` email and raw GDBs excluded). |
| Processing chain and derived layers | See the [QGIS audit/demo steps](outputs/qgis-reopen-and-demo.md) and [exact 25/50 m procedure](outputs/section-proximity-sensitivity.md). Preserve the selected chain and lineage. |
| CRS/transformation, area of use, units, geometry, IDs/cardinality, missingness and counts | [Current QGIS results](outputs/current-qgis-validation.json) and [ZIP extraction audit](outputs/zip-extraction-validation.json): 246 valid feature geometries across all eight relative vector layers, 0 invalid geometries, IDs, fields, EPSG:3400 transforms, 145 section crossings, and five target links. |
| Baseline and changed-variable sensitivity | [Fixed-target comparison](outputs/section-proximity-sensitivity.md): 25 m vs 50 m gives 3 vs 5, adding P04 and P05 (surveyed section associations), verified inside the clean-extracted ZIP. |
| Accessible map and exact text/table equivalent | [Non-colour decision and station summary](outputs/map-text-equivalent.md) and [246-feature table](outputs/map-feature-equivalent.csv) accompany the current PDF. |
| Privacy, bias, community impacts and Indigenous authority | [Governance review](governance-review.md) updated 2026-11-23; private correspondence and raw GDBs excluded; distinctions-based Indigenous authority boundary preserved. |
| AI declaration, peer review and response | [AI declaration](ai-use-declaration.md) finalized in first person on 2026-11-22; actual classmate peer-review/response (two projects, Dec 1–11) remains pending. |
| Manifest, release checklist, README and extracted-package test | [Verified SHA-256 manifest](submission-manifest.txt) and [clean ZIP extraction audit](outputs/zip-extraction-validation.json) completed on `data/processed/gis_release_20261123/AIDA2362_FinalProject_Miles_Zhang.zip`. |
| Recommendation, presentation and D2L handoff | Classroom review only. Demonstrate [the actual QGIS workflow](outputs/qgis-reopen-and-demo.md) from the verified ZIP in Week 15, complete peer review Dec 1–11, and upload to D2L by Dec 14 at 11:59 p.m. |

The [shared gap register](../../shared-resources/submission-readiness.md) preserves an earlier course-level snapshot. Use this checklist and the current D2L assignment for present status.
