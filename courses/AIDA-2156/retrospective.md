# EDA retrospective and personal reflection

Finalized 2026-11-22 by Miles (Renjun) Zhang.

## Personal reflection: why I changed the station match

At first I thought the fifth station, Sylvan Lake (`05CC003`), was temporarily offline. I expected it to have discharge readings and included it when I first considered matching the stations. When I compared the available records, I found that our Sylvan Lake series contained water levels rather than discharge and did not cover enough of the study period to make it a required station.

The four river stations matched at **144,289** timestamps. Requiring a Sylvan Lake reading at the same timestamp reduced that to **95,053**, a loss of **49,236** observations (34.1%). I therefore kept the four-station match for the main analysis and used the five-station match as a sensitivity check (`P-S2`). If I did this again, I would inspect what each station actually measures and check its coverage across the full window before deciding which stations must match.

## Formal EDA lessons

Analyzing the frozen archived observations directly prevented treating assumed route offsets or model residuals as ground-truth data. Key methodological lessons I take from the formal EDA include:

- **Keep denominators and screening policies explicit:** Separating the fixed 158,112-slot UTC window, present numeric values, historical screen, and strict all-`Final` policy (`P-S1`) showed that requiring all nine inputs to be `Final` drops the joint sample from 95,053 to zero. An empty strict overlap is an evidence limit, not a reason to quietly relax rules or fill missing estimates with zeros.
- **Compare subsets on shared calendar support:** Because lake missingness removes entire periods, comparing the lake-complete and river-only cohorts on the 361 shared UTC dates (+0.123 m³/s mean difference, paired 95% block interval [−0.002, +0.315]) clarified that the lake requirement mainly restricts temporal coverage rather than shifting same-date flow means.
- **Verify physical measurement assumptions at the source:** Following up directly with ECCC (Nov 10–17, 2026) confirmed that most hydrometric stations operate in an assumed datum and that conversion factors may not exist or remain contiguous across gauge moves. Combined with the raw source audit—which separated archive revisions from historical availability, satellite masks from real river width, and planned section lines from verified hydraulic profiles—this reinforced why station stage must stay strictly separated from physical depth.

## Supporting ML / V4 experiment lessons and packaged boundary

Across the exploratory modeling sequence (frozen route replacement, rejected tail experiment, inner history reset fix, reverse-time training including the 284 m³/s event, 80/20 comparison, and high-flow weighting), aggregate MAE improved in several slices while crest timing and peak errors remained. The main technical lesson supported by those artifacts is that pooled MAE and split labels are insufficient evidence of physical validity or flood-warning readiness.

Accordingly, the original V4 60/20/20 weights remain frozen unchanged as a research reference only. The separately packaged local Windows prototype uses a source-only adapter that distinguishes observation, receipt, issuance, and validity clocks without using terminal flow to reconstruct inputs; its synthetic demo verifies software behavior, not real-world flood performance.
