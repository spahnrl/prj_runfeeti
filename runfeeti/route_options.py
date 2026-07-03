from __future__ import annotations

from dataclasses import dataclass
import math
import re


MIN_RADIUS_MI = 0.25
MAX_RADIUS_MI = 50.0
DEFAULT_CLI_RADIUS_MI = 1.0
DEFAULT_UI_RADIUS_MI = 5.0
MIN_SEARCH_HALF_MI = 0.1
MAX_SEARCH_HALF_MI = 10.0
DEFAULT_CLI_SEARCH_HALF_MI = 2.0
DEFAULT_UI_SEARCH_HALF_MI = 5.0
MIN_LETTER_GAP = 0
MAX_LETTER_GAP = 10
DEFAULT_LETTER_GAP = 1
MIN_PREVIEW_CELLS = 2.0
MAX_PREVIEW_CELLS = 500.0
DEFAULT_PREVIEW_WIDTH_CELLS = 12
DEFAULT_PREVIEW_HEIGHT_CELLS = 4
MIN_ROADS_FIRST_PENALTY = 1.0
MAX_ROADS_FIRST_PENALTY = 100.0
DEFAULT_ROADS_FIRST_PENALTY = 10.0
SUPPORTED_WORD_PATTERN = re.compile(r"^[A-Z ]+$")


@dataclass(frozen=True)
class RouteOptions:
    radius_mi: float
    letter_gap: int
    block_m: float | None
    search_half_miles: float
    roads_first_penalty: float

    @property
    def block_m_raw(self) -> str:
        return "" if self.block_m is None else f"{self.block_m:g}"


def parse_optional_block_m(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    value = float(s)
    if not math.isfinite(value):
        raise ValueError("Block size must be a finite number.")
    if value <= 0:
        raise ValueError("Block size must be greater than 0 meters.")
    return value


def normalize_word(raw: str | None) -> str:
    if raw is None:
        raise ValueError("Enter a word to spell.")
    word = " ".join(str(raw).upper().split())
    if not word:
        raise ValueError("Enter a word to spell.")
    if not SUPPORTED_WORD_PATTERN.fullmatch(word):
        raise ValueError("Word can only contain letters A-Z and spaces.")
    return word


def parse_route_options(
    *,
    radius_mi: str | float | int,
    letter_gap: str | float | int,
    block_m_raw: str | float | int | None,
    search_half_miles: str | float | int,
    roads_first_penalty: str | float | int = DEFAULT_ROADS_FIRST_PENALTY,
) -> RouteOptions:
    try:
        radius = float(radius_mi)
    except (TypeError, ValueError) as exc:
        raise ValueError("Search radius must be a number of miles.") from exc
    if not math.isfinite(radius):
        raise ValueError("Search radius must be a finite number of miles.")
    if radius < MIN_RADIUS_MI or radius > MAX_RADIUS_MI:
        raise ValueError(f"Search radius must be between {MIN_RADIUS_MI:g} and {MAX_RADIUS_MI:g} miles.")

    try:
        gap_raw = float(letter_gap)
    except (TypeError, ValueError) as exc:
        raise ValueError("Letter gap must be a whole number.") from exc
    if not math.isfinite(gap_raw):
        raise ValueError("Letter gap must be a finite whole number.")
    if not gap_raw.is_integer():
        raise ValueError("Letter gap must be a whole number.")
    gap = int(gap_raw)
    if gap < MIN_LETTER_GAP or gap > MAX_LETTER_GAP:
        raise ValueError(f"Letter gap must be between {MIN_LETTER_GAP} and {MAX_LETTER_GAP}.")

    try:
        search = float(search_half_miles)
    except (TypeError, ValueError) as exc:
        raise ValueError("Grid search span must be a number of miles.") from exc
    if not math.isfinite(search):
        raise ValueError("Grid search span must be a finite number of miles.")
    if search < MIN_SEARCH_HALF_MI or search > MAX_SEARCH_HALF_MI:
        raise ValueError(
            f"Grid search span must be between {MIN_SEARCH_HALF_MI:g} and {MAX_SEARCH_HALF_MI:g} miles."
        )

    try:
        block_m = parse_optional_block_m(block_m_raw)
    except ValueError as exc:
        raise ValueError("Block size must be empty or a positive number of meters.") from exc

    try:
        penalty = float(roads_first_penalty)
    except (TypeError, ValueError) as exc:
        raise ValueError("Roads-first penalty must be a number.") from exc
    if not math.isfinite(penalty):
        raise ValueError("Roads-first penalty must be a finite number.")
    if penalty < MIN_ROADS_FIRST_PENALTY or penalty > MAX_ROADS_FIRST_PENALTY:
        raise ValueError(
            f"Roads-first penalty must be between {MIN_ROADS_FIRST_PENALTY:g} and "
            f"{MAX_ROADS_FIRST_PENALTY:g}."
        )

    return RouteOptions(
        radius_mi=radius,
        letter_gap=gap,
        block_m=block_m,
        search_half_miles=search,
        roads_first_penalty=penalty,
    )


def validate_preview_contract(width_cells: float | int, height_cells: float | int) -> tuple[float, float]:
    try:
        width = float(width_cells)
        height = float(height_cells)
    except (TypeError, ValueError) as exc:
        raise ValueError("Preview grid width and height must be numbers.") from exc
    if not math.isfinite(width):
        raise ValueError("Preview grid width must be a finite number of cells.")
    if not math.isfinite(height):
        raise ValueError("Preview grid height must be a finite number of cells.")
    if width < MIN_PREVIEW_CELLS or width > MAX_PREVIEW_CELLS:
        raise ValueError(
            f"Preview grid width must be between {MIN_PREVIEW_CELLS:g} and {MAX_PREVIEW_CELLS:g} cells."
        )
    if height < MIN_PREVIEW_CELLS or height > MAX_PREVIEW_CELLS:
        raise ValueError(
            f"Preview grid height must be between {MIN_PREVIEW_CELLS:g} and {MAX_PREVIEW_CELLS:g} cells."
        )
    return width, height
