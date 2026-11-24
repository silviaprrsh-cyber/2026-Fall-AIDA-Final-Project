# Computer vision responsible use and limitations

Updated 2026-11-13. The CNN and static baseline have run; independent boundary and physical-width truth remain unavailable.

## Recommendation and harm

**Withhold CV output from the prediction model and operational decisions.** Available imagery is insufficiently clear at native 10 m resolution for the target-width task. The current CV downstream-use objective failed, not the whole river project. Masks can invent a wide channel or remove a flowing narrow channel; neither flooding nor dryness is established.

## Responsibility review

- **Uncertainty:** held-out IoU is automatic-label agreement, not independent truth. Repeated sites, mixed pixels, bridges, shadows, snow/ice, registration and planned/translated transects constrain results. Exact pixel intersections do not create sub-pixel truth.
- **Bias:** screening favours usable unfrozen scenes; no winter test images exist. Narrow tributaries perform worse. Class imbalance and a strong static baseline limit aggregate scores. Do not generalize to new rivers, unseen floods or all dates.
- **Privacy/consent:** inputs are environmental observations, not personal recordings. No personal recording or live employer system is used. Exclude account details, private correspondence and unrelated personal data. Public access is not community consent for operational use.
- **Authority/licensing:** follow [the permission record](docs/data-permission-selection.md). Proposal approval is not a universal licence. Do not package survey originals or private replies with unconfirmed redistribution terms. Include only evidence needed for the CV classroom claim.
- **Accessibility:** pair images with named metrics, per-point values, text failure descriptions and legends distinguishing unknown from background, not colour alone. The failure report names zero-width dates and discharge. Use readable previews; this is not a user-tested accessibility certification.
- **Security:** keep the repository private, exclude credentials/private service details, preserve identities and inspect the exact package. Use restricted loading for trusted local weights. Demonstration must not download or execute remote code. Git ignore alone does not prove package cleanliness.
- **Community/decision impacts:** a coverage gap is not a safe reach. Do not use these outputs for emergency allocation, access restrictions or public warnings. Government access is not Indigenous community endorsement.

## Human-review and safe-failure rule

The current safe action is abstention: no CV width goes to the prediction model. Visual checks identified errors, but the available image detail cannot support reliable manual boundary verification or independent reference labels. Preserve imagery, masks, flags and failures for inspection, not as validated measurements.

Future reconsideration requires a qualified reviewer with sufficiently clear imagery and independent location/date reference measurements, error/uncertainty evaluation and documented acceptance for a defined purpose. Unknown, obscured, unsupported and out-of-scope cases stay unavailable, not land or zero. Human override without better evidence cannot repair the resolution limitation.

## Bounded enterprise decision

Withhold downstream/operational use; retain the reproducible classroom negative result. A future pilot requires improved imagery, traceable reference labels/widths, leakage-controlled independent evaluation, site/season failures, permission and accessible outputs. No retrospective operational threshold or accuracy guarantee is invented.

See data-model-card.md, docs/cv-width-failure-report.md, ai-use-declaration.md and release-checklist.md. The checklist distinguishes technical package checks from student review, peer review and D2L actions.
