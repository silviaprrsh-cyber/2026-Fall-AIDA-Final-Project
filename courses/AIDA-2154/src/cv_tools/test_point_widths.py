"""Tests for native-grid transect weights and correlation edge cases."""
import unittest
import numpy as np
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from cv_tools.validate_point_widths import line_weights,corr,ranks

class WidthTests(unittest.TestCase):
    def test_native_line_length(self):
        with MemoryFile() as mem:
            with mem.open(driver='GTiff',height=61,width=61,count=1,dtype='uint8',transform=from_origin(0,610,10,10),crs='EPSG:32612') as ds:
                weights,_=line_weights(ds,{'direction':[1,0],'xy':[305,305]})
                self.assertAlmostEqual(weights.sum(),500,places=6)
                self.assertAlmostEqual(weights[30,30],10,places=6)
                self.assertEqual(int((weights>0).sum()),51)
    def test_constant_correlation_undefined(self):
        self.assertIsNone(corr([1]*6,range(6)))
    def test_small_sample_not_reported(self):
        self.assertIsNone(corr([1,2],[2,3]))
    def test_rank_ties(self):
        np.testing.assert_equal(ranks([3,1,1]),[3,1.5,1.5])

if __name__=='__main__':unittest.main()
