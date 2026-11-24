# Cross-Course Personal Retrospective — Miles Zhang

**Student:** Miles (Renjun) Zhang  
**Last Updated:** 2026-11-23  
**Course-Specific Retrospectives:** [`courses/AIDA-2154/docs/retrospective.md`](../courses/AIDA-2154/docs/retrospective.md) · [`courses/AIDA-2156/retrospective.md`](../courses/AIDA-2156/retrospective.md)

---

## 1. What I Learned Across the Connected Project

- **Honest boundaries beat inflated metrics:** The biggest shift across the semester was moving from trying to force an end-to-end "working flood model" to letting empirical evidence dictate strict boundaries. Preserving a well-documented negative result in AIDA 2154 (`WITHHOLD`), separating formal observation adequacy from experimental ML in AIDA 2156, and trimming the AIDA 2362 reach to `05CC002` made every course far more defensible.
- **Weak labels can hide real failure modes:** In AIDA 2154, `85.21%` CNN IoU looked slightly better than the `84.41%` static baseline until indirect width checks exposed 5× zero-width errors at `05CC007` and my blind 9-site manual annotation proved the CNN (`79.26%`) actually fell slightly behind the static baseline (`79.80%`) with a `44.83%–83.31%` mixed-pixel uncertainty range.
- **Metadata and agency confirmation matter as much as code:** Writing directly to ECCC (confirming assumed gauge datums on `2026-11-17`) and Alberta EPA (confirming public-information attribution rules on `2026-11-23`) resolved real physical and legal ambiguities that no amount of code refactoring could guess.

## 2. Key Challenges and How I Responded

1. **Scope creep vs. validation evidence (`AIDA 2362`):** My earlier `724 km` and `96.3 km` (Joffre, `P01–P11`) designs had no downstream validation gauge past Red Deer (`05CC002`). *Response:* I reduced active scope to `56.0 km` (`P01–P05`), preserved historical projects separately, and verified the final relative-path ZIP from a clean extraction in QGIS 3.44.14.
2. **Dependency bloat & reproducibility (`AIDA 2156`):** Mixing experimental PyTorch/PostgreSQL pipelines with formal EDA made grading reproduction fragile. *Response:* I decoupled the formal EDA completely so both statistical analysis (`analysis.py`) and accessible SVG plotting (`make_eda_figures.py`) run deterministically using Python 3.13 standard library only (`python -B -E -S`).
3. **Manual annotation fatigue & rigor (`AIDA 2154`):** Pixel-by-pixel labeling across nine `61 × 61` crops was slow and error-prone. *Response:* I kept the tool strictly blind (RGB + NIR only), added an explicit 1-pixel bank-uncertainty ring helper and single-pixel eraser to keep uncertainty labeling consistent, and documented that single-annotator protocol transparently as an audit rather than physical ground truth.

## 3. What I Would Do Differently Next Time

- Start with a smaller, fully verified reach and confirm vertical datums and redistribution permissions in Week 6 rather than late in the semester.
- Build the functional requirements register and contribution map alongside the Week 8 design so every new script immediately maps to a single testable requirement.
