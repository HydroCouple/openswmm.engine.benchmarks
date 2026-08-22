#!/usr/bin/env python3
"""Figures + TRANSITIONS_REPORT.md for the transitions suite.

Visual language: profile figures draw the pipe as an invert/crown tube over a
soil fill (the epa_qa hgl_profile style); solver series use the repo's fixed
categorical order so a solver keeps its color in every figure.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from . import analytic, config, extract
from .cases import CASES, Case
from .solvers import SOLVERS

from harness import engines, scoring

# fixed categorical assignment (validated palette; identity never re-ranked)
COLORS = {"fv": "#2a78d6", "fv-lts": "#eb6834", "dw": "#1baf7a",
          "dw-slot": "#eda100", "dw-legacy": "#e87ba4"}
LABELS = {s.id: s.label for s in SOLVERS}
ORDER = ["fv", "fv-lts", "dw", "dw-slot", "dw-legacy"]   # legend order
ZBOT = list(reversed(ORDER))                             # draw fv last (top)

INK, MUTED, GRIDC = "#0b0b0b", "#898781", "#e1e0d9"
SURFACE, SOIL, PIPE_FILL = "#fcfcfb", "#e2d7bd", "#efede6"
DPI = 120


def _style(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRIDC)
    ax.tick_params(colors=MUTED, labelsize=9)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)
    ax.title.set_color(INK)
    ax.grid(True, color=GRIDC, linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)


def _save(fig, name: str) -> str:
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    path = config.FIGURES_DIR / name
    fig.patch.set_facecolor(SURFACE)
    fig.savefig(path, dpi=DPI, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)
    return f"figures/{name}"


def _load_runs(case: Case) -> dict:
    out = {}
    for s in SOLVERS:
        p = config.RUNS_DIR / case.id / s.id / "model.out"
        if p.exists():
            out[s.id] = extract.read_run(p, case)
    return out


def _tube(ax, case: Case):
    x, z = case.node_x(), case.node_z()
    crown = z + case.node_diam()
    lo = float(z.min()) - 0.8
    ax.fill_between(x, lo, z, color=SOIL, zorder=0)
    ax.fill_between(x, z, crown, color=PIPE_FILL, zorder=1)
    ax.plot(x, z, color=MUTED, lw=1.2, zorder=2)
    ax.plot(x, crown, color=MUTED, lw=1.2, ls=(0, (4, 2)), zorder=2)
    ax.set_ylim(bottom=lo)


def hgl_snapshot(case: Case, runs: dict, t: float, name: str,
                 analytic_h: np.ndarray | None = None,
                 ymax: float | None = None,
                 note: str | None = None) -> str:
    x = case.node_x()
    fig, ax = plt.subplots(figsize=(8.4, 3.6))
    _style(ax)
    _tube(ax, case)
    if analytic_h is not None:
        ax.plot(x, analytic_h, color=INK, lw=1.6, ls="--", zorder=3,
                label="analytic")
    for sid in ZBOT:
        if sid in runs:
            ax.plot(x, extract.heads_at(runs[sid], t), color=COLORS[sid],
                    lw=2.0, zorder=4 + ZBOT.index(sid), label=LABELS[sid])
    tops = [float(np.nanmax(extract.heads_at(runs[s], t)))
            for s in runs] or [0.0]
    if analytic_h is not None:
        tops.append(float(np.max(analytic_h)))
    auto_top = max(max(tops), float((case.node_z() + case.node_diam()).max()))
    ax.set_ylim(top=(ymax if ymax is not None else auto_top + 0.4))
    if note:
        ax.text(0.985, 0.03, note, transform=ax.transAxes, ha="right",
                fontsize=8, color=MUTED, style="italic")
    ax.set_xlabel("chainage (m)")
    ax.set_ylabel("elevation (m)")
    mm = int(round(t // 60))
    ax.set_title(f"{case.id} — hydraulic grade line at t = {mm} min")
    handles, labels = ax.get_legend_handles_labels()
    order = sorted(range(len(labels)),
                   key=lambda i: (["analytic"] + ORDER).index(labels[i])
                   if labels[i] in (["analytic"] + ORDER)
                   else [LABELS[k] for k in ORDER].index(labels[i]) + 1)
    ax.legend([handles[i] for i in order], [labels[i] for i in order],
              fontsize=8, framealpha=0.9, loc="upper right", ncols=2)
    return _save(fig, name)


def fig_front_trajectory(case: Case, runs: dict) -> str:
    fig, ax = plt.subplots(figsize=(6.6, 4.2))
    _style(ax)
    t_ref = np.linspace(0.0, case.L / analytic.front_speed(case), 50)
    ax.plot(t_ref, analytic.front_trajectory(case, t_ref), color=INK,
            lw=1.6, ls="--",
            label=f"analytic bore, {analytic.front_speed(case):.2f} m/s")
    for sid in ZBOT:
        if sid in runs:
            xf = extract.front_series(runs[sid], case)
            keep = xf > 0
            ax.plot(runs[sid]["t"][keep], xf[keep], color=COLORS[sid], lw=2.0,
                    label=LABELS[sid])
    ax.set_xlim(0, 300)
    ax.set_xlabel("time (s)")
    ax.set_ylabel("pressurization front position (m)")
    ax.set_title("rapid-fill — front trajectory")
    ax.legend(fontsize=8, framealpha=0.9, loc="lower right")
    return _save(fig, f"{case.id}__front_trajectory.png")


def fig_timeseries(case: Case, runs: dict, node_i: int, link_i: int,
                   head_ylim: tuple | None = None) -> str:
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 5.4), sharex=True)
    for ax in axes:
        _style(ax)
    x = case.node_x()
    for sid in ZBOT:
        if sid not in runs:
            continue
        r = runs[sid]
        tm = r["t"] / 60.0
        axes[0].plot(tm, r["heads"][node_i], color=COLORS[sid], lw=1.8,
                     label=LABELS[sid])
        axes[1].plot(tm, r["flows"][link_i], color=COLORS[sid], lw=1.8)
    crown = case.node_z()[node_i] + case.node_diam()[node_i]
    axes[0].axhline(crown, color=MUTED, lw=1.2, ls=(0, (4, 2)))
    axes[0].text(0.005, crown, " pipe crown", color=MUTED, fontsize=8,
                 va="bottom", transform=axes[0].get_yaxis_transform())
    if head_ylim:
        axes[0].set_ylim(*head_ylim)
    axes[0].set_ylabel(f"head at x={x[node_i]:g} m (m)")
    axes[1].set_ylabel(f"flow at x≈{x[link_i]:g} m (m³/s)")
    axes[1].set_xlabel("time (min)")
    axes[0].set_title(f"{case.id} — head and flow")
    axes[0].legend(fontsize=8, framealpha=0.9, ncols=2)
    return _save(fig, f"{case.id}__ts.png")


def _cells_by(env: dict) -> dict:
    return {(c["case"], c["solver"]): c for c in env.get("cells", [])}


def fig_continuity(env: dict) -> str:
    cells = _cells_by(env)
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    _style(ax)
    cases = [c.id for c in CASES]
    w = 0.15
    for k, sid in enumerate(ORDER):
        vals, xs = [], []
        for i, cid in enumerate(cases):
            cell = cells.get((cid, sid))
            if cell is None or cell.get("mass_pct") is None:
                continue
            vals.append(max(abs(cell["mass_pct"]), 1e-3))
            xs.append(i + (k - 2) * w)
        ax.bar(xs, vals, width=w * 0.92, color=COLORS[sid], label=LABELS[sid],
               zorder=3)
    ax.set_yscale("log")
    ax.set_ylim(4e-4, 1e5)   # floor below the 1e-3 clamp so FV bars stay visible
    ax.set_yticks([1e-3, 1e-2, 1e-1, 1, 10, 100, 1e3, 1e4])
    ax.set_yticklabels(["≤0.001", "0.01", "0.1", "1", "10", "100",
                        "1 000", "10 000"])
    ax.axhline(0.5, color=INK, lw=1.0, ls=":")
    ax.text(2.42, 0.55, "0.5 % gate", fontsize=8, color=MUTED, ha="right")
    ax.set_xticks(range(len(cases)))
    ax.set_xticklabels(cases, fontsize=9, color=INK)
    ax.set_ylabel("|routing continuity error| (%)")
    ax.set_title("continuity error by case and solver (log scale)")
    ax.legend(fontsize=8, framealpha=0.9, ncols=2)
    return _save(fig, "continuity.png")


def fig_walltime(env: dict) -> str:
    cells = _cells_by(env)
    fig, ax = plt.subplots(figsize=(8.2, 4.0))
    _style(ax)
    cases = [c.id for c in CASES]
    w = 0.15
    for k, sid in enumerate(ORDER):
        vals, xs = [], []
        for i, cid in enumerate(cases):
            cell = cells.get((cid, sid))
            if cell is None or cell.get("wall") is None:
                continue
            vals.append(max(cell["wall"], 1e-2))
            xs.append(i + (k - 2) * w)
        ax.bar(xs, vals, width=w * 0.92, color=COLORS[sid], label=LABELS[sid],
               zorder=3)
    ax.set_yscale("log")
    ax.set_xticks(range(len(cases)))
    ax.set_xticklabels(cases, fontsize=9, color=INK)
    ax.set_ylabel("wall clock (s, log)")
    fv = cells.get(("surcharge-cycle", "fv"), {}).get("wall")
    lts = cells.get(("surcharge-cycle", "fv-lts"), {}).get("wall")
    if fv and lts:
        ax.annotate(f"LTS: {fv / lts:.1f}× faster",
                    xy=(1 + (1 - 2) * w, lts), xytext=(0.24, 0.90),
                    textcoords="axes fraction", fontsize=9, color=INK,
                    arrowprops=dict(arrowstyle="->", color=MUTED, lw=1.0))
    ax.set_title("wall clock by case and solver "
                 "(best of reps; single thread)")
    ax.legend(fontsize=8, framealpha=0.9, ncols=2)
    return _save(fig, "walltime.png")


# ── report ───────────────────────────────────────────────────────────────

def _matrix_table(env: dict) -> list[str]:
    cells = _cells_by(env)
    key_metric = {"rapid-fill": "front_speed_err",
                  "surcharge-cycle": "head_hold_err",
                  "inverted-siphon": "head_steady_err"}
    emoji = {"PASS": "✅", "FAIL": "❌", "XFAIL": "⚠️", "XPASS": "🔔",
             "ERROR": "💥", "SKIP": "—", "UNAVAILABLE": "∅"}
    L = ["| case | " + " | ".join(LABELS[s] for s in ORDER) + " |",
         "|---" * (len(ORDER) + 1) + "|"]
    for case in CASES:
        row = [case.id]
        for sid in ORDER:
            c = cells.get((case.id, sid))
            if c is None:
                row.append("∅")
                continue
            v = c.get("metrics", {}).get(key_metric[case.id])
            vs = f"{v:.3f}" if isinstance(v, (int, float)) else "—"
            row.append(f"{emoji.get(c['verdict'], c['verdict'])} {vs}")
        L.append("| " + " | ".join(row) + " |")
    return L


def _case_section(case: Case, env: dict, figs: dict) -> list[str]:
    cells = _cells_by(env)
    L = [f"## {case.id} — {case.title}", ""]
    L.append(case.notes)
    L.append("")
    L.append(f"Chain: {len(case.pipes)} pipe(s), {case.n_conduits} conduits, "
             f"L = {case.L:g} m; outfall FIXED {case.outfall_stage:g} m; "
             f"routing step {case.dt_routing:g} s; report {case.report_step:g} s.")
    L.append("")
    for f in figs.get(case.id, []):
        L.append(f"![{f}]({f})")
        L.append("")
    keys = {"rapid-fill": ["front_speed", "front_speed_err", "head_drop",
                           "head_drop_err"],
            "surcharge-cycle": ["head_hold_err", "head_hold_range",
                                "links_surcharged", "relief_ok"],
            "inverted-siphon": ["head_steady_err", "barrel_full"]}[case.id]
    L.append("| solver | verdict | " + " | ".join(keys) +
             " | continuity % | wall s |")
    L.append("|---" * (len(keys) + 4) + "|")
    for sid in ORDER:
        c = cells.get((case.id, sid))
        if c is None:
            continue
        m = c.get("metrics", {})
        vals = []
        for k in keys:
            v = m.get(k)
            vals.append(f"{v:.3f}" if isinstance(v, float) else str(v))
        wall = c.get("wall")
        L.append(f"| {LABELS[sid]} | {c['verdict']} | " + " | ".join(vals) +
                 f" | {c.get('mass_pct')} | "
                 f"{wall:.2f} |" if wall is not None else
                 f"| {LABELS[sid]} | {c['verdict']} | " + " | ".join(vals) +
                 f" | {c.get('mass_pct')} | — |")
        if c.get("reasons"):
            L.append(f"| | ↳ {'; '.join(c['reasons'])} " +
                     "| " * (len(keys) + 2))
    L.append("")
    return L


FINDINGS = """\
## Findings (first calibration sweep, 2026-08-12)

Probe artifacts under `runs/_probe/`; every number below is reproducible from
the probe decks.

1. **EXTRAN's surcharge leak grows with mesh refinement.** On
   surcharge-cycle both engines produce bit-identical heads (hold-mean error
   0.001 m) but leak **−6.09 %** of routing volume through one
   pressurize/relieve cycle at 5 m conduits — and the leak was −3.13 % at
   20 m conduits (probe4). FV closes at −0.00 % on the same decks. The
   non-conservative surcharge iteration does not converge away; it gets
   worse as you resolve the network.
2. **The static-slot method (SURCHARGE_METHOD SLOT) is unstable at a fixed
   1 s step on BOTH engines** for surcharge-cycle: refactored −37 235 %,
   legacy −208 % (mixed mesh) / −356 % (probe4). Verdict column is
   expected-fail with this documentation; do not read it as a refactored
   regression.
3. **FV pressurized friction is biased low on coarse cells of sloped
   pipes.** Uniform 20 m cells reach a steady state at roughly HALF the
   Manning friction slope (N0 head 3.07 m vs 5.18 analytic); uniform 5 m
   cells converge (5.22 m, ring ±0.6 m); a mixed 5/20 m mesh is bistable and
   rings ±2.3 m (probe3). The horizontal rapid-fill case shows NO such bias
   at 20 m cells (head drop 1.680 vs 1.647 m analytic), pointing at a
   slope–slot interaction. Suite decks therefore use 5 m conduits for the
   sloped case.
4. **FV local timestepping has a tier-depth cliff on pressurization
   transients** (probe5/probe6, surcharge-cycle, uniform 5 m):
   FV_LTS_MAX_TIERS ≤ 4 is clean (hold-mean 5.22 m, continuity −0.001 %) and
   **2.4× faster** than FV_LTS NO at equal accuracy; 5 tiers rings to 21 m;
   6 tiers (the engine default) collapses with **−687 %** continuity. The
   suite's fv-lts column pins MAX_TIERS 4; the default-6 breakage is an open
   engine defect.
5. **FV fails the steep-legged inverted siphon outright** (19 % drop /
   18 % rise legs, 15 m conduits): spurious head transients spike the barrel
   to 20–60 m. FV_CELL_LENGTH 2 reduces the steady error to ~2.6 m at 33×
   the wall clock; FV_ORDER 2 / RK2 to ~1.9–3.3 m; FV_LTS on the 2 m cells
   breaks conservation (−3.8 %). Expected-fail, under investigation. DW
   (both engines) reproduces the energy-balance HGL to 0.000 m here.
6. **NODE_CONTINUITY SEMI_IMPLICIT distorts stiff pressurized cases on the
   refactored DW path**: rapid-fill front speed drops to 1.69 m/s (analytic
   2.97, EXPLICIT gives 2.93) and the siphon leaks +10.4 % continuity
   (EXPLICIT: −0.10 %). The suite's shared options block pins
   NODE_CONTINUITY EXPLICIT (the epa_qa parity config); legacy ignores the
   key either way.
7. **Benchmark-design note:** junction MaxDepth is set so the flood ceiling
   is unreachable — with ALLOW_PONDING NO, any transient overshoot that
   reaches invert+MaxDepth silently deletes water and masquerades as a
   continuity error (this was conflating solver ringing with mass loss in
   early calibration runs).
"""


def build() -> str:
    env = scoring.load(config.SCORES_FILE)
    if env is None:
        raise SystemExit("no transitions_scores.json — run the sweep first")
    figs: dict[str, list[str]] = {c.id: [] for c in CASES}

    for case in CASES:
        runs = _load_runs(case)
        if case.id == "rapid-fill":
            for t in case.snapshot_times:
                figs[case.id].append(hgl_snapshot(
                    case, runs, t, f"{case.id}__hgl_t{int(t)}s.png"))
            figs[case.id].append(fig_front_trajectory(case, runs))
            figs[case.id].append(fig_timeseries(case, runs, node_i=0,
                                                link_i=12))
        elif case.id == "surcharge-cycle":
            h_ref = analytic.pressurized_hgl(case)
            for t in case.snapshot_times:
                figs[case.id].append(hgl_snapshot(
                    case, runs, t, f"{case.id}__hgl_t{int(t)}s.png",
                    analytic_h=h_ref if t == case.peak_time else None,
                    ymax=10.0,
                    note="y-axis clipped at 10 m — DW (SLOT) exceeds it "
                         "(see findings #2)" if t == case.peak_time else None))
            figs[case.id].append(fig_timeseries(case, runs, node_i=0,
                                                link_i=60,
                                                head_ylim=(0.0, 10.0)))
        else:
            h_ref = analytic.pressurized_hgl(case)
            figs[case.id].append(hgl_snapshot(
                case, runs, case.t_end, f"{case.id}__hgl_final.png",
                analytic_h=h_ref, ymax=13.0,
                note="y-axis clipped at 13 m — FV columns exceed it "
                     "(see findings #5)"))
            figs[case.id].append(fig_timeseries(case, runs, node_i=17,
                                                link_i=13))
    cont = fig_continuity(env)
    wall = fig_walltime(env)

    L = ["# Open-channel ↔ pressurized transition suite", ""]
    L.append(f"Engine SHA `{env.get('engine_sha', '?')}` · refactored "
             f"`{engines.REFACT_EXE}` · legacy `{engines.LEGACY_EXE}` · "
             f"single-threaded, OPENSWMM_2D_BACKEND=cpu · "
             f"swept {env.get('timestamp', '?')}")
    L.append("")
    L.append("Three purpose-built cases stress the open-channel ↔ "
             "pressurized transition: a filling bore with an analytic front "
             "speed, a surcharge/relief cycle with an analytic peak-hold "
             "HGL, and a permanently pressurized inverted siphon with an "
             "energy-balance HGL. Five solver columns run the identical "
             "generated decks (only FLOW_ROUTING and per-solver keys "
             "differ). Grading is analytic; expected-fails are documented "
             "characteristics, never hidden (see Findings).")
    L.append("")
    L.append("## Verdict matrix")
    L.append("")
    L += _matrix_table(env)
    L.append("")
    L.append("Cell = verdict + key metric (rapid-fill: relative front-speed "
             "error; surcharge-cycle: hold-mean head error, m; "
             "inverted-siphon: steady head error, m).")
    L.append("")
    L.append(f"![continuity]({cont})")
    L.append("")
    L.append(f"![walltime]({wall})")
    L.append("")
    for case in CASES:
        L += _case_section(case, env, figs)
    L.append(FINDINGS)
    config.REPORT_FILE.write_text("\n".join(L) + "\n")
    print(f"wrote {config.REPORT_FILE}")
    return str(config.REPORT_FILE)
