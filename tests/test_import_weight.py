from __future__ import annotations

import importlib
import sys
import unittest


class ImportWeightTest(unittest.TestCase):
    def test_gui_import_does_not_load_route_builder(self) -> None:
        old_gui = sys.modules.pop("runfeeti.gui", None)
        old_runner = sys.modules.pop("runfeeti.runner", None)
        try:
            importlib.import_module("runfeeti.gui")
            self.assertNotIn("runfeeti.runner", sys.modules)
        finally:
            sys.modules.pop("runfeeti.gui", None)
            if old_gui is not None:
                sys.modules["runfeeti.gui"] = old_gui
            if old_runner is not None:
                sys.modules["runfeeti.runner"] = old_runner

    def test_result_import_does_not_load_routing_or_directions(self) -> None:
        old_result = sys.modules.pop("runfeeti.result", None)
        old_routing = sys.modules.pop("runfeeti.routing", None)
        old_directions = sys.modules.pop("runfeeti.directions", None)
        try:
            importlib.import_module("runfeeti.result")
            self.assertNotIn("runfeeti.routing", sys.modules)
            self.assertNotIn("runfeeti.directions", sys.modules)
        finally:
            sys.modules.pop("runfeeti.result", None)
            if old_result is not None:
                sys.modules["runfeeti.result"] = old_result
            if old_routing is not None:
                sys.modules["runfeeti.routing"] = old_routing
            if old_directions is not None:
                sys.modules["runfeeti.directions"] = old_directions


if __name__ == "__main__":
    unittest.main()
