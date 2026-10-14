"""Check availability classification for bounded source snapshots offline."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from API import snapshot_scope


class SnapshotTests(unittest.TestCase):
    def sample(self, properties, kind="water", sid="test"):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "response.json"
            path.write_text(json.dumps({"features": [
                {"properties": p, "geometry": None} for p in properties
            ]}), encoding="utf-8")
            with patch.object(snapshot_scope, "ROOT", root), patch.object(
                snapshot_scope, "fetch", return_value=path
            ):
                return snapshot_scope.sample((kind, sid), "offline")

    def test_zero_flow_is_data_and_null_values_are_not(self):
        row = {"STATION_NUMBER": "test", "DATETIME": "2026-10-12T00:00:00Z",
               "LEVEL": None, "DISCHARGE": 0}
        self.assertEqual(self.sample([row])["numeric_record_count"], 1)
        row["DISCHARGE"] = None
        self.assertEqual(self.sample([row])["status"], "no_numeric_observations")

    def test_empty_response_is_distinct_from_filter_failure(self):
        self.assertEqual(self.sample([])["status"], "no_numeric_observations")
        self.assertEqual(self.sample([{"STATION_NUMBER": "wrong"}])["status"], "request_failed")

    def test_precipitation_requires_numerical_valid_measurement(self):
        row = {"msc_id-value": "test", "date_tm-value": "2026-10-12T00:00:00Z",
               "pcpn_amt_pst1hr": 0, "pcpn_amt_pst1hr-qa": 1}
        self.assertEqual(self.sample([row], "weather")["numeric_record_count"], 1)
        row["pcpn_amt_pst1hr-qa"] = 0
        self.assertEqual(self.sample([row], "weather")["numeric_record_count"], 0)

    def test_latest_valid_observation_not_latest_empty_record(self):
        rows = [{"STATION_NUMBER": "test", "DATETIME": t, "LEVEL": level}
                for t, level in [("2026-10-12T01:00:00Z", None),
                                 ("2026-10-12T00:00:00Z", 2.5)]]
        result = self.sample(rows)
        self.assertEqual(result["latest_observation"], "2026-10-12T00:00:00Z")
        self.assertIsNone(result["actual_transmission_time"])


if __name__ == "__main__":
    unittest.main()
