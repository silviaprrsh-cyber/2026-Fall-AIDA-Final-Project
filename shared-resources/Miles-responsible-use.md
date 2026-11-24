# Responsible Use, Governance, and Human Oversight — Miles Zhang

**Last Updated:** 2026-11-23  
**Course-Specific Reviews:** [`courses/AIDA-2154/responsible-use-limitations.md`](../courses/AIDA-2154/responsible-use-limitations.md) · [`courses/AIDA-2156/limitations-and-next-evidence.md`](../courses/AIDA-2156/limitations-and-next-evidence.md) · [`courses/AIDA-2362/governance-review.md`](../courses/AIDA-2362/governance-review.md)

---

## 1. Hard Operational & Safety Boundary

- **Not an operational flood-warning or safety tool:** Across all three courses (including the contextual AIDA 2156 V4 desktop prototype), **no output supports real-world flood alerts, emergency dispatch, property-risk classification, or infrastructure design**.
- **Human-oversight rule:** Every physical width check (2154), hydrological interpretation (2156), and spatial cross-section selection (2362) requires human technical review and verified field/agency records before any real-world action.

## 2. Privacy, Security, and Authority Controls

- **Zero personal data:** All inputs are public environmental stations, satellite tiles, and river geometry—no personally identifiable resident or employee records are collected.
- **Zero credentials or restricted files in Git or ZIPs:** `.env`, API tokens, PostgreSQL passwords, raw government geodatabases, ECCC benchmark PDFs, and private agency emails (including `Classification: Protected A` Alberta EPA correspondence) are excluded from Git and all D2L submission packages.
- **Confirmed data authority:**
  - **Alberta EPA (`2026-11-23`):** Written confirmation that the provided Red Deer River flood-survey data is publicly available information and may be used in the course submission **provided Alberta EPA is credited**. Attribution is included in all GIS inventories, maps, and decision briefs.
  - **ECCC (`2026-11-17`):** Written confirmation that most stations operate in an **assumed datum**, stage records may not be contiguous across gauge moves, and universal elevation conversions may not exist—explicitly documented as a hard physical-depth limitation in AIDA 2156.
  - **Copernicus Sentinel-2 & NRCan:** Public open data with source attribution and checksum provenance retained.

## 3. Uncertainty, Bias, Accessibility, and Community Respect

- **Explicit uncertainty & negative-result honesty:**
  - *AIDA 2154:* Preserved the negative CV result (**WITHHOLD**) rather than inflating weak-label IoU (`85.21%`) into a false validation claim, and quantified 10 m mixed-bank uncertainty (`44.83%–83.31%` IoU bounds) via blind manual audit.
  - *AIDA 2156:* Reported exact denominators, missing/rejected/off-grid counts, autocorrelation-aware 7-day block CIs, and winter/provisional exclusions prominently beside every decision.
  - *AIDA 2362:* Distinguished `38` surveyed vs. `191` planned cross-sections and labeled weather association polygons explicitly as schematic (not physical watersheds).
- **Accessibility:** Colourblind-safe palettes and static numeric/text table equivalents accompany all AIDA 2156 SVG figures ([`accessibility-notes.md`](../courses/AIDA-2156/app-or-report/accessibility-notes.md)) and the AIDA 2362 PDF map ([`map-feature-equivalent.csv`](../courses/AIDA-2362/outputs/map-feature-equivalent.csv)).
- **Community & Indigenous considerations:** Access to provincial/federal open spatial datasets does **not** constitute Indigenous community consultation, local municipal endorsement, or authority over watershed governance (detailed in [`courses/AIDA-2362/governance-review.md`](../courses/AIDA-2362/governance-review.md)).
