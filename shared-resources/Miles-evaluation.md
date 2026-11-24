# Cross-Course Evaluation Summary — Miles Zhang

**Last Updated:** 2026-11-23  
This document summarizes the baselines, comparisons, sensitivities, failures, and verification checks across all three enrolled courses and links directly to each course's detailed outputs.

---

## 1. AIDA 2154 — Computer Vision Evaluation

### 1.1 Frozen 132-Image Weak-Label Evaluation (Original Evaluation, Unchanged)
- **Protocol:** `1,009` unique point-date samples split `708 / 169 / 132` (train / val / test), grouped by acquisition date with a 7-day boundary gap, training-only normalization, fixed threshold `0.5`, seed `42`, 6,113-parameter CPU CNN vs. static per-point training-mask baseline.
- **Pooled Test Metrics (agreement with automatic weak masks — NOT physical-width ground truth):**
  - **Frozen CNN:** `TP 58,327`, `FP 9,096`, `FN 1,025`, `TN 420,985` → **IoU `85.21%`**, Precision `86.51%`, Recall `98.27%`.
  - **Static Baseline:** `TP 53,628`, `FP 4,182`, `FN 5,724`, `TN 425,899` → **IoU `84.41%`**, Precision `92.77%`, Recall `90.36%`.
- **Slice & Failure Evidence ([`courses/AIDA-2154/docs/cv-width-failure-report.md`](../courses/AIDA-2154/docs/cv-width-failure-report.md)):**
  - Narrow tributary weak-label IoU drops to **`62.28%`** (`05CB001`) and **`53.74%`** (`05CC007`).
  - Indirect 500 m transect checks (`124/132` complete widths; `70` matched within 300 s to ECCC discharge): **`05CC007` returned 0 m predicted width on 5 test dates despite positive observed flows (`0.107–0.780 m³/s`)**; station width/flow Spearman correlations are inconsistent (`+0.080`, `-0.619`, `-0.148`, `+0.251`); `P04` weak-label width MAE (`29.69 m`) is worse than the static baseline (`14.93 m`).
- **Reproducibility & Compute:** Clean CPU replay of 132 test images completed in `10.4 s` with exact metric parity + `14/14` portable tests passed ([`courses/AIDA-2154/docs/compute-reproduction.md`](../courses/AIDA-2154/docs/compute-reproduction.md), [`docs/d2l-readiness.md`](../courses/AIDA-2154/docs/d2l-readiness.md)). Separate Windows Server Core LTSC2022 container inference matched host output with `0` valid-pixel difference.

### 1.2 Supplementary 9-Site Blind Manual Audit (2026-11-23, Strictly Separate)
- **Protocol:** Predeclared chronological median held-out test image per site (June–July 2026, disjoint from `test_examples.png`), annotated blind (`clear land`, `clear water`, `uncertain/mixed`) with RGB + NIR only and zero model/mask visibility ([`courses/AIDA-2154/docs/independent-manual-check.md`](../courses/AIDA-2154/docs/independent-manual-check.md)).
- **Pooled Clear-Pixel Results (`30,342` clear pixels):**
  - **Frozen CNN vs. Manual:** **IoU `79.26%`** (Precision `91.86%`, Recall `85.25%`) — **−0.54 percentage points BELOW** the static baseline!
  - **Static Baseline vs. Manual:** **IoU `79.80%`** (Precision `96.03%`, Recall `82.52%`).
  - **Automatic Weak Mask vs. Manual:** **IoU `82.18%`** (Precision `96.31%`, Recall `84.86%`).
- **Uncertainty Bounds (`3,147` uncertain vs. `3,810` clear water pixels = `45.24%` of channel zone):** CNN IoU spans **`44.83%` to `83.31%`** (`38.5 pp` uncertainty width). Specific failures: `05CC007` recall collapse (`23.53%`), `P03` braided side-channel omission (`41.25%` across all automated methods), and `P04` off-channel false positives (`87.09%` CNN vs. `98.71%` baseline).
- **Evidence:** [`courses/AIDA-2154/outputs/independent_manual_eval_20261123/manual_eval_summary.json`](../courses/AIDA-2154/outputs/independent_manual_eval_20261123/manual_eval_summary.json), [`independent_manual_comparison.png`](../courses/AIDA-2154/outputs/independent_manual_eval_20261123/independent_manual_comparison.png).

---

## 2. AIDA 2156 — Exploratory Data Analysis & Statistics Evaluation

- **Clean-Copy Standard-Library Replay:** `python -B -E -S analysis.py` + `tests_or_assertions.py` + `make_eda_figures.py` reproduced all 7 output tables and 4 accessible SVG figures byte-for-byte (`52/52` SHA-256 matches in [`courses/AIDA-2156/submission-manifest.txt`](../courses/AIDA-2156/submission-manifest.txt); [`clean-copy-replay.txt`](../courses/AIDA-2156/output/clean-copy-replay.txt)).
- **Distributional & Dependence Diagnostics:**
  - Strong right-skew across all four river gauges (e.g., `05CC002` median `22.3 m³/s` vs. mean `36.0 m³/s`), requiring non-parametric summaries alongside means.
  - Because 5-minute observations are heavily autocorrelated, uncertainty intervals use **7-day block bootstrap 95% CIs** rather than invalid i.i.d. standard errors (`lagged_relationships.csv`, `fig3_lagged_correlations.svg`).
- **Two Consequential Sensitivity Checks ([`courses/AIDA-2156/output/final_eda/sensitivity-results.csv`](../courses/AIDA-2156/output/final_eda/sensitivity-results.csv)):**
  1. **Sensitivity 1 (`P-S1` — Strict `Final`-only approval):** Joint 4-river cohort drops from **`95,053` → `0` timestamps** because tributaries `05CB001` and `05CC007` are 100% Provisional → **Decision effect:** restricts study to exploratory historical evidence adequacy only.
  2. **Sensitivity 2 (`P-S2` — Requiring Sylvan Lake `05CC003`):** Drops **`48,571` winter river timestamps** due to lake winter shutdown, while changing mean `05CC002` discharge across 361 common days by only **`+0.123 m³/s`** (`95% CI [-0.002, +0.315]`) → **Decision effect:** retain 4 river gauges as the primary comparison cohort and report `05CC003` separately.
- **Contextual ML Boundary (Strictly Separate):** Retained V4 model experiments ([`courses/AIDA-2156/docs/MODEL_EXPERIMENTS.md`](../courses/AIDA-2156/docs/MODEL_EXPERIMENTS.md)) use unverified assumed-datum stage proxies (confirmed `2026-11-17` by ECCC) and are explicitly **withheld from operational flood warning**.

---

## 3. AIDA 2362 — Geographic Information Systems Evaluation

- **Clean-Extraction Portable QGIS Verification (`2026-11-23`):**
  - Rebuilt and clean-extracted `AIDA2362_FinalProject_Miles_Zhang.zip` (`9,500,475` bytes, 37 files, SHA-256 `dbe04ab0...2969f379cb`) into an empty temporary directory and opened in **QGIS 3.44.14**:
  - **8 / 8** local relative vector layers resolved inside the extracted archive; **`246` valid features**, **`0` invalid GEOS geometries**, **`2` print layouts** retained ([`courses/AIDA-2362/outputs/zip-extraction-validation.json`](../courses/AIDA-2362/outputs/zip-extraction-validation.json)).
- **Changed-Variable Spatial Sensitivity (`<= 25 m` vs. `<= 50 m` along-river section offset):**
  - **Baseline (`<= 25 m`):** Selects `3 / 5` targets (`P01`, `P02`, `P03`) — all associated with planned/interpolated cross-sections.
  - **Changed Variable (`<= 50 m`):** Selects `5 / 5` targets (`P01–P05`), adding **`P04` (`37.87 m`)** and **`P05` (`40.76 m`)** — the **only two targets associated with actual field-surveyed cross-sections** ([`courses/AIDA-2362/outputs/section-proximity-sensitivity.md`](../courses/AIDA-2362/outputs/section-proximity-sensitivity.md)).
- **Accessible Map/Table Parity:** [`courses/AIDA-2362/outputs/Overhead view.pdf`](../courses/AIDA-2362/outputs/Overhead%20view.pdf) is paired with [`map-feature-equivalent.csv`](../courses/AIDA-2362/outputs/map-feature-equivalent.csv) (`246` rows matching all active map layers).
