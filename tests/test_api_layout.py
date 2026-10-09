"""Verify source separation, cache reuse and safe paths without contacting providers."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import requests

from rdr.paths import ROOT, resolve_archived_path, source_for_url, source_relative_path


class SourceLayoutTests(unittest.TestCase):
    def test_old_root_export_and_data_relative_provenance_resolve(self):
        moves = {'export.csv': 'data/processed/export.csv',
                 'data/raw/old.json': 'data/sources/provider/raw/old.json'}
        with patch('rdr.paths._relocations', return_value=moves):
            self.assertEqual(resolve_archived_path('export.csv'), ROOT / 'data/processed/export.csv')
            self.assertEqual(resolve_archived_path('raw/old.json'), ROOT / 'data/sources/provider/raw/old.json')
            with self.assertRaises(ValueError):
                resolve_archived_path('../outside.json')

    def test_distinct_products_do_not_share_archive_directories(self):
        urls = [
            'https://api.weather.gc.ca/collections/hydrometric-realtime/items',
            'https://api.weather.gc.ca/collections/swob-realtime/items',
            'https://dd.weather.gc.ca/today/hydrometric/csv/AB/hourly/x.csv',
            'https://dd.weather.gc.ca/today/observations/swob-ml/partners/x.xml',
            'https://geospatial.alberta.ca/titan/rest/services/environment',
        ]
        paths = [source_relative_path(url, 'raw/check/sample.json') for url in urls]
        self.assertEqual(len(set(paths)), len(urls))
        for url, path in zip(urls, paths):
            self.assertEqual(Path(path).parts[1], source_for_url(url))
            self.assertEqual(source_relative_path(url, path), path)

    def test_unknown_sources_traversal_and_mismatched_sources_rejected(self):
        url = 'https://api.weather.gc.ca/collections/swob-realtime/items'
        for path in ['../outside.json', '/outside.json', 'C:/outside.json',
                     'sources/eccc_hydrometric_geomet/raw/wrong.json']:
            with self.assertRaises(ValueError):
                source_relative_path(url, path)
        with self.assertRaises(ValueError):
            source_relative_path('https://unregistered.example/data', 'raw/sample.json')

    def test_fetch_preserves_bytes_and_reuses_source_specific_cache(self):
        from API.client import fetch
        url = 'https://api.weather.gc.ca/collections/swob-realtime/items'
        response = requests.Response()
        response.status_code = 200
        response.url = url
        response._content = b'{"features":[]}'
        response.headers['Content-Type'] = 'application/json'
        with tempfile.TemporaryDirectory() as folder:
            with patch('API.client.DATA', Path(folder)), patch('API.client.log'), \
                    patch('API.client.requests.get', return_value=response) as network:
                first = fetch(url, 'raw/check/sample.json')
                second = fetch(url, 'raw/check/sample.json')
                self.assertEqual(first, second)
                network.assert_called_once()
                self.assertEqual(first.read_bytes(), response.content)
                meta = json.loads(first.with_suffix('.json.meta.json').read_text())
                self.assertEqual(Path(meta['path']), first.relative_to(folder))
                self.assertEqual(first.relative_to(folder).parts[:2], ('sources', 'eccc_weather_geomet'))

    def test_custom_validation_folder_reports_the_actual_source_path(self):
        from API.observations import swob
        with patch('API.observations.get_json', return_value={'features': []}) as network:
            result = swob({'weather_id': 'W'}, folder='raw/custom_validation')
        expected = 'sources/eccc_weather_geomet/raw/custom_validation/W.json'
        self.assertEqual(result['raw_path'], expected)
        self.assertEqual(network.call_args.args[1], expected)


if __name__ == '__main__':
    unittest.main()
