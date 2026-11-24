"""Offline tests for the non-saturating high-flow experiment."""
import unittest
import numpy as np
import torch
from .route_tail import TailChain, raw_context, tail_weights, train_tail, signed_metrics
from .test_route_frozen import fixture
from .route_frozen import align_period


def model():
    grid=np.tile(np.linspace(.01,5,100),(6,1))
    return TailChain(grid,grid*10,np.ones(6)*100,np.zeros(9),np.ones(9),20)


class TailTests(unittest.TestCase):
    def test_raw_context_preserves_units(self):
        x=np.zeros((2,9));x[:,0]=np.log1p(200);x[:,4]=np.log1p(20);x[:,7]=10
        np.testing.assert_allclose(raw_context(x)[:,[0,4,7]],[[200,20,10],[200,20,10]])
        np.testing.assert_allclose(raw_context(torch.tensor(x)).numpy(),raw_context(x))

    def test_flow_unbounded_and_positive(self):
        m=model()
        with torch.no_grad():
            for skip in m.skips:skip.bias[0]=10
        initial=torch.tensor([[10.,1.,1.,0.],[1000.,1.,1.,0.]])
        states,_=m(initial,torch.zeros((2,9)))
        self.assertGreater(float(states[0,-1,0].detach()),10*np.exp(2.1))
        self.assertGreater(float(states[1,-1,0].detach()),float(states[0,-1,0].detach()))
        with torch.no_grad():
            for skip in m.skips:skip.bias[0]=-100000
        states,_=m(initial,torch.zeros((2,9)))
        self.assertTrue(torch.isfinite(states).all());self.assertTrue((states[:,:,0]>0).all())

    def test_geometry_and_gradients(self):
        m=model();states,_=m(torch.tensor([[20.,1.,2.,0.]]),torch.ones((1,9)))
        self.assertTrue(torch.allclose(states[:,:,3],states[:,:,0]/states[:,:,2]))
        self.assertTrue((states[:,:,1]>=m.depths[:,0]).all())
        self.assertTrue((states[:,:,1]<=m.depths[:,-1]).all())
        states[:,-1,:2].square().sum().backward()
        self.assertTrue(all(s.weight.grad.abs().sum()>0 for s in m.skips))
        self.assertTrue(all(b[-1].weight.grad.abs().sum()>0 for b in m.blocks))

    def test_tail_weight_is_symmetric_fixed_threshold(self):
        y=np.array([[20.,1.],[74.,1.],[100.,1.]])
        np.testing.assert_array_equal(tail_weights(y,74),[1,5,5])
        np.testing.assert_array_equal(tail_weights(torch.tensor(y),74).numpy(),[1,5,5])

    def test_signed_subset_denominator(self):
        states=np.zeros((10,6,5));aligned={'labels':np.ones((10,2))}
        population=np.arange(10)<3;mask=np.arange(10)<2
        m=signed_metrics(states,aligned,mask,population)
        self.assertEqual(m['origins'],3);self.assertEqual(m['matched'],2)
        self.assertAlmostEqual(m['coverage'],2/3)
        self.assertEqual(m['discharge']['under_count'],2)
        empty=signed_metrics(states,aligned,mask,np.zeros(10,bool))
        self.assertIsNone(empty['coverage'])

    def test_bounded_training_smoke(self):
        a,s=fixture();train=align_period(a,s[:70],np.zeros(3),0,60000)
        val=align_period(a,s[100:150],np.zeros(3),60000,100000)
        torch.set_num_threads(2);torch.manual_seed(42)
        history,chosen=train_tail(model(),train,val,np.array([1.,.1]),20.,2,2)
        self.assertLessEqual(len(history)-1,2);self.assertIn(chosen,[0,1,2])
        self.assertTrue(all(np.isfinite(r['validation_weighted_objective']) for r in history))


if __name__=='__main__':unittest.main()
