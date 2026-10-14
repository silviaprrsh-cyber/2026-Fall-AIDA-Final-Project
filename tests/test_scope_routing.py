"""Check clipping and named-river constraints without external datasets."""

import unittest
from shapely.geometry import LineString, Point
from scripts.build_scoped_qgis import Network


class ScopeRoutingTests(unittest.TestCase):
    def graph(self, segments):
        graph = Network.__new__(Network)
        graph.edges = [{"id": str(i), "name": name, "direction": direction,
                        "a": str(tuple(coords[0])), "b": str(tuple(coords[-1])),
                        "line": LineString(coords)}
                       for i, (coords, name, direction) in enumerate(segments)]
        return graph

    def test_cuts_inside_one_edge(self):
        graph = self.graph([([(0, 0), (100, 0)], "RED DEER RIVER", 1)])
        line, audit = graph.route(Point(20, 1), Point(80, 1), "RED DEER RIVER")
        self.assertAlmostEqual(line.length, 60)
        self.assertEqual(tuple(line.coords[0]), (20, 0))
        self.assertEqual(tuple(line.coords[-1]), (80, 0))
        self.assertEqual(audit["source_direction_conflict_ids"], [])

    def test_other_named_river_cannot_be_a_shortcut(self):
        graph = self.graph([
            ([(0, 0), (0, 10)], "RED DEER RIVER", 1),
            ([(0, 10), (10, 10)], "", 1),
            ([(10, 10), (10, 0)], "RED DEER RIVER", 1),
            ([(0, 0), (10, 0)], "OTHER RIVER", 1)])
        line, audit = graph.route(Point(0, 1), Point(10, 1), "RED DEER RIVER")
        self.assertAlmostEqual(line.length, 28)
        self.assertNotIn("3", audit["edge_ids"])

    def test_source_direction_conflict_is_retained(self):
        graph = self.graph([([(0, 0), (100, 0)], "RED DEER RIVER", 2)])
        _, audit = graph.route(Point(20, 0), Point(80, 0), "RED DEER RIVER")
        self.assertEqual(audit["source_direction_conflict_ids"], ["0"])

    def test_disconnected_route_fails(self):
        graph = self.graph([([(0, 0), (10, 0)], "RED DEER RIVER", 1),
                            ([(20, 0), (30, 0)], "RED DEER RIVER", 1)])
        with self.assertRaisesRegex(ValueError, "No connected"):
            graph.route(Point(5, 0), Point(25, 0), "RED DEER RIVER")


if __name__ == "__main__":
    unittest.main()
