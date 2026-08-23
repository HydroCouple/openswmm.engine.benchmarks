#!/usr/bin/env python3
"""SWASHES_REPORT.md + figures from swashes_scores.json.

Structure (plan Part 4): header -> comparison-matrix table -> per-case
sections (citation, config, metric tables, figures) -> appendix (legend,
policies, engine limitations). Figure links are relative so the document
survives the repo lift unchanged.
"""
from __future__ import annotations

import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config, extract, metrics
from .genrefs import MissingReferenceError, all_cases, reference_blocks
from .solvers import SOLVERS

from harness import engines, scoring

_VERDICT_MARK = {
    "PASS": "✅ PASS", "FAIL": "❌ FAIL",
    "BASELINE-PASS": "🟦 BASE-PASS", "BASELINE-FAIL": "🟥 BASE-FAIL",
    "XFAIL": "⚪ XFAIL", "XPASS": "🎉 XPASS", "ERROR": "💥 ERROR",
    "SKIP": "—", "UNAVAILABLE": "· n/a ·",
}

# Fixed per-solver style: colour follows the SOLVER, never its position in the
# plotted set. Cases skip different columns, so a rank-ordered colour cycle
# repaints the survivors and the same solver reads as a different series from
# one case figure to the next. Cool hues = 1D family, warm = the 2D pair, and
# the 2D pair also carries distinct markers so the local-acceleration vs
# advection comparison survives greyscale and colour-vision deficiency.
# Hues match suites/transitions (fv blue, dw aqua, legacy magenta).
# Okabe-Ito, chosen for colour-vision deficiency. The reference profile is
# black, so no series takes it.
#
# EVERY series is separated on three channels — hue, marker shape AND dash
# pattern — not just the 2D pair. With six curves overlapping on a metre-scale
# mesh, hue alone does not separate them (the previous palette put a #2a78d6
# blue next to a #4a3aa7 indigo, and `1d-dynwave-semi` had no entry at all, so
# it fell through to an arbitrary auto-colour that could collide with any of
# them).
_STYLE = {
    "1d-dynwave":        ("#0072B2", "o", "-"),
    "1d-dynwave-legacy": ("#E69F00", "s", (0, (5, 1.5))),
    "1d-dynwave-semi":   ("#009E73", "^", (0, (1, 1.2))),
    "1d-dynwave-vj":     ("#CC79A7", "v", (0, (6, 1.5, 1, 1.5))),
    "1d-fv":             ("#D55E00", "D", (0, (3, 1, 1, 1))),
    "2d-explicit":       ("#56B4E9", "P", (0, (4, 1.5, 1, 1.5, 1, 1.5))),
    # Retired columns keep their styling so re-registering one restores the
    # figure it used to draw, unchanged.
    "1d-kinwave":        ("#F0E442", "X", (0, (2, 2))),
    "2d-explicit-adv":   ("#999999", "*", (0, (5, 2))),
}
_LABEL = {
    "2d-explicit": "2d-explicit (local accel.)",
    "2d-explicit-adv": "2d-explicit-adv (+advection)",
}


def _cells_by_key(envelope: dict) -> dict:
    return {(c["case"], c["solver"]): c for c in envelope["cells"]}


def _fmt_cell(cell: dict | None) -> str:
    if cell is None:
        return " "
    mark = _VERDICT_MARK.get(cell.get("verdict"), cell.get("verdict", "?"))
    l1 = (cell.get("metrics") or {}).get("l1_h")
    return f"{mark} ({l1:.3g})" if isinstance(l1, (int, float)) else mark


def _case_figure(case, cells: dict) -> str | None:
    """Free-surface overlay: reference + each solver's profile."""
    try:
        blocks = reference_blocks(case)
    except MissingReferenceError:
        return None                       # bend case pre-pin: no figure yet
    t_plot = max(blocks)
    xr, hr, _ = blocks[t_plot]
    try:
        zr = case.z(xr)
    except Exception:
        zr = np.zeros_like(xr)
    ref_label = ("2D-reference η" if getattr(case, "ref_source", "") == "2d"
                 else f"analytic η (t={t_plot:g}s)")
    fig, (ax, axe) = plt.subplots(
        2, 1, figsize=(9, 6), sharex=True,
        gridspec_kw={"height_ratios": [3, 1]})
    ax.fill_between(xr, 0, zr, color="0.8", label="bed z(x)")
    ax.plot(xr, zr + hr, "k-", lw=1.5, label=ref_label)
    if case.planform is not None and case.planform.theta_deg > 0:
        ax.axvline(case.planform.s_bend, color="crimson", ls=":", lw=1.0)
        axe.axvline(case.planform.s_bend, color="crimson", ls=":", lw=1.0)
    any_model = False
    _eta_series: list = []      # plotted water surfaces, for robust y-limits
    _err_series: list = []
    plotted = 0                 # index among drawn series, for marker stagger
    for solver in SOLVERS:
        cell = cells.get((case.id, solver.id))
        if not cell or cell.get("verdict") in ("SKIP", "UNAVAILABLE", "ERROR"):
            continue
        csv = config.RUNS_DIR / case.id / solver.id / "extracted.csv"
        if not csv.exists():
            continue
        prof = extract.read_extracted_csv(csv)
        tt = min(prof, key=lambda k: abs(k - t_plot))
        x, h = prof[tt]["x"], prof[tt]["h"]
        z = case.z(np.asarray(x))
        colour, marker, dash = _STYLE.get(solver.id, (None, ".", "-"))
        ms = 4 if marker != "." else 3
        label = _LABEL.get(solver.id, solver.id)
        # The LINE uses every mesh point — `x` is one sample per conduit, so a
        # 1 m deck draws all 1000/5000 of them. Only the MARKERS are decimated,
        # and purely for legibility: undecimated they would be a solid band.
        # Stagger each series' marker phase across the interval so overlapping
        # curves interleave their markers instead of stacking on the same x.
        step = max(1, len(x) // 45)
        offset = (plotted * max(1, step // 6)) % step
        mev = (offset, step)
        ax.plot(x, z + h, color=colour, marker=marker, ms=ms, lw=0.9,
                ls=dash, markevery=mev, label=label)
        h_ref_i = np.interp(x, xr, hr)
        axe.plot(x, h - h_ref_i, color=colour, marker=marker, ms=ms, lw=0.9,
                 ls=dash, markevery=mev, label=label)
        plotted += 1
        _eta_series.append(np.asarray(z) + np.asarray(h))
        _err_series.append(np.asarray(h) - h_ref_i)
        any_model = True
    if not any_model:
        plt.close(fig)
        return None
    # Scale to the physics, not to the worst divergence. A blown-up column
    # (e.g. a DW chain that goes unstable on a shock) can exceed the analytic
    # solution by two orders of magnitude; autoscaling to it flattens every
    # other series into one indistinguishable line and the figure stops
    # showing anything. Allow legitimate over/undershoot up to 3x the
    # reference span, then clip and say so.
    eta_ref = zr + hr
    ref_lo, ref_hi = float(np.min(zr)), float(np.max(eta_ref))
    span = max(ref_hi - ref_lo, 1e-9)
    lo_cap, hi_cap = ref_lo - 3.0 * span, ref_hi + 3.0 * span
    lo = min([ref_lo] + [max(float(np.min(s)), lo_cap) for s in _eta_series])
    hi = max([ref_hi] + [min(float(np.max(s)), hi_cap) for s in _eta_series])
    pad = 0.08 * max(hi - lo, 1e-9)
    ax.set_ylim(lo - pad, hi + pad)
    n_clipped = sum(1 for s in _eta_series
                    if float(np.max(s)) > hi + pad or float(np.min(s)) < lo - pad)
    if n_clipped:
        ax.text(0.995, 0.03, f"{n_clipped} diverged series off-scale",
                transform=ax.transAxes, ha="right", fontsize=7,
                style="italic", color="0.35")
    if _err_series:
        emax = max(float(np.max(np.abs(e))) for e in _err_series)
        ecap = min(emax, 3.0 * span)
        axe.set_ylim(-1.15 * ecap, 1.15 * ecap)
    ax.set_ylabel("elevation (m)")
    ax.set_title(f"{case.id} — {case.title} ({case.swashes_ref})")
    ax.legend(fontsize=8, ncol=2)
    axe.axhline(0, color="k", lw=0.5)
    axe.set_xlabel("x (m)")
    axe.set_ylabel("h − ĥ (m)")
    fig.tight_layout()
    name = f"{case.id}__profile.png"
    fig.savefig(config.FIGURES_DIR / name, dpi=110)
    plt.close(fig)
    return name


def build() -> str:
    envelope = scoring.load(config.SCORES_FILE)
    if envelope is None:
        return "no scores yet — run `run_swashes.py run` first"
    return _build(envelope)


def _convergence_section(cells: dict) -> list:
    """Grid convergence, from the `--nx-sweep` refinement rows.

    Single-resolution error says which solver is closer on one mesh; it does
    not say whether a scheme is CONVERGING, or how fast. The refinement rows
    (`<case>@nx<N>`) were already being written to the scores file and never
    reported — this reads them back, tabulates relative L1 depth error against
    dx, and fits the observed order between consecutive levels.

    The order is the discriminating number here. A first-order Godunov scheme
    should show ~1 on smooth cases and fall toward ~0.5 across a shock; a
    scheme that is not converging shows ~0 (or negative), which no amount of
    single-mesh accuracy makes up for.
    """
    rows_by = {}
    for (case_id, solver_id), cell in cells.items():
        if "@nx" not in case_id:
            continue
        base, _, nxs = case_id.partition("@nx")
        try:
            nx = int(nxs)
        except ValueError:
            continue
        l1 = (cell.get("metrics") or {}).get("l1_h")
        if not isinstance(l1, (int, float)):
            continue
        rows_by.setdefault(base, {}).setdefault(solver_id, []).append((nx, l1))

    if not rows_by:
        return []

    # The gating run is a level too — it just is not tagged with @nx.
    for case in all_cases():
        if case.id not in rows_by:
            continue
        for solver_id, seq in rows_by[case.id].items():
            cell = cells.get((case.id, solver_id))
            l1 = (cell or {}).get("metrics", {}).get("l1_h")
            if isinstance(l1, (int, float)):
                seq.append((case.nx, l1))

    doc = ["## Grid convergence", "",
           "Relative L1 depth error against the analytic solution at each "
           "refinement level, and the observed order fitted between "
           "consecutive levels. `dx` is the 1D conduit length; a solver "
           "column that subdivides each conduit resolves finer than `dx` "
           "says.", ""]
    for case in all_cases():
        seq_by = rows_by.get(case.id)
        if not seq_by:
            continue
        doc.append(f"**{case.id}**")
        doc.append("")
        doc.append("| solver | " + " | ".join(
            f"nx={nx}" for nx, _ in sorted(next(iter(seq_by.values())))) +
            " | observed order |")
        doc.append("|" + "---|" * (len(next(iter(seq_by.values()))) + 2))
        for solver in SOLVERS:
            seq = seq_by.get(solver.id)
            if not seq:
                continue
            seq = sorted(set(seq))
            errs = " | ".join(f"{e:.4g}" for _, e in seq)
            orders = []
            for (nc, ec), (nf, ef) in zip(seq, seq[1:]):
                orders.append(metrics.observed_order(case.L / nc, ec,
                                                     case.L / nf, ef))
            otxt = ", ".join(f"{o:.2f}" for o in orders) if orders else "–"
            doc.append(f"| {solver.id} | {errs} | {otxt} |")
        doc.append("")
    return doc


def _build(envelope):
    config.FIGURES_DIR.mkdir(exist_ok=True)
    cells = _cells_by_key(envelope)
    solver_ids = [s.id for s in SOLVERS]

    doc: list[str] = []
    doc.append("# SWASHES Analytical Benchmark Report")
    doc.append("")
    doc.append(f"- generated: {datetime.datetime.now().isoformat(timespec='seconds')}")
    doc.append(f"- engine: `{engines.ENGINE}` @ `{envelope.get('engine_sha', '?')}`")
    doc.append(f"- exes: `{engines.REFACT_EXE.name}` / `{engines.LEGACY_EXE.name}` "
               f"(build `{engines.BUILD_DIR.name}`)")
    doc.append("- determinism: OMP_NUM_THREADS=1, OPENSWMM_2D_BACKEND=cpu")
    doc.append("")
    doc.append("Reference: Delestre et al. (2013), doi 10.1002/fld.3741 — "
               "independent Python implementations (`swasheslib/analytic.py`); "
               "per-case provenance in `cases/<id>/provenance.yaml`.")
    doc.append("")

    doc.append("## Comparison matrix")
    doc.append("")
    doc.append("| case | " + " | ".join(solver_ids) + " |")
    doc.append("|" + "---|" * (len(solver_ids) + 1))
    fam = None
    for case in all_cases():
        if case.family != fam:
            fam = case.family
            doc.append(f"| **{fam}** |" + " |" * len(solver_ids))
        row = [_fmt_cell(cells.get((case.id, s))) for s in solver_ids]
        doc.append(f"| {case.id} | " + " | ".join(row) + " |")
    doc.append("")
    doc.append("Cell = verdict (relative L1 depth error). "
               "Steady cases are graded on the time-mean profile over the "
               "final 50% of the run (residual seiche precedent).")
    doc.append("")

    for case in all_cases():
        doc.append(f"## {case.id} — {case.title}")
        doc.append("")
        doc.append(f"*{case.swashes_ref}* · family `{case.family}` · "
                   f"L={case.L:g} m, W1d={case.W1d:g} m, W2d={case.W2d:g} m, "
                   f"n={case.n_manning:g}, nx={case.nx} (dx={case.dx:g} m), "
                   f"dt={case.dt_routing:g} s, t_end={case.t_end:g} s")
        doc.append("")
        fig = _case_figure(case, cells)
        if fig:
            doc.append(f"![{case.id} profile](figures/{fig})")
            doc.append("")
        doc.append("| solver | mode | verdict | l1_h | linf_h | mass % | "
                   "steady resid | notes |")
        doc.append("|---|---|---|---|---|---|---|---|")
        for s in solver_ids:
            cell = cells.get((case.id, s))
            if cell is None:
                continue
            m = cell.get("metrics") or {}

            def g(key, c=cell, mm=m):
                v = mm.get(key, c.get(key))
                return f"{v:.4g}" if isinstance(v, (int, float)) else "–"
            note = cell.get("note", "") or "; ".join(cell.get("reasons", []))
            doc.append(f"| {s} | {cell.get('mode') or '–'} | "
                       f"{_VERDICT_MARK.get(cell.get('verdict'), '?')} | "
                       f"{g('l1_h')} | {g('linf_h')} | "
                       f"{g('mass_pct')} | {g('steady_resid')} | {note} |")
        doc.append("")

    conv = _convergence_section(cells)
    if conv:
        doc.extend(conv)

    doc.append("## Appendix")
    doc.append("")
    doc.append("**Verdicts**: PASS/FAIL = analytic tolerances; "
               "BASE-PASS/FAIL = vs pinned baseline "
               "(`cases/<id>/baselines/`); XFAIL = documented impossibility; "
               "XPASS = expected-fail passed analytic tolerances — promote; "
               "ERROR = run/extraction failure; n/a = solver unavailable.")
    doc.append("")
    doc.append("**Known engine limitations / findings recorded by this "
               "suite**: (1) RESOLVED 2026-08-03 — the apparent refactored-DW "
               "\"short-conduit\" instability was a fixed-step defect: the "
               "MINIMUM_STEP floor (0.5 s) was applied to fixed ROUTING_STEPs "
               "below 0.5 s, so decks silently marched at 0.5 s. With the "
               "TimestepController fix the refactored engine is bit-identical "
               "to legacy at every routing step on all Phase-A 1D decks "
               "(post-mortem in `runs/lake-at-rest-immersed/_debug/REPRO.md`). "
               "(2) RESOLVED 2026-08-04 — the \"CFL 0.7 unstable on "
               "union-jack meshes\" finding was a length-scale accounting "
               "error, not a scheme limit: cell_lchar (2A/ξ_max, the "
               "altitude) overstated the operator's stable dt by √3 on this "
               "triangulation (von Neumann: λ_checkerboard = "
               "2·(g·h/A)·Σ ξ_f/dn_f ⇒ critical nominal CFL 0.577; measured "
               "0.5 flat / 0.6 seiche). Two engine fixes landed: a "
               "tighten-only dt0 refresh between LTS rebuilds (dt was frozen "
               "up to 32 substeps), and L_char = √(2A/Σ ξ/dn) derived from "
               "the discrete operator — CFL_NUMBER is now a TRUE Courant "
               "fraction (raster recovers the classic 1/√2; the lake is "
               "machine-flat at nominal 0.7, stable through 0.95). The suite "
               "pins CFL 0.5 for ACCURACY (reproduces the truncation error "
               "its tolerances/baselines were calibrated at; "
               "macdonald-long-sub 2.0% vs 3.1% at 0.7); the engine default "
               "0.7 is a genuine 30% stability margin. Sweep record: "
               "`runs/lake-at-rest-immersed/_debug_cfl07/"
               "FINDINGS_CFL_2026-08-03.md`. (3) Implicit Preissmann DW "
               "cannot resolve dry-bed "
               "rarefactions (Ritter; engine corpus precedent), cannot hold "
               "a transcritical choke or steady shock position, and needs "
               "PARTIAL inertial damping + dx >= 1 m on frictionless "
               "flumes. (4) 2D subcritical steady error RESOLVED 2026-08-03: "
               "the dominant 4.4% bump-subcritical error was a stage-BC "
               "offset (collapsed-Manning diffusive-wave conductance "
               "saturating the equilibrium clamp into a Dirichlet cell, plus "
               "a momentum-less SPECIFIED_FLOW inflow invisible to the Perot "
               "reconstruction) — both boundaries now integrate the interior "
               "inertial momentum law with a prognostic bc_q, and "
               "bump-subcritical passes the 3% analytic gate (l1 0.7%). The "
               "wet/dry hysteresis band now scales with H_MOVE "
               "(min(1 mm, H_MOVE/2)), un-freezing shallow shorelines "
               "(Thacker wet count oscillates instead of ratcheting), and "
               "[2D_INITIAL_VELOCITY] seeds face momentum so v(t=0) ≠ 0 "
               "solutions are representable (thacker-planar-2d de-XFAILed). "
               "What remains is the scheme's missing convective-inertia "
               "term: Bernoulli-dip residual ~0.7%, dam breaks / jumps / "
               "oscillation phase drift are baseline-mode, and "
               "macdonald-long-sup (fully supercritical) never steadies — "
               "formal XFAIL pending a full-SWE momentum solver. (5) Legacy "
               "requires an "
               "outlet node (ERROR 145) — closed basins carry a "
               "never-engaged sacrificial spillway. (6) Virtual-junction "
               "chains (`1d-dynwave-vj`, RESOLVED 2026-08-03): the shipped "
               "VJ coupling had three implementation errors (lossy one-slot "
               "chain mapping that left upwinding inert and applied the "
               "convective correction one-sided; no flow-direction handling; "
               "a destabilizing blanket σ_j override) — fixed in "
               "DynamicWave.cpp. The fixed BASIC chain (zero storage + "
               "direction-aware upwinding) matches the junction chain across "
               "all Phase-A regimes and stays stable at fine dx under small "
               "fairness-scaled dt where junction chains seiche (dx=0.2 m/"
               "dt=0.01 s: VJ l1 0.24% vs junctions 21%). FULL's dq4j flux "
               "term double-counts v²·∂A/∂x in EXTRAN's non-conservative "
               "form and remains opt-in/experimental. At the case dt=0.05 s "
               "BOTH chains refine cleanly (nx=125: l1 6.8e-4) — the "
               "frictionless-flume 'seiche' is a low-numerical-dissipation "
               "(small dt) phenomenon, not a dx cap. Full probe matrix: "
               "`runs/_resolution_probe/VJ_FINDINGS.md`. "
               "(7) Planform-blindness implications (bend family, "
               "2026-08-04): the 1D solvers never see `[COORDINATES]` — "
               "junction chains transmit no momentum across nodes and carry "
               "no bend loss unless the user adds `[LOSSES]` K; VJ chains "
               "transmit full scalar momentum through any dogleg. Measured "
               "against the 2D solver on true L-shaped geometry: the "
               "dominant 1D-vs-2D bias is SIDEWALL FRICTION (θ=0 controls: "
               "l1 15.7%/8.1%, matching the RECT_OPEN R = Wh/(W+2h) normal "
               "depths exactly); bend-specific backwater is small "
               "(+17.6 mm / K_Δη ≈ 0.14 at 90°, Fr 0.8) because the "
               "local-inertial reference produces ~a tenth of the "
               "literature miter loss (lower bound); all three 1D "
               "discretizations are indistinguishable at steady state — "
               "the implication is the missing loss, not the "
               "momentum-transmission model; blindly adding literature "
               "K = 1.1 overshoots this reference. Full analysis: "
               "`runs/_bend_study/BEND_FINDINGS.md`. "
               "(8) The 2D axis is exactly two columns as of 2026-08-12: the "
               "local-acceleration marcher as shipped and the same marcher "
               "with `[2D_OPTIONS] ADVECTION YES`. The THETA sweep "
               "(`2d-explicit-th07/-th05`) was retired — θ is the q-centred "
               "de Almeida damping, the only dissipation the scheme has at "
               "n → 0, so it moves sawtooth amplitude on frictionless "
               "plateaus and cannot reach the plateau LEVEL or the shock "
               "position; those follow from the missing convective flux, "
               "which is what the advection column actually tests. "
               "(9) Advection quantifies the bend study's own blind spot "
               "(2026-08-12): running the ADVECTION column on the identical "
               "bent mesh that produced each pinned reference isolates the "
               "convective contribution exactly. It is precisely zero on the "
               "straight gentle control (the Stelling–Duinmeijer term "
               "vanishes in uniform flow — a free correctness check), and "
               "grows monotonically with turn angle: l1_h / linf_h = "
               "0.00024/0.00067 (straight, swift), 0.00068/0.00860 (45°), "
               "0.00560/0.01310 (90° gentle), 0.00506/0.03793 (90° swift). "
               "So the local-inertial reference under-reads bend loss by "
               "~0.5% of depth in the mean and up to ~3.8% locally at the "
               "miter — that bounds the 'lower bound' caveat finding (7) "
               "carries. `bend90-swift-k` is bit-identical to `bend90-swift` "
               "in this column, as it must be (bend_k is a 1D `[LOSSES]` "
               "row the 2D deck never sees).")
    doc.append("")
    config.REPORT_FILE.write_text("\n".join(doc) + "\n", encoding="utf-8")
    return str(config.REPORT_FILE)
