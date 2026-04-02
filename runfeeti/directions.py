from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import geopandas as gpd
import networkx as nx
from geopandas import GeoDataFrame
from shapely.geometry import Point

from runfeeti.geocode import lookup_corner_labels
from runfeeti.routing import RoutedPath


_HW_LABEL = {
    "footway": "footpath",
    "path": "path",
    "pedestrian": "pedestrian way",
    "steps": "steps",
    "living_street": "street",
    "service": "service road",
    "residential": "residential street",
    "unclassified": "road",
}


def _edge_name(attrs: dict) -> str:
    name = attrs.get("name")
    if isinstance(name, list):
        name = name[0] if name else None
    if name:
        return str(name)
    hw = attrs.get("highway")
    if isinstance(hw, list):
        hw = hw[0] if hw else None
    if isinstance(hw, str):
        return _HW_LABEL.get(hw, hw.replace("_", " "))
    return "path"


def _bearing_deg(dx: float, dy: float) -> float:
    """Compass bearing 0=north, 90=east, from previous→next in projected coordinates (y often = northing)."""
    return math.degrees(math.atan2(dx, dy)) % 360.0


def _turn_phrase(delta: float) -> str:
    """Map bearing change to a simple English turn."""
    d = ((delta + 540) % 360) - 180
    if abs(d) < 25:
        return "Continue straight"
    if d > 0:
        return "Turn left"
    return "Turn right"


def _node_latlon(G: nx.MultiDiGraph, node_id: int) -> tuple[float, float]:
    """Graph node projected x/y to WGS84 (lat, lon)."""
    x, y = G.nodes[node_id]["x"], G.nodes[node_id]["y"]
    crs = G.graph["crs"]
    s = gpd.GeoSeries([Point(x, y)], crs=crs).to_crs("EPSG:4326")
    return float(s.iloc[0].y), float(s.iloc[0].x)


@dataclass(frozen=True)
class Step:
    instruction: str
    street: str
    distance_m: float
    corner_lat: float
    corner_lon: float
    corner_label: str = ""

    @property
    def corner_bracket(self) -> str:
        """Display form: [number + street] or best available label."""
        if self.corner_label:
            return f"[{self.corner_label}]"
        return f"[{self.corner_lat:.5f}, {self.corner_lon:.5f}]"


def directions_from_path(routed: RoutedPath) -> List[Step]:
    """Build concise turn-by-turn steps from a routed path (corner_label filled later)."""
    G = routed.graph
    nodes = routed.nodes
    if len(nodes) < 2:
        return []

    steps: List[Step] = []
    prev_bearing: float | None = None
    current_street: str | None = None
    run_m = 0.0
    pending_intro: str | None = "Start"
    run_first_node: int = nodes[0]

    for u, v in zip(nodes, nodes[1:]):
        data = min(G[u][v].values(), key=lambda d: d.get("length", float("inf")))
        geom = data.get("geometry")
        if geom is None:
            xu, yu = G.nodes[u]["x"], G.nodes[u]["y"]
            xv, yv = G.nodes[v]["x"], G.nodes[v]["y"]
            dx, dy = xv - xu, yv - yu
            length = float(data.get("length") or math.hypot(dx, dy))
        else:
            length = float(data.get("length") or geom.length)
            xs, ys = zip(*list(geom.coords)[-2:])
            dx, dy = xs[1] - xs[0], ys[1] - ys[0]

        street = _edge_name(data)
        brg = _bearing_deg(dx, dy)

        if prev_bearing is None:
            prev_bearing = brg
            current_street = street
            run_m = length
            run_first_node = u
            continue

        delta = brg - prev_bearing
        same_street = street == current_street
        straight_enough = abs(((delta + 540) % 360) - 180) < 40

        if same_street and straight_enough:
            run_m += length
            prev_bearing = brg
            continue

        intro = pending_intro or _turn_phrase(delta)
        pending_intro = None
        lat, lon = _node_latlon(G, run_first_node)
        steps.append(
            Step(
                instruction=f"{intro} on {current_street or 'the path'}",
                street=current_street or "the path",
                distance_m=round(run_m, 1),
                corner_lat=lat,
                corner_lon=lon,
            )
        )
        run_first_node = u
        current_street = street
        run_m = length
        prev_bearing = brg

    if run_m > 0 and current_street is not None:
        intro = pending_intro or "Continue"
        lat, lon = _node_latlon(G, run_first_node)
        steps.append(
            Step(
                instruction=f"{intro} on {current_street}",
                street=current_street,
                distance_m=round(run_m, 1),
                corner_lat=lat,
                corner_lon=lon,
            )
        )

    return steps


def enrich_corner_labels(
    steps: List[Step],
    *,
    user_agent: str = "runfeeti/0.1",
    min_delay_s: float = 1.05,
) -> List[Step]:
    """Fill Step.corner_label via Nominatim reverse (rate-limited; deduped by coordinate)."""
    if not steps:
        return []
    labels = lookup_corner_labels(
        [(s.corner_lat, s.corner_lon) for s in steps],
        user_agent=user_agent,
        min_delay_s=min_delay_s,
    )
    return [
        Step(
            instruction=s.instruction,
            street=s.street,
            distance_m=s.distance_m,
            corner_lat=s.corner_lat,
            corner_lon=s.corner_lon,
            corner_label=lab,
        )
        for s, lab in zip(steps, labels, strict=True)
    ]


def format_steps(steps: List[Step]) -> str:
    lines: List[str] = []
    for i, s in enumerate(steps, start=1):
        lines.append(
            f"{i}. {s.corner_bracket} {s.instruction} - "
            f"about {s.distance_m:.0f} m ({s.distance_m * 0.000621371:.2f} mi)."
        )
    return "\n".join(lines)


def summary_from_gdf(edge_gdf: GeoDataFrame) -> tuple[float, int]:
    if edge_gdf is None or edge_gdf.empty:
        return 0.0, 0
    total = float(edge_gdf["length"].fillna(0).sum())
    return total, int(len(edge_gdf))
