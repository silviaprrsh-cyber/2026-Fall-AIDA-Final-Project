"""Focused CNN shape, metric and frozen-split checks."""
import json
import unittest
import numpy as np
import torch
from cv_tools.train_point_cnn import SmallSegCNN, metrics, OUT

class CNNTests(unittest.TestCase):
    def test_output_grid(self):
        self.assertEqual(tuple(SmallSegCNN()(torch.zeros(2,4,61,61)).shape),(2,61,61))
    def test_counts(self):
        r=metrics(np.array([1,1,0,0]),np.array([True,False,True,False]))
        self.assertEqual((r['TP'],r['FP'],r['FN'],r['TN']),(1,1,1,1))
        self.assertAlmostEqual(r['IoU'],1/3)
    def test_unknown_ignored(self):
        r=metrics(np.array([1,0,255,255]),np.array([True,False,True,False]))
        self.assertEqual((r['TP'],r['FP'],r['FN'],r['TN']),(1,0,0,1))
    def test_date_groups(self):
        rows=json.loads((OUT/'dataset_manifest.json').read_text())['records'];groups={}
        for r in rows:groups.setdefault(r['date'][:10],set()).add(r['split'])
        self.assertTrue(all(len(v)==1 for v in groups.values()))
        self.assertEqual(len(rows),len({(r['point_id'],r['date'][:10]) for r in rows}))

if __name__=='__main__':unittest.main()
