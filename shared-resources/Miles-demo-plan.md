# Individual Demonstration & Peer-Review Plan — Miles Zhang

**Presentation & Peer-Review Window:** December 1–11, 2026 (confirm individual slots in D2L)  
**Final D2L Submission Deadline:** December 14, 2026 at 11:59 p.m. (separate upload per course)  
**Presentation Folder:** [`presentation/README.md`](../presentation/README.md) · [`presentation/CLASS-PRESENTATION-NOTES.md`](../presentation/CLASS-PRESENTATION-NOTES.md)

---

## 1. Course-by-Course Demonstration Walkthrough

### AIDA 2154 — Computer Vision (Weeks 13–14)
- **Deck:** [`presentation/AIDA2154-CV-Presentation.pptx`](../presentation/AIDA2154-CV-Presentation.pptx) (9 slides with speaker notes & attribution/Q&A closing slide).
- **Working Artifacts & Evidence to Show:**
  1. Held-out 9-site segmentation panel (`test_examples.png`, Slide 4) and frozen metrics (`85.21%` CNN vs. `84.41%` static baseline on weak labels).
  2. Concrete failure evidence (`hydrometry_width_scatter.png`, Slide 6: `05CC007` 5× zero-width during positive flow).
  3. **Strictly separate 9-site blind manual audit** (`independent_manual_comparison.png`, Slide 7: CNN `79.26%` vs. static baseline `79.80%`; `44.83%–83.31%` uncertainty bounds).
  4. Bounded **WITHHOLD** recommendation + human-review rule (Slide 8).
- **Optional 10-Second Live Offline CPU Replay Command:**
  ```powershell
  python -B run.py -m cv_tools.replay_frozen_cnn --output cv_demo_check
  python -B run.py -m cv_tools.test_release_replay
  ```

### AIDA 2156 — Exploratory Data Analysis & Statistics (Weeks 13–14)
- **Deck:** [`presentation/AIDA2156-EDA-Presentation.pptx`](../presentation/AIDA2156-EDA-Presentation.pptx) (10 slides with all 4 embedded SVG figures, speaker notes & attribution/Q&A closing slide).
- **Working Artifacts & Evidence to Show:**
  1. Formal decision report [`courses/AIDA-2156/app-or-report/final-eda-report.md`](../courses/AIDA-2156/app-or-report/final-eda-report.md) and [`claim-evidence-index.csv`](../courses/AIDA-2156/claim-evidence-index.csv).
  2. Four colourblind-safe accessible SVG figures (`fig1_monthly_coverage.svg` through `fig4_sensitivity_rules.svg`), highlighting exact denominators, 7-day block bootstrap 95% CIs, `P-S1` (`95,053 → 0`), and `P-S2` (`-48,571` winter records, `+0.123 m³/s` shift).
  3. ECCC `2026-11-17` assumed-datum confirmation and prominent non-operational flood-warning boundary.
- **Optional 1-Second Live Standard-Library Command:**
  ```powershell
  python -B -E -S courses/AIDA-2156/analysis/make_eda_figures.py
  python -B -E -S courses/AIDA-2156/analysis/tests_or_assertions.py
  ```

### AIDA 2362 — Geographic Information Systems (Week 15 — Live QGIS Required)
- **Deck:** [`presentation/AIDA2362-GIS-Presentation.pptx`](../presentation/AIDA2362-GIS-Presentation.pptx) (8 slides showing `724 km → 96.3 km → 56.0 km` scope maps, live expression cue & EPA/NRCan/ECCC attribution closing slide).
- **Live QGIS Workflow (open extracted portable `dickson_to_joffre.qgz` in QGIS 3.44.14):**
  1. Verify all 8 local relative layers load cleanly (`EPSG:3400` metric analysis, `246` valid features, Alberta EPA credit).
  2. Select `prediction_points` → **Select by Expression**:
     - Baseline: `abs("nearest_section_along_river_offset_m") <= 25` → highlights `P01`, `P02`, `P03` (`3/5`, all planned sections).
     - Changed variable: `abs("nearest_section_along_river_offset_m") <= 50` → highlights `P01–P05` (`5/5`, adding `P04` and `P05`, the only two surveyed sections).
  3. Open Attribute Table and show accessible [`map-feature-equivalent.csv`](../courses/AIDA-2362/outputs/map-feature-equivalent.csv) and [`Overhead view.pdf`](../courses/AIDA-2362/outputs/Overhead%20view.pdf).

---

## 2. In-Class Peer-Review Plan (Dec 1–11, 2026)

- Review **two different classmates' projects** using the official D2L Peer Review and Evaluation template (10 observation questions + 3 written-feedback prompts).
- Complete two separate forms (`Miles-peer-review-1.docx` and `Miles-peer-review-2.docx`; local blank templates are kept Git-ignored until filled in class) and submit both separately to the D2L Final Project Peer Review assignment.
- Record received classmate feedback and any resulting refinements honestly in each course's release checklist before the **December 14, 2026** final upload.
