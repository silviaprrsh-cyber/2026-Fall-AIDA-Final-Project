-- Additive routing views; schema is selected by the migration session.
CREATE OR REPLACE VIEW v_routing_weather AS
WITH bounds AS (
    SELECT date_bin(interval '1 hour', min(observed_at), '2000-01-01 00:00:00+00'::timestamptz) - interval '25 hours' AS lo,
           date_bin(interval '1 hour', max(observed_at), '2000-01-01 00:00:00+00'::timestamptz) AS hi FROM routing_discharge
), hours AS (
    SELECT generate_series(lo, hi, interval '1 hour') AS hour_utc FROM bounds
), inputs AS (
    SELECT hour_utc, rain_mm, coalesce(rain_mm, 0) AS effective_mm
    FROM hours LEFT JOIN routing_weather_hourly ON observed_at=hour_utc
)
SELECT hour_utc, rain_mm AS observed_rain_mm, effective_mm AS rain_1h_mm,
       sum(effective_mm) OVER w6 AS rain_6h_mm,
       sum(effective_mm) OVER w24 AS rain_24h_mm,
       count(*) FILTER (WHERE rain_mm IS NULL) OVER w24 AS rain_24h_imputed_hours,
       rain_mm IS NULL AS rain_1h_imputed
FROM inputs
WINDOW w6 AS (ORDER BY hour_utc ROWS BETWEEN 5 PRECEDING AND CURRENT ROW),
       w24 AS (ORDER BY hour_utc ROWS BETWEEN 23 PRECEDING AND CURRENT ROW);

CREATE OR REPLACE VIEW v_routing_dickson_zero AS
SELECT station_id, observed_at, discharge_m3_s, false AS is_imputed, source_file_id
FROM routing_discharge WHERE station_id='05CB007'
UNION ALL
SELECT '05CB007', grid.source_at, 0::double precision, true, NULL::integer
FROM generate_series('2026-06-30 18:05+00'::timestamptz,
                     '2026-07-06 15:10+00'::timestamptz, interval '5 minutes') grid(source_at)
WHERE NOT EXISTS (
    SELECT 1 FROM routing_discharge o WHERE o.station_id='05CB007'
      AND o.observed_at=grid.source_at
);

CREATE OR REPLACE VIEW v_routing_short_arrivals AS
WITH candidates AS (
    SELECT h.station_id, h.target_at,
           n.observed_at AS observed_source_at, n.discharge_m3_s, n.source_file_id,
           h.proposed_method, h.desired_epoch_hour
    FROM routing_short_lag_calibration h
    LEFT JOIN LATERAL (
        SELECT o.observed_at, o.discharge_m3_s, o.source_file_id
        FROM routing_discharge o
        WHERE o.station_id=h.station_id
          AND o.observed_at BETWEEN to_timestamp(h.desired_epoch_hour*3600)-interval '150.001 seconds'
                                AND to_timestamp(h.desired_epoch_hour*3600)+interval '150.001 seconds'
          AND o.observed_at<h.target_at
          AND abs(extract(epoch FROM o.observed_at)::double precision/3600-h.desired_epoch_hour)
                  <=2.5/60.0+0.0000001
        ORDER BY abs(extract(epoch FROM o.observed_at)::double precision/3600-h.desired_epoch_hour),o.observed_at
        LIMIT 1
    ) n ON true
), chronology AS (
    SELECT *, max(observed_source_at) OVER (
        PARTITION BY station_id ORDER BY target_at
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS latest_prior_source_at
    FROM candidates
), accepted AS (
    SELECT *, observed_source_at IS NOT NULL
          AND (latest_prior_source_at IS NULL OR observed_source_at>=latest_prior_source_at) AS valid
    FROM chronology
), source AS (
    SELECT a.station_id, a.target_at,
           CASE WHEN a.valid THEN a.observed_source_at WHEN a.station_id='05CB007'
                THEN coalesce(z.observed_at,to_timestamp(a.desired_epoch_hour*3600)) END AS source_at,
           CASE WHEN a.valid THEN a.discharge_m3_s
                WHEN a.station_id='05CB007' THEN 0::double precision END AS discharge_m3_s,
           a.station_id='05CB007' AND NOT a.valid AS is_imputed,
           CASE WHEN a.valid THEN a.source_file_id END AS source_file_id,
           CASE WHEN a.valid THEN a.proposed_method WHEN z.is_imputed THEN 'designated_dickson_gap_zero'
                WHEN a.station_id='05CB007' AND a.observed_source_at IS NULL THEN 'dickson_unmatched_zero_missing'
                WHEN a.station_id='05CB007' THEN 'dickson_unmatched_zero_chronology'
                WHEN a.observed_source_at IS NULL THEN 'unmatched_source_gap_or_outside_archive'
                ELSE 'unmatched_nonmonotone_lag_transition' END AS matching_method
    FROM accepted a
    LEFT JOIN v_routing_dickson_zero z ON NOT a.valid AND a.station_id='05CB007'
      AND z.is_imputed AND z.observed_at=a.target_at-interval '10 hours 30 minutes'
)
SELECT s.station_id, s.source_at, s.target_at AS arrival_at, s.discharge_m3_s, s.is_imputed,
       s.source_file_id, w.hour_utc AS rain_hour_utc, w.rain_1h_mm, w.rain_6h_mm,
       w.rain_24h_mm, w.rain_1h_imputed, w.rain_24h_imputed_hours, s.matching_method
FROM source s
LEFT JOIN v_routing_weather w ON w.hour_utc=date_bin(interval '1 hour', s.source_at,
    '2000-01-01 00:00:00+00'::timestamptz)-interval '1 hour';

CREATE OR REPLACE VIEW v_routing_medicine_parcels AS
WITH spaced AS (
    SELECT observed_at, discharge_m3_s, source_file_id,
           observed_at-lag(observed_at) OVER (ORDER BY observed_at) AS gap
    FROM routing_discharge WHERE station_id='05CC007'
), ordered AS MATERIALIZED (
    SELECT *, row_number() OVER w AS n,
        count(*) FILTER (WHERE gap>interval '30 minutes') OVER w AS wide_gaps
    FROM spaced WINDOW w AS (ORDER BY observed_at)
), context AS (
    SELECT m.observed_at, m.discharge_m3_s, m.source_file_id,
           m.discharge_m3_s-coalesce(p0.discharge_m3_s,p1.discharge_m3_s,p2.discharge_m3_s,p3.discharge_m3_s) AS rise,
           coalesce(p0.discharge_m3_s,p1.discharge_m3_s,p2.discharge_m3_s,p3.discharge_m3_s) AS baseline,
           m.n-coalesce(p0.n,p1.n,p2.n,p3.n)+1 AS coverage_n,
           m.wide_gaps=coalesce(p0.wide_gaps,p1.wide_gaps,p2.wide_gaps,p3.wide_gaps) AS no_wide_gap,
           extract(epoch FROM (m.observed_at-coalesce(p0.observed_at,p1.observed_at,p2.observed_at,p3.observed_at)))/300+1 AS expected_n
    FROM ordered m
    LEFT JOIN ordered p0 ON p0.observed_at=m.observed_at-interval '6 hours'
    LEFT JOIN ordered p1 ON p0.n IS NULL AND p1.observed_at=m.observed_at-interval '6 hours 5 minutes'
    LEFT JOIN ordered p2 ON p0.n IS NULL AND p1.n IS NULL AND p2.observed_at=m.observed_at-interval '6 hours 10 minutes'
    LEFT JOIN ordered p3 ON p0.n IS NULL AND p1.n IS NULL AND p2.n IS NULL AND p3.observed_at=m.observed_at-interval '6 hours 15 minutes'
), lags AS (
    SELECT *, CASE WHEN coverage_n>=0.75*expected_n AND no_wide_gap THEN
        round(603-243*greatest(0,least(1,(rise-0.6)/0.6,(rise/greatest(baseline,0.1)-0.05)/0.05)))::integer
        ELSE 603 END AS lag_bins
    FROM context
)
SELECT m.observed_at AS source_at, m.source_file_id, m.discharge_m3_s,
       m.discharge_m3_s*300 AS parcel_m3, m.lag_bins, m.observed_at+m.lag_bins*interval '5 minutes' AS arrival_center_at,
       coalesce(coverage_n>=0.75*expected_n AND no_wide_gap,false) AS rise_history_adequate,
       w.hour_utc AS rain_hour_utc, w.rain_1h_mm, w.rain_6h_mm, w.rain_24h_mm,
       w.rain_1h_imputed, w.rain_24h_imputed_hours
FROM lags m
LEFT JOIN v_routing_weather w ON w.hour_utc=date_bin(interval '1 hour', m.observed_at, '2000-01-01 00:00:00+00'::timestamptz)-interval '1 hour';

CREATE OR REPLACE VIEW v_routing_medicine_arrivals AS
WITH centers AS (
    SELECT arrival_center_at AS center_at, count(*) AS parcels,
           min(source_at) AS first_source_at, max(source_at) AS last_source_at,
           sum(parcel_m3) AS mass,
           sum(parcel_m3*coalesce(rain_1h_mm,0)) AS rain_1h_mass,
           sum(parcel_m3*coalesce(rain_6h_mm,0)) AS rain_6h_mass,
           sum(parcel_m3*coalesce(rain_24h_mm,0)) AS rain_24h_mass,
           sum(parcel_m3) FILTER (WHERE NOT rain_1h_imputed) AS observed_rain_mass,
           sum(parcel_m3*(24-coalesce(rain_24h_imputed_hours,24))) AS rain_24h_coverage_mass
    FROM v_routing_medicine_parcels GROUP BY arrival_center_at
), spread AS (
    SELECT c.*, center_at+k*interval '5 minutes' AS arrival_at,
           (37-abs(k))/1369.0::double precision AS weight, k
    FROM centers c CROSS JOIN generate_series(-36,36) o(k)
)
SELECT arrival_at, sum(mass*weight)/300 AS discharge_m3_s, sum(parcels)::integer AS parcel_count,
       coalesce(sum(parcels) FILTER (WHERE k=0),0)::integer AS arriving_centers,
       min(first_source_at) AS first_source_at, max(last_source_at) AS last_source_at,
       coalesce(sum(rain_1h_mass*weight)/nullif(sum(mass*weight),0),0) AS rain_1h_mm,
       coalesce(sum(rain_6h_mass*weight)/nullif(sum(mass*weight),0),0) AS rain_6h_mm,
       coalesce(sum(rain_24h_mass*weight)/nullif(sum(mass*weight),0),0) AS rain_24h_mm,
       coalesce(sum(observed_rain_mass*weight)/nullif(sum(mass*weight),0),0) AS rain_1h_observed_volume_fraction,
       coalesce(sum(rain_24h_coverage_mass*weight)/nullif(sum(mass*weight)*24,0),0) AS rain_24h_observed_volume_fraction
FROM spread GROUP BY arrival_at;

CREATE OR REPLACE VIEW v_routing_arrival_audit AS
WITH medicine_sequence AS (
    SELECT observed_at, lag(observed_at) OVER(ORDER BY observed_at) AS prior_at
    FROM routing_discharge WHERE station_id='05CC007'
), medicine_bounds AS (
    SELECT min(observed_at) AS first_at, max(observed_at) AS last_at FROM medicine_sequence
), gap_ranges AS (
    SELECT tstzrange(prior_at+interval '27 hours 5 minutes',
                     observed_at+interval '53 hours 15 minutes', '[)') AS uncertain_range
    FROM medicine_sequence WHERE observed_at-prior_at>interval '5 minutes'
    UNION ALL
    SELECT tstzrange(NULL,first_at+interval '53 hours 15 minutes','[)') FROM medicine_bounds
    UNION ALL
    SELECT tstzrange(last_at+interval '27 hours 5 minutes',NULL,'[)') FROM medicine_bounds
), uncertain AS (
    SELECT range_agg(uncertain_range) AS uncertain_times FROM gap_ranges
)
SELECT q.observed_at AS arrival_at, q.discharge_m3_s AS red_deer_observed_q_m3_s,
       q.source_file_id AS red_deer_source_file_id,
       d.discharge_m3_s AS dickson_q_m3_s, d.source_at AS dickson_source_at,
       d.source_file_id AS dickson_source_file_id, d.is_imputed AS dickson_is_imputed,
       d.rain_hour_utc AS dickson_rain_hour_utc, d.rain_1h_mm AS dickson_rain_1h_mm,
       d.rain_6h_mm AS dickson_rain_6h_mm, d.rain_24h_mm AS dickson_rain_24h_mm,
       d.rain_1h_imputed AS dickson_rain_1h_imputed, d.rain_24h_imputed_hours::bigint AS dickson_rain_24h_imputed_hours,
       l.discharge_m3_s AS little_red_deer_q_m3_s, l.source_at AS little_red_deer_source_at,
       l.source_file_id AS little_red_deer_source_file_id,
       l.rain_hour_utc AS little_red_deer_rain_hour_utc, l.rain_1h_mm AS little_red_deer_rain_1h_mm,
       l.rain_6h_mm AS little_red_deer_rain_6h_mm, l.rain_24h_mm AS little_red_deer_rain_24h_mm,
       l.rain_1h_imputed AS little_red_deer_rain_1h_imputed, l.rain_24h_imputed_hours::bigint AS little_red_deer_rain_24h_imputed_hours,
       m.discharge_m3_s AS medicine_q_m3_s, m.first_source_at AS medicine_first_source_at,
       m.last_source_at AS medicine_last_source_at, m.parcel_count AS medicine_parcel_count,
       m.arriving_centers AS medicine_arriving_centers,
       q.observed_at <@ u.uncertain_times AS medicine_possible_source_gap,
       m.rain_1h_mm AS medicine_rain_1h_mm,
       m.rain_6h_mm AS medicine_rain_6h_mm, m.rain_24h_mm AS medicine_rain_24h_mm,
       m.rain_1h_observed_volume_fraction AS medicine_rain_1h_observed_volume_fraction,
       m.rain_24h_observed_volume_fraction AS medicine_rain_24h_observed_volume_fraction,
       d.discharge_m3_s IS NOT NULL AND l.discharge_m3_s IS NOT NULL AND m.discharge_m3_s IS NOT NULL AS hydro_complete,
       array_remove(ARRAY[CASE WHEN d.discharge_m3_s IS NULL THEN '05CB007' END,
                    CASE WHEN l.discharge_m3_s IS NULL THEN '05CB001' END,
                    CASE WHEN m.discharge_m3_s IS NULL THEN '05CC007' END],NULL) AS missing_upstream_stations,
       d.matching_method AS dickson_matching_method,
       l.matching_method AS little_red_deer_matching_method,
       CASE WHEN e.approximate_depth_m>=0 THEN e.approximate_depth_m END AS endpoint_depth_proxy_m,
       coalesce(e.depth_status,'no_depth_proxy_row') AS endpoint_depth_status,
       true AS retrospective_match_uses_terminal_history,
       d.possible_source_gap AS dickson_possible_source_gap,
       l.possible_source_gap AS little_red_deer_possible_source_gap,
       d.parcel_count AS dickson_arrival_parcel_count,
       l.parcel_count AS little_red_deer_arrival_parcel_count,
       d.volume_m3 AS dickson_arrival_volume_m3, l.volume_m3 AS little_red_deer_arrival_volume_m3,
       m.discharge_m3_s*300 AS medicine_arrival_volume_m3,
       d.discharge_m3_s+l.discharge_m3_s+m.discharge_m3_s AS upstream_total_q_m3_s,
       d.volume_m3+l.volume_m3+m.discharge_m3_s*300 AS upstream_total_volume_m3
FROM routing_discharge q CROSS JOIN uncertain u
LEFT JOIN v_routing_short_volume_arrivals d ON d.station_id='05CB007' AND d.arrival_at=q.observed_at
LEFT JOIN v_routing_short_volume_arrivals l ON l.station_id='05CB001' AND l.arrival_at=q.observed_at
LEFT JOIN v_routing_medicine_arrivals m ON m.arrival_at=q.observed_at
LEFT JOIN v_observations_bed_proxy_context e ON e.station_id=q.station_id AND e.observed_at=q.observed_at
    AND e.bundle_id='475b8778e3a937b68cc06f50ca556c126b3a5eb7c76672bd344ae9ee4dd66abf'
WHERE q.station_id='05CC002';

CREATE OR REPLACE VIEW v_routing_training AS
SELECT arrival_at, dickson_q_m3_s, little_red_deer_q_m3_s, medicine_q_m3_s,
       dickson_rain_1h_mm, dickson_rain_6h_mm, dickson_rain_24h_mm,
       little_red_deer_rain_1h_mm, little_red_deer_rain_6h_mm, little_red_deer_rain_24h_mm,
       medicine_rain_1h_mm, medicine_rain_6h_mm, medicine_rain_24h_mm,
       endpoint_depth_proxy_m AS label_endpoint_depth_proxy_m, upstream_total_q_m3_s, upstream_total_volume_m3
FROM v_routing_arrival_audit WHERE hydro_complete AND endpoint_depth_proxy_m IS NOT NULL;

