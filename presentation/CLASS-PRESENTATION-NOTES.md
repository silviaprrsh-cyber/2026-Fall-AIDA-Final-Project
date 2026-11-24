# Red Deer River Classroom Presenter Notes (Three Standalone Course Decks)

[简体中文](CLASS-PRESENTATION-NOTESCN.md) · [Deck Index](README.md) · [Demo Plan](../shared-resources/Miles-demo-plan.md) · [Synthetic Fallback](SYNTHETIC-DEMO-FALLBACK.md)

Updated **2026-11-23** to match the three standalone course PowerPoint decks, the 2026-11-23 AIDA 2154 9-site blind manual audit, the 2026-11-17 ECCC assumed-datum confirmation, and the 2026-11-23 Alberta EPA attribution clearance & clean-extracted ZIPs. Presentations and two classmate peer reviews run **December 1–11, 2026** (confirm individual course slots in D2L).

---

## Course 1 — AIDA 2154 (Computer Vision) · Weeks 13–14

**Deck:** [`AIDA2154-CV-Presentation.pptx`](AIDA2154-CV-Presentation.pptx) (**9 slides**)  
**Files to keep open before speaking:**
- [`test_examples.png`](../courses/AIDA-2154/data/processed/point_cnn_20261113/test_examples.png) & [`result.json`](../courses/AIDA-2154/data/processed/point_cnn_20261113/result.json)
- [`independent_manual_comparison.png`](../courses/AIDA-2154/outputs/independent_manual_eval_20261123/independent_manual_comparison.png) & [`independent-manual-check.md`](../courses/AIDA-2154/docs/independent-manual-check.md)
- Optional 10-second live CPU replay (offline, zero network/DB):
  ```powershell
  python -B run.py -m cv_tools.replay_frozen_cnn --output cv_demo_check
  python -B run.py -m cv_tools.test_release_replay
  ```
  *(Do NOT substitute the Windows river viewer for the CV demonstration.)*

### Slide-by-Slide Cue (`AIDA2154-CV-Presentation.pptx`)

- **Slide 1 · Title (0:20):** “My AIDA 2154 question is whether native 10-metre Sentinel-2 imagery can supply reliable river-width evidence across nine Red Deer River sites from Dickson Dam to gauge 05CC002. My conclusion is a documented negative result: **withhold**.”
- **Slide 2 · One River, Three Contributions (0:30):** “GIS defines the 56 km reach and nine target points, EDA audits historical flow records, and CV tests satellite water extraction independently—no CV width entered the hydrological model.”
- **Slide 3 · Weak-Label Agreement ≠ Physical Width (0:45):** “I built a leak-free date-grouped 708/169/132 split with a 7-day boundary gap and compared a 6,113-parameter CPU CNN against a static training-mask baseline. The CNN scored 85.21% IoU vs. 84.41% baseline—but those are automatic weak masks, not field-measured river widths.”
- **Slide 4 · Held-Out Segmentation Panel (0:45):** Point to `05CB001` and `05CC007` on the left: “These are the first held-out test scenes per site, not cherry-picked. At 10 m resolution, narrow tributaries are only 1–2 pixels wide and fragment into isolated dots.”
- **Slide 5 · 500 m GIS Transects & Indirect Widths (0:40):** “Using frozen 0.5-threshold masks across centre and ±50 m transects, 124 of 132 scenes had complete widths and 70 station scenes matched ECCC flow within 300 seconds. P01–P05 have no local gauges and no winter test scenes exist.”
- **Slide 6 · Concrete Failure Evidence (0:50):** Point to `05CC007`: “Behind the 85.21% headline, Medicine River (`05CC007`) returned **zero predicted width five times** while observed discharge was positive (`0.107–0.780 m³/s`), and P04 width error was worse than the static baseline.”
- **Slide 7 · Supplementary Blind Manual Audit (1:05 — Key Feedback 1 Response):** “Separately from the 132-image evaluation, I ran a strictly blind manual check on nine predeclared chronological-median summer test crops—one per site, RGB and NIR only, zero model or mask visibility, labeling clear land, clear water, and uncertain mixed bank pixels. On 30,342 clear pixels, the CNN scored **79.26% IoU**—actually **below** the static baseline (**79.80%**). Uncertainty across 3,147 mixed bank pixels (45.2% of the channel zone) spans **44.83% to 83.31%**, exposing narrow recall collapse at `05CC007` (23.5%), missed braided side channels at `P03` (~41%), and off-channel false positives at `P04` (87.1% vs. 98.7% baseline).”
- **Slide 8 · Bounded Decision & Clean Replay (0:45):** “Decision: **WITHHOLD** all CV masks and widths from downstream modeling and defer physical widths to field surveys. The clean D2L package (`AIDA2154_CV_D2L_ready_20261123.zip`, 60 files) passed fresh-extraction verification, 132-image CPU replay, 14 portable tests, and blind-audit re-scoring.”
- **Slide 9 · Attribution, Acknowledgements & Q&A:** Leave up during questions — explicitly credits ESA/Copernicus (`Contains modified Copernicus Sentinel data [2016–2026]`), ECCC, NRCan, Alberta EPA, Red Deer Polytechnic / Instructor Jomis John, and AI verification disclosure.

---

## Course 2 — AIDA 2156 (Exploratory Data Analysis & Statistics) · Weeks 13–14

**Deck:** [`AIDA2156-EDA-Presentation.pptx`](AIDA2156-EDA-Presentation.pptx) (**10 slides**)  
**Files to keep open before speaking:**
- [`final-eda-report.md`](../courses/AIDA-2156/app-or-report/final-eda-report.md) & [`claim-evidence-index.csv`](../courses/AIDA-2156/claim-evidence-index.csv)
- [`analysis.py`](../courses/AIDA-2156/analysis/analysis.py) & [`sensitivity-results.csv`](../courses/AIDA-2156/output/final_eda/sensitivity-results.csv)
- Optional 1-second live standard-library replay (zero third-party packages):
  ```powershell
  python -B -E -S courses/AIDA-2156/analysis/make_eda_figures.py
  python -B -E -S courses/AIDA-2156/analysis/tests_or_assertions.py
  ```

### Slide-by-Slide Cue (`AIDA2156-EDA-Presentation.pptx`)

- **Slide 1 · Title (0:20):** “My AIDA 2156 study asks which frozen 5-minute ECCC historical observations (May 2025 – Nov 2026 UTC) support a defensible reach comparison from Dickson Dam to `05CC002`. This is a historical evidence-adequacy study, not an operational flood forecast.”
- **Slide 2 · Shared Context & Firewall (0:25):** “Formal EDA runs purely on five frozen station tables using Python 3.13 standard library only—kept strictly separate from CV and from contextual V4 modeling.”
- **Slide 3 · Unit, Denominators & Core Decision (0:45):** “The unit is station × UTC timestamp × parameter across `158,112` inferred 5-minute slots per series, explicitly separating valid, missing, rejected, and off-grid rows. Four river gauges supply discharge and stage; Sylvan Lake supplies level only.”
- **Slide 4 · Figure 1 — Monthly Coverage (0:40):** Point to the winter blank band: “River gauges hold 97.3%–99.7% coverage, while Sylvan Lake drops to 0% across winter (`66.9%` overall), creating a major coverage tradeoff.”
- **Slide 5 · Figure 2 — Distributions & Skew (0:35):** “All four river gauges are strongly right-skewed—Red Deer median is `22.3 m³/s` versus mean `36.0` and max `284.0`—so medians and percentiles must sit beside means.”
- **Slide 6 · Figure 3 — Lagged Correlations & Serial Dependence (0:45):** “Because 5-minute rows are serially correlated, treating rows as independent would understate uncertainty. I resampled **7-day UTC blocks** (78–79 blocks, 1,000 resamples). Dickson peaks at 12 h (`0.953`), only `0.012` above 0 h, and Medicine's interval is wide (`0.253–0.815`)—covariation does not prove flood transit time.”
- **Slide 7 · Figure 4 — Two Formal Sensitivities (1:00 — Core Decision Slide):** “**P-S1** requires explicit `Final` approval across all 9 series: joint rows collapse from **95,053 to 0** because both tributaries are 100% Provisional, restricting us to exploratory historical analysis. **P-S2** compares 4 river gauges (`144,289` rows) against requiring Sylvan Lake (`95,053` rows): requiring the lake discards **48,571 winter river records**, while shifting the 361-day common mean by only **+0.123 m³/s** (`95% CI [-0.002, +0.315]`). Decision: keep 4 river gauges as primary and report Sylvan Lake separately.”
- **Slide 8 · Optional Context — V4 Historical Test (0:40):** “Kept strictly separate from formal EDA: V4 achieved 10.31 cm average MAE on 27,256 historical rows, yet missed the June crest timing by **57 h 20 min** and underestimated peak depth by `9.21 cm`—reinforcing why average error cannot justify operational flood use.” *(If showing the optional local synthetic viewer, ensure the **DEMO** banner is visible first; otherwise use [`SYNTHETIC-DEMO-FALLBACK.md`](SYNTHETIC-DEMO-FALLBACK.md).)*
- **Slide 9 · Decision, ECCC Datum Limit & Clean Package (0:45):** “On **2026-11-17**, ECCC confirmed most gauges operate in an **assumed datum**, so gauge stage is not verified physical water depth. Release for exploratory course review only; **withhold all flood-warning or safety decisions**. Clean ZIP (`AIDA2156_EDA_D2L_ready_20261123.zip`, 3.72 MB) replayed 7 tables + 4 SVGs byte-for-byte with `-B -E -S`.”
- **Slide 10 · Attribution, Acknowledgements & Q&A:** Leave up during questions — credits ECCC Water Survey of Canada, MSC GeoMet, ECCC Hydrological Services (AB) for the datum clarification, RDP / Jomis John, and AI verification disclosure.

---

## Course 3 — AIDA 2362 (Geographic Information Systems) · Week 15 (Live QGIS Required)

**Deck:** [`AIDA2362-GIS-Presentation.pptx`](AIDA2362-GIS-Presentation.pptx) (**8 slides** — slides introduce scope; **live QGIS is mandatory**)  
**Files to open before speaking:**
- **Real QGIS 3.44.14** opened from the clean-extracted portable ZIP (`AIDA2362_FinalProject_Miles_Zhang.zip` → `project/dickson_to_joffre.qgz`)
- [`Overhead view.pdf`](../courses/AIDA-2362/outputs/Overhead%20view.pdf) & [`map-feature-equivalent.csv`](../courses/AIDA-2362/outputs/map-feature-equivalent.csv) (`246` features)

### Slide-by-Slide & Live QGIS Cue (`AIDA2362-GIS-Presentation.pptx`)

- **Slide 1 · Title (0:20):** “My AIDA 2362 project maps where monitoring stations and Alberta flood-survey cross-sections support review along the 56.0 km Dickson Dam to `05CC002` reach.”
- **Slide 2 · Headline Finding (0:30):** “A nearby cross-section is not automatically a field-surveyed section—out of 229 sections in the active reach, only 38 are surveyed and 191 are planned.”
- **Slides 3–5 · Scope Reduction Story (`724 km → 96.3 km → 56.0 km`) (1:00):** “I narrowed from the 724 km full basin to 96.3 km (Joffre, `P01–P11`), and finally stopped at Red Deer gauge `05CC002` (`56.0 km`, `P01–P05`) because no comparable validation gauge constrained downstream extrapolation past `05CC002`. Historical snapshots remain preserved separately.”
- **Slide 6 → SWITCH TO LIVE QGIS 3.44.14 (2:00 — Core Live Demo):**
  1. Show all **8 local relative vector layers** loaded cleanly inside the extracted ZIP (`246` valid GEOS features, `0` invalid geometries).
  2. Explain CRS roles: `EPSG:4326` (storage), `EPSG:3857` (web display), **`EPSG:3400`** (Alberta 10-TM metric along-river distance calculations), and `EPSG:3780` / CGVD28 (original survey vertical datum—not tied to ECCC assumed gauge zeros).
  3. Select `prediction_points` → **Select by Expression**:
     - Run `abs("nearest_section_along_river_offset_m") <= 25` → highlights **`P01, P02, P03`** (`3/5`, all linked to planned sections).
     - Change to `abs("nearest_section_along_river_offset_m") <= 50` → highlights **`P01–P05`** (`5/5`), adding **`P04` (`37.87 m`) and `P05` (`40.76 m`)**—open the Attribute Table to show these are the **only two targets linked to actual surveyed sections**.
  4. Point to [`map-feature-equivalent.csv`](../courses/AIDA-2362/outputs/map-feature-equivalent.csv) as the accessible 246-row table equivalent of [`Overhead view.pdf`](../courses/AIDA-2362/outputs/Overhead%20view.pdf).
- **Slide 7 · Governance, EPA Clearance & Decision (0:45):** “On **2026-11-23**, Alberta EPA confirmed in writing that the provided survey data is publicly available information usable in submission with EPA credit (`Protected A` emails and raw GDBs remain excluded). Decision: prioritize **`P04` and `P05`** for physical survey/datum verification; keep reach bounded at `05CC002`; **no flood-hazard or property decisions supported**.”
- **Slide 8 · Attribution, Acknowledgements & Q&A:** Leave up during questions — explicitly credits **Government of Alberta (EPA)** per 2026-11-23 written clearance, **NRCan**, **ECCC**, **OpenStreetMap contributors**, **QGIS 3.44.14 LTR**, RDP / Jomis John, and AI verification disclosure.

---

## Defence Q&A (Updated for All 3 Courses)

- **Why did the CNN score LOWER than the static baseline on your blind manual check (`79.26%` vs. `79.80%`)?** On automatic weak masks the CNN got a tiny `+0.80` pp edge by mimicking the automatic mask rules. On independent blind clear pixels, off-channel false positives at `P04` (`FP = 94`, dropping CNN to `87.1%` vs. `98.7%` baseline) and `P05` (`FP = 53`), combined with narrow recall collapse at `05CC007` (`23.5%`), erased that gain—confirming the **WITHHOLD** decision.
- **How did you keep the 9-site blind manual check independent and document uncertainty?** Samples were chosen programmatically before viewing as the chronological median held-out test date per site (June–July 2026, disjoint from `test_examples.png`). The offline HTML tool showed stretched RGB and NIR only—zero predictions or masks. A 3-class protocol (`land`, `water`, `uncertain/mixed`) with a 1-pixel bank-uncertainty ring quantified single-annotator 10 m boundary ambiguity (`44.83%–83.31%` IoU bounds), reported strictly separately from the 132-image evaluation.
- **Why not treat 5-minute ECCC rows as independent in AIDA 2156?** Adjacent 5-minute observations are strongly autocorrelated. Resampling 7-day UTC blocks preserves within-week serial dependence, while still noting that adjacent weeks can remain correlated and do not represent independent flood events.
- **What did ECCC (`2026-11-17`) and Alberta EPA (`2026-11-23`) officially confirm?** ECCC confirmed most stations operate in an **assumed datum** (so gauge stage cannot be equated to physical river depth without verified conversions). Alberta EPA confirmed the Red Deer River flood-survey layers are publicly available information usable in the course submission with EPA credit (`Protected A` emails and raw GDBs remain excluded).
- **Why did the study stop at `05CC002` and why keep `dickson_to_joffre.qgz` as the filename?** `05CC002` is the furthest downstream reach with a comparable validation gauge in the selected archive; stopping there prevents unsupported extrapolation to `P06–P11`. The filename was retained for script/path compatibility while all internal layers, extents, and maps end at `05CC002`.
- **How did you verify AI-assisted work?** All AI-assisted scripts and docs (`OpenAI ChatGPT/Codex`, `Google Antigravity/Gemini`) were verified via independent local execution (clean-extracted ZIP replays for 2154/2156/2362, SHA-256 checksums, XML validation, visual inspection of rendered SVGs/PNGs, and personally completed blind manual annotations); see [`Miles-ai-use.md`](../shared-resources/Miles-ai-use.md).
