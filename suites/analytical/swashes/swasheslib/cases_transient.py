#!/usr/bin/env python3
"""Transient Phase-A cases (plan Part 3 tables).

compare_times are integer seconds so SWMM reporting periods (>= 1 s
resolution) line up exactly with the vendored reference blocks.
Dam-break baseline rationale: the implicit Preissmann DW scheme cannot
resolve the Ritter rarefaction (engine corpus precedent,
dw-ritter-drybed-strip); analytic tolerances stay recorded so the future FV
solver can flip those cells to PASS (or surface as XPASS on DW).
"""
from __future__ import annotations

import numpy as np

from . import analytic as an
from .casespec import BC, CaseSpec, CellPolicy, mirror_dw_variants
from .cases_steady import BASE_TOL

_DAM_TOL = {"l1_h": 0.05, "front_err_dx": 3.0}


def _stoker_h0(x):
    h, _ = an.stoker(x, 0.0)
    return h


def _ritter_h0(x):
    h, _ = an.ritter(x, 0.0)
    return h


def _thacker_h0(x):
    h, _ = an.thacker_planar_1d(x, 0.0)
    return h


TRANSIENT_CASES = [
    CaseSpec(
        id="stoker-wet-dam-break", swashes_ref="SWASHES 4.1.1",
        family="dam-breaks", title="Stoker dam break on a wet domain",
        dims=(1, 2), L=10.0, W1d=1.0, W2d=1.0,
        z=lambda x: np.zeros_like(x), n_manning=0.0,
        upstream=BC("wall"), downstream=BC("wall"),
        h0=_stoker_h0, steady=False,
        t_end=6.0, dt_routing=0.01, report_step=1.0,
        compare_times=(2.0, 4.0, 6.0), probes=(4.0, 6.0, 8.0),
        nx=200, refine_nx=(100, 400),
        opts_2d={"DRY_DEPTH": "0.0001", "H_MOVE": "0.0001"},
        cells={
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.05},
                note="DW MEETS analytic tolerance on the wet dam break "
                     "(l1 4.8%, mass 0.0%) — bit-identical to legacy since "
                     "the MINIMUM_STEP floor fix; wet bed: no front metric"),
            "1d-dynwave-legacy": CellPolicy(
                "analytic", {"l1_h": 0.05},
                note="legacy DW MEETS analytic tolerance on the wet dam "
                     "break (l1 4.8%, mass 0.0%)"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.05}),
            "2d-explicit": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="local-inertial; DRY_DEPTH/H_MOVE lowered to 1e-4 "
                     "(depth scale is mm). TWO separate errors on the star "
                     "region (exact 0.00254 flat, x 4.8-6.2): a +-4.5% "
                     "sawtooth, which is what the de Almeida q-centred damping "
                     "leaves at n=0 (THETA defaults to 0.8 and IS active - at "
                     "zero friction the friction denominator is identically "
                     "1.0 and adds no dissipation); and a plateau 31% high "
                     "(0.00333) with the shock at x~5.8 vs 6.25, which is the "
                     "MISSING CONVECTIVE MOMENTUM FLUX giving wrong Rankine-"
                     "Hugoniot conditions. Lowering THETA addresses only the "
                     "first"),
            "2d-explicit-adv": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="the convective flux the 2d-explicit note names as the "
                     "cause of the star-plateau error, switched on: l1 "
                     "6.15% -> 4.83%, i.e. restoring the Rankine-Hugoniot "
                     "physics recovers about a fifth of the error while the "
                     "q-centred sawtooth (a damping artefact at n=0) is "
                     "untouched. Still baseline-graded: first-order upwinding "
                     "of the new term leaves its own diffusion at this "
                     "resolution"),
        }),
    CaseSpec(
        id="ritter-dry-dam-break", swashes_ref="SWASHES 4.1.2",
        family="dam-breaks", title="Ritter dam break on a dry domain",
        dims=(1, 2), L=10.0, W1d=1.0, W2d=1.0,
        z=lambda x: np.zeros_like(x), n_manning=0.0,
        upstream=BC("wall"), downstream=BC("wall"),
        h0=_ritter_h0, steady=False,
        t_end=6.0, dt_routing=0.01, report_step=1.0,
        compare_times=(2.0, 4.0, 6.0), probes=(4.0, 6.0, 8.0),
        nx=200, refine_nx=(100, 400),
        opts_2d={"DRY_DEPTH": "0.0001", "H_MOVE": "0.0001"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="corpus precedent: implicit DW cannot resolve the "
                     "dry-bed rarefaction (dw-ritter-drybed-strip); front "
                     "lags analytic (~27 dx), mass clean — bit-identical to "
                     "legacy since the MINIMUM_STEP floor fix"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="front lags analytic by ~27 dx (corpus precedent); "
                     "mass clean"),
            "1d-fv": CellPolicy("analytic", _DAM_TOL),
            "2d-explicit": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="wet/dry front under local inertia; same two-part error "
                     "as stoker (undamped sawtooth at n=0 plus a missing "
                     "convective flux), and the front lags because the scheme "
                     "carries no advection to drive it"),
            "2d-explicit-adv": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="wet/dry front under local inertia; same two-part error "
                     "as stoker (undamped sawtooth at n=0 plus a missing "
                     "convective flux), and the front lags because the scheme "
                     "carries no advection to drive it"),
        }),
    CaseSpec(
        id="dressler-dry-dam-break", swashes_ref="SWASHES 4.1.3",
        family="dam-breaks",
        title="Dressler dam break on a dry domain with friction",
        dims=(1, 2), L=2000.0, W1d=500.0, W2d=10.0,
        z=lambda x: np.zeros_like(x),
        n_manning=an.dressler_manning_equiv(),   # Chézy C=40 → n ≈ 0.0294
        upstream=BC("wall"), downstream=BC("wall"),
        h0=lambda x: np.where(x <= an.DR_X0, an.DR_HL, 0.0), steady=False,
        t_end=40.0, dt_routing=0.01, report_step=1.0,
        compare_times=(10.0, 20.0, 40.0), probes=(1200.0, 1400.0, 1600.0),
        nx=2000, refine_nx=(200,),   # dx=1.0 (2026-08-13 hires: was dx=5)
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="dry-bed front precedent (ritter); reference friction "
                     "is Chézy C=40 — deck carries the equivalent Manning "
                     "n = (4/9·hl)^(1/6)/C (approximation recorded in "
                     "provenance)"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL),
            "1d-fv": CellPolicy(
                "analytic", {"l1_h": 0.08},
                note="graded on l1_h only: Dressler's front is pinned at "
                     "Ritter's FRICTIONLESS position xB = x0+2t√(ghl) (his "
                     "first-order correction does not move the front — a "
                     "stated limit of the solution), so every frictional "
                     "solver undershoots it (FV: 1300 vs 1580 m at t=40) "
                     "and front_err cannot gate; body l1 = 3.4% at t=40. "
                     "Chézy→Manning mismatch also over-damps the shallow "
                     "tip (n_eq fixed at the star depth)"),
            "2d-explicit": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL,
                note="wet/dry front under local inertia with friction"),
            "2d-explicit-adv": CellPolicy(
                "baseline", _DAM_TOL, baseline_tol=BASE_TOL),
        }),
    CaseSpec(
        id="thacker-planar-1d", swashes_ref="SWASHES 4.2.1",
        family="oscillations", title="Thacker planar surface in a parabola",
        dims=(1, 2), L=4.0, W1d=1.0, W2d=0.5,
        z=an.thacker_z, n_manning=0.0,
        upstream=BC("wall"), downstream=BC("wall"),
        h0=_thacker_h0, steady=False,
        t_end=10.0, dt_routing=0.004, report_step=1.0,
        compare_times=(2.0, 4.0, 10.0), probes=(2.0,),
        nx=200, refine_nx=(100, 400),
        opts_2d={"DRY_DEPTH": "0.0001", "H_MOVE": "0.0001"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", {"l1_h": 0.05, "mass_pct": 15.0},
                baseline_tol=BASE_TOL,
                note="NOT gradual wet/dry mass loss: a t=0 blow-up. 200 of 202 "
                     "nodes flood at 0 00:00 at 36-48 CMS in a basin holding "
                     "~1 m3; depths pin at MaxDepth and the excess is "
                     "discarded (ALLOW_PONDING NO), so Flooding Loss is 177x "
                     "the Initial Stored Volume and the -27912% is that over a "
                     "near-zero denominator. The ICs are correct (planar eta, "
                     "dry bank above the waterline). Prime suspect is "
                     "conditioning: MIN_SURFAREA floors the DENOMINATOR of the "
                     "node head update (DynamicWave.cpp:3210/3325), and this "
                     "deck sets 0.01 m2 against the 1.167 m2 default - 117x "
                     "smaller - at ROUTING_STEP 0.004. Oscillation heavily "
                     "damped vs analytic; bit-identical to legacy since the "
                     "MINIMUM_STEP floor fix"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", {"l1_h": 0.05, "mass_pct": 15.0},
                baseline_tol=BASE_TOL,
                note="same t=0 blow-up as 1d-dynwave (see that row): whole-"
                     "network flooding at 0 00:00, 98x the Initial Stored "
                     "Volume discarded, suspect the 0.01 m2 MIN_SURFAREA "
                     "denominator; oscillation heavily damped vs analytic"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.05}),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.05}, baseline_tol=BASE_TOL,
                note="u(x,0)=0 — depth-only IC is exact at t=0"),
            "2d-explicit-adv": CellPolicy(
                "baseline", {"l1_h": 0.05}, baseline_tol=BASE_TOL,
                note="u(x,0)=0 — depth-only IC is exact at t=0"),
        }),
]

_T2 = 2.0 * np.pi / np.sqrt(8.0 * an.G * 0.1)      # radial period ≈ 2.24 s

TWO_D_ONLY_CASES = [
    CaseSpec(
        id="thacker-radial-2d", swashes_ref="SWASHES 4.2.2 (radial)",
        family="oscillations",
        title="Thacker radially-symmetric paraboloid oscillation",
        dims=(2,), L=4.0, W1d=1.0, W2d=4.0,
        z=lambda x: np.zeros_like(x), n_manning=0.0,
        upstream=BC("wall"), downstream=BC("wall"),
        h0=None, steady=False,
        z2d=an.thacker2d_z,
        h02d=lambda x, y: an.thacker2d_radial(x, y, 0.0)[0],
        t_end=float(3.0 * _T2), dt_routing=0.0, report_step=0.25,
        compare_times=(2.0, 4.0, 6.0), probes=(2.0,),
        nx=80,                                     # target edge 0.05 m
        opts_2d={"DRY_DEPTH": "0.0001", "H_MOVE": "0.0001"},
        cells={
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.05}, baseline_tol=BASE_TOL,
                note="u=v=0 at t=0 (depth-only IC exact); phase/amplitude "
                     "drift expected of local inertia — XPASS flips analytic"),
            "2d-explicit-adv": CellPolicy(
                "baseline", {"l1_h": 0.05}, baseline_tol=BASE_TOL,
                note="u=v=0 at t=0 (depth-only IC exact); phase/amplitude "
                     "drift expected of local inertia — XPASS flips analytic"),
        }),
    CaseSpec(
        id="thacker-planar-2d", swashes_ref="SWASHES 4.2.2 (planar)",
        family="oscillations",
        title="Thacker planar surface in a paraboloid",
        dims=(2,), L=4.0, W1d=1.0, W2d=4.0,
        z=lambda x: np.zeros_like(x), n_manning=0.0,
        upstream=BC("wall"), downstream=BC("wall"),
        h0=None, steady=False,
        z2d=an.thacker2d_z,
        h02d=lambda x, y: an.thacker2d_planar(x, y, 0.0)[0],
        uv02d=lambda x, y: an.thacker2d_planar(x, y, 0.0)[1:3],
        t_end=float(3.0 * 2.0 * np.pi / np.sqrt(2.0 * an.G * 0.1)),
        dt_routing=0.0, report_step=0.25,
        compare_times=(2.0, 4.0), probes=(2.0,),
        nx=80,
        opts_2d={"DRY_DEPTH": "0.0001", "H_MOVE": "0.0001"},
        cells={
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.05}, baseline_tol=BASE_TOL,
                note="v(t=0)=eta*omega seeded via [2D_INITIAL_VELOCITY] "
                     "(engine edge-flux seeding, 2026-08-03); remaining "
                     "error is local-inertia phase/front drift — XPASS "
                     "flips analytic"),
            "2d-explicit-adv": CellPolicy(
                "baseline", {"l1_h": 0.05}, baseline_tol=BASE_TOL,
                note="v(t=0)=eta*omega seeded via [2D_INITIAL_VELOCITY] "
                     "(engine edge-flux seeding, 2026-08-03); remaining "
                     "error is local-inertia phase/front drift — XPASS "
                     "flips analytic"),
        }),
]


def reference_profile_t(case: CaseSpec, x: np.ndarray, t: float):
    """(h, q) at time t for the 1D transient cases (q = h*u)."""
    if case.id == "stoker-wet-dam-break":
        h, u = an.stoker(x, t)
    elif case.id == "ritter-dry-dam-break":
        h, u = an.ritter(x, t)
    elif case.id == "dressler-dry-dam-break":
        h, u = an.dressler(x, t)
    elif case.id == "thacker-planar-1d":
        h, u = an.thacker_planar_1d(x, t)
    else:
        raise KeyError(case.id)
    return h, h * u


def reference_strip_2donly(case: CaseSpec, x: np.ndarray, t: float,
                           n_y: int = 41):
    """Strip-averaged (h, q) through the domain for the 2D-only cases:
    average the 2D analytic field over y at each x (matches the extractor's
    strip binning)."""
    y = np.linspace(0.0, case.W2d, n_y)
    X, Y = np.meshgrid(x, y)
    if case.id == "thacker-radial-2d":
        h, u, _ = an.thacker2d_radial(X, Y, t)
    elif case.id == "thacker-planar-2d":
        h, u, _ = an.thacker2d_planar(X, Y, t)
    else:
        raise KeyError(case.id)
    return h.mean(axis=0), (h * u).mean(axis=0)


ALL_TRANSIENT = TRANSIENT_CASES + TWO_D_ONLY_CASES

# The requested DW surcharge x continuity column set applies to every family
# (2026-08-13); 2D-only cases have no DW cells, so the mirror is a no-op there.
mirror_dw_variants(ALL_TRANSIENT)
