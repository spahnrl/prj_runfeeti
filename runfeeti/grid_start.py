"""
Search for a route template center with a more grid-like OSM walking network.

Uses the walk graph geometry only (orthogonal edge fraction, node density in the
letter footprint). House-number / hundred-block heuristics would need extra
geocoding and are not implemented here.
"""

from __future__ import annotations

import math
from typing import List, Tuple

import geopandas as gpd
import networkx as nx
from geopandas import GeoDataFrame
from shapely.geometry import Point

from runfeeti.letters import layout_word_fixed_pitch, polyline_bounds
from runfeeti.routing import (
    grid_waypoints,
    median_block_meters,
    path_to_edge_gdf,
    route_weight_attr,
    snap_route,
    start_xy_projected,
)


def bbox_wgs84_around_point(latitude: float, longitude: float, half_span_m: float) -> Tuple[float, float, float, float]:
    """Return (north, south, east, west) for OSMnx graph_from_bbox."""
    lat_delta = half_span_m / 111_320.0
    cos_lat = max(0.2, abs(math.cos(math.radians(latitude))))
    lon_delta = half_span_m / (111_320.0 * cos_lat)
    return (
        latitude + lat_delta,
        latitude - lat_delta,
        longitude + lon_delta,
        longitude - lon_delta,
    )


def projected_xy_to_latlon(graph: nx.MultiDiGraph, x: float, y: float) -> Tuple[float, float]:
    crs = graph.graph["crs"]
    s = gpd.GeoSeries([Point(x, y)], crs=crs).to_crs("EPSG:4326")
    return float(s.iloc[0].y), float(s.iloc[0].x)


def template_half_extents_m(word: str, gap: int, block_m: float) -> Tuple[float, float]:
    """
    Half-width and half-height in projected meters for the letter template plus
    padding. Enforces a minimum "canvas" of about 10×2 blocks (map units) as the
    user described, expanded if the word needs more space.
    """
    g = layout_word_fixed_pitch(word, gap=gap)
    minx, miny, maxx, maxy = polyline_bounds(g)
    cw = float(maxx - minx)
    ch = float(maxy - miny)
    pad_cells = 2.0
    half_w_cells = max(cw / 2.0 + pad_cells, 5.0)
    half_h_cells = max(ch / 2.0 + pad_cells, 1.0)
    return half_w_cells * block_m, half_h_cells * block_m


def _nodes_in_rect(graph: nx.MultiDiGraph, cx: float, cy: float, half_w: float, half_h: float) -> int:
    n = 0
    for _, data in graph.nodes(data=True):
        x, y = data["x"], data["y"]
        if abs(x - cx) <= half_w and abs(y - cy) <= half_h:
            n += 1
    return n


def _orthogonality_fraction(
    graph: nx.MultiDiGraph,
    cx: float,
    cy: float,
    half_w: float,
    half_h: float,
) -> float:
    """Share of edges (touching the window) that are nearly axis-aligned."""
    hw, hh = half_w * 1.25, half_h * 1.25
    inside: set[int] = set()
    for node, data in graph.nodes(data=True):
        x, y = data["x"], data["y"]
        if abs(x - cx) <= hw and abs(y - cy) <= hh:
            inside.add(node)
    if not inside:
        return 0.0
    aligned = 0
    total = 0
    for u, v, _k in graph.edges(keys=True):
        if u not in inside and v not in inside:
            continue
        xu, yu = graph.nodes[u]["x"], graph.nodes[u]["y"]
        xv, yv = graph.nodes[v]["x"], graph.nodes[v]["y"]
        dx, dy = abs(xv - xu), abs(yv - yu)
        if dx < 1e-6 and dy < 1e-6:
            continue
        total += 1
        lo, hi = min(dx, dy), max(dx, dy)
        if hi < 1e-6 or lo / hi < 0.18:
            aligned += 1
    if total == 0:
        return 0.0
    return aligned / total


def _path_length_m(graph: nx.MultiDiGraph, nodes: List[int]) -> float:
    s = 0.0
    weight_attr = route_weight_attr(graph)
    for u, v in zip(nodes, nodes[1:]):
        if not graph.has_edge(u, v):
            continue
        data = min(
            graph[u][v].values(),
            key=lambda d: d.get(weight_attr, d.get("length", float("inf"))),
        )
        ln = data.get("length")
        if ln is not None:
            s += float(ln)
    return s


def _try_route(
    graph: nx.MultiDiGraph,
    center_lat: float,
    center_lon: float,
    word: str,
    letter_gap: int,
    block_m: float,
) -> List[int] | None:
    try:
        cx, cy = start_xy_projected(graph, center_lat, center_lon)
        xy_pts = grid_waypoints(word, gap=letter_gap, block_m=block_m, center_x=cx, center_y=cy)
        return snap_route(graph, xy_pts)
    except ValueError:
        return None


def _meter_offset_grid(span_m: float, step_m: float) -> List[float]:
    if step_m <= 0:
        return [0.0]
    out: List[float] = []
    x = -span_m
    while x <= span_m + 1e-6:
        out.append(x)
        x += step_m
    return out


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(h)))


def search_best_route_on_graph(
    graph: nx.MultiDiGraph,
    origin_lat: float,
    origin_lon: float,
    word: str,
    letter_gap: int,
    block_m: float,
    *,
    search_half_miles: float,
    bbox_half_span_m: float,
) -> Tuple[List[int], GeoDataFrame, float, float, str] | None:
    """
    Scan projected offsets within ±bbox_half_span_m of the origin for a center
    that yields a connected template route with a strong local grid.

    Returns (nodes, edge_gdf, best_lat, best_lon, note) or None if no candidate works.
    """
    span_m = max(400.0, bbox_half_span_m)
    step_m = max(220.0, min(block_m * 3.0, span_m / 6.0))
    half_w_m, half_h_m = template_half_extents_m(word, letter_gap, block_m)

    cx0, cy0 = start_xy_projected(graph, origin_lat, origin_lon)
    north, south, east, west = bbox_wgs84_around_point(origin_lat, origin_lon, span_m)

    best: Tuple[float, List[int], float, float] | None = None
    best_score = -1.0
    min_nodes = max(12, int((half_w_m * half_h_m) / max(block_m * block_m, 1.0) * 0.15))

    for dx in _meter_offset_grid(span_m, step_m):
        for dy in _meter_offset_grid(span_m, step_m):
            cx, cy = cx0 + dx, cy0 + dy
            lat, lon = projected_xy_to_latlon(graph, cx, cy)
            if not (south <= lat <= north and west <= lon <= east):
                continue
            if _nodes_in_rect(graph, cx, cy, half_w_m, half_h_m) < min_nodes:
                continue
            nodes = _try_route(graph, lat, lon, word, letter_gap, block_m)
            if not nodes:
                continue
            ortho = _orthogonality_fraction(graph, cx, cy, half_w_m, half_h_m)
            n_rect = _nodes_in_rect(graph, cx, cy, half_w_m, half_h_m)
            plen = _path_length_m(graph, nodes)
            score = ortho * 800.0 + n_rect * 3.0 - plen / 120.0
            if score > best_score:
                best_score = score
                best = (score, nodes, lat, lon)

    if best is None:
        return None
    _sc, nodes, best_lat, best_lon = best
    gdf = path_to_edge_gdf(graph, nodes)
    dist_m = haversine_m(origin_lat, origin_lon, best_lat, best_lon)
    note = (
        f"Grid search (±{search_half_miles:g} mi) moved the template center "
        f"~{dist_m:.0f} m from your address toward a more orthogonal block mesh."
    )
    return nodes, gdf, best_lat, best_lon, note
