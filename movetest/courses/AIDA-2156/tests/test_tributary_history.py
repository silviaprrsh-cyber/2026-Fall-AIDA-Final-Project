"""Verify daily-data paging, identity checks and missing-value semantics offline."""

import json
import csv
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from API import download_tributary_history as download
from eda_tools.prepare_tributary_history import normalize, summarize, write_csv


def feature(day="2000-01-01", sid="05CC004", value=0):
    return {"id": sid + "." + day, "properties": {"STATION_NUMBER": sid,
            "DATE": day, "IDENTIFIER": sid + "." + day, "DISCHARGE": value, "LEVEL": None}}


class HistoryTests(unittest.TestCase):
    def test_csv_rebuild_preserves_date_precision_null_zero_and_symbols(self):
        rows = normalize([feature()], "05CC004", "page.json", "2026-10-13T04:43:19.853572+00:00")
        rows[0]["discharge_symbol"] = 'Estimated, "revised"'
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "daily.csv"
            write_csv(path, rows)
            with path.open(encoding="utf-8", newline="") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["received_at_utc"], rows[0]["received_at_utc"])
            self.assertEqual(row["date"], "2000-01-01")
            self.assertEqual(row["level_m"], "")
            self.assertEqual(row["discharge_m3_s"], "0")
            self.assertEqual(row["discharge_symbol"], rows[0]["discharge_symbol"])

    def test_zero_missing_and_date_precision(self):
        rows = normalize([feature(), feature("2000-01-02", value=None)], "05CC004", "page.json", "received")
        self.assertEqual(rows[0]["discharge_m3_s"], 0)
        self.assertIsNone(rows[1]["discharge_m3_s"])
        self.assertEqual(rows[0]["date"], "2000-01-01")
        result = summarize({"parent_chain": ["SYLVAN CREEK"]}, rows)
        self.assertEqual(result["discharge_m3_s_count"], 1)
        self.assertEqual(result["both_missing_rows"], 1)
        self.assertEqual(result["has_data"], "Y")

    def test_mismatched_station_and_instantaneous_time_rejected(self):
        for row in (feature(sid="OTHER"), feature(day="2000-01-01T00:00:00Z"), feature(value=True)):
            with self.assertRaises(ValueError):
                normalize([row], "05CC004", "page.json", "received")

    def test_duplicate_daily_date_rejected(self):
        rows = normalize([feature(), feature()], "05CC004", "page.json", "received")
        with self.assertRaises(ValueError):
            summarize({"parent_chain": []}, rows)

    def page_result(self, pages):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            paths = []
            for i, page in enumerate(pages):
                path = root / f"{i}.json"
                path.write_text(json.dumps(page), encoding="utf-8")
                paths.append(path)
            with patch.object(download, "ROOT", root), patch.object(download, "acquire", side_effect=paths):
                return download.station_history("05CC004", "test")

    def test_complete_next_page_and_incomplete_count(self):
        first = {"features": [feature()], "numberMatched": 2, "links": [{"rel": "next",
                 "href": download.BASE + "/hydrometric-daily-mean/items?offset=1"}]}
        last = {"features": [feature("2000-01-02")], "numberMatched": 2}
        result = self.page_result([first, last])
        self.assertTrue(result["complete"])
        self.assertEqual(result["record_count"], 2)
        self.assertFalse(self.page_result([{**last, "numberMatched": 3}])["complete"])

    def test_duplicate_and_untrusted_next_link_rejected(self):
        first = {"features": [feature()], "numberMatched": 2, "links": [{"rel": "next",
                 "href": download.BASE + "/hydrometric-daily-mean/items?offset=1"}]}
        self.assertFalse(self.page_result([first, {"features": [feature()]}])["complete"])
        first["links"][0]["href"] = "https://example.com/history"
        self.assertFalse(self.page_result([first])["complete"])


if __name__ == "__main__":
    unittest.main()
