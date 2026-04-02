# Changelog

All notable changes to this project are documented in this file. Entries are appended newest-last.

## [Unreleased]

### Added

- Optional **grid start search** (`runfeeti/grid_start.py`): scans candidate template centers within a configurable half-span (default ±2 mi) on a downloaded OSM walk bbox; scores local mesh (orthogonal edges, node density, path length). Wired through `build_route(..., optimize_start=..., search_half_miles=...)`, CLI (`--optimize-start`, `--search-half-mi`), and GUI (checkbox + ± mi field).
- **Turtle map block grid** aligned to `RoutedPath.block_m`, plus a green dot at the template center (`center_latitude` / `center_longitude`).
- **`RoutedPath`** fields: `block_m`, `center_latitude`, `center_longitude`, optional `grid_search_note`.
- **`load_walk_graph_bbox`** in `routing.py` for bbox-based OSM walk downloads used by grid search.
- **Streamlit web UI** (`streamlit_app.py` at repo root): wide layout, sidebar form (address, word, expanders for route options and grid search), turn-by-turn text area, **Folium** map via **streamlit-folium** (polyline + start/end markers), download `.txt`, **Clear results**. New **`runfeeti/web_map.py`** converts the route to WGS84 `(lat, lon)` for the map.
- **Explicit preview grid contract** (Grid preview only, MVP): Streamlit **Preview grid width / height (cells)** (defaults **12** × **4**); `layout_word_in_contract_cells`, `letter_polyline_intrinsic_cell_span` in `letters.py`; `grid_waypoints_in_contract` and contract args on `build_grid_preview` / `GridPreviewContext` in `routing.py`; report + truth-check in `runner.py`. Template-fallback red rectangle = **contract × block_m** centered on start; street-box map outline unchanged when resolved.

### Changed

- **Branding and docs:** product name **RunFeeti** (replacing Runffiti) across UI strings, README, checkpoints, `.cursor/rules`, `run_streamlit.bat`, and `tools/rename_project_folder.ps1` (target folder `prj_RunFeeti`). Streamlit form keys and download filename prefix use **`runfeeti_`**. IDE example run config points at **`runfeeti/`**.
- **`runner`**: Progress line for corner reverse-geocoding prints to **stdout** with `flush=True` and clearer wording (avoids IDE styling stderr as an error).
- **`turtle_map`**: Turn labels use a **golden-angle spiral** for anchor offsets; slightly smaller cap font when there are many steps.
- **`turtle_map`**: After each full route polyline, **`penup()`** flushes the line buffer with **`speed(0)`**; **`tracer(0)` / `update()` / `tracer(1)`** for reliable redraw.
- **`turtle_map`**: **`Screen.clear()`** (with `tk.TclError` guard) before each map draw so repeated **Turtle map** opens do not stack old grids, routes, or labels.
- **`GridDebugBuildResult`**: `grid_width_cells` / `grid_height_cells` replaced by **`preview_contract_w`** / **`preview_contract_h`**.

### Notes

- Project folder rename to `prj_RunFeeti`: recreate or fix `.venv` activation scripts if they still point at an old path; prefer `python -m venv .venv` then `pip install -r requirements.txt`.
- Full **snapped route** still uses `grid_waypoints` without the preview-only contract; contract sizing applies only to **Grid preview only** and the template-fallback rectangle on that map.
