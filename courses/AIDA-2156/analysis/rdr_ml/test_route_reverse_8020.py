import unittest,numpy as np
from .route_reverse_8020 import isolated_split,subset,timestamp
class SplitTests(unittest.TestCase):
 def fixture(self):
  t=np.arange(timestamp('2025-05-03T00:00:00Z'),timestamp('2026-11-01T00:00:00Z'),3600)
  return {'origins':t,'label_times':t+3600,'common_arrivals':t+3700,'source_rows':np.repeat((t-7200)[:,None,None],3,axis=1),'valid':np.ones(len(t),bool),'labels':np.ones((len(t),2))}
 def test_isolation_and_no_ratio_discard(self):
  a=self.fixture();tr,te,r=isolated_split(a);cut=timestamp(r['boundary_utc'])
  self.assertFalse(np.any(tr&te));self.assertTrue(np.all(a['common_arrivals'][te]<cut));self.assertTrue(np.all(a['source_rows'][tr,:,0]-7200>=cut));self.assertTrue(np.all(a['origins'][tr]-25*3600>=cut));self.assertEqual(tr.sum(),r['before_ratio_trim_train']);self.assertEqual(te.sum(),r['before_ratio_trim_test']);self.assertLess(abs(r['development_fraction']-.8),.002)
 def test_labels_do_not_choose_split(self):
  a=self.fixture();tr,te,r=isolated_split(a);a['labels'][:]=1e9;tr2,te2,r2=isolated_split(a);np.testing.assert_array_equal(tr,tr2);np.testing.assert_array_equal(te,te2);self.assertEqual(r,r2)
 def test_subset_preserves_selected_rows(self):
  a=self.fixture();tr,te,r=isolated_split(a);b=subset(a,tr);self.assertEqual(len(b['valid']),tr.sum());self.assertTrue(b['valid'].all());np.testing.assert_array_equal(b['origins'],a['origins'][tr])
if __name__=='__main__':unittest.main()
