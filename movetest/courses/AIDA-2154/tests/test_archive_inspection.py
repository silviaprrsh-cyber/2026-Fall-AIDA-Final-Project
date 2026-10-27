"""Check that empty imagery cannot be reported as a usable CV input."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import rasterio
from rasterio.transform import from_origin
from cv_tools.inspect_archive import summarize


class ArchiveInspectionTests(unittest.TestCase):
    def test_empty_and_cloud_masks_are_distinct(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'quality.tif'
            bands = np.array([[[6, 8], [3, 4]], [[0, 0], [0, 0]]], dtype='uint8')
            for valid in [False, True]:
                bands[1] = int(valid)
                with rasterio.open(path, 'w', driver='GTiff', width=2, height=2, count=2,
                                   dtype='uint8', crs='EPSG:32612', transform=from_origin(300000, 5800000, 10, 10)) as dst:
                    dst.write(bands)
                with patch('cv_tools.inspect_archive.WORKSPACE', Path(folder)):
                    result = summarize(path)
                self.assertEqual(result['usable_data_present'], valid)
                self.assertEqual(result['valid_pixels'], 4 if valid else 0)
                self.assertEqual(result['cloud_shadow_pixels'], 2 if valid else 0)
