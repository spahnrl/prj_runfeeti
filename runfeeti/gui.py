from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from tkinter import scrolledtext

from runfeeti.result import RouteBuildResult
from runfeeti.route_options import (
    DEFAULT_CLI_RADIUS_MI,
    DEFAULT_CLI_SEARCH_HALF_MI,
    DEFAULT_LETTER_GAP,
    DEFAULT_ROADS_FIRST_PENALTY,
    RouteOptions,
    normalize_word,
    parse_route_options,
)
from runfeeti.us_address import (
    abbrev_from_display,
    build_geocode_line,
    state_display_values,
)


def _run_build(
    address: str,
    word: str,
    options: RouteOptions,
    *,
    optimize_start: bool,
    roads_first: bool,
) -> RouteBuildResult:
    from runfeeti.runner import build_route_result

    return build_route_result(
        address,
        word,
        options.radius_mi,
        options.letter_gap,
        options.block_m_raw,
        optimize_start=optimize_start,
        search_half_miles=options.search_half_miles,
        roads_first=roads_first,
        roads_first_penalty=options.roads_first_penalty,
    )


def run_app() -> None:
    root = tk.Tk()
    root.title("RunFeeti - directions")
    root.minsize(560, 520)

    last_build: list[RouteBuildResult | None] = [None]

    main = ttk.Frame(root, padding=10)
    main.pack(fill=tk.BOTH, expand=True)

    row = 0
    ttk.Label(main, text="Street address (number + street)").grid(
        row=row, column=0, sticky=tk.W, pady=(0, 2)
    )
    row += 1
    street_var = tk.StringVar()
    street_entry = ttk.Entry(main, textvariable=street_var, width=56)
    street_entry.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 6))
    row += 1

    addr_row = ttk.Frame(main)
    addr_row.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
    row += 1
    addr_row.columnconfigure(1, weight=1)

    ttk.Label(addr_row, text="City").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
    city_var = tk.StringVar()
    ttk.Entry(addr_row, textvariable=city_var, width=22).grid(
        row=0, column=1, sticky=tk.EW, padx=(0, 12)
    )

    ttk.Label(addr_row, text="State").grid(row=0, column=2, sticky=tk.W, padx=(0, 6))
    state_var = tk.StringVar()
    state_combo = ttk.Combobox(
        addr_row,
        textvariable=state_var,
        values=state_display_values(),
        state="readonly",
        width=26,
    )
    state_combo.grid(row=0, column=3, sticky=tk.W, padx=(0, 12))
    state_var.set(state_display_values()[0])

    ttk.Label(addr_row, text="ZIP").grid(row=0, column=4, sticky=tk.W, padx=(0, 6))
    zip_var = tk.StringVar()
    ttk.Entry(addr_row, textvariable=zip_var, width=12).grid(row=0, column=5, sticky=tk.W)

    ttk.Label(main, text="Word to spell").grid(row=row, column=0, sticky=tk.W, pady=(0, 2))
    row += 1
    word_var = tk.StringVar()
    ttk.Entry(main, textvariable=word_var, width=24).grid(row=row, column=0, sticky=tk.W, pady=(0, 8))
    row += 1

    opts = ttk.Frame(main)
    opts.grid(row=row, column=0, columnspan=2, sticky=tk.EW, pady=(0, 8))
    row += 1

    ttk.Label(opts, text="Radius (mi)").grid(row=0, column=0, sticky=tk.W, padx=(0, 6))
    radius_var = tk.StringVar(value=f"{DEFAULT_CLI_RADIUS_MI:g}")
    ttk.Entry(opts, textvariable=radius_var, width=8).grid(row=0, column=1, sticky=tk.W, padx=(0, 16))

    ttk.Label(opts, text="Letter gap").grid(row=0, column=2, sticky=tk.W, padx=(0, 6))
    gap_var = tk.StringVar(value=str(DEFAULT_LETTER_GAP))
    ttk.Entry(opts, textvariable=gap_var, width=6).grid(row=0, column=3, sticky=tk.W, padx=(0, 16))

    ttk.Label(opts, text="Block m (optional)").grid(row=0, column=4, sticky=tk.W, padx=(0, 6))
    block_var = tk.StringVar()
    ttk.Entry(opts, textvariable=block_var, width=10).grid(row=0, column=5, sticky=tk.W)

    opt_route = ttk.Frame(main)
    opt_route.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
    row += 1
    roads_first_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        opt_route,
        text="Prefer street grid (penalize footpath shortcuts)",
        variable=roads_first_var,
    ).pack(side=tk.LEFT)
    ttk.Label(opt_route, text="Penalty").pack(side=tk.LEFT, padx=(12, 4))
    roads_first_penalty_var = tk.StringVar(value=f"{DEFAULT_ROADS_FIRST_PENALTY:g}")
    ttk.Entry(opt_route, textvariable=roads_first_penalty_var, width=6).pack(side=tk.LEFT)

    opt2 = ttk.Frame(main)
    opt2.grid(row=row, column=0, columnspan=2, sticky=tk.W, pady=(0, 8))
    row += 1
    optimize_grid_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        opt2,
        text="Find better grid start (scan ±mi for orthogonal blocks; slower, bigger OSM download)",
        variable=optimize_grid_var,
    ).pack(side=tk.LEFT)
    ttk.Label(opt2, text="± mi").pack(side=tk.LEFT, padx=(12, 4))
    search_half_mi_var = tk.StringVar(value=f"{DEFAULT_CLI_SEARCH_HALF_MI:g}")
    ttk.Entry(opt2, textvariable=search_half_mi_var, width=6).pack(side=tk.LEFT)

    log = scrolledtext.ScrolledText(
        main,
        height=20,
        width=72,
        wrap=tk.WORD,
        font=("Consolas", 10) if _has_consolas() else ("TkFixedFont", 10),
        state=tk.DISABLED,
    )
    log.grid(row=row, column=0, columnspan=2, sticky=tk.NSEW, pady=(4, 8))
    row += 1
    main.rowconfigure(row - 1, weight=1)
    main.columnconfigure(0, weight=1)

    btn_frame = ttk.Frame(main)
    btn_frame.grid(row=row, column=0, columnspan=2, sticky=tk.EW)

    def append_log(text: str) -> None:
        log.configure(state=tk.NORMAL)
        log.insert(tk.END, text)
        if not text.endswith("\n"):
            log.insert(tk.END, "\n")
        log.see(tk.END)
        log.configure(state=tk.DISABLED)

    def clear_log() -> None:
        log.configure(state=tk.NORMAL)
        log.delete("1.0", tk.END)
        log.configure(state=tk.DISABLED)

    def set_busy(busy: bool) -> None:
        go_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)

    def on_done_bundle(res: RouteBuildResult) -> None:
        last_build[0] = res
        clear_log()
        append_log(res.report_text)
        map_btn.configure(state=tk.NORMAL)
        set_busy(False)

    def on_error(err: str) -> None:
        last_build[0] = None
        clear_log()
        append_log(err)
        map_btn.configure(state=tk.DISABLED)
        set_busy(False)

    def do_run() -> None:
        try:
            word = normalize_word(word_var.get())
        except ValueError as e:
            clear_log()
            append_log(str(e))
            return
        try:
            abbr = abbrev_from_display(state_var.get())
            addr = build_geocode_line(
                street_var.get(),
                city_var.get(),
                abbr,
                zip_var.get(),
            )
        except ValueError as e:
            clear_log()
            append_log(str(e))
            return
        try:
            options = parse_route_options(
                radius_mi=radius_var.get(),
                letter_gap=gap_var.get(),
                block_m_raw=block_var.get(),
                search_half_miles=search_half_mi_var.get(),
                roads_first_penalty=roads_first_penalty_var.get(),
            )
        except ValueError as e:
            clear_log()
            append_log(str(e))
            return

        set_busy(True)
        clear_log()
        append_log(f"Lookup address: {addr}\n")
        if optimize_grid_var.get():
            append_log(
                f"Grid search enabled (±{options.search_half_miles:g} mi). Fetching larger street network, scanning centers…\n"
            )
        append_log(
            "Fetching map data, building route, then resolving [address] per step (rate-limited)...\n"
        )

        def work() -> None:
            try:
                res = _run_build(
                    addr,
                    word,
                    options,
                    optimize_start=optimize_grid_var.get(),
                    roads_first=roads_first_var.get(),
                )
                root.after(0, lambda r=res: on_done_bundle(r))
            except ValueError as e:
                es = str(e)
                root.after(0, lambda s=es: on_error(s))
            except Exception as e:
                msg = f"Error: {e}"
                root.after(0, lambda m=msg: on_error(m))

        threading.Thread(target=work, daemon=True).start()

    go_btn = ttk.Button(btn_frame, text="Get directions", command=do_run)
    go_btn.pack(side=tk.LEFT)

    def show_map() -> None:
        b = last_build[0]
        if not b or len(b.routed.nodes) < 2:
            return
        from runfeeti.turtle_map import show_route_turtle

        w = word_var.get().strip() or "route"
        show_route_turtle(b.routed, b.steps, title=f"RunFeeti - {w}")

    map_btn = ttk.Button(btn_frame, text="Turtle map", command=show_map, state=tk.DISABLED)
    map_btn.pack(side=tk.LEFT, padx=(8, 0))

    ttk.Button(btn_frame, text="Clear log", command=clear_log).pack(side=tk.LEFT, padx=(8, 0))

    street_entry.focus_set()
    root.mainloop()


def _has_consolas() -> bool:
    try:
        import tkinter.font as tkfont

        return "Consolas" in tkfont.families()
    except Exception:
        return False


if __name__ == "__main__":
    run_app()
