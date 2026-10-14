"""Check geographic selection rules independently of the archived project data."""

import unittest
from shapely.geometry import LineString
from scripts.build_prediction_points import bridge_position, first_downstream


class PredictionPointTests(unittest.TestCase):
    def test_first_section_must_be_strictly_downstream(self):
        sections = [{"chainage_m": 8}, {"chainage_m": 10}, {"chainage_m": 15}, {"chainage_m": 11}]
        self.assertEqual(first_downstream(sections, 10)["chainage_m"], 11)
        with self.assertRaises(ValueError):
            first_downstream(sections, 15)

    def test_divided_bridge_has_single_mean_chainage(self):
        main = LineString([(0, 0), (100, 0)])
        bridges = {i: {"geometry": [{"lon": x, "lat": -10}, {"lon": x, "lat": 10}]}
                   for i, x in [(1, 40), (2, 60)]}
        chainage, distances = bridge_position(main, bridges, [1, 2], lambda x, y: (x, y))
        self.assertEqual(chainage, 50)
        self.assertEqual(distances, [0, 0])

    def test_wrong_river_or_proposed_bridge_rejected(self):
        main = LineString([(0, 0), (100, 0)])
        wrong = {1: {"geometry": [{"lon": 20, "lat": 20}, {"lon": 30, "lat": 30}]}}
        with self.assertRaises(ValueError):
            bridge_position(main, wrong, [1], lambda x, y: (x, y))
        wrong[1]["tags"] = {"highway": "proposed"}
        with self.assertRaises(ValueError):
            bridge_position(main, wrong, [1], lambda x, y: (x, y))


if __name__ == "__main__":
    unittest.main()
