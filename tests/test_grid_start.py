from __future__ import annotations

import unittest

import networkx as nx

from runfeeti.grid_start import _path_length_m
from runfeeti.routing import apply_roads_first_mvp_weights


class GridStartScoringTest(unittest.TestCase):
    def test_path_length_uses_selected_weighted_parallel_edge(self) -> None:
        graph = nx.MultiDiGraph()
        graph.add_node(1, x=0.0, y=0.0)
        graph.add_node(2, x=100.0, y=0.0)
        graph.add_edge(
            1,
            2,
            key="shortcut",
            length=50.0,
            highway="footway",
        )
        graph.add_edge(
            1,
            2,
            key="street",
            length=100.0,
            highway="residential",
        )
        apply_roads_first_mvp_weights(graph, penalty=10.0)

        self.assertEqual(_path_length_m(graph, [1, 2]), 100.0)


if __name__ == "__main__":
    unittest.main()
