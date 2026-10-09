"""Verify lossless normalization of the provider-specific station index."""
import csv
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from rdr.station_index import HEADER, normalize_station_index, parse_provider_line


class StationIndexTests(unittest.TestCase):
    def test_valid_csv_preserves_commas_quotes_and_empty_fields(self):
        fields = ['05CA009', 'RIVER, AT "BRIDGE"', '51\u00b003\'41"', '', '']
        buffer = io.StringIO(newline='')
        csv.writer(buffer).writerow(fields)
        actual, repairs = parse_provider_line(buffer.getvalue().rstrip('\r\n'))
        self.assertEqual(actual, fields)
        self.assertEqual(repairs, 0)

    def test_provider_quotes_and_padding_are_normalized_without_changing_original(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder)/'source.csv'
            target = Path(folder)/'normalized.csv'
            line = '05BM017,"......CANAL "B" NEAR HEADGATE",51\u00b003\'41",113\u00b049\'02"' + ',' * 15
            body = (','.join(HEADER) + '\r\n' + line + '\r\n\r\nFooter note\r\n').encode('utf-8-sig')
            source.write_bytes(body)
            normalize_station_index(source, target)
            with target.open(encoding='utf-8-sig', newline='') as handle:
                rows = list(csv.reader(handle, strict=True))
            self.assertTrue(all(len(row) == 18 for row in rows))
            self.assertEqual(rows[1][1], '......CANAL "B" NEAR HEADGATE')
            self.assertEqual(rows[1][2], '51\u00b003\'41"')
            self.assertEqual(rows[-1][0], 'Footer note')
            self.assertEqual(source.read_bytes(), body)
            provenance = json.loads(target.with_suffix('.csv.meta.json').read_text())
            self.assertEqual(provenance['source_sha256'], hashlib.sha256(body).hexdigest())
            self.assertEqual(provenance['normalized_sha256'], hashlib.sha256(target.read_bytes()).hexdigest())

    def test_ambiguous_or_nonempty_extra_columns_are_rejected(self):
        with self.assertRaises(ValueError):
            parse_provider_line('05CA009,"unclosed name')
        with tempfile.TemporaryDirectory() as folder:
            source, target = Path(folder)/'source.csv', Path(folder)/'normalized.csv'
            source.write_text(','.join(HEADER) + '\n' + ','.join(['05CA009'] + [''] * 17 + ['unexpected']), encoding='utf-8')
            with self.assertRaises(ValueError):
                normalize_station_index(source, target)
            self.assertFalse(target.exists())
            with self.assertRaises(ValueError):
                normalize_station_index(source, source)


if __name__ == '__main__':
    unittest.main()
