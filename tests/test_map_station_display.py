"""Test observation-time colors and unique station markers without network access."""

from datetime import date, datetime, timezone
import unittest

from scripts.update_scoped_stations import partition, recent, window_start


class StationDisplayTests(unittest.TestCase):
    def setUp(self):
        self.rules = {"as_of_local_date": "2026-10-13", "recent_calendar_months": 3,
                      "time_zone": "America/Edmonton", "excluded_station_ids": ["EXCLUDED"]}
        self.end = datetime(2026, 10, 14, 0, 43, 19, tzinfo=timezone.utc)

    def test_calendar_month_boundary_and_timezone(self):
        start = window_start(date(2026, 10, 13), 3, "America/Edmonton")
        self.assertEqual(start.isoformat(), "2026-07-13T00:00:00-06:00")
        self.assertTrue(recent("2026-07-13T06:00:00Z", start, self.end))
        self.assertFalse(recent("2026-07-13T05:59:59Z", start, self.end))
        self.assertFalse(recent("2026-10-14T01:00:00Z", start, self.end))
        self.assertEqual(window_start(date(2026, 5, 31), 3, "America/Edmonton").date(), date(2026, 2, 28))

    def test_daily_dates_do_not_acquire_fabricated_times(self):
        start = window_start(date(2026, 10, 13), 3, "America/Edmonton")
        self.assertTrue(recent("2026-07-13", start, self.end))
        self.assertFalse(recent("2026-07-12", start, self.end))
        self.assertFalse(recent("2026-10-14", start, self.end))

    def test_overlapping_history_live_and_exclusions(self):
        def summary(sid):
            return {"station_id": sid, "role": "tributary_channel_station", "has_data": "Y",
                    "longitude": -114.0, "latitude": 52.0, "discharge_m3_s_last_date": "2024-10-31"}
        f = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-114,52]},
             "properties": {"station_id": "B", "latest_observation_utc": "2026-10-12T12:00:00Z"}}
        blue,yellow = partition([f], [summary(s) for s in ("B","Y","EXCLUDED")], [], self.rules, self.end)
        self.assertEqual([x['id'] for x in blue], ["B"])
        self.assertEqual([x['id'] for x in yellow], ["Y"])

    def test_missing_numeric_sample_is_not_recent_by_receipt_date(self):
        s = {"station_id": "Y", "role": "tributary_channel_station", "has_data": "Y",
             "longitude": -114, "latitude": 52, "discharge_m3_s_last_date": "1922-10-31"}
        blue, yellow = partition([], [s], [{"station_id":"Y", "status":"no_numeric_observations",
            "received_at_utc":"2026-10-14T00:40:00Z"}], self.rules, self.end)
        self.assertFalse(blue)
        self.assertEqual(yellow[0]["properties"]["map_color"], "yellow")

    def test_lake_reference_replaces_excluded_creek_without_claiming_recent_absence(self):
        self.rules.update(reference_station_ids=["LAKE"], yellow_reference_ids=["LAKE"],
                          excluded_station_ids=["CREEK"])
        summaries = [{"station_id": sid, "role": role, "has_data": "Y", "longitude": -114,
                      "latitude": 52, "level_m_last_date": "2024-10-31"}
                     for sid, role in [("LAKE", "lake_level_reference"), ("CREEK", "tributary_channel_station")]]
        blue, yellow = partition([], summaries, [], self.rules, self.end)
        self.assertFalse(blue)
        self.assertEqual([f["id"] for f in yellow], ["LAKE"])
        self.assertEqual(yellow[0]["properties"]["recent_data"], "unknown")
        blue2, yellow2 = partition(yellow, summaries, [], self.rules, self.end)
        self.assertEqual((blue, yellow), (blue2, yellow2))


if __name__ == "__main__":
    unittest.main()
