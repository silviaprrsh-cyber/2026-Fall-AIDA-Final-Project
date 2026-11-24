"""Regression checks for disjoint reverse-time periods and training peak retention."""
import unittest
import numpy as np
from .route_reverse_v1 import strict_align,calibrate


def fixture():
    t=np.arange(1200,dtype=float)*3600
    q=20+np.sin(t/100000);q[800]=100
    a={'boundaries':np.array([0,t[-1]+1]),'distances':np.ones(3)*600,
       'endpoint_times':t,'endpoint_values':np.column_stack([q,np.ones(len(t))])}
    for k in range(3):a['source'+str(k)]=np.column_stack([t,np.ones(len(t))*10,np.ones(len(t)),np.ones(len(t))*2,np.ones(len(t))*5,np.zeros(len(t)),np.ones(len(t))])
    s=np.column_stack([t,np.zeros((len(t),3)),np.ones(len(t))*10,np.ones(len(t))*999])
    return a,s


class ReverseTests(unittest.TestCase):
    def test_all_history_within_period(self):
        a,s=fixture();lo=600*3600;hi=1100*3600;seeds=s[(s[:,0]>=lo)&(s[:,0]<hi)]
        r=strict_align(a,seeds,np.zeros(3),lo,hi);v=r['valid']
        self.assertTrue(v.any());self.assertFalse(v[:25].any())
        self.assertTrue(np.all(r['source_rows'][v,:,0]>=lo))
        self.assertTrue(np.all(r['source_rows'][v,:,0]<=seeds[v,0,None]))
        self.assertTrue(np.all((r['label_times'][v]>=lo)&(r['label_times'][v]<hi)))

    def test_calibration_ignores_earlier_test_and_keeps_peak(self):
        a,s=fixture();lo=600*3600;hi=1100*3600;seeds=s[(s[:,0]>=lo)&(s[:,0]<hi)]
        first,report=calibrate(a,seeds,lo,hi)
        self.assertEqual(report['training_observed_peak_m3_s'],100)
        self.assertGreater(report['selected']['matched_training_peak_rows'],0)
        b={k:v.copy() for k,v in a.items()};b['endpoint_values'][b['endpoint_times']<lo]=1e9
        for k in range(3):
            src=b['source'+str(k)];src[src[:,0]<lo,1:]=1e8
        second,changed=calibrate(b,seeds,lo,hi)
        np.testing.assert_array_equal(first,second);self.assertEqual(report,changed)

    def test_inner_holdout_can_use_training_history_before_cut(self):
        a,s=fixture();lo=600*3600;hi=1100*3600
        # Medicine arrives 100 hours after its observation. The 125-hour
        # inner holdout has fewer than 30 matches if its input history is reset.
        a['distances'][2]=360000
        seeds=s[(s[:,0]>=lo)&(s[:,0]<hi)]
        _,report=calibrate(a,seeds,lo,hi)
        self.assertGreaterEqual(report['selected']['holdout_matched'],30)
        self.assertIn('past-only',report['inner_holdout_history'])

    def test_unmatched_training_peak_is_not_silently_accepted(self):
        a,s=fixture();lo=600*3600;hi=1100*3600;seeds=s[(s[:,0]>=lo)&(s[:,0]<hi)]
        t=np.append(a['endpoint_times'],hi-1);y=np.vstack([a['endpoint_values'],[1000,1]])
        order=np.argsort(t);a['endpoint_times']=t[order];a['endpoint_values']=y[order]
        with self.assertRaisesRegex(ValueError,'No route preserves actual training peak'):
            calibrate(a,seeds,lo,hi)


if __name__=='__main__':unittest.main()
