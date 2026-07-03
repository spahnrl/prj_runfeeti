from __future__ import annotations

import argparse
import sys

from runfeeti import __version__
from runfeeti.route_options import (
    DEFAULT_CLI_RADIUS_MI,
    DEFAULT_CLI_SEARCH_HALF_MI,
    DEFAULT_LETTER_GAP,
    DEFAULT_ROADS_FIRST_PENALTY,
    normalize_word,
    parse_route_options,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="RunFeeti: spell a word with city blocks and print turn-by-turn running directions.",
    )
    p.add_argument("address", nargs="?", help="Starting address (geocoded via OpenStreetMap Nominatim).")
    p.add_argument("word", nargs="?", help="Letters to spell (A-Z). Spaces add extra gap.")
    p.add_argument(
        "--gui",
        action="store_true",
        help="Open the Tkinter desktop interface.",
    )
    p.add_argument(
        "--version",
        action="store_true",
        help="Print the RunFeeti version and exit.",
    )
    p.add_argument(
        "--radius-mi",
        type=float,
        default=DEFAULT_CLI_RADIUS_MI,
        help=f"Search radius in miles for street data (default: {DEFAULT_CLI_RADIUS_MI:g}).",
    )
    p.add_argument(
        "--letter-gap",
        type=int,
        default=DEFAULT_LETTER_GAP,
        help=f"Extra grid units between letters (default: {DEFAULT_LETTER_GAP}).",
    )
    p.add_argument(
        "--block-m",
        type=float,
        default=None,
        help="Override meters per template 'block' (default: median OSM edge length in the area).",
    )
    p.add_argument(
        "--map",
        action="store_true",
        help="Open a turtle window with the route and turn names after printing directions.",
    )
    p.add_argument(
        "--optimize-start",
        action="store_true",
        help=(
            "Search within ±SEARCH_HALF_MI miles for a template center with a more grid-like "
            "walk mesh (slower; downloads a larger OSM bbox)."
        ),
    )
    p.add_argument(
        "--search-half-mi",
        type=float,
        default=DEFAULT_CLI_SEARCH_HALF_MI,
        help=f"Half-span in miles for --optimize-start scan (default: {DEFAULT_CLI_SEARCH_HALF_MI:g}).",
    )
    p.add_argument(
        "--no-roads-first",
        action="store_true",
        help="Do not penalize footpath-like shortcuts when routing.",
    )
    p.add_argument(
        "--roads-first-penalty",
        type=float,
        default=DEFAULT_ROADS_FIRST_PENALTY,
        help=(
            "Multiplier applied to footpath-like edges when roads-first routing is on "
            f"(default: {DEFAULT_ROADS_FIRST_PENALTY:g})."
        ),
    )
    args = p.parse_args(argv)

    if args.version:
        print(f"RunFeeti {__version__}")
        return 0

    if args.gui:
        from runfeeti.gui import run_app

        run_app()
        return 0

    if not args.address or args.word is None:
        p.print_usage(sys.stderr)
        print("runfeeti: error: address and word are required unless --gui is used.", file=sys.stderr)
        return 2

    try:
        word = normalize_word(args.word)
        options = parse_route_options(
            radius_mi=args.radius_mi,
            letter_gap=args.letter_gap,
            block_m_raw=args.block_m,
            search_half_miles=args.search_half_mi,
            roads_first_penalty=args.roads_first_penalty,
        )
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2

    from runfeeti.runner import build_route_result

    try:
        result = build_route_result(
            args.address,
            word,
            options.radius_mi,
            options.letter_gap,
            options.block_m_raw,
            optimize_start=args.optimize_start,
            search_half_miles=options.search_half_miles,
            roads_first=not args.no_roads_first,
            roads_first_penalty=options.roads_first_penalty,
        )
    except ValueError as e:
        msg = str(e)
        print(msg, file=sys.stderr)
        if "Could not geocode" in msg or "Address is empty" in msg:
            return 2
        return 3

    print(result.report_text)
    if args.map:
        from runfeeti.turtle_map import show_route_turtle

        print("Opening turtle map (close the map window to finish)...", file=sys.stderr)
        show_route_turtle(
            result.routed,
            result.steps,
            title=f"RunFeeti - {word}",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
