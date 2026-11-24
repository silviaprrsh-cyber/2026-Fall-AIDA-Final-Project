# EDA AI-use declaration and verification

Updated 2026-11-22 by Miles (Renjun) Zhang. I have reviewed, verified, and approved this declaration for my AIDA 2156 final project submission.

## Tools and assistance disclosed

During this project, I used **OpenAI assistants (ChatGPT / Codex)** and **Google Antigravity (Gemini)** as coding, data-auditing, and documentation aids. Specifically, AI assistance was used to:

- inspect the local repository, archived hydrology/weather/GIS/CV inputs, and course requirements;
- implement and verify the formal standard-library EDA script (`analysis/analysis.py`), assertions (`analysis/tests_or_assertions.py`), seven-day block bootstrap intervals, and P-S1 / P-S2 sensitivity checks;
- assist with earlier exploratory ML / V4 modeling experiments, PostgreSQL views, and the separate local Windows prototype;
- run reproducibility checks, verify file checksums, and draft/align English reports and Chinese review companions.

No other AI tools were used.

## My direction, verification, and responsibility

- I framed the bounded Red Deer River historical comparison question, directed the decision to switch the main comparison from five stations to four river stations after discovering Sylvan Lake's level-only series and winter missingness, and kept the five-station join as sensitivity check P-S2.
- I independently contacted Environment and Climate Change Canada (Nov 10, 2026) regarding gauge-zero elevations and vertical datums and reviewed their Nov 17, 2026 confirmation that most stations operate in an assumed datum, reinforcing why reported stage cannot be treated as surveyed river depth.
- I reviewed the final EDA outputs, sensitivity tables, claim-to-evidence index, and V4 failure diagnostics, and I take full responsibility for explaining and defending the unit, denominator, non-causal limits, sensitivity impact, and operational-use withhold decision in class.

## Boundaries

Computational reproducibility and checksum verification confirm that the scripts run cleanly on the frozen inputs; they do not by themselves establish causal validity, operational flood readiness, peer-review completion, or D2L submission. Remaining course handoff items (clean package assembly, genuine classmate peer review/response, presentation, and D2L upload) are tracked in [submission-manifest.txt](submission-manifest.txt).
