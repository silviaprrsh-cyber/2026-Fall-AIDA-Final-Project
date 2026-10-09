import unittest
from scripts.refine_outlets import select_gauge


class GaugeSelectionTests(unittest.TestCase):
    def candidate(self,straight,route=None,offset=10):
        return {'straight_distance_m':straight,'along_river_distance_m':route,
                'mapped_river_offset_m':offset}

    def test_same_name_far_from_river_is_not_selected(self):
        candidate=self.candidate(1000,offset=6000)
        selected,method=select_gauge([candidate])
        self.assertIsNone(selected)
        self.assertEqual(method,'same_name_location_unverified')

    def test_unrouted_farther_gauge_cannot_beat_shorter_verified_route(self):
        near=self.candidate(1000,route=2000)
        selected,method=select_gauge([near,self.candidate(5000)])
        self.assertIs(selected,near)
        self.assertEqual(method,'along_same_river_network')

    def test_missing_nearby_route_prevents_claiming_network_nearest(self):
        unknown=self.candidate(1500)
        _,method=select_gauge([self.candidate(1000,route=2000),unknown])
        self.assertEqual(method,'straight_distance_provisional')

if __name__=='__main__':unittest.main()
