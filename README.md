# RunFeeti

**RunFeeti** is a Python tool that builds a **walking route** from a start address and a **word**. It lays out orthogonal “digital” letters on a grid, snaps corners to **OpenStreetMap** pedestrian paths, and outputs **turn-by-turn directions** plus an optional **turtle** map.

## What it does

1. **Geocode** your starting address (via **Nominatim** / OpenStreetMap).
2. **Download** a walkable street network around that point (**OSMnx**, `network_type="walk"`).
3. Place a **letter template** (A–Z) on a grid in **map projection** (north/east), scaled by a **block size** (default: median OSM edge length in the area, or your override in meters).
4. **Snap** template corners to the nearest graph nodes and connect them with **shortest paths** along walkable edges.
5. Emit **step-by-step directions**; optionally **reverse-geocode** each step corner for a `[number + street]` prefix (rate-limited, ~1 s per unique corner).
6. Optionally open a **Streamlit** web UI (map + directions), a **Tkinter GUI**, or a **turtle** window.

Letters follow **map north/east**, not necessarily your local street grid, so the path may not look like the word from a bird’s-eye photo.

## Requirements

- **Python 3.x** (project tested with 3.13).
- Dependencies in **`requirements.txt`** (includes **osmnx**, **geopy**, **networkx**, **numpy**, **scipy**, **geopandas**, **shapely**, and Streamlit/Folium web UI packages).

## Setup

```text
cd prj_RunFeeti
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Run from the **project root** so the `runfeeti` package is importable.

If you **rename the project folder**, recreate the venv or fix activation scripts so `VIRTUAL_ENV` points at the new path.

For editable command installation, use:

```text
pip install -e .
runfeeti "123 Main St, Austin, TX" RICK --radius-mi 1.0
```

## Command line

```text
python -m runfeeti "123 Main St, Austin, TX" RICK --radius-mi 1.0
```

Useful options:

- `--letter-gap` — extra grid units between letters.
- `--block-m` — override meters per template unit (default: median edge length).
- `--map` — open turtle map after printing directions.
- `--version` — print the installed RunFeeti version.
- `--optimize-start` — search within ±`--search-half-mi` (default `2.0`) for a template center with a more grid-like walk mesh (larger OSM download, slower).
- `--search-half-mi` — half-span for that search (validated between 0.1 and 10 when used from CLI).
- `--no-roads-first` - allow footpath-like shortcuts without the street-grid penalty.
- `--roads-first-penalty` - multiplier for footpath-like edges when roads-first routing is on (default: `10`).

## Web UI (Streamlit)

From the project root (after `pip install -r requirements.txt`):

```text
streamlit run streamlit_app.py
```

On **Windows**, you can double-click **`run_streamlit.bat`** in the project folder (uses `.venv` if it exists).

Uses a **sidebar** for address, word, and options (expanders for route tuning and grid search). Shows **turn-by-turn text** and an **interactive OpenStreetMap** (Folium) with the route polyline. **Clear results** resets the session. **Download** exports the report as `.txt`.

## Desktop GUI (Tkinter)

```text
python -m runfeeti --gui
```

After `pip install -e .`, the same GUI is available with:

```text
runfeeti --gui
```

Structured address fields, **Get directions**, **Turtle map**, optional **Find better grid start** and ± mi field.

## Verify

Run these checks from the project root before handing off changes:

```text
.\tools\verify.ps1
```

That script runs the same checks as:

```text
python -m unittest discover -s tests
python -m compileall -q runfeeti streamlit_app.py tests
```

## Limitations and safety

- Data is **OpenStreetMap** only; names may differ from postal addresses.
- Directions are **advisory**; check **access**, **private property**, and **real-world safety**.
- Respect **Nominatim** and OSM usage policies (no bulk hammering; built-in throttling on reverse geocode).

## License / attribution

Follow **OpenStreetMap** and **Nominatim** attribution and license terms when publishing maps or derived works.

## More detail

See **`CHANGELOG.md`** for recent changes and **`CHECKPOINT_*.md`** in the repo root for session handoff notes.
