from __future__ import annotations

import contextlib
import io
import pathlib
import sys
import tomllib
import types
import unittest

from runfeeti import __version__
from runfeeti.__main__ import main
from runfeeti.geocode import _queries_to_try
from runfeeti.letters import (
    MVP_CELL_H,
    MVP_CELL_W,
    layout_word_fixed_pitch,
    layout_word_in_contract_cells,
    polyline_bounds,
)
from runfeeti.route_options import (
    DEFAULT_CLI_RADIUS_MI,
    DEFAULT_CLI_SEARCH_HALF_MI,
    DEFAULT_LETTER_GAP,
    DEFAULT_PREVIEW_HEIGHT_CELLS,
    DEFAULT_PREVIEW_WIDTH_CELLS,
    DEFAULT_ROADS_FIRST_PENALTY,
    DEFAULT_UI_RADIUS_MI,
    DEFAULT_UI_SEARCH_HALF_MI,
    MAX_LETTER_GAP,
    MAX_PREVIEW_CELLS,
    MAX_RADIUS_MI,
    MAX_ROADS_FIRST_PENALTY,
    MAX_SEARCH_HALF_MI,
    MIN_LETTER_GAP,
    MIN_PREVIEW_CELLS,
    MIN_RADIUS_MI,
    MIN_ROADS_FIRST_PENALTY,
    MIN_SEARCH_HALF_MI,
    normalize_word,
    parse_optional_block_m,
    parse_route_options,
    validate_preview_contract,
)
from runfeeti.us_address import (
    abbrev_from_display,
    build_geocode_line,
    normalize_zip,
    state_display_values,
)


class AddressHelpersTest(unittest.TestCase):
    def test_state_display_parses_selected_state(self) -> None:
        self.assertEqual(abbrev_from_display("Texas (TX)"), "TX")

    def test_state_placeholder_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Choose a state"):
            abbrev_from_display(state_display_values()[0])

    def test_zip_normalization(self) -> None:
        self.assertEqual(normalize_zip("78739"), "78739")
        self.assertEqual(normalize_zip("78739 1234"), "78739-1234")

    def test_build_geocode_line_validates_required_parts(self) -> None:
        self.assertEqual(
            build_geocode_line("123 Main St", "Austin", "tx", "78739"),
            "123 Main St, Austin, TX 78739",
        )
        with self.assertRaisesRegex(ValueError, "Enter a city"):
            build_geocode_line("123 Main St", "", "TX", "78739")


class LetterLayoutTest(unittest.TestCase):
    def test_fixed_pitch_letters_fit_cell_height(self) -> None:
        pts = layout_word_fixed_pitch("HI")
        min_x, min_y, max_x, max_y = polyline_bounds(pts)
        self.assertEqual((min_y, max_y), (0, MVP_CELL_H))
        self.assertGreaterEqual(max_x - min_x, MVP_CELL_W)

    def test_contract_layout_stays_inside_requested_box(self) -> None:
        pts = layout_word_in_contract_cells("RUN", contract_width=12, contract_height=4)
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        self.assertGreaterEqual(min(xs), 0)
        self.assertLessEqual(max(xs), 12)
        self.assertGreaterEqual(min(ys), 0)
        self.assertLessEqual(max(ys), 4)


class ParsingAndGeocodeQueryTest(unittest.TestCase):
    def test_parse_optional_block_m(self) -> None:
        self.assertIsNone(parse_optional_block_m(" "))
        self.assertEqual(parse_optional_block_m("42.5"), 42.5)

    def test_geocode_queries_include_suffix_fallbacks_and_zipless_variant(self) -> None:
        queries = _queries_to_try("123 Oak Lane, Austin, TX 78739")
        self.assertEqual(queries[0], "123 Oak Lane, Austin, TX 78739")
        self.assertIn("123 Oak Drive, Austin, TX 78739", queries)
        self.assertIn("123 Oak Lane, Austin, TX", queries)


class WordValidationTest(unittest.TestCase):
    def test_normalize_word_uppercases_and_collapses_spaces(self) -> None:
        self.assertEqual(normalize_word("  run   feeti  "), "RUN FEETI")

    def test_normalize_word_rejects_empty_or_unsupported_characters(self) -> None:
        with self.assertRaisesRegex(ValueError, "Enter a word"):
            normalize_word("   ")
        with self.assertRaisesRegex(ValueError, "A-Z and spaces"):
            normalize_word("RUN42")


class RouteOptionsTest(unittest.TestCase):
    def test_shared_defaults_are_inside_valid_bounds(self) -> None:
        self.assertLessEqual(MIN_RADIUS_MI, DEFAULT_CLI_RADIUS_MI)
        self.assertLessEqual(DEFAULT_CLI_RADIUS_MI, MAX_RADIUS_MI)
        self.assertLessEqual(MIN_RADIUS_MI, DEFAULT_UI_RADIUS_MI)
        self.assertLessEqual(DEFAULT_UI_RADIUS_MI, MAX_RADIUS_MI)
        self.assertLessEqual(MIN_SEARCH_HALF_MI, DEFAULT_CLI_SEARCH_HALF_MI)
        self.assertLessEqual(DEFAULT_CLI_SEARCH_HALF_MI, MAX_SEARCH_HALF_MI)
        self.assertLessEqual(MIN_SEARCH_HALF_MI, DEFAULT_UI_SEARCH_HALF_MI)
        self.assertLessEqual(DEFAULT_UI_SEARCH_HALF_MI, MAX_SEARCH_HALF_MI)
        self.assertLessEqual(MIN_LETTER_GAP, DEFAULT_LETTER_GAP)
        self.assertLessEqual(DEFAULT_LETTER_GAP, MAX_LETTER_GAP)
        self.assertLessEqual(MIN_PREVIEW_CELLS, DEFAULT_PREVIEW_WIDTH_CELLS)
        self.assertLessEqual(DEFAULT_PREVIEW_WIDTH_CELLS, MAX_PREVIEW_CELLS)
        self.assertLessEqual(MIN_PREVIEW_CELLS, DEFAULT_PREVIEW_HEIGHT_CELLS)
        self.assertLessEqual(DEFAULT_PREVIEW_HEIGHT_CELLS, MAX_PREVIEW_CELLS)
        self.assertLessEqual(MIN_ROADS_FIRST_PENALTY, DEFAULT_ROADS_FIRST_PENALTY)
        self.assertLessEqual(DEFAULT_ROADS_FIRST_PENALTY, MAX_ROADS_FIRST_PENALTY)

    def test_parse_route_options_normalizes_values(self) -> None:
        options = parse_route_options(
            radius_mi="1.5",
            letter_gap="2",
            block_m_raw="40",
            search_half_miles="3",
        )
        self.assertEqual(options.radius_mi, 1.5)
        self.assertEqual(options.letter_gap, 2)
        self.assertEqual(options.block_m, 40)
        self.assertEqual(options.block_m_raw, "40")
        self.assertEqual(options.search_half_miles, 3)
        self.assertEqual(options.roads_first_penalty, 10.0)

    def test_parse_route_options_accepts_roads_first_penalty(self) -> None:
        options = parse_route_options(
            radius_mi="1.5",
            letter_gap="2",
            block_m_raw="",
            search_half_miles="3",
            roads_first_penalty="25",
        )
        self.assertEqual(options.roads_first_penalty, 25.0)

    def test_parse_route_options_rejects_invalid_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "Search radius"):
            parse_route_options(
                radius_mi="0",
                letter_gap="1",
                block_m_raw="",
                search_half_miles="2",
            )
        with self.assertRaisesRegex(ValueError, "Letter gap"):
            parse_route_options(
                radius_mi="1",
                letter_gap="1.5",
                block_m_raw="",
                search_half_miles="2",
            )
        with self.assertRaisesRegex(ValueError, "Block size"):
            parse_route_options(
                radius_mi="1",
                letter_gap="1",
                block_m_raw="-4",
                search_half_miles="2",
            )
        with self.assertRaisesRegex(ValueError, "finite"):
            parse_route_options(
                radius_mi="nan",
                letter_gap="1",
                block_m_raw="",
                search_half_miles="2",
            )
        with self.assertRaisesRegex(ValueError, "Roads-first penalty"):
            parse_route_options(
                radius_mi="1",
                letter_gap="1",
                block_m_raw="",
                search_half_miles="2",
                roads_first_penalty="0.5",
            )

    def test_preview_contract_validation(self) -> None:
        self.assertEqual(validate_preview_contract(12, "4"), (12.0, 4.0))
        with self.assertRaisesRegex(ValueError, "Preview grid width"):
            validate_preview_contract(1, 4)
        with self.assertRaisesRegex(ValueError, "finite"):
            validate_preview_contract(float("inf"), 4)


class CliValidationTest(unittest.TestCase):
    def test_version_flag_prints_package_version(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = main(["--version"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue().strip(), f"RunFeeti {__version__}")

    def test_invalid_options_fail_before_route_build_import(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["123 Main St, Austin, TX", "HI", "--radius-mi", "0"])
        self.assertEqual(code, 2)

    def test_invalid_word_fails_before_route_build_import(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = main(["123 Main St, Austin, TX", "HI!"])
        self.assertEqual(code, 2)

    def test_missing_address_or_word_returns_usage_error(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            code = main([])
        self.assertEqual(code, 2)

    def test_gui_flag_works_through_main_entrypoint(self) -> None:
        calls: list[str] = []
        fake_gui = types.ModuleType("runfeeti.gui")

        def run_app() -> None:
            calls.append("run")

        fake_gui.run_app = run_app
        old_gui = sys.modules.get("runfeeti.gui")
        sys.modules["runfeeti.gui"] = fake_gui
        try:
            code = main(["--gui"])
        finally:
            if old_gui is None:
                sys.modules.pop("runfeeti.gui", None)
            else:
                sys.modules["runfeeti.gui"] = old_gui

        self.assertEqual(code, 0)
        self.assertEqual(calls, ["run"])

    def test_route_build_receives_normalized_word(self) -> None:
        calls: list[dict] = []
        fake_runner = types.ModuleType("runfeeti.runner")

        class FakeResult:
            report_text = "ok"
            routed = None
            steps = []

        def build_route_result(*args, **kwargs) -> FakeResult:
            calls.append({"args": args, "kwargs": kwargs})
            return FakeResult()

        fake_runner.build_route_result = build_route_result
        old_runner = sys.modules.get("runfeeti.runner")
        sys.modules["runfeeti.runner"] = fake_runner
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["123 Main St, Austin, TX", " run   feeti "])
        finally:
            if old_runner is None:
                sys.modules.pop("runfeeti.runner", None)
            else:
                sys.modules["runfeeti.runner"] = old_runner

        self.assertEqual(code, 0)
        self.assertEqual(calls[0]["args"][1], "RUN FEETI")

    def test_route_build_receives_parsed_cli_options(self) -> None:
        calls: list[dict] = []
        fake_runner = types.ModuleType("runfeeti.runner")

        class FakeResult:
            report_text = "ok"
            routed = None
            steps = []

        def build_route_result(*args, **kwargs) -> FakeResult:
            calls.append({"args": args, "kwargs": kwargs})
            return FakeResult()

        fake_runner.build_route_result = build_route_result
        old_runner = sys.modules.get("runfeeti.runner")
        sys.modules["runfeeti.runner"] = fake_runner
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "123 Main St, Austin, TX",
                        "HI",
                        "--no-roads-first",
                        "--roads-first-penalty",
                        "25",
                    ]
                )
        finally:
            if old_runner is None:
                sys.modules.pop("runfeeti.runner", None)
            else:
                sys.modules["runfeeti.runner"] = old_runner

        self.assertEqual(code, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"][:2], ("123 Main St, Austin, TX", "HI"))
        self.assertFalse(calls[0]["kwargs"]["roads_first"])
        self.assertEqual(calls[0]["kwargs"]["roads_first_penalty"], 25.0)


class MetadataVersionTest(unittest.TestCase):
    def test_package_version_matches_pyproject_version(self) -> None:
        root = pathlib.Path(__file__).resolve().parents[1]
        with (root / "pyproject.toml").open("rb") as f:
            pyproject = tomllib.load(f)
        self.assertEqual(pyproject["project"]["version"], __version__)


if __name__ == "__main__":
    unittest.main()
