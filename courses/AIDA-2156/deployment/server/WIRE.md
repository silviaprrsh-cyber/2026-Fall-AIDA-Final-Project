# Snapshot API v1

Routes: `GET /healthz` and `GET /api/v1/snapshot`. Optional Bearer on the second route. Do not embed credentials in a URL. The snapshots use UTC ISO-8601 on every clock and contain no credentials or binary model.

- `mode`: `demo` (synthetic observations) or `live` (official provider, database-backed).
- `generated_at`: issue/collection timestamp after the batch has been saved and before inference; not the observed clock.
- `flows`: one per configured discharge gauge, numeric m3/s or null; `observed_at`, `retrieved_at`, `available_at`, `status` (`ok`, `stale`, `missing`), age and source. The last provider release signal is a lower bound, not necessarily actual first publication. The adapter also checks first actual retrieval; unretrieved values cannot be used.
- `rain`: one mm accumulation at station string `3025484`, with hourly start `observed_at` and `window_end_at`. Inference separately references earlier completed hourly buckets for each contributing branch.
- `depths` and `inference`: current 0 h group. Additive `horizons` contains `{hours: 3, depths, inference}` and `{hours: 9, depths, inference}`. Exactly six standard nodes each. `valid_at` is the target grid timestamp, even when a value is unavailable. `status` is `experimental` or `unavailable`. No real flood use. Last node `P06` maps to `05CC002`, others are unvalidated latent sections.
- `inference.provenance` records nominal requested/actual donor stamps, rain coverage, and Medicine candidate coverage, or a specific unavailable reason; it never serializes training observations or physical hazards. The +9 h group requires the Little Red Deer observation at the current five-minute grid, retrieved and known by issuance. This group is unavailable when a required input is missing or arrives late.
- `collection.failed_sources` is sanitized; an absent provider record never fabricates zero flow. `/healthz` indicates recent processing and database-write health; source-level problems remain visible in the snapshot, not in guessed water readings.
