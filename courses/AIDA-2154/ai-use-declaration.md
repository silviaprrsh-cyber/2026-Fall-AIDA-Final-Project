# Computer vision AI-use declaration and verification

Updated 2026-11-22 by Miles (Renjun) Zhang. I have reviewed, verified, and approved this declaration for my AIDA 2154 final project submission.

## Tools and assistance disclosed

During this project, I used **OpenAI assistants (ChatGPT / Codex)** and **Google Antigravity (Gemini)** as coding, auditing, and documentation aids. Specifically, AI assistance was used to:

- inspect course requirements and local project files;
- help locate GIS target imagery, implement automatic candidate water masks, and build/run the CPU CNN and static training-mask baseline;
- generate evaluation tables, held-out metric summaries, indirect width/hydrometry checks, and portable unit tests;
- draft and organize English documentation, Chinese review companions, failure evidence, reproducibility/resource checks, and clean package manifests;
- implement the separate PostgreSQL audit/view and Windows Docker inference engineering workflow requested as an extension.

No other AI tools were used.

## My direction, verification, and decisions

I directed the project design, reviewed the outputs, and made the core technical and release decisions:

- I defined and corrected the nine-point target scope (`P01–P05` plus `05CB001`, `05CB007`, `05CC002`, `05CC007`), source-preservation rules, and privacy boundaries.
- I corrected mask morphology to use water closing (dilate then erode) rather than opening, required unknown/cloud/shadow/snow pixels to be excluded rather than labelled dry, retained visible pixels under partial cloud, and required checkpoint saving on every strict validation-loss decrease.
- I visually inspected held-out crops and masks, confirmed that native 10 m Sentinel-2 imagery cannot reliably resolve riverbanks in narrow target reaches, and explicitly insisted on distinguishing weak-label agreement from independent physical ground truth.
- Based on the concrete failure evidence (including five zero-width predictions at `05CC007` during positive flow), **I made the decision to reject and withhold CV outputs from the downstream river prediction model**.

## Limits and remaining course actions

- Automated tests, preservation hashes, frozen 132-image CPU replay (IoU 85.2136% vs. 84.4083% baseline), and the separate Windows Docker verification (zero valid-pixel probability difference across 132 images) confirm computational reproducibility; they do not establish independent physical-width accuracy.
- I take full responsibility for explaining and defending the data selection, mask rules, date-grouped split, CNN architecture, baseline comparison, failure slices, and withhold recommendation independently in class.
- Actual classmate peer review/response, in-class demonstration, final private GitHub commit recording, and D2L upload remain tracked separately in [release-checklist.md](release-checklist.md) and are not claimed as complete here.
