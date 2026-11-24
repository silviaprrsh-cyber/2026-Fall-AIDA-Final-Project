# Sensitivity outcomes

Two formal observational analyses are indexed in [sensitivity-results.csv](sensitivity-results.csv). See [exact output](final_eda/sensitivity-results.csv), [time blocks](final_eda/time_blocks.csv), and the [report](../app-or-report/final-eda-report.md).

- **P-S1: approval policy.** The historical screening yields 95,053 joint, lake-complete timestamps. Requiring final approval on all nine inputs leaves zero, because two river stations had no eligible final values. No joint uncertainty interval or mean difference can be estimated.
- **P-S2: lake missingness.** Of the 144,289 river-only timestamps, 48,571 are on dates outside the lake-complete set. Restricting to 361 shared UTC dates, lake completeness changes the endpoint mean from 39.704 to 39.827 m³/s, a +0.123 m³/s difference (95% paired seven-day-block interval −0.002 to +0.315). Use the broad river-only cohort for general archive descriptions; mark lake results as conditional.

The prior S1/S2 ML protocol comparisons remain in [model sensitivity history](model-sensitivity-history.csv). They did not isolate one model choice and are not these two formal comparisons.
