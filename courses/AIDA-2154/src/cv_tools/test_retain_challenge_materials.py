"""Run with project bootstrap: -m cv_tools.test_retain_challenge_materials."""
import unittest
from unittest.mock import patch
from pathlib import Path
from cv_tools.retain_challenge_materials import classify
from cv_tools.summarize_cv_gaps import inventory_rows
from project_paths import WORKSPACE


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.row = dict(hash_verified=True, signal_present=True, valid_corridor_pixels=500,
                        corridor_pixels=500, river_core_pixels=30, valid_corridor_fraction=1.,
                        clear_corridor_fraction=1., clear_river_core_fraction=1., snow_ice_corridor_fraction=0.)

    def test_clear_proxy_is_only_review(self):
        self.assertEqual(classify(self.row, {}), 'clear_proxy_label_review')

    def test_zero_clear_score_does_not_reject(self):
        self.row.update(clear_corridor_fraction=0., clear_river_core_fraction=0.)
        self.assertEqual(classify(self.row, {}), 'challenge_region_review')

    def test_low_coverage_still_retained(self):
        self.row.update(valid_corridor_fraction=.01, river_core_pixels=0)
        self.assertEqual(classify(self.row, {}), 'challenge_region_review')

    def test_haze_hold_reclassified(self):
        self.assertEqual(classify(self.row, {'decision': 'hold_haze_review'}), 'challenge_region_review')

    def test_snow_is_review_not_land(self):
        self.row['snow_ice_corridor_fraction'] = 1.
        self.assertEqual(classify(self.row, {}), 'challenge_region_review')

    def test_input_failures_separate(self):
        for field, value in [('hash_verified', False), ('signal_present', False), ('valid_corridor_pixels', 0)]:
            with self.subTest(field=field):
                self.assertEqual(classify({**self.row, field: value}, {}), 'unreliable_input_review')

    def test_unknown_job_never_reads_metadata_even_if_present(self):
        for present in [False, True]:
            with patch.object(Path, 'is_file', return_value=present), patch.object(Path, 'read_text', side_effect=AssertionError('must not read')):
                rows = inventory_rows([dict(id='unknown', status='needs_review', cv_candidate=True, quality={'valid_fraction': 1})], WORKSPACE/'fake')
            self.assertIsNone(rows[0]['cv_candidate'])
            self.assertIsNone(rows[0]['valid_fraction'])
            self.assertEqual(rows[0]['image'], '')
            self.assertEqual(rows[0]['actual_sensing_times'], '')
            self.assertIsNone(rows[0]['actual_PU'])

    def test_downloaded_missing_files_reported_without_read(self):
        with patch.object(Path, 'is_file', return_value=False), patch.object(Path, 'read_text', side_effect=AssertionError('missing file')):
            row = inventory_rows([dict(id='done', status='downloaded')], WORKSPACE/'fake')[0]
        self.assertEqual(row['pixel_material_status'], 'downloaded_files_missing')

    def test_downloaded_metadata_read(self):
        with patch.object(Path, 'is_file', return_value=True), patch.object(Path, 'read_text', return_value='{"tiles":[{"date":"2026-01-01T00:00:00Z"}]}'):
            row = inventory_rows([dict(id='done', status='downloaded', cv_candidate=True)], WORKSPACE/'fake')[0]
        self.assertEqual(row['actual_sensing_times'], '2026-01-01T00:00:00Z')
        self.assertEqual(row['pixel_material_status'], 'downloaded_files_present')


if __name__ == '__main__':
    unittest.main()
