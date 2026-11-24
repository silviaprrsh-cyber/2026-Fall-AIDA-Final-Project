# Accessibility and alternate formats

The [decision report](final-eda-report.md) is static Markdown accompanied by four labelled vector SVG figures (`output/final_eda/figures/fig1_monthly_coverage.svg` through `fig4_sensitivity_rules.svg`), with descriptive headings, units, table headers, Markdown alt text, and embedded SVG `<title>`/`<desc>` descriptions. All figures use an Okabe-Ito colourblind-safe palette, distinct shapes/line dashes, and direct numeric labels so no value or conclusion depends on colour or an image. No dashboard, map interaction, login, script execution or hover action is required to read the findings.

| What to find | Static SVG figure | Plain-table version |
| --- | --- | --- |
| Coverage, missingness and source quality | [Figure 1: Monthly coverage](../output/final_eda/figures/fig1_monthly_coverage.svg) | [Coverage by time/station](../output/final_eda/coverage.csv) and [quality flags](../output/final_eda/quality_counts.csv) |
| Distribution, including extremes | [Figure 2: Discharge distributions](../output/final_eda/figures/fig2_discharge_distributions.svg) | [Distribution table](../output/final_eda/distributions.csv) |
| Lagged associations and uncertainty | [Figure 3: Lagged correlations](../output/final_eda/figures/fig3_lagged_correlations.svg) | [Lagged results](../output/final_eda/lagged_relationships.csv) and [UTC time blocks](../output/final_eda/time_blocks.csv) |
| What changes when the data rules change | [Figure 4: P-S1 & P-S2 sensitivities](../output/final_eda/figures/fig4_sensitivity_rules.svg) | [Formal comparison values](../output/final_eda/sensitivity-results.csv) and [decision impact index](../output/sensitivity-results.csv) |
| What the original weather, satellite and GIS sources cannot validate | *(text/table audit)* | [Original-source context with values and interpretations](source-context.md) |

Use heading navigation in a screen-reader-friendly Markdown viewer or open any CSV in a spreadsheet or plain-text editor. Load CSV as UTF-8 and preserve station identifiers as text. The headline values also appear as sentences in the report if a wide table is difficult to navigate. All comparisons are available as text and tables; no figure-only information needs separate image alternatives. These are design provisions, not a claim of user testing or WCAG compliance. This note does not assess the separate Windows receiver.
