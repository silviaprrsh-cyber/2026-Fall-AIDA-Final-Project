# CV retrospective and personal reflection

Finalized 2026-11-22 by Miles (Renjun) Zhang.

## Goal and outcome

My goal in AIDA 2154 was to test whether satellite water segmentation at nine Red Deer River target locations (`P01–P05` and four discharge stations) could supply reliable point water-width estimates for a downstream river prediction model. The outcome is a documented negative result: at the native 10 m spatial resolution available to this project, the imagery is not sufficiently clear to resolve channel banks reliably in narrow reaches, so I withheld all current CV outputs from the prediction model. This closes the current satellite-width approach rather than invalidating the broader river study.

## Personal reflection

My biggest takeaway from this course project came from inspecting the actual 10 m image crops and masks with my own eyes rather than trusting a headline metric. On paper, a test IoU of **85.2136%** can look encouraging at first glance. However, when I visually reviewed the target patches and compared the CNN against a simple static per-point training-mask baseline (**84.4083%** IoU), I realized two critical things:

1. **Resolution is a hard physical limit, not a tuning problem.** In narrow tributary reaches such as `05CC007` and `05CB001`, a single 10 m pixel mixes water, bank, vegetation, or shadow. When even a human eye looking directly at the crop cannot trace the true waterline with confidence, adding more training epochs or tweaking morphology cannot manufacture accuracy that is absent from the sensor.
2. **Choosing to withhold an unreliable model is the right engineering decision.** Earlier in the project I wanted CV widths to feed directly into my hydrology pipeline. Seeing concrete failure cases—especially five `05CC007` test dates where the CNN returned zero river width despite positive observed discharge—convinced me not to force CV outputs into the prediction model. Documenting why an approach fails, preserving the negative evidence, and setting a clear stop rule proved far more valuable than chasing a higher weak-label score.

If I were to revisit satellite river-width estimation in the future, I would start with a small visual feasibility check on sub-metre or commercial/aerial imagery and establish an independent physical-width reference before building an end-to-end training pipeline.

## Technical summary of what was established

- **Reproducible pipeline:** Nine verified GIS points, source-preserving offline 61 × 61 native-grid crops, 2,322 automatic candidate masks, and 1,009 screened/deduplicated point-date samples split chronologically by date with a seven-day boundary gap (`708 / 169 / 132`). Unknown/cloud/shadow/snow pixels are excluded rather than labelled dry.
- **Controlled baseline & indirect checks:** The 6,113-parameter CPU CNN selected epoch 40 by validation loss and beat the static training-mask baseline by only 0.8052 percentage points on weak-label IoU, with narrow-site IoU dropping to 62.28% (`05CB001`) and 53.74% (`05CC007`). Indirect transect checks against hydrometric records showed weak/inconsistent Spearman correlations and five zero-width/positive-flow failures at `05CC007`.
- **Key engineering lessons retained:**
  - Verify GIS identity and raster coordinates before processing; broad-corridor imagery is not automatically target-point evidence.
  - Preserve source archives, hashes, and earlier experiment snapshots rather than overwriting inconvenient results.
  - Water closing helps preserve channel continuity, but morphology cannot recreate missing sensor detail.
  - Keep weak-label agreement metrics strictly separate from independent physical ground-truth accuracy.

## Remaining course handoff items

Actual classmate peer review and response, in-class demonstration/defence, final commit recording, and D2L package upload remain tracked in [release-checklist.md](../release-checklist.md).
