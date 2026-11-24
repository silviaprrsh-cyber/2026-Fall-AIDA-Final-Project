-- Forward-volume replacement for the two short retrospective routes.
-- Install after routing_views.sql and after routing_short_lag_calibration exists.
-- This does NOT make the terminal-history-derived calibration independent or
-- causal. It changes volume accounting, not the historical timing evidence.
-- Every observed five-minute Q contributes Q*300 exactly once. There is no
-- source reuse, chronology rejection, interpolation across outages, or spread.

CREATE INDEX IF NOT EXISTS routing_short_lag_source_lookup_idx
    ON routing_short_lag_calibration (station_id, desired_epoch_hour, target_at);

CREATE OR REPLACE VIEW v_routing_short_volume_parcels AS
WITH routes(station_id,min_lag,max_lag,fallback_lag) AS (
    VALUES ('05CB007'::text, interval '2 hours', interval '30 hours', interval '10 hours 30 minutes'),
           ('05CB001'::text, interval '1 hour', interval '36 hours', interval '9 hours')
), assigned AS (
    SELECT o.station_id, o.observed_at AS source_at, o.discharge_m3_s,
           o.source_file_id,
           coalesce(h.target_at,
               date_bin(interval '5 minutes',o.observed_at+
                        (n.target_at-to_timestamp(n.desired_epoch_hour*3600))+interval '150 seconds',
                        '2000-01-01 00:00:00+00'::timestamptz),
               date_bin(interval '5 minutes',o.observed_at+r.fallback_lag+interval '150 seconds',
                        '2000-01-01 00:00:00+00'::timestamptz)) AS arrival_at,
           coalesce(h.target_at,n.target_at) AS calibration_target_at,
           coalesce(h.desired_epoch_hour,n.desired_epoch_hour) AS calibration_desired_epoch_hour,
           coalesce(h.proposed_method,n.proposed_method) AS calibration_method,
           h.target_at IS NULL AS lag_is_fallback,
           CASE WHEN h.target_at IS NOT NULL THEN 'inverse_historical_hint:'||h.proposed_method
                WHEN n.target_at IS NOT NULL THEN 'nearby_historical_lag:'||n.proposed_method
                WHEN o.station_id='05CB007' THEN 'forward_nominal_10h30m_no_local_hint'
                ELSE 'forward_nominal_9h_no_local_hint' END AS matching_method
    FROM routing_discharge o
    JOIN routes r USING (station_id)
    LEFT JOIN LATERAL (
        -- Bounded source-time range uses the index above. At most one target
        -- is selected per measured source. Earlier target breaks equal errors.
        -- The half-bin tolerance is inherited from the old source lookup;
        -- without a local inverse, first reuse a nearby historical lag below.
        SELECT c.target_at,c.desired_epoch_hour,c.proposed_method
        FROM routing_short_lag_calibration c
        WHERE c.station_id=o.station_id
          AND c.desired_epoch_hour BETWEEN extract(epoch FROM o.observed_at)::double precision/3600-2.5/60.0-0.0000001
                                       AND extract(epoch FROM o.observed_at)::double precision/3600+2.5/60.0+0.0000001
          AND c.target_at BETWEEN o.observed_at+r.min_lag AND o.observed_at+r.max_lag
          AND c.target_at=date_bin(interval '5 minutes',c.target_at,'2000-01-01 00:00:00+00'::timestamptz)
        ORDER BY abs(c.desired_epoch_hour-extract(epoch FROM o.observed_at)::double precision/3600),c.target_at
        LIMIT 1
    ) h ON true
    LEFT JOIN LATERAL (
        -- A local inverse can be absent at archive edges or lag transitions.
        -- Reuse the nearest historical lag within three source hours, but add
        -- that lag to THIS source time. Never collapse an archive tail onto
        -- the anchor target. This index range is inspected only on an inverse
        -- miss; the regular case reads just the half-bin candidate range.
        SELECT c.target_at,c.desired_epoch_hour,c.proposed_method
        FROM routing_short_lag_calibration c
        WHERE h.target_at IS NULL AND c.station_id=o.station_id
          AND c.desired_epoch_hour BETWEEN extract(epoch FROM o.observed_at)::double precision/3600-3
                                       AND extract(epoch FROM o.observed_at)::double precision/3600+3
          AND c.desired_epoch_hour BETWEEN extract(epoch FROM c.target_at-r.max_lag)::double precision/3600
                                       AND extract(epoch FROM c.target_at-r.min_lag)::double precision/3600
        ORDER BY abs(c.desired_epoch_hour-extract(epoch FROM o.observed_at)::double precision/3600),c.target_at
        LIMIT 1
    ) n ON true
)
SELECT a.station_id,a.source_at,a.arrival_at,a.discharge_m3_s,a.source_file_id,
       a.discharge_m3_s*300 AS parcel_m3,
       a.calibration_target_at,a.calibration_desired_epoch_hour,a.calibration_method,
       a.lag_is_fallback,a.matching_method,
       w.hour_utc AS rain_hour_utc,coalesce(w.rain_1h_mm,0) AS rain_1h_mm,
       coalesce(w.rain_6h_mm,0) AS rain_6h_mm,coalesce(w.rain_24h_mm,0) AS rain_24h_mm,
       coalesce(w.rain_1h_imputed,true) AS rain_1h_imputed,
       coalesce(w.rain_24h_imputed_hours,24::bigint) AS rain_24h_imputed_hours
FROM assigned a
LEFT JOIN v_routing_weather w ON w.hour_utc=date_bin(interval '1 hour',a.source_at,
    '2000-01-01 00:00:00+00'::timestamptz)-interval '1 hour';

CREATE OR REPLACE VIEW v_routing_short_volume_arrivals AS
WITH arrivals AS MATERIALIZED (
    SELECT station_id,arrival_at,min(source_at) AS first_source_at,max(source_at) AS last_source_at,
           CASE WHEN count(DISTINCT source_file_id)=1 THEN min(source_file_id) END AS source_file_id,
           count(*)::integer AS parcel_count,sum(parcel_m3) AS volume_m3,
           min(rain_hour_utc) AS rain_hour_utc,
           -- Zero-flow observed contributors still carry source weather. Their
           -- arithmetic mean is only the undefined zero-total-volume fallback.
           coalesce(sum(parcel_m3*rain_1h_mm)/nullif(sum(parcel_m3),0),avg(rain_1h_mm),0) AS rain_1h_mm,
           coalesce(sum(parcel_m3*rain_6h_mm)/nullif(sum(parcel_m3),0),avg(rain_6h_mm),0) AS rain_6h_mm,
           coalesce(sum(parcel_m3*rain_24h_mm)/nullif(sum(parcel_m3),0),avg(rain_24h_mm),0) AS rain_24h_mm,
           bool_or(rain_1h_imputed) AS rain_1h_imputed,
           max(rain_24h_imputed_hours) AS rain_24h_imputed_hours,
           string_agg(DISTINCT matching_method,';' ORDER BY matching_method) AS matching_method,
           coalesce(sum(parcel_m3) FILTER(WHERE NOT rain_1h_imputed)/nullif(sum(parcel_m3),0),0)
               AS rain_1h_observed_volume_fraction,
           coalesce(sum(parcel_m3*(24-rain_24h_imputed_hours))/nullif(sum(parcel_m3)*24,0),0)
               AS rain_24h_observed_volume_fraction
    FROM v_routing_short_volume_parcels
    GROUP BY station_id,arrival_at
), dickson_empty AS (
    -- Only Dickson gets a post-routing target zero. No source interval is
    -- invented and these rows have zero parcel_count and zero volume_m3.
    SELECT q.observed_at AS arrival_at,
           CASE WHEN h.desired_epoch_hour BETWEEN
                    extract(epoch FROM q.observed_at-interval '30 hours')::double precision/3600 AND
                    extract(epoch FROM q.observed_at-interval '2 hours')::double precision/3600
                THEN to_timestamp(h.desired_epoch_hour*3600)
                ELSE q.observed_at-interval '10 hours 30 minutes' END AS intended_source_at
    FROM routing_discharge q
    LEFT JOIN routing_short_lag_calibration h ON h.station_id='05CB007' AND h.target_at=q.observed_at
    WHERE q.station_id='05CC002' AND NOT EXISTS (
        SELECT 1 FROM arrivals a WHERE a.station_id='05CB007' AND a.arrival_at=q.observed_at
    )
), combined AS (
    SELECT a.station_id,a.first_source_at AS source_at,a.arrival_at,a.volume_m3/300 AS discharge_m3_s,
           false AS is_imputed,a.source_file_id,a.rain_hour_utc,a.rain_1h_mm,a.rain_6h_mm,a.rain_24h_mm,
           a.rain_1h_imputed,a.rain_24h_imputed_hours,a.matching_method,
           a.parcel_count,a.volume_m3,a.first_source_at,a.last_source_at,
           a.rain_1h_observed_volume_fraction,a.rain_24h_observed_volume_fraction
    FROM arrivals a
    UNION ALL
    SELECT '05CB007',e.intended_source_at,e.arrival_at,0::double precision,
           true,NULL::integer,w.hour_utc,coalesce(w.rain_1h_mm,0),coalesce(w.rain_6h_mm,0),coalesce(w.rain_24h_mm,0),
           coalesce(w.rain_1h_imputed,true),coalesce(w.rain_24h_imputed_hours,24::bigint),
           'dickson_no_routed_parcel_zero',0::integer,0::double precision,NULL::timestamptz,NULL::timestamptz,
           0::double precision,0::double precision
    FROM dickson_empty e
    LEFT JOIN v_routing_weather w ON w.hour_utc=date_bin(interval '1 hour',e.intended_source_at,
        '2000-01-01 00:00:00+00'::timestamptz)-interval '1 hour'
), routes(station_id,min_lag,max_lag) AS (
    VALUES ('05CB007'::text,interval '2 hours',interval '30 hours'),
           ('05CB001'::text,interval '1 hour',interval '36 hours')
), source_sequence AS (
    SELECT o.station_id,o.observed_at,
           lag(o.observed_at) OVER(PARTITION BY o.station_id ORDER BY o.observed_at) AS prior_at
    FROM routing_discharge o JOIN routes r USING(station_id)
), bounds AS (
    SELECT station_id,min(observed_at) AS first_at,max(observed_at) AS last_at
    FROM source_sequence GROUP BY station_id
), uncertain_ranges AS (
    -- A warning only: absent input may have contributed anywhere permitted by
    -- this route's lag envelope. Existing numeric arrivals are not nulled out.
    SELECT s.station_id,tstzrange(s.prior_at+interval '5 minutes'+r.min_lag,
                                 s.observed_at+r.max_lag,'[)') AS uncertain_range
    FROM source_sequence s JOIN routes r USING(station_id)
    WHERE s.observed_at-s.prior_at>interval '5 minutes'
    UNION ALL
    SELECT b.station_id,tstzrange(NULL,b.first_at+r.max_lag,'[)')
    FROM bounds b JOIN routes r USING(station_id)
    UNION ALL
    SELECT b.station_id,tstzrange(b.last_at+interval '5 minutes'+r.min_lag,NULL,'[)')
    FROM bounds b JOIN routes r USING(station_id)
), uncertain AS (
    SELECT station_id,range_agg(uncertain_range) AS uncertain_times
    FROM uncertain_ranges GROUP BY station_id
)
SELECT c.station_id,c.source_at,c.arrival_at,c.discharge_m3_s,c.is_imputed,c.source_file_id,
       c.rain_hour_utc,c.rain_1h_mm,c.rain_6h_mm,c.rain_24h_mm,c.rain_1h_imputed,
       c.rain_24h_imputed_hours,c.matching_method,c.parcel_count,c.volume_m3,
       c.first_source_at,c.last_source_at,
       coalesce(c.arrival_at <@ u.uncertain_times,true) AS possible_source_gap,
       c.rain_1h_observed_volume_fraction,c.rain_24h_observed_volume_fraction
FROM combined c LEFT JOIN uncertain u USING(station_id);
