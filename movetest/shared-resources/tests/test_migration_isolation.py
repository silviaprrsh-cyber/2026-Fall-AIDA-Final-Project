"""Catch accidental imports and path writes into the original project."""
import importlib
from pathlib import Path
import unittest
from project_paths import WORKSPACE, ROOT, DATA, require_local, resolve_runtime_path, archive_relative


class MigrationIsolationTests(unittest.TestCase):
    def test_shared_and_course_modules_resolve_inside_candidate(self):
        for name in ['API.client', 'rdr.storage', 'rdr.paths', 'rdr_eda.etl',
                     'rdr_gis.spatial', 'gis_tools.build_prediction_points', 'cv_tools.inspect_archive']:
            module = importlib.import_module(name)
            self.assertTrue(Path(module.__file__).resolve().is_relative_to(WORKSPACE), name)

    def test_runtime_root_is_shared_data_in_candidate(self):
        self.assertEqual(ROOT, WORKSPACE/'shared-resources')
        self.assertEqual(DATA, ROOT/'data')
        for name in ['API.snapshot_scope', 'API.validate_satellite_once', 'rdr.storage', 'rdr.paths']:
            self.assertEqual(importlib.import_module(name).ROOT, ROOT)

    def test_external_path_is_rejected(self):
        with self.assertRaises(ValueError): require_local(WORKSPACE.parent/'data')

    def test_source_ownership_and_provenance_round_trip(self):
        examples = [('copernicus_sentinel2', '2154'),
                    ('eccc_weather_geomet', '2156'),
                    ('eccc_hydrometric_datamart', '2156'),
                    ('alberta_flood_surveys', '2362'), ('nrcan_nhn', '2362')]
        for source, course in examples:
            logical = DATA/f'sources/{source}/raw/example.json'
            physical = resolve_runtime_path(logical)
            self.assertEqual(physical, WORKSPACE/f'courses/AIDA-{course}/data/sources/{source}/raw/example.json')
            self.assertEqual(DATA/archive_relative(physical, DATA), logical)
            self.assertEqual(resolve_runtime_path(physical), physical)

    def test_existing_cross_course_inputs_are_available(self):
        for relative in ['processed/etl/profiles.json', 'processed/weather_links.json',
                         'processed/nhn_named_rivers.geojson']:
            path = resolve_runtime_path(DATA/relative)
            self.assertTrue(path.is_file(), str(path))
            self.assertTrue(path.is_relative_to(WORKSPACE/'courses'))
