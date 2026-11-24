# Cross-Course Decision Brief — Miles Zhang

**Audience:** Hypothetical municipal river-infrastructure reviewer  
**Study Reach:** Red Deer River, Dickson Dam outlet (`05CB007`) to Red Deer gauge `05CC002` (~56.0 km, targets `P01–P05`)  
**Last Updated:** 2026-11-23

---

## Executive Summary of Bounded Recommendations

| Course | Decision Question | Recommendation | Key Supporting Evidence | What Could Change This Decision |
|---|---|---|---|---|
| **AIDA 2154** (CV) | Can 10 m Sentinel-2 segmentation supply reliable river-width evidence for downstream modeling? | **WITHHOLD.** Do not feed CV masks or derived widths into hydrological models or operational decisions. | Weak-label IoU (`85.21%` vs. `84.41%` baseline) is not physical truth; `05CC007` returned **5× zero-width predictions during positive flows** (`0.107–0.780 m³/s`); in the strictly separate 9-site blind manual audit, CNN clear IoU (**`79.26%`**) trailed the static baseline (**`79.80%`**) with a **`44.83%–83.31%`** uncertainty band. | Sub-metre aerial/satellite imagery resolving narrow banks + independent field-surveyed river-width ground truth across seasons and high-flow events. |
| **AIDA 2156** (EDA) | Which station inclusion and quality rules support a defensible historical reach comparison? | **RESTRICT TO EXPLORATORY 4-RIVER HISTORICAL STUDY; REPORT SYLVAN LAKE SEPARATELY; WITHHOLD OPERATIONAL FLOOD USE.** | `P-S1`: strict `Final`-only filter collapses joint timestamps **`95,053 → 0`** (`05CB001`, `05CC007` are 100% Provisional). `P-S2`: requiring Sylvan Lake drops **`48,571` winter river records** while shifting common-day mean `05CC002` flow by only **`+0.123 m³/s`**. ECCC confirmed (`2026-11-17`) most gauges use **assumed datums** (stage ≠ physical depth). | Official ECCC `Final` approval of tributary records, verified gauge-zero datum conversions to geodetic cross-sections, and formal hydraulic validation. |
| **AIDA 2362** (GIS) | Which locations along `Dickson Dam → 05CC002` merit priority physical-section verification? | **PRIORITIZE `P04` AND `P05` FOR FIELD/DATUM REVIEW; KEEP REACH BOUNDED AT `05CC002`; NO FLOOD-HAZARD OR PROPERTY CLAIMS.** | Reducing scope from `96.3 km` to `56.0 km` avoids unsupported extrapolation past `05CC002`. Relaxing along-river section proximity from `<= 25 m` (`P01–P03`) to `<= 50 m` adds **`P04` (`37.87 m`) and `P05` (`40.76 m`)**—the only two targets linked to **actual surveyed cross-sections** (out of 229 sections: `38` surveyed, `191` planned). | New downstream hydrometric validation gauges past `05CC002`, surveyed cross-sections at `P01–P03`, and verified hydraulic connectivity analysis. |

---

## Course-Level Detail Links

- **AIDA 2154:** [`courses/AIDA-2154/docs/cv-width-failure-report.md`](../courses/AIDA-2154/docs/cv-width-failure-report.md) · [`courses/AIDA-2154/docs/independent-manual-check.md`](../courses/AIDA-2154/docs/independent-manual-check.md) · [`courses/AIDA-2154/data-model-card.md`](../courses/AIDA-2154/data-model-card.md)
- **AIDA 2156:** [`courses/AIDA-2156/app-or-report/final-eda-report.md`](../courses/AIDA-2156/app-or-report/final-eda-report.md) · [`courses/AIDA-2156/claim-evidence-index.csv`](../courses/AIDA-2156/claim-evidence-index.csv) · [`courses/AIDA-2156/limitations-and-next-evidence.md`](../courses/AIDA-2156/limitations-and-next-evidence.md)
- **AIDA 2362:** [`courses/AIDA-2362/decision-brief.md`](../courses/AIDA-2362/decision-brief.md) · [`courses/AIDA-2362/outputs/section-proximity-sensitivity.md`](../courses/AIDA-2362/outputs/section-proximity-sensitivity.md)
