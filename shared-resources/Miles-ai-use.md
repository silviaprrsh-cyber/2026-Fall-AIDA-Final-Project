# AI-Use Declaration and Verification — Miles Zhang

**Student:** Miles (Renjun) Zhang  
**Reviewed & Signed Off:** 2026-11-22 (updated 2026-11-23 to include blind manual tool & guide alignment)  
**Detailed Course-Specific First-Person Declarations:**  
- AIDA 2154: [`courses/AIDA-2154/ai-use-declaration.md`](../courses/AIDA-2154/ai-use-declaration.md)  
- AIDA 2156: [`courses/AIDA-2156/ai-use-declaration.md`](../courses/AIDA-2156/ai-use-declaration.md)  
- AIDA 2362: [`courses/AIDA-2362/ai-use-declaration.md`](../courses/AIDA-2362/ai-use-declaration.md)

---

## 1. AI Tools Used and How They Contributed

Across all three courses, I used **OpenAI assistants (ChatGPT / Codex)** and **Google Antigravity (Gemini)** as coding, debugging, packaging, and technical-writing assistants. Specifically, AI assisted with:
- Structuring Python scripts for data auditing, deterministic standard-library SVG figure generation (`make_eda_figures.py`), CPU CNN replay (`replay_frozen_cnn.py`), the offline blind manual annotation web tool (`independent_manual_eval.py`), and QGIS ZIP extraction validation (`build_and_verify_release_zip.py`).
- Drafting and organizing bilingual (English/Chinese) documentation, presentation slide layouts, and course checklists under my direction.

## 2. What Remained Strictly My Own Decisions and Verification

I retained full responsibility for every scientific decision, scope boundary, agency inquiry, manual annotation, and final claim:
- **Personal domain & field checks:** I personally visited the Red Deer River (`2026-11-03`), initiated direct email inquiries with **ECCC** (`2026-11-10`, reply `2026-11-17`) and **Alberta EPA** (`2026-11-23` attribution clearance), and personally completed all nine blind manual Sentinel-2 annotations (`2026-11-23`) without viewing any model prediction or automatic mask.
- **Independent execution & audit:** Every reported metric, SHA-256 checksum, clean-copy standard-library EDA replay (`52/52` manifest matches), 14 portable CV tests, and clean-extracted QGIS 3.44.14 verification (`8/8` layers, `246` valid features) was executed locally and inspected against raw outputs.

## 3. Concrete AI Outputs Rejected or Corrected

- **Rejected over-claiming CV accuracy:** Early AI-drafted wording tended to emphasize the `85.21%` IoU headline; I enforced keeping **WITHHOLD** prominent, documenting `05CC007` zero-width failures, and running the blind 9-site manual check that proved CNN (`79.26%`) trailed the static baseline (`79.80%`).
- **Corrected visual & packaging defects:** I inspected rendered EDA SVG figures and rejected overlapping legends/callout text (`fig2`, `fig3`, `fig4`) and Unicode glyph collisions in `independent_manual_comparison.png`, requiring regeneration and re-inspection; I also caught and corrected stale deadline dates (`Dec 7` → `Dec 14`) and excluded `Protected A` correspondence and raw GDBs from Git and ZIPs.
- **No fabricated evidence:** Zero synthetic peer reviews, fabricated ground-truth widths, or invented D2L submission receipts were permitted.
