# GIS AI-use declaration and verification

Updated 2026-11-22 by Miles (Renjun) Zhang. I have reviewed, verified, and approved this declaration for my AIDA 2362 final project submission.

## Tools and assistance disclosed

During this project, I used **OpenAI assistants (ChatGPT / Codex)** and **Google Antigravity (Gemini)** as coding, verification, and documentation aids. Specifically, AI assistance was used to:

- organize and maintain GIS helper scripts (`src/gis_tools/`), configuration files, and scope-reduction checks;
- verify QGIS project reopening, geometry/CRS/field counts (246 features across eight relative vector layers), and the 25 m vs. 50 m section-proximity sensitivity procedure;
- help compile the per-layer inventory (`data/layer-inventory.csv`, `data/layer-inventory.md`), accessible map equivalents (`outputs/map-text-equivalent.md`, `outputs/map-feature-equivalent.csv`), and preflight manifest (`submission-manifest.txt`);
- draft and align English and Chinese decision, governance, release-checklist, and presentation documents.

No other AI tools were used.

## My direction, verification, and responsibility

- I selected and narrowed the study reach from the full basin (~724 km) to Dickson–Joffre (~96.3 km) and then to Dickson Dam–`05CC002` (~56.0 km, retaining `P01–P05`) because the selected archive lacked a comparable validation gauge downstream of `05CC002`.
- I directly requested and obtained the Red Deer River flood-survey geodatabases from Alberta Environment and Protected Areas for non-commercial academic use at Red Deer Polytechnic (Sept 30, 2026) and contacted ECCC regarding station vertical datums (Nov 10–17, 2026).
- I verified the QGIS project (`project/dickson_to_joffre.qgz`), exported PDF/PNG layouts, independent relative-path copy reopening (QGIS 3.44.14, 8 local vector layers, 246 features), and the 25 m vs. 50 m sensitivity results (`3/5` to `5/5`, adding `P04` and `P05`).
- I take full responsibility for demonstrating the live QGIS workflow in Week 15 and independently explaining the CRS choices (`EPSG:4326` storage, `EPSG:3857` display, `EPSG:3400` metre distances, `EPSG:3780`/CGVD28 survey source), spatial limitations, governance review, and release boundaries.

## Boundaries

AI assistance does not substitute for instructor approval, Indigenous/community authority, actual classmate peer review, or final D2L submission. Alberta Environment and Protected Areas confirmed permission to use the survey data with attribution on 2026-11-23; remaining open handoff items (peer review, Week 15 live QGIS demo, and D2L upload) are tracked in [release-checklist.md](release-checklist.md) and [submission-manifest.txt](submission-manifest.txt).
