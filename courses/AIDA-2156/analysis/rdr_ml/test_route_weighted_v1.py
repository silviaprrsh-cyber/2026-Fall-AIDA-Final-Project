import unittest,numpy as np
from .route_weighted_v1 import event_masks,weights,timestamp,joined_proxy_depths,tail_metrics,error_metrics
class WeightedTests(unittest.TestCase):
 def test_threshold(self):np.testing.assert_array_equal(weights(np.array([99.9,100,284])),[1,5,5])
 def test_event_masks_no_target_overlap(self):
  lo=timestamp('2026-05-28T00:00:00Z');hi=timestamp('2026-06-25T00:00:00Z')
  a={'origins':np.array([lo-7200,lo-3600,lo+3600,hi-3600,hi+3600]),'label_times':np.array([lo-3600,lo+3600,lo+7200,hi+3600,hi+7200]),'common_arrivals':np.array([lo-3600,lo+3600,lo+7200,hi+3600,hi+7200])}
  f,v,_,_=event_masks(a);np.testing.assert_array_equal(f,[1,0,0,0,1]);np.testing.assert_array_equal(v,[0,1,1,0,0]);self.assertFalse(np.any(f&v))
 def test_masks_ignore_target_magnitude(self):
  lo=timestamp('2026-05-28T00:00:00Z');a={'origins':np.array([lo]),'label_times':np.array([lo+1]),'common_arrivals':np.array([lo+1]),'labels':np.array([[100,3]])};f,v,*_=event_masks(a);a['labels'][:]=1e9;f2,v2,*_=event_masks(a);np.testing.assert_array_equal(f,f2);np.testing.assert_array_equal(v,v2)
class ApproximateDepthTests(unittest.TestCase):
 def setUp(self):
  self.values=np.array([[100.,10.,2.,.5],[200.,20.,3.,1.5],[300.,30.,4.,2.5]])
  self.times=np.array([100.,300.]);self.expected=self.values[[0,2],1:3].copy()
 def test_exact_join_uses_depth_once(self):
  old=self.values.copy();depth=joined_proxy_depths(self.values,self.times,self.expected,-1.5,'gauge')
  np.testing.assert_array_equal(depth,[.5,2.5]);np.testing.assert_array_equal(self.values,old)
 def test_missing_timestamp_rejected(self):
  with self.assertRaisesRegex(ValueError,'every frozen'):joined_proxy_depths(self.values,np.array([150.]),self.expected[:1],-1.5,'gauge')
 def test_duplicate_timestamp_rejected(self):
  self.values[1,0]=100
  with self.assertRaisesRegex(ValueError,'duplicate'):joined_proxy_depths(self.values,self.times,self.expected,-1.5,'gauge')
 def test_changed_flow_rejected(self):
  self.expected[0,0]+=1
  with self.assertRaisesRegex(ValueError,'Q/stage'):joined_proxy_depths(self.values,self.times,self.expected,-1.5,'gauge')
 def test_wrong_or_double_offset_rejected(self):
  self.values[:,3]-=.1
  with self.assertRaisesRegex(ValueError,'single station offset'):joined_proxy_depths(self.values,self.times,self.expected,-1.5,'gauge')
 def test_nonpositive_depth_rejected(self):
  self.values[0,2]=1.;self.values[0,3]=-.5;self.expected[0,1]=1.
  with self.assertRaisesRegex(ValueError,'Invalid approximate'):joined_proxy_depths(self.values,self.times,self.expected,-1.5,'gauge')
 def test_stage_depth_error_translation_invariant(self):
  labels=np.array([[100.,3.],[150.,4.]])
  pred=np.array([[90.,3.1],[125.,3.8]])
  expected=error_metrics(pred,labels,np.ones(2,dtype=bool))
  labels[:,1]-=1.6;pred[:,1]-=1.6
  actual=error_metrics(pred,labels,np.ones(2,dtype=bool))
  for name in ['discharge','variable_depth']:
   for key in ['bias','mae','rmse']:self.assertAlmostEqual(actual[name][key],expected[name][key])
 def test_high_flow_reports_empty_threshold(self):
  result=tail_metrics(np.array([[90.,1.]]),np.array([[100.,1.2]]))
  self.assertEqual(result['100']['n'],1);self.assertEqual(result['100']['q_under_fraction'],1)
  self.assertEqual(result['140']['n'],0);self.assertIsNone(result['140']['metrics']['discharge']['bias'])
if __name__=='__main__':unittest.main()
