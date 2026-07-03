from __future__ import annotations

import inspect
import unittest

from runfeeti import routing
from runfeeti import runner
from runfeeti.route_options import (
    DEFAULT_LETTER_GAP,
    DEFAULT_PREVIEW_HEIGHT_CELLS,
    DEFAULT_PREVIEW_WIDTH_CELLS,
    DEFAULT_ROADS_FIRST_PENALTY,
    DEFAULT_UI_SEARCH_HALF_MI,
)


def _default(function: object, parameter: str) -> object:
    return inspect.signature(function).parameters[parameter].default


class InternalDefaultsTest(unittest.TestCase):
    def test_routing_defaults_use_shared_route_options(self) -> None:
        self.assertEqual(
            _default(routing.apply_roads_first_mvp_weights, "penalty"),
            DEFAULT_ROADS_FIRST_PENALTY,
        )
        self.assertEqual(_default(routing.grid_waypoints, "gap"), DEFAULT_LETTER_GAP)
        self.assertEqual(_default(routing.build_grid_preview, "letter_gap"), DEFAULT_LETTER_GAP)
        self.assertEqual(
            _default(routing.build_grid_preview, "roads_first_penalty"),
            DEFAULT_ROADS_FIRST_PENALTY,
        )
        self.assertEqual(
            _default(routing.build_grid_preview, "preview_contract_w"),
            DEFAULT_PREVIEW_WIDTH_CELLS,
        )
        self.assertEqual(
            _default(routing.build_grid_preview, "preview_contract_h"),
            DEFAULT_PREVIEW_HEIGHT_CELLS,
        )
        self.assertEqual(_default(routing.build_route, "letter_gap"), DEFAULT_LETTER_GAP)
        self.assertEqual(
            _default(routing.build_route, "search_half_miles"),
            DEFAULT_UI_SEARCH_HALF_MI,
        )
        self.assertEqual(
            _default(routing.build_route, "roads_first_penalty"),
            DEFAULT_ROADS_FIRST_PENALTY,
        )

    def test_runner_defaults_use_shared_route_options(self) -> None:
        self.assertEqual(
            _default(runner.build_grid_debug_result, "roads_first_penalty"),
            DEFAULT_ROADS_FIRST_PENALTY,
        )
        self.assertEqual(
            _default(runner.build_grid_debug_result, "preview_contract_w"),
            DEFAULT_PREVIEW_WIDTH_CELLS,
        )
        self.assertEqual(
            _default(runner.build_grid_debug_result, "preview_contract_h"),
            DEFAULT_PREVIEW_HEIGHT_CELLS,
        )
        self.assertEqual(
            _default(runner.build_route_result, "search_half_miles"),
            DEFAULT_UI_SEARCH_HALF_MI,
        )
        self.assertEqual(
            _default(runner.build_route_result, "roads_first_penalty"),
            DEFAULT_ROADS_FIRST_PENALTY,
        )


if __name__ == "__main__":
    unittest.main()
