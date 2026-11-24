# EDA supporting model evidence

Recorded 2026-11-11 from saved experiments completed 2026-11-10. This is supporting evidence for the observation/assumption adequacy question, not a completed decision-led EDA.

The five retained protocols are frozen V1, rejected tail V2, reverse V1, reverse approximately80/20, and weighted V1. Full original population metrics and report references are in ../output/model-experiment-metrics.csv. The two-epoch frozen smoke remains execution evidence only.

Frozen V1 selects one training-only route rather than intersecting all27; its forward training peak is129 and test reaches281. V2 did not repair high-Q errors and was rejected. Reverse V1 includes284 in training, but predicts its two peak rows166.03/165.60. Later80/20 retains49380 development/12350 test after external input-window isolation; internal low-water validation selected4 epochs. Weighted V1 retains exactly those external rows, weights Q>=100 by5, and uses May28-June25 high-water targets for internal validation. It has42788 fit/6512 validation, temporarily excludes80 boundary rows, selects1 epoch, then refits all49380 for one epoch. Peak284 predictions remain129.52/126.95.

Identical-row comparisons are in ../output/identical-test-comparison.csv: 80/20 improves over the prior reverse model, while weighting improves high water and worsens overall errors. All46 test rows Q>=140 remain underestimated. These are changes to compound protocols, not causal evidence that split percentage or weighting alone caused the outcome.

The first reverse calibration failed because internal history was reset; correction permits known past inputs within outer training while separating inner target labels. External isolation was retained. No all27 intersection was reinstated.

Internal route selection and validation are not fully independent; past upstream histories may overlap. Endpoint labels do not validate intermediate nodes. Repeated five-minute rows are not independent events. Publication-time availability was not verified. Gauge datum and geometry transfer are unresolved. Operational release is withheld.

The earlier plan still needs distributions, relationships, quality/missingness comparisons, uncertainty and the two planned EDA sensitivities. No new experiment or clean-run claim is made by this report.

## Current release boundary

This evidence remains the dated 2026-11-11 comparison. For later model selection, see [the V4 final-test report](../docs/MODEL_EXPERIMENTS.md). The new [server/receiver package](../README.md) does not validate the original or deployed adapter for actual flood use.
