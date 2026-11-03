# `segment_etl.json`

Segment ETL policy read by `rdr_eda.segments`: seed gauge, three input gauges, endpoint validation gauge, lake-feature location, observation-age limits and arrival-match tolerances. Current configurable defaults: river source age at most 1 hour, lake feature age at most 24 hours, endpoint match and initial branch arrival spread at most 30 minutes. These are explicit experimental settings, not provider guarantees or calibrated travel times. Velocity comes only from submodel outputs. This configuration runs no code and writes no files itself.
