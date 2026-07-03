from __future__ import annotations

import unittest

import networkx as nx
from shapely.geometry import LineString

from runfeeti.directions import directions_from_path
from runfeeti.routing import (
    RoutedPath,
    apply_roads_first_mvp_weights,
    projected_polyline,
    route_weight_attr,
)


def _parallel_edge_graph() -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:3857"
    graph.add_node(1, x=0.0, y=0.0)
    graph.add_node(2, x=100.0, y=0.0)
    graph.add_edge(
        1,
        2,
        key="footway",
        length=50.0,
        highway="footway",
        name="Cut Through",
        geometry=LineString([(0.0, 0.0), (50.0, 10.0), (100.0, 0.0)]),
    )
    graph.add_edge(
        1,
        2,
        key="street",
        length=100.0,
        highway="residential",
        name="Main Street",
        geometry=LineString([(0.0, 0.0), (100.0, 0.0)]),
    )
    return graph


def _routed(graph: nx.MultiDiGraph) -> RoutedPath:
    return RoutedPath(
        graph=graph,
        nodes=[1, 2],
        edge_gdf=None,
        block_m=100.0,
        center_latitude=0.0,
        center_longitude=0.0,
        template_bbox_min_x=0.0,
        template_bbox_min_y=0.0,
        template_bbox_max_x=100.0,
        template_bbox_max_y=0.0,
    )


def _turn_graph(turn: str) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()
    graph.graph["crs"] = "EPSG:3857"
    graph.add_node(1, x=0.0, y=0.0)
    graph.add_node(2, x=0.0, y=100.0)
    if turn == "right":
        graph.add_node(3, x=100.0, y=100.0)
        end_xy = (100.0, 100.0)
    else:
        graph.add_node(3, x=-100.0, y=100.0)
        end_xy = (-100.0, 100.0)
    graph.add_edge(
        1,
        2,
        length=100.0,
        highway="residential",
        name="North Street",
        geometry=LineString([(0.0, 0.0), (0.0, 100.0)]),
    )
    graph.add_edge(
        2,
        3,
        length=100.0,
        highway="residential",
        name="Cross Street",
        geometry=LineString([(0.0, 100.0), end_xy]),
    )
    return graph


def _turn_routed(graph: nx.MultiDiGraph) -> RoutedPath:
    return RoutedPath(
        graph=graph,
        nodes=[1, 2, 3],
        edge_gdf=None,
        block_m=100.0,
        center_latitude=0.0,
        center_longitude=0.0,
        template_bbox_min_x=-100.0,
        template_bbox_min_y=0.0,
        template_bbox_max_x=100.0,
        template_bbox_max_y=100.0,
    )


class RoutingDirectionsTest(unittest.TestCase):
    def test_roads_first_weight_marks_footpaths_more_expensive(self) -> None:
        graph = _parallel_edge_graph()
        apply_roads_first_mvp_weights(graph, penalty=10.0)

        self.assertEqual(route_weight_attr(graph), "mvp_weight")
        self.assertEqual(graph[1][2]["street"]["mvp_weight"], 100.0)
        self.assertEqual(graph[1][2]["footway"]["mvp_weight"], 500.0)

    def test_projected_polyline_uses_selected_route_weight_for_parallel_edges(self) -> None:
        graph = _parallel_edge_graph()
        apply_roads_first_mvp_weights(graph, penalty=10.0)

        self.assertEqual(projected_polyline(graph, [1, 2]), [(0.0, 0.0), (100.0, 0.0)])

    def test_directions_use_selected_route_weight_for_parallel_edges(self) -> None:
        graph = _parallel_edge_graph()
        apply_roads_first_mvp_weights(graph, penalty=10.0)

        steps = directions_from_path(_routed(graph))

        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].street, "Main Street")
        self.assertEqual(steps[0].instruction, "Start on Main Street")
        self.assertEqual(steps[0].distance_m, 100.0)

    def test_positive_bearing_delta_is_right_turn(self) -> None:
        steps = directions_from_path(_turn_routed(_turn_graph("right")))

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1].instruction, "Turn right on Cross Street")

    def test_negative_bearing_delta_is_left_turn(self) -> None:
        steps = directions_from_path(_turn_routed(_turn_graph("left")))

        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[1].instruction, "Turn left on Cross Street")


if __name__ == "__main__":
    unittest.main()
