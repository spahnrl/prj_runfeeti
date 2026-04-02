"""Convert routed paths to WGS84 coordinates for web maps (e.g. Folium)."""

from __future__ import annotations

from typing import List, Tuple

import geopandas as gpd
from shapely.geometry import LineString

from runfeeti.routing import RoutedPath, projected_polyline


def route_polyline_latlon(routed: RoutedPath) -> List[Tuple[float, float]]:
    """
    Ordered (latitude, longitude) along the walking route for Folium PolyLine.

    Empty if the route has fewer than two distinct geometry points.
    """
    pts = projected_polyline(routed.graph, routed.nodes)
    if len(pts) < 2:
        return []
    crs = routed.graph.graph["crs"]
    line = LineString(pts)
    gdf = gpd.GeoDataFrame(geometry=[line], crs=crs)
    g4326 = gdf.to_crs("EPSG:4326")
    # Shapely uses x=lon, y=lat in EPSG:4326
    out: List[Tuple[float, float]] = []
    for lon, lat in g4326.geometry.iloc[0].coords:
        out.append((float(lat), float(lon)))
    return out
