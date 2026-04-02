"""
Orthogonal "digital" letter shapes on a small grid.

Each letter is (width, points) where points are (x, y) integer vertices in letter space:
- x increases east, y increases north; bottom of the letter sits on y=0.
- Consecutive points share either x or y (axis-aligned segments only).

Product baseline (lettering):
- Templates are scaled by LETTER_GRID_SCALE so cap height is 8 grid steps (legacy 4 × 2),
  giving higher resolution for snapping — roughly "4 logical blocks" tall with finer strokes.
- MVP routing uses layout_word_fixed_pitch: each glyph is fit into a 3×4 cell with pitch (cell_w + gap).
- Legacy layout_word retains scaled variable-width placement for non-MVP experiments.
- Route shape fidelity scoring belongs in routing, not here.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

Point = Tuple[int, int]
LetterDef = Tuple[int, List[Point]]

# Integer scale applied to legacy 0..4 cap-height definitions (previously felt "2-block" coarse).
LETTER_GRID_SCALE = 2

# MVP fixed-pitch cell (grid units) and inter-letter gutter; cursor starts at 0 (no leading pad).
MVP_CELL_W = 3
MVP_CELL_H = 4
MVP_GAP_DEFAULT = 1


def _manhattan_bridge(a: Point, b: Point) -> List[Point]:
    """Insert intermediate vertices so the walk a→b is axis-aligned (horizontal then vertical)."""
    ax, ay = a
    bx, by = b
    if a == b:
        return []
    if ax == bx or ay == by:
        return [b]
    return [(bx, ay), b]


def expand_axis_aligned(points: List[Point]) -> List[Point]:
    if not points:
        return []
    out: List[Point] = [points[0]]
    for nxt in points[1:]:
        prev = out[-1]
        if prev == nxt:
            out.append(nxt)
            continue
        bridge = _manhattan_bridge(prev, nxt)
        out.extend(bridge)
    return out


def _scale_letterdef(defn: LetterDef, scale: int) -> LetterDef:
    w, pts = defn
    return (w * scale, [(scale * x, scale * y) for x, y in pts])


# fmt: off
# Corner sequences (may include implied diagonals); expand_axis_aligned makes them grid-legal.
# Stored at legacy resolution; LETTER_GRID_SCALE multiplies footprint for readability.
_LETTERS_RAW_BASE: Dict[str, LetterDef] = {
    "A": (4, [(0, 0), (0, 4), (2, 4), (2, 2), (1, 2), (2, 2), (2, 4), (4, 4), (4, 0)]),
    "B": (4, [(0, 0), (0, 4), (3, 4), (3, 3), (0, 3), (3, 3), (3, 2), (0, 2), (3, 2), (3, 0), (0, 0)]),
    "C": (4, [(4, 0), (0, 0), (0, 4), (4, 4)]),
    "D": (4, [(0, 0), (0, 4), (3, 4), (3, 0), (0, 0)]),
    "E": (4, [(4, 0), (0, 0), (0, 4), (4, 4), (0, 4), (0, 2), (3, 2)]),
    "F": (4, [(0, 0), (0, 4), (4, 4), (0, 4), (0, 2), (3, 2)]),
    "G": (4, [(2, 2), (4, 2), (4, 0), (0, 0), (0, 4), (4, 4), (4, 2)]),
    "H": (4, [(0, 0), (0, 4), (0, 2), (4, 2), (4, 4), (4, 0)]),
    "I": (2, [(0, 0), (0, 4), (1, 4), (1, 0), (0, 0)]),
    "J": (4, [(0, 4), (4, 4), (4, 0), (2, 0), (0, 0), (0, 3)]),
    "K": (4, [(0, 0), (0, 4), (0, 2), (3, 4), (0, 2), (3, 0)]),
    "L": (4, [(0, 4), (0, 0), (4, 0)]),
    "M": (5, [(0, 0), (0, 4), (2, 4), (2, 2), (3, 2), (3, 4), (5, 4), (5, 0)]),
    "N": (4, [(0, 0), (0, 4), (1, 4), (2, 3), (3, 2), (4, 1), (4, 0), (4, 4)]),
    "O": (4, [(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)]),
    "P": (4, [(0, 0), (0, 4), (3, 4), (3, 2), (0, 2)]),
    "Q": (4, [(0, 0), (0, 4), (4, 4), (4, 0), (2, 0), (4, 2), (4, 0), (0, 0)]),
    "R": (4, [(0, 0), (0, 4), (3, 4), (3, 2), (1, 2), (3, 0), (0, 0)]),
    "S": (4, [(4, 4), (0, 4), (0, 2), (4, 2), (4, 0), (0, 0)]),
    "T": (4, [(0, 4), (4, 4), (2, 4), (2, 0)]),
    "U": (4, [(0, 4), (0, 0), (4, 0), (4, 4)]),
    "V": (4, [(0, 4), (2, 0), (4, 4)]),
    "W": (5, [(0, 4), (0, 0), (2, 2), (4, 0), (4, 4)]),
    "X": (4, [(0, 4), (4, 0), (2, 2), (4, 4), (0, 0)]),
    "Y": (4, [(0, 4), (2, 2), (4, 4), (2, 2), (2, 0)]),
    "Z": (4, [(0, 4), (4, 4), (0, 0), (4, 0)]),
}
# fmt: on

_LETTERS_RAW: Dict[str, LetterDef] = {
    ch: _scale_letterdef(defn, LETTER_GRID_SCALE) for ch, defn in _LETTERS_RAW_BASE.items()
}

_LETTERS: Dict[str, LetterDef] = {
    ch: (w, expand_axis_aligned(pts)) for ch, (w, pts) in _LETTERS_RAW.items()
}

_FALLBACK_RAW_BASE: LetterDef = (4, [(0, 0), (0, 4), (4, 4), (4, 0), (0, 0)])
_FALLBACK_RAW: LetterDef = _scale_letterdef(_FALLBACK_RAW_BASE, LETTER_GRID_SCALE)
_FALLBACK: LetterDef = (_FALLBACK_RAW[0], expand_axis_aligned(_FALLBACK_RAW[1]))


def letter(ch: str) -> LetterDef:
    c = ch.upper()
    return _LETTERS.get(c, _FALLBACK)


def _fit_glyph_to_cell(pts: List[Point], cell_w: int, cell_h: int) -> List[Point]:
    """Uniform scale + translate legacy glyph into [0, cell_w] x [0, cell_h], baseline at y=0, centered in x."""
    if not pts:
        return [(0, 0), (cell_w, 0)]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w_box = max(float(maxx - minx), 1e-9)
    h_box = max(float(maxy - miny), 1e-9)
    s = min(cell_w / w_box, cell_h / h_box)
    sw = w_box * s
    ox = (cell_w - sw) / 2.0
    oy = 0.0
    rounded: List[Point] = []
    for x, y in pts:
        fx = (x - minx) * s + ox
        fy = (y - miny) * s + oy
        rounded.append((int(round(fx)), int(round(fy))))
    out: List[Point] = [rounded[0]]
    for p in rounded[1:]:
        if p != out[-1]:
            out.append(p)
    return out


def layout_word_fixed_pitch(
    word: str,
    *,
    cell_w: int = MVP_CELL_W,
    cell_h: int = MVP_CELL_H,
    gap: int = MVP_GAP_DEFAULT,
) -> List[Point]:
    """
    Fixed-pitch MVP layout: fit each scaled glyph into a cell_w × cell_h box, advance by (cell_w + gap).
    Whitespace advances one slot (cell_w + gap). No leading padding; content starts at x=0.
    """
    w = word.upper().strip()
    if not w:
        return [(0, 0)]

    out: List[Point] = []
    cursor_x = 0
    first = True

    for ch in w:
        if ch.isspace():
            cursor_x += cell_w + gap
            continue
        _adv, pts = letter(ch)
        fitted = expand_axis_aligned(_fit_glyph_to_cell(pts, cell_w, cell_h))
        shifted = expand_axis_aligned([(cursor_x + x, y) for x, y in fitted])
        if first:
            out.extend(shifted)
            first = False
        elif shifted:
            joint = expand_axis_aligned([out[-1], shifted[0]])
            out.extend(joint[1:])
            out.extend(shifted[1:])
        cursor_x += cell_w + gap

    return out


def layout_word_in_contract_cells(
    word: str,
    *,
    gap: int = MVP_GAP_DEFAULT,
    contract_width: float,
    contract_height: float,
) -> List[Tuple[float, float]]:
    """
    Place the fixed-pitch letter polyline inside a rectangle [0, contract_width] × [0, contract_height]
    in abstract grid cells (uniform scale, centered; aspect ratio preserved).
    """
    if contract_width <= 0 or contract_height <= 0:
        raise ValueError("contract_width and contract_height must be positive")

    grid = layout_word_fixed_pitch(word, gap=gap)
    if len(grid) < 2:
        grid = [(0, 0), (1, 0)]

    minx, miny, maxx, maxy = polyline_bounds(grid)
    lw = float(maxx - minx)
    lh = float(maxy - miny)
    if lw < 1e-9:
        lw = 1.0
    if lh < 1e-9:
        lh = 1.0

    cw, ch = float(contract_width), float(contract_height)
    s = min(cw / lw, ch / lh)
    sw, sh = lw * s, lh * s
    ox = (cw - sw) / 2.0
    oy = (ch - sh) / 2.0

    out: List[Tuple[float, float]] = []
    for gx, gy in grid:
        ux = (float(gx) - float(minx)) * s + ox
        uy = (float(gy) - float(miny)) * s + oy
        out.append((ux, uy))
    return out


def letter_polyline_intrinsic_cell_span(word: str, *, gap: int = MVP_GAP_DEFAULT) -> Tuple[int, int]:
    """Width and height span of fixed-pitch layout in integer cell units (max−min)."""
    grid = layout_word_fixed_pitch(word, gap=gap)
    if len(grid) < 2:
        return 1, 1
    gx0, gy0, gx1, gy1 = polyline_bounds(grid)
    return max(int(gx1 - gx0), 1), max(int(gy1 - gy0), 1)


def layout_word(word: str, gap: int = 1) -> List[Point]:
    """Concatenate letter polylines with a horizontal gap between letters (same baseline y=0)."""
    w = word.upper().strip()
    if not w:
        return [(0, 0)]

    out: List[Point] = []
    cursor_x = 0
    first = True

    for ch in w:
        if ch.isspace():
            cursor_x += gap + 2 * LETTER_GRID_SCALE
            continue
        width, pts = letter(ch)
        shifted = expand_axis_aligned([(cursor_x + x, y) for x, y in pts])
        if first:
            out.extend(shifted)
            first = False
        elif shifted:
            joint = expand_axis_aligned([out[-1], shifted[0]])
            out.extend(joint[1:])
            out.extend(shifted[1:])
        cursor_x += width + gap

    return out


def polyline_bounds(points: List[Point]) -> Tuple[int, int, int, int]:
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)
