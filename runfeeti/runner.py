from __future__ import annotations

from dataclasses import dataclass

import networkx as nx

from runfeeti.directions import (
    directions_from_path,
    enrich_corner_labels,
    format_steps,
    summary_from_gdf,
)
from runfeeti.geocode import geocode_address, lookup_corner_labels
from runfeeti.letters import MVP_CELL_H, MVP_CELL_W
from runfeeti.result import RouteBuildResult
from runfeeti.route_options import (
    DEFAULT_PREVIEW_HEIGHT_CELLS,
    DEFAULT_PREVIEW_WIDTH_CELLS,
    DEFAULT_ROADS_FIRST_PENALTY,
    DEFAULT_UI_SEARCH_HALF_MI,
    normalize_word,
    parse_route_options,
    validate_preview_contract,
)
from runfeeti.routing import (
    GridPreviewContext,
    RoutedPath,
    StreetBoxResolution,
    build_grid_preview,
    build_route,
    projected_point_to_latlon,
    resolve_street_box_corners,
)


@dataclass(frozen=True)
class GridDebugBuildResult:
    """Grid visualization only: no snap, no shortest-path routing."""

    report_text: str
    graph: nx.MultiDiGraph
    preview: GridPreviewContext
    grid_points_latlon: list[tuple[float, float]]
    box_ring_latlon: list[tuple[float, float]]
    layout_mode_line: str
    preview_contract_w: float
    preview_contract_h: float
    total_grid_points: int
    active_box_label: str


def _template_block_diagnostic_lines(
    routed: RoutedPath,
    *,
    secondary: bool = False,
) -> list[str]:
    G = routed.graph
    minx = routed.template_bbox_min_x
    miny = routed.template_bbox_min_y
    maxx = routed.template_bbox_max_x
    maxy = routed.template_bbox_max_y
    corners_proj: list[tuple[str, float, float]] = [
        ("Bottom left", minx, miny),
        ("Bottom right", maxx, miny),
        ("Top right", maxx, maxy),
        ("Top left", minx, maxy),
    ]
    latlons = [projected_point_to_latlon(G, px, py) for _, px, py in corners_proj]
    print(
        "Resolving intended text-block corners (~1 s per corner via Nominatim)...",
        flush=True,
    )
    labels = lookup_corner_labels(latlons)
    crs = G.graph.get("crs", "")
    title = (
        "Secondary — intended text block corners (axis-aligned bbox of letter template; route still centered here):"
        if secondary
        else "Intended text block corners (axis-aligned bbox of letter template in map space; before snap):"
    )
    lines = [
        title,
        f"  Projected CRS: {crs}",
    ]
    for (title, px, py), (lat, lon), lab in zip(corners_proj, latlons, labels, strict=True):
        lines.append(
            f"  {title}: [{lab}]  proj_m=({px:.1f}, {py:.1f})  WGS84=({lat:.5f}, {lon:.5f})"
        )
    lines.append("")
    return lines


def _street_box_diagnostic_lines(
    G: nx.MultiDiGraph,
    resolution: StreetBoxResolution,
) -> list[str]:
    if not resolution.ok:
        err = resolution.error or "Unknown error"
        return [
            "Street-grid box: could not resolve all four corners from OSM street names.",
            f"  {err}",
            "  Routing still uses the usual template-centered placement (see template bbox below).",
            "",
        ]
    corners: list[tuple[str, float, float]] = [
        ("Bottom-left (BL)", resolution.bl[0], resolution.bl[1]),
        ("Bottom-right (BR)", resolution.br[0], resolution.br[1]),
        ("Top-left (TL)", resolution.tl[0], resolution.tl[1]),
        ("Top-right (TR)", resolution.tr[0], resolution.tr[1]),
    ]
    latlons = [projected_point_to_latlon(G, px, py) for _, px, py in corners]
    print(
        "Resolving street-box corners (~1 s per corner via Nominatim)...",
        flush=True,
    )
    labels = lookup_corner_labels(latlons)
    crs = G.graph.get("crs", "")
    lines = [
        "Street-grid box corners (named OSM streets intersection; letters are not yet placed inside this rectangle):",
        (
            f"  Streets — bottom {resolution.bottom_q!r}, top {resolution.top_q!r}, "
            f"left {resolution.left_q!r}, right {resolution.right_q!r}"
        ),
        f"  Projected CRS: {crs}",
    ]
    for (title, px, py), (lat, lon), lab in zip(corners, latlons, labels, strict=True):
        lines.append(
            f"  {title}: [{lab}]  proj_m=({px:.1f}, {py:.1f})  WGS84=({lat:.5f}, {lon:.5f})"
        )
    if resolution.notes:
        lines.append("  Resolution notes:")
        for note in resolution.notes:
            lines.append(f"    • {note}")
    lines.append("")
    return lines


def _template_box_ring_latlon(
    G: nx.MultiDiGraph,
    preview: GridPreviewContext,
) -> list[tuple[float, float]]:
    mi_x, mi_y = preview.template_min_x, preview.template_min_y
    ma_x, ma_y = preview.template_max_x, preview.template_max_y
    bl = projected_point_to_latlon(G, mi_x, mi_y)
    br = projected_point_to_latlon(G, ma_x, mi_y)
    tr = projected_point_to_latlon(G, ma_x, ma_y)
    tl = projected_point_to_latlon(G, mi_x, ma_y)
    return [bl, br, tr, tl, bl]


def _street_box_ring_latlon(
    G: nx.MultiDiGraph,
    resolution: StreetBoxResolution,
) -> list[tuple[float, float]]:
    assert resolution.ok and resolution.bl and resolution.br and resolution.tl and resolution.tr
    bl = projected_point_to_latlon(G, resolution.bl[0], resolution.bl[1])
    br = projected_point_to_latlon(G, resolution.br[0], resolution.br[1])
    tr = projected_point_to_latlon(G, resolution.tr[0], resolution.tr[1])
    tl = projected_point_to_latlon(G, resolution.tl[0], resolution.tl[1])
    return [bl, br, tr, tl, bl]


def build_grid_debug_result(
    address: str,
    word: str,
    radius_mi: float,
    letter_gap: int,
    block_m_raw: str,
    *,
    roads_first: bool = True,
    roads_first_penalty: float = DEFAULT_ROADS_FIRST_PENALTY,
    street_box: tuple[str, str, str, str] | None = None,
    preview_contract_w: float = DEFAULT_PREVIEW_WIDTH_CELLS,
    preview_contract_h: float = DEFAULT_PREVIEW_HEIGHT_CELLS,
) -> GridDebugBuildResult:
    """
    Geocode, download walk graph, compute fixed-pitch grid waypoints and active box corners.
    Does not run snap_route or directions. Grid-search optimize_start is not used.
    """
    word = normalize_word(word)
    options = parse_route_options(
        radius_mi=radius_mi,
        letter_gap=letter_gap,
        block_m_raw=block_m_raw,
        search_half_miles=DEFAULT_UI_SEARCH_HALF_MI,
        roads_first_penalty=roads_first_penalty,
    )
    preview_contract_w, preview_contract_h = validate_preview_contract(
        preview_contract_w,
        preview_contract_h,
    )

    radius_m = max(400.0, options.radius_mi * 1609.34)
    geo = geocode_address(address)
    preview = build_grid_preview(
        geo.latitude,
        geo.longitude,
        word,
        radius_m=radius_m,
        letter_gap=options.letter_gap,
        block_scale=options.block_m,
        roads_first=roads_first,
        roads_first_penalty=options.roads_first_penalty,
        preview_contract_w=preview_contract_w,
        preview_contract_h=preview_contract_h,
    )
    G = preview.graph

    street_res: StreetBoxResolution | None = None
    if street_box is not None:
        bq, tq, lq, rq = street_box
        street_res = resolve_street_box_corners(G, bq, tq, lq, rq)

    if street_res is not None and street_res.ok:
        box_ring = _street_box_ring_latlon(G, street_res)
        active_label = "Street-grid box (named OSM streets ∩)"
    else:
        box_ring = _template_box_ring_latlon(G, preview)
        if street_res is not None and not street_res.ok:
            active_label = (
                "Template axis-aligned bbox (street box failed; corners from letter template)"
            )
        else:
            active_label = "Template axis-aligned bbox (letter layout, centered on start)"

    grid_ll = [
        projected_point_to_latlon(G, x, y) for x, y in preview.waypoints_xy
    ]
    n_pts = len(preview.waypoints_xy)
    pcw, pch = preview.preview_contract_w, preview.preview_contract_h
    footprint_m_w = pcw * preview.block_m
    footprint_m_h = pch * preview.block_m
    layout_line = (
        f"fixed-pitch {MVP_CELL_W}×{MVP_CELL_H} glyphs, letter gap {options.letter_gap}; "
        f"preview contract {pcw:g}×{pch:g} cells"
    )

    lines: list[str] = [
        "=== GRID PREVIEW (no walking route) ===",
        "",
        f"Start: {geo.display_name}",
        f"Word: {word.upper().strip()!r}",
        f"Radius: {options.radius_mi} mi ({radius_m:.0f} m) - default raised for route building; larger OSM download.",
        f"Cell / block size (meters per contract cell): {preview.block_m:.1f} m",
        f"Requested preview footprint: {footprint_m_w:.1f} m × {footprint_m_h:.1f} m "
        f"({pcw:g} × {pch:g} cells × block size).",
        "",
        "Layout mode:",
        f"  {layout_line}",
        f"  Letter intrinsic span (fixed-pitch cells, before uniform fit): "
        f"{preview.letter_intrinsic_w} × {preview.letter_intrinsic_h}",
        f"  Placement: contract centered on geocoded start (optimize_start not used in preview).",
        "",
        "Preview contract (explicit):",
        f"  Requested width (cells):  {pcw:g}",
        f"  Requested height (cells): {pch:g}",
        f"  Actual plotted vertices: {n_pts}",
        "",
        f"Active box on map: {active_label}",
        "  Corners WGS84 (BL → BR → TR → TL, closed ring on map):",
    ]
    for i, (lat, lon) in enumerate(box_ring[:-1]):
        lines.append(f"    {i + 1}. ({lat:.5f}, {lon:.5f})")
    lines.append("")
    if street_res is not None and street_res.ok:
        lines.append(
            "Note: Street box resolved — red outline on the map follows OSM street geometry, "
            "not the axis-aligned preview contract. Blue vertices still use the contract × block size at the start."
        )
        lines.append("")

    if street_box is not None and street_res is not None:
        if street_res.ok:
            lines.append("Street names (reference):")
            lines.append(
                f"  bottom {street_res.bottom_q!r}, top {street_res.top_q!r}, "
                f"left {street_res.left_q!r}, right {street_res.right_q!r}"
            )
            if street_res.notes:
                lines.append("  Notes:")
                for note in street_res.notes:
                    lines.append(f"    • {note}")
        else:
            lines.append("Street-grid box: could not resolve from OSM names.")
            lines.append(f"  {street_res.error or 'Unknown error'}")
        lines.append("")

    if geo.note:
        lines.append(geo.note)
        lines.append("")

    lines.append(
        'Next: turn off "Grid preview only" to build a full snapped route and directions.'
    )
    lines.append("")
    lines.append(
        "Truth check: when the street box is off or unresolved, the red rectangle is exactly "
        f"the {pcw:g}×{pch:g} cell contract × {preview.block_m:.1f} m/cell on the projected map; "
        "blue vertices are the word uniformly scaled to fit inside that rectangle."
    )
    report = "\n".join(lines)

    return GridDebugBuildResult(
        report_text=report,
        graph=G,
        preview=preview,
        grid_points_latlon=grid_ll,
        box_ring_latlon=box_ring,
        layout_mode_line=layout_line,
        preview_contract_w=pcw,
        preview_contract_h=pch,
        total_grid_points=n_pts,
        active_box_label=active_label,
    )


def build_route_result(
    address: str,
    word: str,
    radius_mi: float,
    letter_gap: int,
    block_m_raw: str,
    *,
    optimize_start: bool = False,
    search_half_miles: float = DEFAULT_UI_SEARCH_HALF_MI,
    roads_first: bool = True,
    roads_first_penalty: float = DEFAULT_ROADS_FIRST_PENALTY,
    street_box: tuple[str, str, str, str] | None = None,
) -> RouteBuildResult:
    """Geocode, build OSM route, enrich steps, format full report text."""
    word = normalize_word(word)
    options = parse_route_options(
        radius_mi=radius_mi,
        letter_gap=letter_gap,
        block_m_raw=block_m_raw,
        search_half_miles=search_half_miles,
        roads_first_penalty=roads_first_penalty,
    )

    radius_m = max(400.0, options.radius_mi * 1609.34)

    geo = geocode_address(address)
    routed = build_route(
        geo.latitude,
        geo.longitude,
        word,
        radius_m=radius_m,
        letter_gap=options.letter_gap,
        block_scale=options.block_m,
        optimize_start=optimize_start,
        search_half_miles=options.search_half_miles,
        roads_first=roads_first,
        roads_first_penalty=options.roads_first_penalty,
    )
    street_res: StreetBoxResolution | None = None
    if street_box is not None:
        bq, tq, lq, rq = street_box
        street_res = resolve_street_box_corners(routed.graph, bq, tq, lq, rq)

    total_m, n_edges = summary_from_gdf(routed.edge_gdf)
    steps = directions_from_path(routed)

    lines: list[str] = [
        f"Start: {geo.display_name}",
        f"Word: {word.upper().strip()!r}",
        f"Radius: {options.radius_mi} mi ({radius_m:.0f} m)",
        f"Grid unit (~one template step): {routed.block_m:.1f} m",
        f"Letter layout: fixed-pitch {MVP_CELL_W}x{MVP_CELL_H}, gap {options.letter_gap}",
    ]
    if optimize_start:
        lines.append(
            f"Grid search: ±{options.search_half_miles:g} mi from address (OSM walk mesh; larger download)."
        )
    if roads_first:
        lines.append(
            f"Roads-first routing: footpaths/paths/pedestrian/steps/bridleway ×{options.roads_first_penalty:g} vs street length."
        )
    lines.append("")
    if geo.note:
        lines.append(geo.note)
        lines.append("")
    if routed.grid_search_note:
        lines.append(routed.grid_search_note)
        lines.append("")
    if street_box is not None and street_res is not None:
        lines.extend(_street_box_diagnostic_lines(routed.graph, street_res))
    template_secondary = (
        street_box is not None and street_res is not None and street_res.ok
    )
    lines.extend(_template_block_diagnostic_lines(routed, secondary=template_secondary))
    lines.extend(
        [
            f"Approximate route length along streets: {total_m:.0f} m "
            f"({total_m * 0.000621371:.2f} mi), {n_edges} segments.",
            "",
            "Directions (template uses map north/east, not your local street grid):",
            "Each step starts with [house number + street] at the beginning of that leg (Nominatim reverse; ~1 s per unique corner).",
            "",
        ]
    )
    if steps:
        # Stdout (not stderr) so terminals do not style this as an error; flush for CLI progress.
        print(
            "Resolving corner addresses (~1 s per unique corner via Nominatim)...",
            flush=True,
        )
        steps = enrich_corner_labels(steps)
        lines.append(format_steps(steps))
    else:
        lines.append("Could not derive steps (route too short).")
    lines.extend(
        [
            "",
            "Note: OpenStreetMap walking paths only; verify safety and access before running.",
        ]
    )
    return RouteBuildResult(report_text="\n".join(lines), routed=routed, steps=steps)
