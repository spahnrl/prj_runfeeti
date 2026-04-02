from __future__ import annotations

import argparse
import sys

from runfeeti.runner import build_route_result
from runfeeti.turtle_map import show_route_turtle


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="RunFeeti: spell a word with city blocks and print turn-by-turn running directions.",
    )
    p.add_argument("address", help="Starting address (geocoded via OpenStreetMap Nominatim).")
    p.add_argument("word", help="Letters to spell (A–Z). Spaces add extra gap.")
    p.add_argument(
        "--radius-mi",
        type=float,
        default=1.0,
        help="Search radius in miles for street data (default: 1.0).",
    )
    p.add_argument(
        "--letter-gap",
        type=int,
        default=1,
        help="Extra grid units between letters (default: 1).",
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
        default=2.0,
        help="Half-span in miles for --optimize-start scan (default: 2.0).",
    )
    args = p.parse_args(argv)
    if args.search_half_mi <= 0 or args.search_half_mi > 10:
        print("--search-half-mi must be between 0 and 10.", file=sys.stderr)
        return 2

    block_raw = "" if args.block_m is None else str(args.block_m)

    try:
        result = build_route_result(
            args.address,
            args.word,
            args.radius_mi,
            args.letter_gap,
            block_raw,
            optimize_start=args.optimize_start,
            search_half_miles=args.search_half_mi,
        )
    except ValueError as e:
        msg = str(e)
        print(msg, file=sys.stderr)
        if "Could not geocode" in msg or "Address is empty" in msg:
            return 2
        return 3

    print(result.report_text)
    if args.map:
        print("Opening turtle map (close the map window to finish)...", file=sys.stderr)
        show_route_turtle(
            result.routed,
            result.steps,
            title=f"RunFeeti - {args.word.upper().strip()}",
        )
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--gui":
        from runfeeti.gui import run_app

        run_app()
    else:
        raise SystemExit(main())
