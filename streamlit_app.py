"""
RunFeeti web UI (Streamlit). Run from project root:

    streamlit run streamlit_app.py

OpenStreetMap tiles: © OpenStreetMap contributors.
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import folium
from streamlit_folium import st_folium

from runfeeti.runner import GridDebugBuildResult, build_grid_debug_result, build_route_result
from runfeeti.us_address import abbrev_from_display, build_geocode_line, state_display_values
from runfeeti.web_map import route_polyline_latlon

_APP_DIR = Path(__file__).resolve().parent
_BRANDING_ICON = _APP_DIR / "assets" / "runfeeti_icon_v01.png"


def _state_options() -> list[str]:
    return list(state_display_values())


def _default_state_index(options: list[str]) -> int:
    for i, o in enumerate(options):
        if o.startswith("Texas ("):
            return i
    return min(1, len(options) - 1)


def _build_folium_map(latlons: list[tuple[float, float]]) -> folium.Map:
    lats = [p[0] for p in latlons]
    lons = [p[1] for p in latlons]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))
    m = folium.Map(location=list(center), zoom_start=15, tiles="OpenStreetMap")
    folium.PolyLine(
        latlons,
        color="#1565c0",
        weight=5,
        opacity=0.9,
    ).add_to(m)
    folium.Marker(
        latlons[0],
        popup="Start",
        tooltip="Start",
        icon=folium.Icon(color="green", icon="info-sign"),
    ).add_to(m)
    folium.Marker(
        latlons[-1],
        popup="End",
        tooltip="End",
        icon=folium.Icon(color="red", icon="info-sign"),
    ).add_to(m)
    pad = 0.0008
    m.fit_bounds(
        [
            [min(lats) - pad, min(lons) - pad],
            [max(lats) + pad, max(lons) + pad],
        ]
    )
    return m


def _build_folium_grid_debug_map(
    box_ring_latlon: list[tuple[float, float]],
    grid_points_latlon: list[tuple[float, float]],
) -> folium.Map:
    """Active box polygon (red), grid vertices as blue dots, corner labels BL/BR/TR/TL."""
    corner_labels = ("BL", "BR", "TR", "TL")
    ring_open = box_ring_latlon[:-1] if len(box_ring_latlon) > 4 else box_ring_latlon
    all_pts = list(ring_open) + list(grid_points_latlon)
    if not all_pts:
        return folium.Map(location=[30.27, -97.74], zoom_start=14, tiles="OpenStreetMap")
    lats = [p[0] for p in all_pts]
    lons = [p[1] for p in all_pts]
    center = (sum(lats) / len(lats), sum(lons) / len(lons))
    m = folium.Map(location=list(center), zoom_start=16, tiles="OpenStreetMap")
    locs = [[lat, lon] for lat, lon in box_ring_latlon]
    folium.Polygon(
        locations=locs,
        color="#b71c1c",
        weight=3,
        fill=True,
        fill_color="#ffcdd2",
        fill_opacity=0.2,
    ).add_to(m)
    for lab, (lat, lon) in zip(corner_labels, ring_open):
        folium.CircleMarker(
            location=[lat, lon],
            radius=7,
            color="#e65100",
            fill=True,
            fill_opacity=0.9,
            tooltip=lab,
            popup=lab,
        ).add_to(m)
    for i, (lat, lon) in enumerate(grid_points_latlon):
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color="#1565c0",
            weight=1,
            fill=True,
            fill_opacity=0.9,
            tooltip=f"Vertex {i}",
        ).add_to(m)
    pad = 0.00035
    m.fit_bounds(
        [
            [min(lats) - pad, min(lons) - pad],
            [max(lats) + pad, max(lons) + pad],
        ]
    )
    return m


def main() -> None:
    if _BRANDING_ICON.is_file():
        st.set_page_config(
            page_title="RunFeeti",
            layout="wide",
            initial_sidebar_state="expanded",
            page_icon=str(_BRANDING_ICON),
        )
    else:
        st.set_page_config(
            page_title="RunFeeti",
            layout="wide",
            initial_sidebar_state="expanded",
        )

    if "route_result" not in st.session_state:
        st.session_state.route_result = None
    if "route_error" not in st.session_state:
        st.session_state.route_error = None
    if "last_word" not in st.session_state:
        st.session_state.last_word = ""
    if "grid_debug_result" not in st.session_state:
        st.session_state.grid_debug_result = None

    if _BRANDING_ICON.is_file():
        h1, h2 = st.columns((0.11, 0.89), gap="small")
        with h1:
            st.image(str(_BRANDING_ICON), width=72)
        with h2:
            st.title("RunFeeti")
    else:
        st.title("RunFeeti")
    st.caption(
        "Build a walking route that spells a word using OpenStreetMap paths. "
        "Template uses map north/east, not necessarily your local street grid."
    )
    st.caption(
        "MVP defaults: **5.0 mi** search radius and **5.0 mi** grid-scan span (when optimize-start is on) "
        "for a larger OSM walk network download."
    )

    state_opts = _state_options()
    default_idx = _default_state_index(state_opts)

    with st.sidebar:
        if _BRANDING_ICON.is_file():
            st.image(str(_BRANDING_ICON), use_container_width=True)
        st.header("Where you start")
        with st.form("runfeeti_form", clear_on_submit=False):
            street = st.text_input("Street (number + street)", placeholder="1234 Oak Drive")
            c1, c2 = st.columns(2)
            with c1:
                city = st.text_input("City", placeholder="Austin")
            with c2:
                zip_code = st.text_input("ZIP", placeholder="78739")
            state_choice = st.selectbox("State", options=state_opts, index=default_idx)

            st.divider()
            word = st.text_input(
                "Word to spell",
                placeholder="EAT",
                help="Letters A–Z; spaces add gap. Try simple shapes first: I, L, HI, TIC, EAT on a downtown grid.",
            )

            with st.expander("Route options", expanded=False):
                grid_preview_only = st.checkbox(
                    "Grid preview only (MVP debug)",
                    value=False,
                    help=(
                        "Skip snapped routing. Letter polyline is scaled to fit inside an explicit "
                        "W×H cell contract (default 12×4), then drawn in meters per cell (block size). "
                        "Red outline: street box if resolved, else that contract rectangle."
                    ),
                )
                c_pw, c_ph = st.columns(2)
                with c_pw:
                    preview_grid_w = st.number_input(
                        "Preview grid width (cells)",
                        min_value=2,
                        max_value=500,
                        value=12,
                        step=1,
                        disabled=not grid_preview_only,
                        help="Explicit contract width in abstract cells (map span = width × block meters).",
                    )
                with c_ph:
                    preview_grid_h = st.number_input(
                        "Preview grid height (cells)",
                        min_value=2,
                        max_value=500,
                        value=4,
                        step=1,
                        disabled=not grid_preview_only,
                        help="Explicit contract height in abstract cells.",
                    )
                radius_mi = st.number_input(
                    "Search radius (miles)",
                    min_value=0.25,
                    max_value=50.0,
                    value=5.0,
                    step=0.25,
                    help=(
                        "OSM walk network download radius around the geocoded address. "
                        "Default 5 mi for MVP testing (bigger download, fewer edge-of-graph gaps)."
                    ),
                )
                letter_gap = st.number_input(
                    "Letter gap",
                    min_value=0,
                    max_value=10,
                    value=1,
                    step=1,
                    help="Extra grid units between letters.",
                )
                block_m_raw = st.text_input(
                    "Block size (meters, optional)",
                    placeholder="Auto from median block",
                    help="Leave empty to use median OSM edge length in the area.",
                )
                roads_first = st.checkbox(
                    label="Roads-first MVP (penalize footpath shortcuts)",
                    value=True,
                    help="Prefer street grid on the walk network; footways/paths stay allowed if much shorter.",
                )

            with st.expander("Street-grid box (MVP)", expanded=False):
                use_street_box = st.checkbox(
                    "Street-grid box (MVP)",
                    value=False,
                    help=(
                        "Resolve four corners from named OSM streets on the walk graph (report only; "
                        "route still uses template placement)."
                    ),
                )
                street_bottom = st.text_input(
                    "Bottom street",
                    placeholder="W 6th Street",
                    disabled=not use_street_box,
                )
                street_top = st.text_input(
                    "Top street",
                    placeholder="W 5th Street",
                    disabled=not use_street_box,
                )
                street_left = st.text_input(
                    "Left street",
                    placeholder="Colorado Street",
                    disabled=not use_street_box,
                )
                street_right = st.text_input(
                    "Right street",
                    placeholder="Lavaca Street",
                    disabled=not use_street_box,
                )

            with st.expander("Grid search (advanced)", expanded=False):
                optimize_start = st.checkbox(
                    "Find better grid start",
                    value=False,
                    help="Scan ±miles for a more orthogonal walk mesh; larger download, slower.",
                )
                search_half_miles = st.number_input(
                    "± miles to scan",
                    min_value=0.1,
                    max_value=10.0,
                    value=5.0,
                    step=0.5,
                    help="Half-span for optimize-start grid search (default 5 mi for MVP testing).",
                )

            submitted = st.form_submit_button("Get directions", type="primary", use_container_width=True)

    if submitted:
        st.session_state.route_error = None
        st.session_state.route_result = None
        st.session_state.grid_debug_result = None
        w = word.strip()
        if not w:
            st.session_state.route_error = "Enter a word to spell."
        else:
            try:
                abbr = abbrev_from_display(state_choice)
                addr = build_geocode_line(street, city, abbr, zip_code)
            except ValueError as e:
                st.session_state.route_error = str(e)
                addr = None

            if addr is not None and st.session_state.route_error is None:
                if use_street_box and not all(
                    x.strip()
                    for x in (
                        street_bottom,
                        street_top,
                        street_left,
                        street_right,
                    )
                ):
                    st.session_state.route_error = (
                        "Street-grid box: enter bottom, top, left, and right street names, "
                        "or turn off Street-grid box (MVP)."
                    )
                elif search_half_miles <= 0 or search_half_miles > 10:
                    st.session_state.route_error = "± miles for grid search must be between 0 and 10."
                else:
                    try:
                        sb_tuple: tuple[str, str, str, str] | None = None
                        if use_street_box:
                            sb_tuple = (
                                street_bottom.strip(),
                                street_top.strip(),
                                street_left.strip(),
                                street_right.strip(),
                            )
                        if grid_preview_only:
                            with st.status("Grid preview (geocode, OSM, layout only)…", expanded=True) as status:
                                status.write("Geocoding and downloading walk graph…")
                                gres = build_grid_debug_result(
                                    addr,
                                    w,
                                    float(radius_mi),
                                    int(letter_gap),
                                    block_m_raw.strip(),
                                    roads_first=roads_first,
                                    street_box=sb_tuple,
                                    preview_contract_w=float(preview_grid_w),
                                    preview_contract_h=float(preview_grid_h),
                                )
                                status.write("Done.")
                            st.session_state.grid_debug_result = gres
                            st.session_state.last_word = w.upper()
                            if "directions_text" in st.session_state:
                                del st.session_state["directions_text"]
                        else:
                            with st.status("Building route (geocode, OSM, directions)…", expanded=True) as status:
                                status.write("Geocoding and downloading map data…")
                                res = build_route_result(
                                    addr,
                                    w,
                                    float(radius_mi),
                                    int(letter_gap),
                                    block_m_raw.strip(),
                                    optimize_start=optimize_start,
                                    search_half_miles=float(search_half_miles),
                                    roads_first=roads_first,
                                    street_box=sb_tuple,
                                )
                                status.write("Done.")
                            st.session_state.route_result = res
                            st.session_state.last_word = w.upper()
                            if "directions_text" in st.session_state:
                                del st.session_state["directions_text"]
                    except ValueError as e:
                        st.session_state.route_error = str(e)
                    except Exception as e:
                        st.session_state.route_error = f"Error: {e}"

    err = st.session_state.route_error
    res = st.session_state.route_result
    gdebug: GridDebugBuildResult | None = st.session_state.grid_debug_result

    if err:
        st.error(err)

    if gdebug is not None:
        left, right = st.columns((1.05, 1.0), gap="large")
        with left:
            st.subheader("Grid preview report")
            st.text_area(
                "Grid preview",
                value=gdebug.report_text,
                height=560,
                disabled=True,
                label_visibility="collapsed",
            )
            st.download_button(
                label="Download grid preview as .txt",
                data=gdebug.report_text.encode("utf-8"),
                file_name=f"runfeeti_grid_{st.session_state.last_word or 'preview'}.txt",
                mime="text/plain",
            )
        with right:
            st.subheader("Map")
            st.caption(
                "Red outline: street box if resolved; otherwise the explicit preview contract "
                f"({gdebug.preview_contract_w:g}×{gdebug.preview_contract_h:g} cells × block size). "
                "Orange: corners BL–TR. Blue: letter vertices (uniformly scaled inside the contract when not street box)."
            )
            fmap = _build_folium_grid_debug_map(
                gdebug.box_ring_latlon,
                gdebug.grid_points_latlon,
            )
            st_folium(
                fmap,
                height=520,
                use_container_width=True,
                returned_objects=[],
                key="runfeeti_folium_grid_debug",
            )
            st.caption("Map data © OpenStreetMap contributors.")
    elif res is not None:
        left, right = st.columns((1.05, 1.0), gap="large")
        with left:
            st.subheader("Turn-by-turn")
            st.text_area(
                "Directions",
                value=res.report_text,
                height=560,
                disabled=True,
                label_visibility="collapsed",
            )
            st.download_button(
                label="Download directions as .txt",
                data=res.report_text.encode("utf-8"),
                file_name=f"runfeeti_{st.session_state.last_word or 'route'}.txt",
                mime="text/plain",
            )
        with right:
            st.subheader("Map")
            latlons = route_polyline_latlon(res.routed)
            if len(latlons) < 2:
                st.info("Route too short to draw on the map.")
            else:
                fmap = _build_folium_map(latlons)
                st_folium(
                    fmap,
                    height=520,
                    use_container_width=True,
                    returned_objects=[],
                    key="runfeeti_folium_map",
                )
                st.caption("Map data © OpenStreetMap contributors.")

    with st.sidebar:
        st.divider()
        if st.button("Clear results", use_container_width=True):
            st.session_state.route_result = None
            st.session_state.grid_debug_result = None
            st.session_state.route_error = None
            st.session_state.last_word = ""
            st.session_state.pop("directions_text", None)
            st.rerun()

        st.markdown(
            """
**Tips**

- OSM street names may differ from your mail (e.g. Lane vs Drive).
- Verify safety and legal access before running.
- Nominatim reverse geocoding is rate-limited (~1 s per unique corner).
            """.strip()
        )


if __name__ == "__main__":
    main()
