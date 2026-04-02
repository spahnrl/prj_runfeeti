from __future__ import annotations

import math
import tkinter as tk
import turtle
from typing import Sequence, Tuple

import geopandas as gpd
from shapely.geometry import Point

from runfeeti.directions import Step
from runfeeti.routing import RoutedPath, projected_polyline


def _turn_display_name(step: Step, index: int) -> str:
    """Short multi-line label: maneuver + street (turn name)."""
    ins = step.instruction
    if ins.startswith("Start"):
        turn = "Start"
    elif "Turn left" in ins:
        turn = "Left"
    elif "Turn right" in ins:
        turn = "Right"
    elif "Continue straight" in ins:
        turn = "Straight"
    elif ins.startswith("Continue"):
        turn = "Continue"
    else:
        turn = f"#{index}"
    street = step.street.strip() or "path"
    if len(street) > 36:
        street = street[:33] + "..."
    return f"{index}. {turn}\n{street}"


def _latlon_to_projected(routed: RoutedPath, lat: float, lon: float) -> Tuple[float, float]:
    crs = routed.graph.graph["crs"]
    s = gpd.GeoSeries([Point(lon, lat)], crs="EPSG:4326").to_crs(crs)
    return float(s.iloc[0].x), float(s.iloc[0].y)


def _draw_block_grid(
    pen: turtle.Turtle,
    llx: float,
    lly: float,
    urx: float,
    ury: float,
    block_m: float,
    *,
    color: str = "#c5c5c5",
) -> None:
    """Axis-aligned lines spaced by block_m (map projection meters)."""
    if block_m <= 0:
        return
    pen.speed(0)
    pen.hideturtle()
    pen.penup()
    pen.pencolor(color)
    pen.pensize(max(0.5, (urx - llx) / 700.0))
    x = math.floor(llx / block_m) * block_m
    while x <= urx + 1e-6:
        pen.goto(x, lly)
        pen.pendown()
        pen.goto(x, ury)
        pen.penup()
        x += block_m
    y = math.floor(lly / block_m) * block_m
    while y <= ury + 1e-6:
        pen.goto(llx, y)
        pen.pendown()
        pen.goto(urx, y)
        pen.penup()
        y += block_m


def _label_offsets(n: int, scale: float) -> list[tuple[float, float]]:
    """
    Place label anchors on a golden-angle spiral in world meters so clustered
    corners (tight letter geometry) do not stack on the same four spots.
    """
    base = 14.0 * scale
    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    out: list[tuple[float, float]] = []
    for i in range(n):
        r = base * math.sqrt(i + 1)
        theta = i * golden_angle
        out.append((r * math.cos(theta), r * math.sin(theta)))
    return out


def show_route_turtle(
    routed: RoutedPath,
    steps: Sequence[Step],
    *,
    title: str = "RunFeeti map",
    line_color: str = "#1565c0",
    label_color: str = "#b71c1c",
    margin_ratio: float = 0.08,
    show_grid: bool = True,
) -> None:
    """
    Draw the walking route in projected meters (north approx. +y) with turn / street names.

    Blocks until the turtle window is closed. Call from the GUI main thread.
    """
    G = routed.graph
    pts = projected_polyline(G, routed.nodes)
    if len(pts) < 2:
        w = turtle.Screen()
        try:
            w.clear()
        except tk.TclError:
            pass
        w.setup(480, 320)
        w.title(title)
        t = turtle.Turtle(visible=False)
        t.write("Route too short to draw.", align="center", font=("Arial", 14, "normal"))
        turtle.done()
        return

    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    dx = max(max_x - min_x, 1.0)
    dy = max(max_y - min_y, 1.0)
    mx = dx * margin_ratio
    my = dy * margin_ratio
    llx, urx = min_x - mx, max_x + mx
    lly, ury = min_y - my, max_y + my

    # Uniform world size for a square canvas so aspect is true (meters).
    span = max(urx - llx, ury - lly)
    cx, cy = (llx + urx) / 2.0, (lly + ury) / 2.0
    half = span / 2.0
    llx, urx = cx - half, cx + half
    lly, ury = cy - half, cy + half

    w = turtle.Screen()
    try:
        w.clear()
    except tk.TclError:
        pass
    w.setup(width=720, height=720)
    w.bgcolor("#f5f5f5")
    w.title(title)
    w.setworldcoordinates(llx, lly, urx, ury)
    # With speed(0), turtle buffers polyline points and only flushes to the
    # canvas when the pen goes up or after 42 points; without this, short routes
    # can show a grid but no blue line.
    w.tracer(0, 0)

    scale = span / 400.0
    if show_grid:
        grid_pen = turtle.Turtle(visible=False)
        _draw_block_grid(grid_pen, llx, lly, urx, ury, routed.block_m)
        tcx, tcy = _latlon_to_projected(routed, routed.center_latitude, routed.center_longitude)
        if llx <= tcx <= urx and lly <= tcy <= ury:
            mark = turtle.Turtle(visible=False)
            mark.penup()
            mark.goto(tcx, tcy)
            mark.dot(max(5, int(span / 120.0)), "#2e7d32")

    draw = turtle.Turtle(visible=False)
    draw.speed(0)
    draw.pensize(max(2.0, span / 300.0))
    draw.pencolor(line_color)
    draw.penup()
    draw.goto(float(pts[0][0]), float(pts[0][1]))
    draw.pendown()
    for p in pts[1:]:
        draw.goto(float(p[0]), float(p[1]))
    draw.penup()

    pen = turtle.Turtle(visible=False)
    pen.speed(0)
    pen.pencolor(label_color)
    pen.penup()

    offsets = _label_offsets(len(steps), scale)
    for i, step in enumerate(steps, start=1):
        px, py = _latlon_to_projected(routed, step.corner_lat, step.corner_lon)
        ox, oy = offsets[(i - 1) % len(offsets)]
        pen.goto(px + ox, py + oy)
        # Slightly smaller type when there are many steps so spirals stay compact.
        cap = 11 if len(steps) > 24 else 14
        fs = max(6, min(cap, int(9 * max(0.5, min(2.0, scale)))))
        pen.write(
            _turn_display_name(step, i),
            align="left",
            font=("Arial", fs, "normal"),
        )

    w.update()
    w.tracer(1)
    turtle.done()
