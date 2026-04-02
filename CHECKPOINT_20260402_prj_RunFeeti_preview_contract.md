# Checkpoint — Explicit preview grid contract (12×4 MVP) (2026-04-02)

## 1. Objective

Make **Grid preview only (MVP debug)** use an **explicit target grid size** (width × height in abstract cells) instead of inferring footprint only from the legacy template-centered `grid_waypoints` scaling, so downtown testing can reason about a **12×4** (or user-set) contract while **pausing** full routing/snap/optimize work.

## 2. What was broken

Preview footprint on the map stayed **visually compressed** relative to intent: increasing OSM **radius** grew the download, not the **declared** letter canvas; there was no first-class **W×H cell contract** for the preview.

## 3. Root cause confirmed

Preview used **`grid_waypoints`** (letter polyline bounds × `block_m`, centered on start). Map red rectangle for template fallback tracked the **tight bbox of vertices**, not a user-declared **12×4** (or similar) rectangle.

## 4. Changes made

- **`runfeeti/letters.py`:** `layout_word_in_contract_cells` (uniform scale + center inside `[0, W]×[0, H]`), `letter_polyline_intrinsic_cell_span`.
- **`runfeeti/routing.py`:** `grid_waypoints_in_contract`; `build_grid_preview(..., preview_contract_w, preview_contract_h)`; `GridPreviewContext` now stores contract dimensions + intrinsic letter span.
- **`runfeeti/runner.py`:** `build_grid_debug_result(..., preview_contract_w, preview_contract_h)`; richer report + truth-check line; street-box note when red outline is OSM, not the axis-aligned contract; `GridDebugBuildResult` uses `preview_contract_w` / `preview_contract_h` instead of old `grid_width_cells` / `grid_height_cells`.
- **`streamlit_app.py`:** Preview **width/height (cells)** inputs (defaults 12/4, disabled when preview off); pass-through to `build_grid_debug_result`; map caption uses contract dimensions.
- **`CHANGELOG.md`:** Appended **Unreleased** notes for this work.

## 5. Observed results

With **street box off** (or unresolved), the **red polygon** matches the **explicit contract × block_m** in projected meters, centered on the geocoded start; **blue** dots are vertices after **uniform** fit inside that contract. With **street box resolved**, red outline remains the **OSM** quadrilateral; report states vertices still use contract × block at start.

## 6. Current known-good state

- Streamlit **Grid preview only** remains the debug entry point.
- Defaults: **12×4** cells; **5 mi** radius / grid-scan defaults from earlier MVP work unchanged for full route.
- Full **`build_route` / `grid_waypoints`** path unchanged.

## 7. Open issue(s) / remaining risks

1. **Street box vs contract:** When the street box resolves, the **red** frame is not the numeric contract; aligning letter **placement** to the street quadrilateral is **not** done yet.
2. **Uniform scale** leaves **empty margin** inside the contract if the word’s aspect ratio does not fill 12×4; that is intentional (no non-uniform stretch in this patch).
3. **`block_m`** still comes from **median edge length** (or user override); contract **cell** size in meters is not independently tunable beyond that.

## 8. Recommended next chat scope

1. Optionally **map** the contract into the **street box** affine (when both exist) without touching snap/retrace yet.
2. Separate **cell size** from median-block heuristic for preview-only experiments.
3. Keep **routing complexity paused** until preview footprint matches product expectations.

## 9. Files changed in this session

| Path |
|------|
| `runfeeti/letters.py` |
| `runfeeti/routing.py` |
| `runfeeti/runner.py` |
| `streamlit_app.py` |
| `CHANGELOG.md` |
| `CHECKPOINT_20260402_prj_RunFeeti_preview_contract.md` (this file) |
| `backups/zzz_letters.py__pre_20260402_141151.py` |
| `backups/zzz_routing.py__pre_20260402_141151.py` |
| `backups/zzz_runner.py__pre_20260402_141151.py` |
| `backups/zzz_streamlit_app.py__pre_20260402_141151.py` (and sibling backups for letters/routing/runner) |

---

**Truth check:** With template/street fallback (red = contract rectangle), geographic span is **exactly** `preview_contract_w × block_m` by `preview_contract_h × block_m` in the graph’s projected CRS; blue points lie **inside** that rectangle (inset possible due to uniform scaling).
