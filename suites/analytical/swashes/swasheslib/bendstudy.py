#!/usr/bin/env python3
"""Bend-implications analysis -> runs/_bend_study/BEND_FINDINGS.md + figures.

Quantifies what ignoring planform bends costs the 1D solvers, using the
pinned 2D bent-geometry references (cases/<id>/reference_2d.csv) and each
1D solver's steady profile (runs/<id>/<solver>/extracted.csv):

  1. d_eta upstream of the corner (window s in [s_bend-15, s_bend-3]),
     per case x solver, control-subtracted per regime.
  2. Effective bend-loss coefficient K_eff extracted from energy-head line
     fits on the straight reaches extrapolated to the corner, for the 2D
     reference AND each 1D profile; compared with literature miter
     K = 1.1*(1 - cos theta).
  3. Sidewall-friction attribution of the control bias (1D RECT_OPEN wets
     the walls; the 2D solver frictions the bed only).
  4. dx = 0.25 m reference-sensitivity rerun of bend90-swift
     (informational, cached).
"""
from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config, extract
from .cases_bends import BEND_CASES, G, _N, _W

SOLVERS_1D = ["1d-dynwave", "1d-dynwave-legacy", "1d-dynwave-vj"]
OUT = config.SUITE_ROOT / "runs" / "_bend_study"
FIG = OUT / "figures"

_CONTROL = {"gentle": "bend00-gentle", "swift": "bend00-swift"}


def _regime_of(case) -> str:
    return "gentle" if "gentle" in case.id else "swift"


def _case_by_id(cid):
    for c in BEND_CASES:
        if c.id == cid:
            return c
    raise KeyError(cid)


def _ref_profile(case):
    pin = config.CASES_DIR / case.id / "reference_2d.csv"
    p = extract.read_extracted_csv(pin)
    t = max(p)
    return p[t]["x"], p[t]["h"], p[t]["q"]


def _solver_profile(case, solver_id):
    csv = config.RUNS_DIR / case.id / solver_id / "extracted.csv"
    if not csv.exists():
        return None
    p = extract.read_extracted_csv(csv)
    t = max(p)
    return p[t]["x"], p[t]["h"], p[t]["q"]


def _energy_head(case, s, h, q):
    z = case.z(np.asarray(s))
    with np.errstate(divide="ignore", invalid="ignore"):
        vh = np.where(h > 1e-6, q / h, 0.0)
    return z + h + vh * vh / (2.0 * G)


def _k_eff(case, s, h, q) -> tuple:
    """(K_eff, dH_bend): straight-reach energy-line fits extrapolated to the
    corner; v from the profile at s_bend - 5."""
    sb = case.planform.s_bend
    H = _energy_head(case, s, h, q)
    up = (s >= 25.0) & (s <= 50.0)
    dn = (s >= 70.0) & (s <= 110.0)
    cu = np.polyfit(s[up], H[up], 1)
    cd = np.polyfit(s[dn], H[dn], 1)
    dH = float(np.polyval(cu, sb) - np.polyval(cd, sb))
    iv = int(np.argmin(np.abs(s - (sb - 5.0))))
    v = float(q[iv] / max(h[iv], 1e-9))
    return 2.0 * G * dH / (v * v), dH


def _deta(case, s1, h1, s2, h2) -> float:
    """Mean water-surface offset (profile1 - profile2) upstream of the
    corner, window s in [s_bend-15, s_bend-3]."""
    sb = case.planform.s_bend
    lo, hi = sb - 15.0, sb - 3.0
    z1 = case.z(np.asarray(s1))
    z2 = case.z(np.asarray(s2))
    m1 = (s1 >= lo) & (s1 <= hi)
    grid = s1[m1]
    e1 = (z1 + h1)[m1]
    e2 = np.interp(grid, s2, z2 + h2)
    return float(np.mean(e1 - e2))


def _sidewall_normal_depth(q: float, s0: float) -> float:
    """1D RECT_OPEN normal depth with R = Wh/(W+2h) (bisection)."""
    lo, hi = 1e-3, 5.0
    def f(h):
        v = q / h
        r = _W * h / (_W + 2.0 * h)
        return _N * _N * v * v / r ** (4.0 / 3.0) - s0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _dx025_sensitivity() -> str:
    """Informational: rerun the bend90-swift 2D reference at dx=0.25 and
    report the K_eff shift (cached under runs/bend90-swift/_2d_ref_dx025)."""
    from . import gen2d
    from .runcase2d import extract_for_case
    from .solvers import BY_ID
    from harness import engines, runner

    base = _case_by_id("bend90-swift")
    fine = dataclasses.replace(base, nx=base.nx * 2)
    d = config.RUNS_DIR / base.id / "_2d_ref_dx025"
    d.mkdir(parents=True, exist_ok=True)
    inp = d / "model.inp"
    h5 = d / "surface.h5"
    text = gen2d.build_inp(fine, BY_ID["2d-explicit"], "surface.h5")
    if not (inp.exists() and inp.read_text(encoding="utf-8") == text and h5.exists()):
        inp.write_text(text, encoding="utf-8")
        r = runner.run(engines.REFACT_EXE, inp, d / "model.rpt",
                       d / "model.out", cwd=d, timeout=7200.0)
        if not r["ok"]:
            return "dx=0.25 sensitivity run FAILED — not available"
    res = extract_for_case(fine, h5)
    p = res["mean"]
    k_f, dh_f = _k_eff(fine, p["x_h"], p["h"], p["q"])
    s0, h0, q0 = _ref_profile(base)
    k_c, dh_c = _k_eff(base, s0, h0, q0)
    return (f"dx=0.25 m reference rerun: K_eff {k_c:.3f} -> {k_f:.3f} "
            f"(dH {dh_c*1000:.1f} -> {dh_f*1000:.1f} mm) — grid sensitivity "
            f"{abs(k_f-k_c):.3f} in K units")


def build() -> str:
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)

    # ---- gather ------------------------------------------------------------
    ref = {c.id: _ref_profile(c) for c in BEND_CASES}
    prof = {(c.id, sid): _solver_profile(c, sid)
            for c in BEND_CASES for sid in SOLVERS_1D}

    # d_eta vs 2D reference, per case x solver
    deta: dict = {}
    for c in BEND_CASES:
        s_r, h_r, _ = ref[c.id]
        for sid in SOLVERS_1D:
            pr = prof[(c.id, sid)]
            if pr is None:
                continue
            deta[(c.id, sid)] = _deta(c, pr[0], pr[1], s_r, h_r)

    # K_eff per case for the reference and each solver
    keff: dict = {}
    dhb: dict = {}
    for c in BEND_CASES:
        s_r, h_r, q_r = ref[c.id]
        keff[(c.id, "2d-reference")], dhb[(c.id, "2d-reference")] = \
            _k_eff(c, s_r, h_r, q_r)
        for sid in SOLVERS_1D:
            pr = prof[(c.id, sid)]
            if pr is not None:
                keff[(c.id, sid)], dhb[(c.id, sid)] = _k_eff(c, *pr)

    # ---- figures -----------------------------------------------------------
    for c in BEND_CASES:
        s_r, h_r, _ = ref[c.id]
        z_r = c.z(np.asarray(s_r))
        fig, (ax, axe) = plt.subplots(2, 1, figsize=(9, 6), sharex=True,
                                      gridspec_kw={"height_ratios": [3, 1]})
        ax.fill_between(s_r, 0, z_r, color="0.85", label="bed z(s)")
        ax.plot(s_r, z_r + h_r, "k-", lw=1.6, label="2D reference η")
        for sid in SOLVERS_1D:
            pr = prof[(c.id, sid)]
            if pr is None:
                continue
            z_s = c.z(np.asarray(pr[0]))
            ax.plot(pr[0], z_s + pr[1], lw=0.9, label=sid)
            axe.plot(pr[0], z_s + pr[1] - np.interp(pr[0], s_r, z_r + h_r),
                     lw=0.9, label=sid)
        ax.axvline(c.planform.s_bend, color="crimson", ls=":", lw=1.0)
        axe.axvline(c.planform.s_bend, color="crimson", ls=":", lw=1.0)
        axe.axhline(0, color="k", lw=0.5)
        ax.set_ylabel("elevation (m)")
        ax.set_title(f"{c.id} — {c.title}")
        ax.legend(fontsize=8, ncol=2)
        axe.set_xlabel("centerline arc length s (m)")
        axe.set_ylabel("η − η₂D (m)")
        fig.tight_layout()
        fig.savefig(FIG / f"{c.id}__eta.png", dpi=110)
        plt.close(fig)

    # K_eff bar chart
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ids = [c.id for c in BEND_CASES]
    width = 0.2
    xpos = np.arange(len(ids))
    for k, sid in enumerate(["2d-reference"] + SOLVERS_1D):
        vals = [keff.get((cid, sid), np.nan) for cid in ids]
        ax.bar(xpos + (k - 1.5) * width, vals, width, label=sid)
    ax.axhline(1.1, color="crimson", ls="--", lw=1.0,
               label="K_miter 90° = 1.1")
    ax.axhline(0.322, color="darkorange", ls="--", lw=1.0,
               label="K_miter 45° = 0.32")
    ax.set_xticks(xpos, ids, rotation=20, fontsize=8)
    ax.set_ylabel("K_eff (corner energy jump)")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    fig.savefig(FIG / "keff_bars.png", dpi=110)
    plt.close(fig)

    # ---- sidewall attribution ---------------------------------------------
    from .cases_bends import _Q_G, _Q_S, _S0_G, _S0_S
    hsw_g = _sidewall_normal_depth(_Q_G, _S0_G)
    hsw_s = _sidewall_normal_depth(_Q_S, _S0_S)

    dx_note = _dx025_sensitivity()

    # ---- document ----------------------------------------------------------
    L: list[str] = []
    L.append("# Bend-implications study — planform-blind 1D momentum vs "
             "true bent geometry")
    L.append("")
    L.append("The 1D solvers never see `[COORDINATES]`: junction chains "
             "transmit no momentum across nodes and carry no bend loss "
             "unless the user adds a `[LOSSES]` K; virtual-junction chains "
             "transmit FULL scalar momentum through any planform dogleg. "
             "This study measures what that costs against the engine's own "
             "2D solver on the true L-shaped geometry (mitered-shear mesh, "
             "CFL 0.3, taper_mult=2 — see stillwater probes here). The 2D "
             "local-inertial reference neglects convective inertia, so its "
             "bend losses are LOWER BOUNDS on the physical ones.")
    L.append("")
    L.append("## 1. Water-surface offset upstream of the corner "
             "(Δη = η₁D − η₂D, window s ∈ [45, 57] m)")
    L.append("")
    L.append("| case | θ | regime | " + " | ".join(SOLVERS_1D) +
             " | control-subtracted (1d-dynwave) |")
    L.append("|---|---|---|" + "---|" * (len(SOLVERS_1D) + 1))
    for c in BEND_CASES:
        reg = _regime_of(c)
        ctrl = deta.get((_CONTROL[reg], "1d-dynwave"), 0.0)
        row = [f"{1000*deta.get((c.id, sid), np.nan):+.1f} mm"
               for sid in SOLVERS_1D]
        sub = deta.get((c.id, "1d-dynwave"), np.nan) - ctrl
        mark = "—" if c.id in _CONTROL.values() else f"{1000*sub:+.1f} mm"
        L.append(f"| {c.id} | {c.planform.theta_deg:g}° | {reg} | "
                 + " | ".join(row) + f" | {mark} |")
    L.append("")
    L.append("## 2. Effective bend-loss coefficient at the corner")
    L.append("")
    L.append("Raw energy-line K_eff (line fits extrapolated to the corner) "
             "is contaminated by backwater-profile curvature in the gentle "
             "regime (controls read −0.37 with zero actual corner loss), so "
             "the table reports CONTROL-SUBTRACTED K_eff, plus the "
             "Δη-derived estimate K_Δη = 2g·Δη_sub/v² for the 2D reference "
             "(velocity heads match across the corner at the same regime, "
             "so the control-subtracted surface offset IS the energy jump).")
    L.append("")
    L.append("| case | 2D ref K_eff (ctrl-sub) | 2D ref K_Δη | " +
             " | ".join(f"{s} (ctrl-sub)" for s in SOLVERS_1D) +
             " | literature K_miter |")
    L.append("|---|---|---|" + "---|" * (len(SOLVERS_1D) + 1))
    kdeta: dict = {}
    for c in BEND_CASES:
        th = c.planform.theta_deg
        reg = _regime_of(c)
        ctrl_id = _CONTROL[reg]
        km = 1.1 * (1.0 - np.cos(np.radians(th))) if th > 0 else 0.0
        v = _Q_G / 1.0 if reg == "gentle" else _Q_S / 0.4
        dsub = (deta.get((c.id, "1d-dynwave"), np.nan)
                - deta.get((ctrl_id, "1d-dynwave"), 0.0))
        # the 1D minus 2D offset, control-subtracted, is the loss the 2D
        # reference exhibits but the (loss-free) 1D model does not
        kdeta[c.id] = 2.0 * G * dsub / (v * v)
        cells = []
        for sid in ["2d-reference"] + SOLVERS_1D:
            kk = (keff.get((c.id, sid), np.nan)
                  - keff.get((ctrl_id, sid), 0.0))
            cells.append(f"{kk:+.3f}")
        cells.insert(1, f"{kdeta[c.id]:+.3f}"
                     if c.id not in _CONTROL.values() else "—")
        L.append(f"| {c.id} | " + " | ".join(cells) + f" | {km:.2f} |")
    L.append("")
    L.append("(The `-k` case's 1d columns read ≈ +0.87: the `[LOSSES]` "
             "Kentry mechanism measurably applies the requested loss — the "
             "shortfall vs 1.1 is the definitional difference between the "
             "entry-velocity head the engine uses and the s−5 m profile "
             "velocity used here.)")
    L.append("")
    L.append("![K_eff](figures/keff_bars.png)")
    L.append("")
    L.append("## 3. Findings")
    L.append("")
    # control-subtracted values for prose
    d90s = 1000 * (deta.get(("bend90-swift", "1d-dynwave"), np.nan)
                   - deta.get(("bend00-swift", "1d-dynwave"), 0.0))
    d90g = 1000 * (deta.get(("bend90-gentle", "1d-dynwave"), np.nan)
                   - deta.get(("bend00-gentle", "1d-dynwave"), 0.0))
    d45s = 1000 * (deta.get(("bend45-swift", "1d-dynwave"), np.nan)
                   - deta.get(("bend00-swift", "1d-dynwave"), 0.0))
    k2d90 = keff.get(("bend90-swift", "2d-reference"), np.nan)
    k2d45 = keff.get(("bend45-swift", "2d-reference"), np.nan)
    sf_leg_s = 1000 * _S0_S * 60.0
    L.append(f"1. **The dominant 1D-vs-2D discrepancy is NOT the bend — it "
             f"is sidewall friction.** The θ=0 controls measure l1 15.7% "
             f"(gentle) / 8.1% (swift). Predicted 1D normal depths with "
             f"R = Wh/(W+2h): gentle {hsw_g:.3f} m vs the 2D's 1.000 m "
             f"(+{100*(hsw_g-1.0):.0f}%), swift {hsw_s:.3f} m vs 0.400 m "
             f"(+{100*(hsw_s-0.4)/0.4:.0f}%) — matching the measured "
             f"control bias almost exactly. Any bend treatment matters "
             f"less than choosing the right conveyance model for wide "
             f"shallow channels.")
    L.append(f"2. **Bend-specific backwater is small at these regimes "
             f"(against the local-inertial reference):** control-subtracted "
             f"Δη upstream of the corner is {d90g:+.1f} mm (90° gentle), "
             f"{d90s:+.1f} mm (90° swift), {d45s:+.1f} mm (45° swift). The "
             f"corner effect is localized: linf on bend90-swift rises to "
             f"13.3% vs 8.5% for its control (+4.8% at the corner).")
    k90 = kdeta.get("bend90-swift", np.nan)
    k90g = kdeta.get("bend90-gentle", np.nan)
    k45 = kdeta.get("bend45-swift", np.nan)
    L.append(f"3. **The 2D reference exhibits only K_Δη ≈ {k90:.2f} "
             f"(90° swift) / {k90g:.2f} (90° gentle) / {k45:.2f} (45°) — "
             f"roughly a tenth of the literature miter K (1.1 / 0.32).** "
             f"Expected: a local-inertial scheme cannot produce the "
             f"separation/recirculation that generates most miter-bend "
             f"loss. These are lower bounds; physical losses lie between "
             f"K_Δη and K_miter.")
    L.append("4. **All three 1D discretizations are indistinguishable at "
             "steady state** (l1 differs in the 4th digit): head-only "
             "junction chains, legacy, and full-momentum VJ chains give the "
             "same bent-channel answer — at steady subcritical flow the "
             "planform-blindness implication is purely the MISSING LOSS, "
             "not the momentum-transmission model. (Transient/supercritical "
             "regimes may differ; not covered by Phase A.)")
    L.append("5. **Blindly adding the literature miter K overshoots this "
             "reference**: bend90-swift-k grades l1 14.7% vs 8.8% without "
             "K — because the local-inertial reference contains almost none "
             "of that loss. Against REAL bends the literature K remains the "
             "engineering-correct mitigation; validating it needs a "
             "convective-inertia-resolving reference (full-SWE solver or "
             "flume data).")
    L.append(f"6. **Scaling guidance**: the missing physical head loss is "
             f"ΔH = K·v²/2g ≈ 141 mm (90°, swift, K=1.1) against a "
             f"friction head of {sf_leg_s:.0f} mm per 60 m leg — bends "
             f"dominate when K·v²/2g ≳ S_f·L_reach, i.e. short steep "
             f"high-Fr systems (storm drains with elbows), and vanish in "
             f"mild long networks (gentle: 50 mm vs 33 mm — comparable "
             f"even there).")
    L.append("")
    L.append("## 4. Caveats")
    L.append("")
    L.append("- The 2D reference is a local-inertial marcher (no convective "
             "inertia): bend recirculation is under-resolved and K_eff is a "
             "lower bound. CFL pinned 0.3; mitered-shear mesh needs "
             "taper_mult=2 (see `stillwater_*` probes: default taper corner "
             "cells destabilize, growing 1e-8 → 5e-2 in 10 min; taper 2 is "
             "machine-flat).")
    L.append("- The .rpt Virtual Junction momentum-residual column assumes "
             "collinear conduits — at planform doglegs it misreads "
             "direction change as conservation error; do not quote it for "
             "bent chains.")
    L.append(f"- {dx_note}")
    L.append("- Steady subcritical only; dam-break-through-a-bend and "
             "supercritical bend hydraulics (standing waves at the miter) "
             "are Phase-B candidates.")
    L.append("")
    L.append("Per-case η(s) overlays: `figures/<case>__eta.png`; mesh "
             "renders: `figures/bend90-swift__mesh.png`, "
             "`figures/bend45-swift__mesh.png`.")
    L.append("")
    path = OUT / "BEND_FINDINGS.md"
    path.write_text("\n".join(L), encoding="utf-8")
    return str(path)
