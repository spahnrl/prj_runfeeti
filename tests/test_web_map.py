from __future__ import annotations

import unittest
from unittest.mock import patch

import networkx as nx

from runfeeti.routing import RoutedPath
from runfeeti.web_map import route_polyline_latlon


def _routed_for_web_map() -> RoutedPath:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:3857"
    return RoutedPath(
        graph=graph,
        nodes=[1, 2],
        edge_gdf=None,
        block_m=100.0,
        center_latitude=0.0,
        center_longitude=0.0,
        template_bbox_min_x=0.0,
        template_bbox_min_y=0.0,
        template_bbox_max_x=0.0,
        template_bbox_max_y=0.0,
    )


class WebMapTest(unittest.TestCase):
    def test_route_polyline_returns_empty_for_duplicate_only_points(self) -> None:
        with patch(
            "runfeeti.web_map.projected_polyline",
            return_value=[(0.0, 0.0), (0.0, 0.0)],
        ):
            self.assertEqual(route_polyline_latlon(_routed_for_web_map()), [])

    def test_route_polyline_converts_projected_points_to_latlon(self) -> None:
        with patch(
            "runfeeti.web_map.projected_polyline",
            return_value=[(0.0, 0.0), (111_319.4908, 0.0)],
        ):
            latlons = route_polyline_latlon(_routed_for_web_map())

        self.assertEqual(len(latlons), 2)
        self.assertAlmostEqual(latlons[0][0], 0.0, places=5)
        self.assertAlmostEqual(latlons[0][1], 0.0, places=5)
        self.assertAlmostEqual(latlons[1][0], 0.0, places=5)
        self.assertAlmostEqual(latlons[1][1], 1.0, places=4)

if __name__ == "__main__":
    unittest.main()
