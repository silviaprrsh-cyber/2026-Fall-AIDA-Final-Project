"""Focused regression tests for point-mask morphology and unknown pixels."""
import unittest
import numpy as np
from cv_tools.make_point_water_masks import closing, connected, segment, points

class PointMasksTests(unittest.TestCase):
    def test_narrow_channel_survives(self):
        a=np.zeros((15,15),bool);a[:,7]=True
        self.assertTrue(closing(a)[3:-3,7].all())
    def test_close_single_pixel_hole(self):
        a=np.zeros((15,15),bool);a[3:12,5:10]=True;a[7,7]=False
        self.assertTrue(closing(a)[7,7])
    def test_seed_does_not_fill_background(self):
        a=np.zeros((15,15),bool);s=a.copy();s[7,7]=True
        self.assertFalse(connected(a,s).any())
    def test_unknown_cloud_not_water(self):
        a=np.zeros((6,15,15),dtype='uint16');a[0]=200;a[1]=400;a[2]=200;a[3]=100;a[4]=9;a[5]=1
        label,_=segment(a,np.ones((15,15),bool))
        self.assertTrue((label==255).all())
    def test_unclassified_water_allowed(self):
        a=np.zeros((6,15,15),dtype='uint16');a[0]=200;a[1]=400;a[2]=200;a[3]=100;a[4]=7;a[5]=1
        label,_=segment(a,np.ones((15,15),bool))
        self.assertTrue((label[3:-3,3:-3]==1).all())
    def test_scope(self):
        self.assertEqual(len(points()),9)

if __name__=='__main__':unittest.main()
