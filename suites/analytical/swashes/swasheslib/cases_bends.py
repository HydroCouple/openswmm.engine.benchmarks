#!/usr/bin/env python3
"""Bend family — planform-blindness implications study (plan 2026-08-03).

L-shaped channels (two 60 m legs, mitered corner at s = 60 m) graded against
the engine's own 2D shallow-water solver running the TRUE bent geometry
(`ref_source="2d"`, pinned via `run_swashes.py gen-2d-ref --pin`). No
analytic solution exists for bends; the 2D local-inertial reference
UNDER-predicts bend loss (no convective inertia) so measured effects are
lower bounds. theta = 0 controls isolate bend-specific error from generic
1D-vs-2D bias (e.g. the sidewall-friction difference: 1D RECT_OPEN wets the
walls, the 2D solver frictions the bed only).

Regime sizing (wide-channel R = h): v = Fr*sqrt(g*h_n),
S0 = n^2 v^2 / h_n^(4/3), bed z(s) = S0*(L - s), downstream stage = h_n.
gentle: h_n = 1.0 m, Fr = 0.30; swift: h_n = 0.4 m, Fr = 0.80.
Expected miter-bend loss K = 1.1*(1 - cos theta): 90deg -> 1.1
(dH = K v^2/2g = 0.141 m at swift), 45deg -> 0.322.
"""
from __future__ import annotations

import numpy as np

from .casespec import BC, CaseSpec, CellPolicy, mirror_dw_variants
from .planform import MiterPlanform

G = 9.81
_W = 4.0          # channel width, W1d == W2d — the SAME physical channel
_LEG = 60.0
_L = 2.0 * _LEG   # centerline length; corner at s = 60 m = node N0120
_NX = 240         # dx = 0.5 m
_N = 0.025

# Tolerances calibrated 2026-08-04 to ~1.3x the first pinned-run measured
# values (the measured 1D-vs-2D error IS the study output; green = "within
# expected 1D fidelity"). The dominant, control-measured bias is SIDEWALL
# FRICTION (1D RECT_OPEN wets the walls, R = Wh/(W+2h); the 2D solver
# frictions the bed only, R = h): gentle l1 15.7%, swift 8.1%. Bend-specific
# (control-subtracted) additions are small: 90deg gentle +0.2%, 90deg swift
# +0.7% (linf +4.9% at the corner), 45deg swift +0.1%. Adding the literature
# miter K = 1.1 OVERSHOOTS this local-inertial reference (l1 8.8% -> 14.7%).
_TOL = {
    "bend00-gentle": {"l1_h": 0.21, "linf_h": 0.23, "mass_pct": 1.0},
    "bend00-swift": {"l1_h": 0.11, "linf_h": 0.11, "mass_pct": 1.0},
    "bend90-gentle": {"l1_h": 0.21, "linf_h": 0.23, "mass_pct": 1.0},
    "bend90-swift": {"l1_h": 0.12, "linf_h": 0.18, "mass_pct": 1.0},
    "bend45-swift": {"l1_h": 0.11, "linf_h": 0.12, "mass_pct": 1.0},
    "bend90-swift-k": {"l1_h": 0.19, "linf_h": 0.53, "mass_pct": 1.0},
}


def _regime(h_n: float, fr: float):
    v = fr * np.sqrt(G * h_n)
    q = v * h_n                     # unit discharge (m2/s)
    s0 = _N * _N * v * v / h_n ** (4.0 / 3.0)
    return v, q, s0


_V_G, _Q_G, _S0_G = _regime(1.0, 0.30)
_V_S, _Q_S, _S0_S = _regime(0.4, 0.80)


def _bend_z(s0: float):
    return lambda s: s0 * (_L - np.asarray(s, dtype=float))


# Advection-column tolerances, calibrated 2026-08-12 to ~1.3x the measured
# deviation of the SAME bent mesh run with the convective momentum flux on
# (0.001 floor so ulp-level noise on the null cases cannot fail).
#
# This column is NOT a fidelity test of the 1D schemes — it quantifies the
# reference's own documented blind spot: the pinned local-inertial reference
# carries no convective inertia, so whatever advection moves here is exactly
# the bend loss the reference cannot see. Measured (l1_h / linf_h):
#
#   straight, gentle   0.00000 / 0.00000   <- exactly inert, as it must be:
#   straight, swift    0.00024 / 0.00067      the Stelling-Duinmeijer term
#   45 deg, swift      0.00068 / 0.00860      vanishes in uniform flow
#   90 deg, gentle     0.00560 / 0.01310
#   90 deg, swift      0.00506 / 0.03793   <- 3.8% local error at the corner
#
# The contribution scales monotonically with turn angle and concentrates at
# the miter — i.e. the reference under-reads bend loss by ~0.5% of depth in
# the mean and up to ~4% locally, which bounds the "lower bound" caveat the
# bend study carries. bend90-swift-k is bit-identical to bend90-swift here
# (bend_k is a 1D [LOSSES] row; the 2D deck never sees it) — a free
# cross-check that the columns are wired to the right decks.
_TOL_ADV = {
    "bend00-gentle": {"l1_h": 0.001, "linf_h": 0.001, "mass_pct": 1.0},
    "bend00-swift": {"l1_h": 0.001, "linf_h": 0.001, "mass_pct": 1.0},
    "bend45-swift": {"l1_h": 0.001, "linf_h": 0.012, "mass_pct": 1.0},
    "bend90-gentle": {"l1_h": 0.008, "linf_h": 0.018, "mass_pct": 1.0},
    "bend90-swift": {"l1_h": 0.007, "linf_h": 0.050, "mass_pct": 1.0},
    "bend90-swift-k": {"l1_h": 0.007, "linf_h": 0.050, "mass_pct": 1.0},
}


def _case(cid: str, title: str, theta: float, h_n: float, q: float,
          s0: float, h_max: float, tol: dict, bend_k: float = 0.0,
          opts_2d: dict | None = None, note_extra: str = "") -> CaseSpec:
    note = ("graded against the pinned 2D bent-geometry reference "
            "(local-inertial — lower-bound bend loss)" +
            (f"; {note_extra}" if note_extra else ""))
    cells = {
        "1d-dynwave": CellPolicy("analytic", dict(tol), note=note),
        "1d-dynwave-legacy": CellPolicy("analytic", dict(tol), note=note),
        "1d-dynwave-vj": CellPolicy("analytic", dict(tol), note=note),
        "1d-fv": CellPolicy("analytic", dict(tol)),
        "1d-fv-nodedt": CellPolicy("analytic", dict(tol)),
        "1d-fv-sub4": CellPolicy("analytic", dict(tol)),
        # Same bent mesh, same everything, convective momentum flux ON — so
        # the deviation from the reference IS the advection contribution.
        "2d-explicit-adv": CellPolicy("analytic", dict(_TOL_ADV[cid]),
                                      note="convective-inertia contribution "
                                           "vs the local-inertial reference "
                                           "on the identical bent mesh"),
        # 1d-kinwave omitted (no backwater); 2d-explicit omitted (its deck is
        # byte-identical to the reference generator's — self-comparison).
    }
    return CaseSpec(
        id=cid, swashes_ref="n/a — 2D cross-reference", family="bends",
        title=title, dims=(1, 2),
        L=_L, W1d=_W, W2d=_W, z=_bend_z(s0), n_manning=_N,
        upstream=BC("inflow_q", q=q), downstream=BC("stage", eta=h_n),
        h0=None,                                  # dry start (VJ-compatible)
        t_end=3600.0, dt_routing=0.05, report_step=10.0,
        compare_times=(3600.0,), probes=(40.0, 55.0, 65.0, 80.0, 100.0),
        nx=_NX, steady=True,
        opts_2d=dict(opts_2d or {}),
        # taper_mult=2: still-water probes on the mitered-shear mesh show the
        # default taper's corner cells destabilize the marcher at CFL 0.3
        # (grows 1e-8 -> 5e-2 in 10 min); doubling the taper span is
        # machine-flat (decays to 4e-9). See runs/_bend_study/stillwater_*.
        planform=MiterPlanform(theta_deg=theta, s_bend=_LEG, L=_L, W=_W,
                               taper_mult=2.0),
        h_max=h_max, bend_k=bend_k, ref_source="2d",
        cells=cells)


BEND_CASES = [
    _case("bend00-gentle", "Straight control, gentle flow (Fr 0.30)",
          0.0, 1.0, _Q_G, _S0_G, 2.0, _TOL["bend00-gentle"],
          note_extra="theta=0 control — generic 1D-vs-2D bias incl. "
                     "sidewall friction"),
    _case("bend00-swift", "Straight control, swift flow (Fr 0.80)",
          0.0, 0.4, _Q_S, _S0_S, 1.5, _TOL["bend00-swift"],
          opts_2d={"FROUDE_MAX": "3"},
          note_extra="theta=0 control for the swift regime"),
    _case("bend90-gentle", "90-degree miter bend, gentle flow (Fr 0.30)",
          90.0, 1.0, _Q_G, _S0_G, 2.0, _TOL["bend90-gentle"]),
    _case("bend90-swift", "90-degree miter bend, swift flow (Fr 0.80)",
          90.0, 0.4, _Q_S, _S0_S, 1.5, _TOL["bend90-swift"],
          opts_2d={"FROUDE_MAX": "3"}),
    _case("bend45-swift", "45-degree miter bend, swift flow (Fr 0.80)",
          45.0, 0.4, _Q_S, _S0_S, 1.5, _TOL["bend45-swift"],
          opts_2d={"FROUDE_MAX": "3"}),
    _case("bend90-swift-k", "90-degree bend, swift flow, literature miter K",
          90.0, 0.4, _Q_S, _S0_S, 1.5, _TOL["bend90-swift-k"],
          bend_k=1.1, opts_2d={"FROUDE_MAX": "3"},
          note_extra="1D decks carry K_miter = 1.1(1-cos90) = 1.1 as Kentry "
                     "on the corner conduit — the standard mitigation"),
]

mirror_dw_variants(BEND_CASES)
