"""Portable focused tests; GIS-source scope verification stays in the full workspace."""
import json
import unittest
from cv_tools.test_point_water_masks import PointMasksTests
from cv_tools.test_point_cnn import CNNTests
from cv_tools.test_point_widths import WidthTests
from cv_tools.train_point_cnn import OUT

class FrozenScopeTests(unittest.TestCase):
    def test_exact_frozen_point_ids(self):
        rows=json.loads((OUT/'dataset_manifest.json').read_text())['records']
        self.assertEqual({r['point_id'] for r in rows},{'P01','P02','P03','P04','P05','05CB001','05CB007','05CC002','05CC007'})

if __name__=='__main__':
    loader=unittest.TestLoader();suite=unittest.TestSuite()
    for name in loader.getTestCaseNames(PointMasksTests):
        if name!='test_scope':suite.addTest(PointMasksTests(name))
    for cls in [CNNTests,WidthTests,FrozenScopeTests]:suite.addTests(loader.loadTestsFromTestCase(cls))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
