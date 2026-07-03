from __future__ import annotations

import unittest

from runfeeti.runner import build_grid_debug_result, build_route_result


class RunnerValidationTest(unittest.TestCase):
    def test_build_route_result_rejects_invalid_options_before_geocoding(self) -> None:
        with self.assertRaisesRegex(ValueError, "Search radius"):
            build_route_result(
                "123 Main St, Austin, TX",
                "HI",
                0,
                1,
                "",
            )

        with self.assertRaisesRegex(ValueError, "Grid search span"):
            build_route_result(
                "123 Main St, Austin, TX",
                "HI",
                1,
                1,
                "",
                search_half_miles=0,
            )

    def test_build_grid_debug_result_rejects_invalid_options_before_geocoding(self) -> None:
        with self.assertRaisesRegex(ValueError, "Letter gap"):
            build_grid_debug_result(
                "123 Main St, Austin, TX",
                "HI",
                1,
                1.5,
                "",
            )

        with self.assertRaisesRegex(ValueError, "Preview grid width"):
            build_grid_debug_result(
                "123 Main St, Austin, TX",
                "HI",
                1,
                1,
                "",
                preview_contract_w=1,
            )


if __name__ == "__main__":
    unittest.main()
