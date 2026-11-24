"""Offline regression tests for frozen-route calibration and causal matching."""
import unittest
import numpy as np
import torch
from .route_frozen import align_period, calibrate_routes, coverage_objective, past_index, ridge_fit, ridge_predict, metrics_with_baselines, fresh_network


def fixture():
    times = np.arange(0., 120001., 600.)
    arrays = {'boundaries':np.array([0.,40000.,80000.,120001.]),
              'distances':np.array([600.,600.,600.]),'endpoint_times':times,
              'endpoint_values':np.column_stack([20+np.sin(times/10000),1+times/1e7])}
    for k in range(3):
        arrays['source'+str(k)] = np.column_stack([times,10+np.sin(times/10000),
            np.ones(len(times)),np.ones(len(times))*2,np.ones(len(times))*5,
            np.zeros(len(times)),np.ones(len(times))])
    origins = times[(times>=3600)&(times<114000)]
    seeds = np.column_stack([origins,np.zeros((len(origins),3)),np.ones(len(origins))*10,np.ones(len(origins))*999])
    return arrays,seeds


class FrozenRouteTests(unittest.TestCase):
    def test_past_lookup_never_uses_future(self):
        np.testing.assert_array_equal(past_index(np.array([10.,20.,30.]),np.array([5.,10.,19.,25.])),[-1,0,0,1])

    def test_history_warmup_and_future_guard(self):
        a,s=fixture(); s=s[(s[:,0]>=60000)&(s[:,0]<66000)]
        r=align_period(a,s,np.zeros(3),60000,66000)
        self.assertTrue(r['valid'][0])
        self.assertTrue(np.all(r['source_rows'][r['valid'],:,0]<=s[r['valid'],0,None]))
        self.assertTrue(np.all(r['label_times'][r['valid']]<66000))
        self.assertFalse(r['valid'][-1])

    def test_no_future_source_rescue(self):
        a,s=fixture(); a['source1']=a['source1'][a['source1'][:,0]>=60000]
        r=align_period(a,s[:5],np.zeros(3),0,120001)
        self.assertFalse(r['valid'].any())

    def test_invalid_is_worse_than_arbitrarily_large_valid_error(self):
        y=np.zeros((2,2)); p=np.ones((2,2))*1000
        self.assertLess(coverage_objective(p,y,np.ones(2,bool),np.ones(2)),1)
        self.assertEqual(coverage_objective(p,y,np.zeros(2,bool),np.ones(2)),1)

    def test_ridge_uses_fit_scaling(self):
        x=np.arange(100.,dtype=float).reshape(50,2);y=np.column_stack([x[:,0]*2,x[:,1]*3])
        fit=ridge_fit(x,y)
        self.assertLess(np.abs(ridge_predict(x,fit)-y).mean(),1)

    def test_subset_denominator(self):
        a,s=fixture(); r=align_period(a,s[:10],np.zeros(3),0,120001)
        r['labels'][:2,0]=150
        states=np.zeros((10,6,5));states[:,-1,:2]=r['labels']
        result=metrics_with_baselines(a,r,states)['subsets']['high_flow_ge100']
        self.assertEqual(result['candidate_count'],2)
        self.assertEqual(result['model']['origins'],2)
        self.assertEqual(result['model']['matched'],2)
        self.assertEqual(result['model']['coverage'],1.)
        empty=metrics_with_baselines(a,r,states)['subsets']['high_flow_ge200']['model']
        self.assertEqual(empty['origins'],0)
        self.assertIsNone(empty['coverage'])

    def test_old_learned_weights_are_not_reused(self):
        depths=np.tile(np.linspace(.1,5,10),(6,1))
        g={'depths':depths,'areas':depths*10,'distances':np.ones(6)*100}
        torch.manual_seed(5); saved=fresh_network(g,np.zeros(9),np.ones(9)).state_dict()
        torch.manual_seed(42); first=fresh_network(saved,np.zeros(9),np.ones(9))
        for name,value in saved.items():
            if name.startswith('blocks.'):
                value.add_(999)
        g=saved
        torch.manual_seed(42); second=fresh_network(g,np.zeros(9),np.ones(9))
        self.assertTrue(all(torch.equal(v,second.state_dict()[k]) for k,v in first.state_dict().items()))

    def test_calibration_independent_of_future_values(self):
        a,s=fixture(); train=s[s[:,0]<90000]
        logits,report=calibrate_routes(a,train,0,90000)
        b={k:v.copy() for k,v in a.items()}
        b['endpoint_values'][b['endpoint_times']>=90000]=1e9
        for k in range(3):
            x=b['source'+str(k)];x[x[:,0]>=90000,1:]=1e8
        other,changed=calibrate_routes(b,train,0,90000)
        np.testing.assert_array_equal(logits,other)
        self.assertEqual(report,changed)
        self.assertTrue(report['route_frozen_before_validation_and_test'])


if __name__=='__main__':
    unittest.main()
