from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Sequence, Tuple

import networkx as nx
import numpy as np
import osmnx as ox
from geopandas import GeoDataFrame

from runfeeti.letters import (
    Point,
    layout_word_fixed_pitch,
    layout_word_in_contract_cells,
    letter_polyline_intrinsic_cell_span,
    polyline_bounds,
)

# Penalized in roads-first MVP routing (walk graph keeps them but avoids when a street exists).
_FOOTPATH_LIKE_HW: frozenset[str] = frozenset(
    {"footway", "path", "pedestrian", "steps", "bridleway"}
)

# Graph meta: which edge attribute shortest_path / route_to_gdf should minimize.
_RUNFEETI_ROUTE_WEIGHT_KEY = "runfeeti_route_weight"
_DEFAULT_ROUTE_WEIGHT = "length"
_MVP_ROUTE_WEIGHT = "mvp_weight"


@dataclass(frozen=True)
class RoutedPath:
    """Projected graph node order plus edge geometries for mapping / directions."""

    graph: nx.MultiDiGraph
    nodes: List[int]
    edge_gdf: GeoDataFrame
    block_m: float
    center_latitude: float
    center_longitude: float
    # Axis-aligned bbox of the intended letter template in projected meters (same CRS as graph).
    template_bbox_min_x: float
    template_bbox_min_y: float
    template_bbox_max_x: float
    template_bbox_max_y: float
    grid_search_note: str | None = None


def load_walk_graph(latitude: float, longitude: float, radius_m: float) -> nx.MultiDiGraph:
    """Download and project a pedestrian network around a point."""
    G = ox.graph_from_point(
        (latitude, longitude),
        dist=radius_m,
        network_type="walk",
        simplify=True,
        truncate_by_edge=True,
    )
    if G.number_of_nodes() == 0:
        raise ValueError("No walkable streets found in this area. Try a larger radius or another address.")
    return ox.project_graph(G)


def load_walk_graph_bbox(north: float, south: float, east: float, west: float) -> nx.MultiDiGraph:
    """Download and project a pedestrian network for a WGS84 bounding box."""
    G = ox.graph_from_bbox(
        (north, south, east, west),
        network_type="walk",
        simplify=True,
        truncate_by_edge=True,
    )
    if G.number_of_nodes() == 0:
        raise ValueError("No walkable streets in the search rectangle. Try a smaller search area or another address.")
    return ox.project_graph(G)


def _highway_tag(edge_data: dict) -> str | None:
    hw = edge_data.get("highway")
    if isinstance(hw, list):
        hw = hw[0] if hw else None
    if isinstance(hw, str):
        return hw
    return None


def _edge_base_length_m(graph: nx.MultiDiGraph, u: int, v: int, data: dict) -> float:
    ln = data.get("length")
    if ln is not None and float(ln) > 0:
        return float(ln)
    geom = data.get("geometry")
    if geom is not None and not geom.is_empty:
        return float(geom.length)
    xu, yu = graph.nodes[u]["x"], graph.nodes[u]["y"]
    xv, yv = graph.nodes[v]["x"], graph.nodes[v]["y"]
    return float(math.hypot(xv - xu, yv - yu))


def apply_roads_first_mvp_weights(graph: nx.MultiDiGraph, *, penalty: float = 10.0) -> None:
    """
    On a projected walk graph, set mvp_weight = length for street-like edges and
    length * penalty for footpath-like highway tags. Sets graph meta so routing
    uses mvp_weight for shortest_path / route_to_gdf.
    """
    for u, v, _k, d in graph.edges(keys=True, data=True):
        base = _edge_base_length_m(graph, u, v, d)
        if base <= 0:
            base = 1.0
        hw = _highway_tag(d)
        mult = penalty if hw is not None and hw in _FOOTPATH_LIKE_HW else 1.0
        d[_MVP_ROUTE_WEIGHT] = base * mult
    graph.graph[_RUNFEETI_ROUTE_WEIGHT_KEY] = _MVP_ROUTE_WEIGHT


def route_weight_attr(graph: nx.MultiDiGraph) -> str:
    """Edge attribute name for NetworkX shortest_path and OSMnx route_to_gdf."""
    w = graph.graph.get(_RUNFEETI_ROUTE_WEIGHT_KEY)
    if w == _MVP_ROUTE_WEIGHT:
        return _MVP_ROUTE_WEIGHT
    return _DEFAULT_ROUTE_WEIGHT


def start_xy_projected(graph: nx.MultiDiGraph, latitude: float, longitude: float) -> Tuple[float, float]:
    """Project lon/lat to the same CRS as the graph."""
    import geopandas as gpd
    from shapely.geometry import Point

    crs = graph.graph["crs"]
    s = gpd.GeoSeries([Point(longitude, latitude)], crs="EPSG:4326").to_crs(crs)
    return float(s.iloc[0].x), float(s.iloc[0].y)


def projected_point_to_latlon(graph: nx.MultiDiGraph, x: float, y: float) -> Tuple[float, float]:
    """Projected (x, y) in graph CRS → (latitude, longitude) WGS84."""
    import geopandas as gpd
    from shapely.geometry import Point

    crs = graph.graph["crs"]
    s = gpd.GeoSeries([Point(x, y)], crs=crs).to_crs("EPSG:4326")
    return float(s.iloc[0].y), float(s.iloc[0].x)


def template_bbox_projected_m(xy_pts: Sequence[Tuple[float, float]]) -> Tuple[float, float, float, float]:
    """Min/max x,y of template waypoints in projected meters (bottom ≈ min y, north ≈ max y)."""
    xs = [p[0] for p in xy_pts]
    ys = [p[1] for p in xy_pts]
    return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))


@dataclass(frozen=True)
class StreetBoxResolution:
    """Four corners from OSM named street polylines (projected CRS). Routing may still use template placement."""

    ok: bool
    error: str | None
    notes: tuple[str, ...]
    bottom_q: str
    top_q: str
    left_q: str
    right_q: str
    bl: tuple[float, float] | None
    br: tuple[float, float] | None
    tl: tuple[float, float] | None
    tr: tuple[float, float] | None


def _edge_street_names(data: dict) -> list[str]:
    nm = data.get("name")
    if nm is None:
        return []
    if isinstance(nm, list):
        return [str(x).strip() for x in nm if x is not None and str(x).strip()]
    return [str(nm).strip()]


def _street_name_query_matches(names: list[str], query: str) -> bool:
    qn = query.strip().lower()
    if not qn or not names:
        return False
    q_compact = qn.replace(" ", "")
    for n in names:
        nl = n.lower().strip()
        n_compact = nl.replace(" ", "")
        if qn in nl or nl in qn or q_compact in n_compact or n_compact in q_compact:
            return True
    return False


def _street_edge_geometries(
    G: nx.MultiDiGraph,
    query: str,
    *,
    allow_footpaths: bool,
) -> list:
    from shapely.geometry.base import BaseGeometry

    geoms: list[BaseGeometry] = []
    for _u, _v, _k, d in G.edges(keys=True, data=True):
        if not allow_footpaths:
            hw = _highway_tag(d)
            if hw is not None and hw in _FOOTPATH_LIKE_HW:
                continue
        if not _street_name_query_matches(_edge_street_names(d), query):
            continue
        g = d.get("geometry")
        if g is not None and not g.is_empty:
            geoms.append(g)
    return geoms


def merged_street_polyline_for_project(
    G: nx.MultiDiGraph,
    query: str,
) -> tuple["LineString | MultiLineString | None", bool]:
    """
    Union + linemerge of graph edges whose name matches query (projected CRS).
    Returns (merged_line_or_none, used_footpath_edges_because_no_street_match).
    """
    from shapely.geometry import LineString, MultiLineString
    from shapely.ops import linemerge, unary_union

    geoms = _street_edge_geometries(G, query, allow_footpaths=False)
    fp_fallback = False
    if not geoms:
        geoms = _street_edge_geometries(G, query, allow_footpaths=True)
        fp_fallback = True
    if not geoms:
        return None, False
    u = unary_union(geoms)
    if u.is_empty:
        return None, False
    if u.geom_type == "LineString":
        return u, fp_fallback
    merged = linemerge(u)
    if merged.is_empty:
        return None, False
    if merged.geom_type == "GeometryCollection":
        from shapely.geometry import MultiLineString

        parts: list = []
        for g in merged.geoms:
            if g.geom_type == "LineString":
                parts.append(g)
            elif g.geom_type == "MultiLineString":
                parts.extend(list(g.geoms))
        if not parts:
            return None, False
        merged = MultiLineString(parts)
    if merged.geom_type not in ("LineString", "MultiLineString"):
        return None, False
    return merged, fp_fallback


def _projected_xy_from_corner_geometry(
    inter: "BaseGeometry",
    label: str,
) -> tuple[tuple[float, float] | None, str | None]:
    """Extract one (x,y) from intersection geometry; return note if approximate."""
    g = inter
    if g.is_empty:
        return None, None
    if g.geom_type == "Point":
        return (float(g.x), float(g.y)), None
    if g.geom_type == "MultiPoint":
        p = g.geoms[0]
        return (float(p.x), float(p.y)), None
    if g.geom_type == "GeometryCollection":
        for sub in g.geoms:
            if sub.geom_type == "Point":
                return (float(sub.x), float(sub.y)), None
    if g.geom_type in ("LineString", "MultiLineString"):
        rp = g.representative_point()
        return (float(rp.x), float(rp.y)), (
            f"{label}: intersection is overlapping segments; using a point along the overlap"
        )
    try:
        rp = g.representative_point()
        return (float(rp.x), float(rp.y)), f"{label}: using representative point of {g.geom_type!r}"
    except Exception:
        return None, None


def corner_from_two_street_polylines(
    line_a: "LineString | MultiLineString",
    line_b: "LineString | MultiLineString",
    label: str,
) -> tuple[tuple[float, float] | None, str | None]:
    """
    Prefer exact intersection of OSM polylines; else midpoint of Shapely nearest_points.
    Returns (projected_xy, note_if_fallback).
    """
    from shapely.ops import nearest_points

    inter = line_a.intersection(line_b)
    if not inter.is_empty:
        xy, note = _projected_xy_from_corner_geometry(inter, label)
        if xy is not None:
            return xy, note
    pa, pb = nearest_points(line_a, line_b)
    mid = ((float(pa.x) + float(pb.x)) / 2.0, (float(pa.y) + float(pb.y)) / 2.0)
    return mid, (
        f"{label}: no single point intersection; using midpoint of nearest points on named polylines"
    )


def resolve_street_box_corners(
    G: nx.MultiDiGraph,
    bottom_q: str,
    top_q: str,
    left_q: str,
    right_q: str,
) -> StreetBoxResolution:
    """
    Resolve BL/BR/TL/TR as intersections of bottom/top polylines with left/right polylines.
    Does not change routing; for reporting and future letter placement inside the box.
    """
    errs: list[str] = []
    notes: list[str] = []

    lb, fb_b = merged_street_polyline_for_project(G, bottom_q)
    lt, fb_t = merged_street_polyline_for_project(G, top_q)
    ll, fb_l = merged_street_polyline_for_project(G, left_q)
    lr, fb_r = merged_street_polyline_for_project(G, right_q)

    if lb is None:
        errs.append(f"no edges matched bottom street {bottom_q!r}")
    if lt is None:
        errs.append(f"no edges matched top street {top_q!r}")
    if ll is None:
        errs.append(f"no edges matched left street {left_q!r}")
    if lr is None:
        errs.append(f"no edges matched right street {right_q!r}")
    if errs:
        return StreetBoxResolution(
            ok=False,
            error="; ".join(errs),
            notes=tuple(notes),
            bottom_q=bottom_q,
            top_q=top_q,
            left_q=left_q,
            right_q=right_q,
            bl=None,
            br=None,
            tl=None,
            tr=None,
        )

    for nm, flag in (
        (bottom_q, fb_b),
        (top_q, fb_t),
        (left_q, fb_l),
        (right_q, fb_r),
    ):
        if flag:
            notes.append(f"{nm!r}: only matched after including footpath-like edges")

    def grab_corner(
        a: "LineString | MultiLineString",
        b: "LineString | MultiLineString",
        tag: str,
    ) -> tuple[tuple[float, float] | None, str | None]:
        return corner_from_two_street_polylines(a, b, tag)

    bl, n1 = grab_corner(lb, ll, "BL (bottom ∩ left)")
    br, n2 = grab_corner(lb, lr, "BR (bottom ∩ right)")
    tl, n3 = grab_corner(lt, ll, "TL (top ∩ left)")
    tr, n4 = grab_corner(lt, lr, "TR (top ∩ right)")
    for n in (n1, n2, n3, n4):
        if n:
            notes.append(n)

    if bl is None or br is None or tl is None or tr is None:
        return StreetBoxResolution(
            ok=False,
            error="could not compute one or more corner points from OSM geometries",
            notes=tuple(notes),
            bottom_q=bottom_q,
            top_q=top_q,
            left_q=left_q,
            right_q=right_q,
            bl=bl,
            br=br,
            tl=tl,
            tr=tr,
        )

    return StreetBoxResolution(
        ok=True,
        error=None,
        notes=tuple(notes),
        bottom_q=bottom_q,
        top_q=top_q,
        left_q=left_q,
        right_q=right_q,
        bl=bl,
        br=br,
        tl=tl,
        tr=tr,
    )


@dataclass(frozen=True)
class GridPreviewContext:
    """
    Projected walk graph plus intended letter polyline vertices (no snap, no shortest paths).
    Center is always the geocoded start; grid-search optimize_start is not applied here.
    Preview footprint uses an explicit contract (preview_contract_w × preview_contract_h cells × block_m).
    """

    graph: nx.MultiDiGraph
    block_m: float
    center_latitude: float
    center_longitude: float
    waypoints_xy: List[Tuple[float, float]]
    template_min_x: float
    template_min_y: float
    template_max_x: float
    template_max_y: float
    preview_contract_w: float
    preview_contract_h: float
    letter_intrinsic_w: int
    letter_intrinsic_h: int
    letter_gap: int


def median_block_meters(graph: nx.MultiDiGraph) -> float:
    lengths = [d for *_, d in graph.edges(data="length") if d is not None and d > 0]
    if not lengths:
        return 100.0
    return float(np.median(lengths))


def grid_waypoints(
    word: str,
    *,
    gap: int = 1,
    block_m: float,
    center_x: float,
    center_y: float,
) -> List[Tuple[float, float]]:
    """Map abstract letter grid to projected meters, centered on (center_x, center_y)."""
    grid: List[Point] = layout_word_fixed_pitch(word, gap=gap)
    if len(grid) < 2:
        grid = [(0, 0), (1, 0)]

    minx, miny, maxx, maxy = polyline_bounds(grid)
    cen_x = (minx + maxx) / 2.0
    cen_y = (miny + maxy) / 2.0

    out: List[Tuple[float, float]] = []
    for gx, gy in grid:
        x = (gx - cen_x) * block_m + center_x
        y = (gy - cen_y) * block_m + center_y
        out.append((x, y))
    return out


def grid_waypoints_in_contract(
    word: str,
    *,
    gap: int,
    contract_w: float,
    contract_h: float,
    block_m: float,
    center_x: float,
    center_y: float,
) -> tuple[List[Tuple[float, float]], tuple[float, float, float, float]]:
    """
    Map fixed-pitch word into an explicit W×H cell contract, then into projected meters
    centered on (center_x, center_y). Returns (waypoints, contract_bbox axis-aligned in proj m).
    """
    tw = float(contract_w)
    th = float(contract_h)
    cells = layout_word_in_contract_cells(
        word, gap=gap, contract_width=tw, contract_height=th
    )
    out: List[Tuple[float, float]] = []
    half_w = tw / 2.0 * block_m
    half_h = th / 2.0 * block_m
    for ux, uy in cells:
        x = center_x + (ux - tw / 2.0) * block_m
        y = center_y + (uy - th / 2.0) * block_m
        out.append((x, y))
    tminx = center_x - half_w
    tmaxx = center_x + half_w
    tminy = center_y - half_h
    tmaxy = center_y + half_h
    return out, (tminx, tminy, tmaxx, tmaxy)


def build_grid_preview(
    latitude: float,
    longitude: float,
    word: str,
    *,
    radius_m: float,
    letter_gap: int = 1,
    block_scale: float | None = None,
    roads_first: bool = False,
    roads_first_penalty: float = 10.0,
    preview_contract_w: float = 12.0,
    preview_contract_h: float = 4.0,
) -> GridPreviewContext:
    """
    Download walk graph, compute block size and preview waypoints using an explicit cell contract.
    Skips snap_route / path finding (MVP grid visualization).
    """
    G = load_walk_graph(latitude, longitude, radius_m)
    if roads_first:
        apply_roads_first_mvp_weights(G, penalty=roads_first_penalty)
    block_m = block_scale if block_scale is not None else median_block_meters(G)
    cx, cy = start_xy_projected(G, latitude, longitude)
    letter_iw, letter_ih = letter_polyline_intrinsic_cell_span(word, gap=letter_gap)
    tw = float(preview_contract_w)
    th = float(preview_contract_h)
    xy_pts, (tminx, tminy, tmaxx, tmaxy) = grid_waypoints_in_contract(
        word,
        gap=letter_gap,
        contract_w=tw,
        contract_h=th,
        block_m=block_m,
        center_x=cx,
        center_y=cy,
    )
    return GridPreviewContext(
        graph=G,
        block_m=block_m,
        center_latitude=latitude,
        center_longitude=longitude,
        waypoints_xy=xy_pts,
        template_min_x=tminx,
        template_min_y=tminy,
        template_max_x=tmaxx,
        template_max_y=tmaxy,
        preview_contract_w=tw,
        preview_contract_h=th,
        letter_intrinsic_w=letter_iw,
        letter_intrinsic_h=letter_ih,
        letter_gap=letter_gap,
    )


def snap_route(
    graph: nx.MultiDiGraph,
    xy_points: Sequence[Tuple[float, float]],
) -> List[int]:
    """Shortest-path through the graph visiting waypoints in order (snapped to nearest nodes)."""
    nodes: List[int] = []
    for x, y in xy_points:
        n = ox.distance.nearest_nodes(graph, x, y)
        if not nodes or n != nodes[-1]:
            nodes.append(n)

    if len(nodes) < 2:
        raise ValueError(
            "All template corners snapped to the same street junction. "
            "Try a larger search radius or a denser street grid."
        )

    full: List[int] = []
    for i in range(len(nodes) - 1):
        a, b = nodes[i], nodes[i + 1]
        try:
            segment = nx.shortest_path(graph, a, b, weight=route_weight_attr(graph))
        except nx.NetworkXNoPath as exc:
            raise ValueError(
                "The walking network is disconnected for this template. "
                "Try a larger radius or a different starting point."
            ) from exc
        if full:
            full.extend(segment[1:])
        else:
            full.extend(segment)
    return full


def path_to_edge_gdf(graph: nx.MultiDiGraph, nodes: Sequence[int]) -> GeoDataFrame:
    """Edge rows along a node route (handles parallel edges by weight attr)."""
    return ox.routing.route_to_gdf(graph, list(nodes), weight=route_weight_attr(graph))


def projected_polyline(graph: nx.MultiDiGraph, nodes: Sequence[int]) -> List[Tuple[float, float]]:
    """Ordered (x, y) points along the route in the graph's projected CRS (meters)."""
    out: List[Tuple[float, float]] = []
    nodes = list(nodes)
    if len(nodes) < 2:
        if len(nodes) == 1:
            n = nodes[0]
            return [(graph.nodes[n]["x"], graph.nodes[n]["y"])]
        return []

    def append_pt(x: float, y: float) -> None:
        if not out or (out[-1][0] != x or out[-1][1] != y):
            out.append((x, y))

    for u, v in zip(nodes, nodes[1:]):
        wattr = route_weight_attr(graph)
        data = min(graph[u][v].values(), key=lambda d: d.get(wattr, d.get("length", float("inf"))))
        geom = data.get("geometry")
        xu, yu = graph.nodes[u]["x"], graph.nodes[u]["y"]
        xv, yv = graph.nodes[v]["x"], graph.nodes[v]["y"]

        if geom is not None and not geom.is_empty:
            coords = list(geom.coords)
            du0 = (coords[0][0] - xu) ** 2 + (coords[0][1] - yu) ** 2
            duv = (coords[-1][0] - xu) ** 2 + (coords[-1][1] - yu) ** 2
            if du0 > duv:
                coords = list(reversed(coords))
            for c in coords:
                append_pt(float(c[0]), float(c[1]))
        else:
            append_pt(xu, yu)
            append_pt(xv, yv)

    return out


def build_route(
    latitude: float,
    longitude: float,
    word: str,
    *,
    radius_m: float,
    letter_gap: int = 1,
    block_scale: float | None = None,
    optimize_start: bool = False,
    search_half_miles: float = 5.0,
    roads_first: bool = False,
    roads_first_penalty: float = 10.0,
) -> RoutedPath:
    """
    Geocode is assumed done by caller; lat/lon are the user's starting address.

    block_scale: meters per one grid unit. Defaults to median edge length in the downloaded graph.

    optimize_start: download a larger bbox (±search_half_miles) and scan for a template center
    with denser, more orthogonal local streets before snapping the word polyline.

    roads_first: on the walk graph, penalize footway/path/pedestrian/steps/bridleway edges so
    shortest routes prefer street grids (paths still allowed if much shorter).
    """
    if optimize_start:
        from runfeeti.grid_start import bbox_wgs84_around_point, search_best_route_on_graph

        span_m = max(radius_m, search_half_miles * 1609.34)
        n, s, e, w = bbox_wgs84_around_point(latitude, longitude, span_m)
        G = load_walk_graph_bbox(n, s, e, w)
        if roads_first:
            apply_roads_first_mvp_weights(G, penalty=roads_first_penalty)
        block_m = block_scale if block_scale is not None else median_block_meters(G)
        found = search_best_route_on_graph(
            G,
            latitude,
            longitude,
            word,
            letter_gap,
            block_m,
            search_half_miles=search_half_miles,
            bbox_half_span_m=span_m,
        )
        if found is not None:
            node_path, gdf, clat, clon, note = found
            tcx, tcy = start_xy_projected(G, clat, clon)
            xy_pts_found = grid_waypoints(
                word, gap=letter_gap, block_m=block_m, center_x=tcx, center_y=tcy
            )
            tminx, tminy, tmaxx, tmaxy = template_bbox_projected_m(xy_pts_found)
            return RoutedPath(
                graph=G,
                nodes=list(node_path),
                edge_gdf=gdf,
                block_m=block_m,
                center_latitude=clat,
                center_longitude=clon,
                grid_search_note=note,
                template_bbox_min_x=tminx,
                template_bbox_min_y=tminy,
                template_bbox_max_x=tmaxx,
                template_bbox_max_y=tmaxy,
            )
        G = load_walk_graph(latitude, longitude, radius_m)
        if roads_first:
            apply_roads_first_mvp_weights(G, penalty=roads_first_penalty)
        block_m = block_scale if block_scale is not None else median_block_meters(G)
        cx, cy = start_xy_projected(G, latitude, longitude)
        xy_pts = grid_waypoints(word, gap=letter_gap, block_m=block_m, center_x=cx, center_y=cy)
        tminx, tminy, tmaxx, tmaxy = template_bbox_projected_m(xy_pts)
        node_path = snap_route(G, xy_pts)
        gdf = path_to_edge_gdf(G, node_path)
        return RoutedPath(
            graph=G,
            nodes=list(node_path),
            edge_gdf=gdf,
            block_m=block_m,
            center_latitude=latitude,
            center_longitude=longitude,
            grid_search_note=(
                f"Grid search (±{search_half_miles:g} mi) did not find a stronger mesh; "
                "using your address as the template center."
            ),
            template_bbox_min_x=tminx,
            template_bbox_min_y=tminy,
            template_bbox_max_x=tmaxx,
            template_bbox_max_y=tmaxy,
        )

    G = load_walk_graph(latitude, longitude, radius_m)
    if roads_first:
        apply_roads_first_mvp_weights(G, penalty=roads_first_penalty)
    cx, cy = start_xy_projected(G, latitude, longitude)
    block_m = block_scale if block_scale is not None else median_block_meters(G)
    xy_pts = grid_waypoints(word, gap=letter_gap, block_m=block_m, center_x=cx, center_y=cy)
    tminx, tminy, tmaxx, tmaxy = template_bbox_projected_m(xy_pts)
    node_path = snap_route(G, xy_pts)
    gdf = path_to_edge_gdf(G, node_path)
    return RoutedPath(
        graph=G,
        nodes=list(node_path),
        edge_gdf=gdf,
        block_m=block_m,
        center_latitude=latitude,
        center_longitude=longitude,
        grid_search_note=None,
        template_bbox_min_x=tminx,
        template_bbox_min_y=tminy,
        template_bbox_max_x=tmaxx,
        template_bbox_max_y=tmaxy,
    )
