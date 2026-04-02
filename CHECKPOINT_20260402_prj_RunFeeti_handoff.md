# Checkpoint — Hand off to next chat: folder rename `prj_RunFeeti` (2026-04-02)

## 1. Objective

Provide a clean **handoff** for a **new chat** after the user **manually renames** the project folder from **`prj_Runffiti`** to **`prj_RunFeeti`**. The user will perform the rename outside the agent; follow-on work **refactors references** (paths, docs, tooling) so everything stays consistent with **RunFeeti** branding and the **`runfeeti`** package.

## 2. What was broken

Nothing new in code for this checkpoint. **Operational note:** after any folder rename, **`.venv`** activation scripts (`activate`, `activate.bat`, etc.) may still embed the **old** absolute path until the venv is recreated or paths are patched.

## 3. Root cause confirmed

N/A for this checkpoint. Historical pattern: hard-coded `VIRTUAL_ENV` in venv `Scripts/` is generated at `python -m venv` time and **does not** auto-update when the parent folder moves.

## 4. Changes made

**This session (checkpoint only):** added this file  
`CHECKPOINT_20260402_prj_RunFeeti_handoff.md`.

No application code was changed for the rename.

## 5. Observed results

Prior work (Streamlit UI, `run_streamlit.bat`, `web_map.py`, routing/turtle/grid search, README/CHANGELOG) is assumed **working** under folder name **`prj_RunFeeti`** with package **`runfeeti`**.

## 6. Current known good state

- **Folder:** `prj_RunFeeti` (or equivalent path on disk).
- **Python package name:** `runfeeti` (import path `runfeeti.*`).
- **Entry points:** `python -m runfeeti`, `python -m runfeeti --gui`, `streamlit run streamlit_app.py`, `run_streamlit.bat`.
- **Branding:** user-facing strings use **RunFeeti**; docs and `.cursor/rules` refer to **RunFeeti** / `prj_RunFeeti` / `runfeeti`.

## 7. Open issue(s) / remaining risks

1. **Venv:** after any folder rename, **recreate** `.venv` or fix activation paths; **`pip install -r requirements.txt`** again.
2. **IDE/workspace:** Cursor/VS Code may still point at an old folder path until reopened on the new folder.

## 8. Recommended next chat scope

1. Optional **CLI flag** to disable turtle grid or center dot for minimal maps (see routing checkpoint).
2. **House-number-aware block spacing** prototype behind a flag (cost/latency analysis).
3. **Automated smoke test** (mocked graph or tiny fixture) for `RoutedPath` and turtle behavior.

## 9. Files changed in this session

| Action | Path |
|--------|------|
| Added | `CHECKPOINT_20260402_prj_RunFeeti_handoff.md` |

---

**For the user:** open the project folder in Cursor; branding is **RunFeeti**, module is **`runfeeti`**.
