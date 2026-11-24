# Coverage and recorded verification of retained imagery

This post-acquisition snapshot contains 2,749 new plus 775 historical images, total 3,524. Two needs_review requests have no confirmed imagery and are separately listed in non_downloaded_requests.csv. They are not material, and their cost or labels is not inferred.

## Groups

- Clear-proxy review: 1,426 = 280 historical + 1,146 new.
- Challenging-region review: 2,098 = 495 historical + 1,603 new.
- The downloader's strict new subset was 1,149. Moving previews 8/9/13 to challenge review explains the difference of three; none was deleted or lost. Recomputed pixel statistics agree with acquisition records.
- All eight previous holds remain retained. Clear-proxy does not mean visually confirmed, and challenge-review does not mean all regions are annotatable.

## Date, season and year coverage

all_materials.csv sensing dates span 2016-05-02 to 2026-11-04, 348 dates. Dates are not independent samples: same-day grids, adjacent overpasses and overlapping locations still require unified event/leakage groups.

- New images: 2,749 over 249 dates; spring 390, summer 1490, autumn 869, winter 0.
- Historical images: 775 over 99 dates, 2025-05-05 to 2026-10-30; spring 134, summer 313, autumn 242, winter 86.
- Combined: spring 524, summer 1803, autumn 1111, winter 86.
- Clear-proxy: 279 dates; spring 136, summer 670, autumn 620, winter 0.
- Challenge: 343 dates; spring 388, summer 1133, autumn 491, winter 86.

Groups may contain different images from the same date, so date counts cannot be summed. Northern calendar seasons: March-May spring, June-August summer, September-November autumn, December-February winter. Retained winter/ice material supports suitability/failure review, not a claim of suitability for unfrozen-water analysis.

Year counts: 2016=109; 2017=108; 2018=341; 2019=252; 2020=279; 2021=447; 2022=425; 2023=404; 2024=356; 2025=438; 2026=365.

## Recorded checks, not a new rerun

All 3,524 identities were unique and image SHA-256 checks passed. All review masks were reopened and checked for EPSG:32612, 10 m spacing, one band, allowed codes and review-use tags. Class counts matched region_quality_inventory.csv, and extent counts matched the inventory. Recomputed clarity, coverage and ice fractions matched historical screening/acquisition. Neither unknown request had image.tif or userdata.json, so quality was not read or fabricated. Final original-manifest hashes matched the input snapshot. Nine rules/missing-file regression tests and the then-required Chinese UTF-8 check passed.

Historical snapshots and originals remain identifiable. This stage trained no model, created no water truth and did not label cloud/shadow/invalid pixels as non-water. Costs and uncertain execution outcomes belong to the separate acquisition audit, not this snapshot.
