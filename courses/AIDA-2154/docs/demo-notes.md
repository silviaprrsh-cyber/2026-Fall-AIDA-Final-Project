# CV demonstration and defence notes
Status: speaking outline for Weeks 13–14 (latest supplied D2L); individual assigned slot and completed presentation are not verified. See [submission readiness](d2l-readiness.md).

1. Decision (45 seconds): the municipal reviewer needs usable point-water-width evidence, not a decorative segmentation map. Nine fixed locations, historical data, CPU only. Available 10 m imagery does not resolve boundaries sufficiently for reliable model inputs.
2. Show the pipeline (60 seconds): archived RGB/NIR -> GIS-centred crops -> automatic masks with water closing -> date-grouped weak-label training -> frozen CNN output. Explain label 255 and why provider SCL is not truth.
3. Reproduce (60 seconds): run the frozen replay command in the course README. Show the passed result, fixed model/data hashes and 708/169/132 split. No network, API credentials, GIS application or database is needed for this replay.
4. Compare (60 seconds): TP 58,327; FP 9,096; FN 1,025; IoU 85.21%; baseline 84.41%. Emphasize weak-label agreement. Display first-per-point test_examples.png and use point_metrics.csv as its accessible numeric companion.
5. Failure (60 seconds): 05CC007 five zero-width results while observed discharge is positive; no inference that the river is dry. P04 weak-mask width discrepancy exceeds the static baseline. Explain narrow mixed pixels, occlusion and non-independent labels.
6. Recommendation (45 seconds): withhold CV output from prediction features/labels and flood warnings. Preserve the negative result; redesign only if suitable higher-detail imagery and independent width evidence become available. No requirement that the owner manually label every current image.

Defence prompts:
- Why does 85% IoU not prove good width? It compares against automatic masks and pixel accuracy does not guarantee bank accuracy.
- Why no width-flow success claim? Correlation is indirect and affected by geometry/season; zero width is an output warning, not dry-channel evidence.
- Why date groups? Same-date overlapping scenes and fixed sites are correlated; random pixel splits would leak.
- Why not use 0.6 after sensitivity? Test-informed tuning would consume the holdout; 0.5 remains frozen.
- What is reproducible? Frozen input-to-inference and scoring; not raw archive regeneration, real-width truth or a cloud deployment.
- What remains personal? Student review of AI declaration/technical retrospective, actual peer review, in-class explanation and D2L upload.
