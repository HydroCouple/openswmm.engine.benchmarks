#!/usr/bin/env python3
"""§3.5 MacDonald pseudo-2D cases — variable-width (and trapezoidal)
channels, 1D solver columns only.

These validate non-prismatic conveyance: every conduit carries its own local
bottom width B(x_mid) (and side slope Z), which is exactly SWMM's
representation strength. The 2D columns are intentionally absent: meshing
the variable-width planform is a separate build (the strip generator
extrudes a constant width) — noted in the README.

Conventions (casespec.py): with `width_fn` set, upstream BC.q is the TOTAL
discharge (20 m³/s); extraction divides link flow by the local width, so the
compared q is the local unit discharge Q/B (informational for the
trapezoidal cases — only l1_h and shock position gate).
"""
from __future__ import annotations

import numpy as np

from . import analytic as an
from .casespec import BC, CaseSpec, CellPolicy, mirror_dw_variants
from .cases_steady import BASE_TOL

SHOCK_X = {"p2d-jump-short": 120.0, "p2d-jump-long": 120.0}

_Q = an.P2D_Q                                   # 20 m³/s
_N = an.P2D_N                                   # 0.03


def _bed(h_fn, dh_fn, B_fn, dB_fn, Z, L):
    """Datum-anchored interpolable bed (min z = 0) + shifted z(L)."""
    xd = np.linspace(0.0, L, 20001)
    z = an.p2d_bed(xd, h_fn, dh_fn, B_fn, dB_fn, Z)
    z = z - z.min()

    def z_of(x):
        return np.interp(x, xd, z)
    return z_of, float(z[-1])


_z_sub_s, _zL_sub_s = _bed(an.p2d_sub_short_h, an._p2d_sub_short_dh,
                           an.p2d_B1, an._p2d_dB1, 0.0, 200.0)
_z_sup_s, _zL_sup_s = _bed(an.p2d_sup_short_h, an._p2d_sup_short_dh,
                           an.p2d_B1, an._p2d_dB1, 0.0, 200.0)
_z_trans_s, _zL_trans_s = _bed(an.p2d_trans_short_h, an._p2d_trans_short_dh,
                               an.p2d_B1, an._p2d_dB1, 0.0, 200.0)
_z_jump_s, _zL_jump_s = _bed(an.p2d_jump_short_h, an._p2d_jump_short_dh,
                             an.p2d_B1, an._p2d_dB1, 0.0, 200.0)
_z_sub_l, _zL_sub_l = _bed(an.p2d_sub_long_h, an._p2d_sub_long_dh,
                           an.p2d_B2, an._p2d_dB2, 2.0, 400.0)
_z_jump_l, _zL_jump_l = _bed(an.p2d_jump_long_h, an._p2d_jump_long_dh,
                             an.p2d_B2, an._p2d_dB2, 2.0, 400.0)


def _eta(h_fn, zL, L):
    return float(h_fn(np.array([L]))[0]) + zL


def _puddle(h_fn, z_of, zL, L):
    """Paper IC: h = max(hex(L) + z(L) − z(x), 0) — lake at the outlet."""
    eta = _eta(h_fn, zL, L)

    def h0(x):
        return np.maximum(eta - z_of(x), 0.0)
    return h0


# 2026-08-13 UPDATE (runs/_p2d_probe/FINDINGS.md) — the family-wide error is
# NOT a uniform deep bias: it is ANTISYMMETRIC in the sign of dB/dx. On
# p2d-sub-short 1d-fv: +0.135/+0.225 m where the channel CONTRACTS, -0.009 m
# at the throat where B'=0, -0.266/-0.122 m where it EXPANDS, ~0 at the BCs.
# That is the fingerprint of the missing width-gradient momentum source
# (q²/(gA³))·h·B'(x): gen1d gives each conduit ONE width, so B'=0 inside every
# cell and the whole source collapses onto the junctions, where the flux
# carries no wall-pressure term. Magnitude check: deleting the source from the
# steady ODE gives 6.66% on p2d-sub-long vs FV's actual 7.03%. The BENCHMARK
# IS VALIDATED — an independent RK4 integration of the momentum ODE reproduces
# the vendored reference to l1 0.000%, so these reds are engine-side.
# Acceptance test for the eventual single-flux junction fix: the contraction
# and expansion errors must go to zero TOGETHER, checked at two resolutions
# (the defect is dx-independent, so a refinement study cannot see it).
# The jump cases are not special — the shock-free subcritical case fails
# hardest (FV 16.5%); a misplaced jump is a consequence of the wrong upstream
# momentum balance, not a shock-capturing defect.
#
# Family-wide mechanism (measured 2026-08-12/13, all six cases): with q(x)
# EXACT everywhere and the downstream stage honored, depths run 17-45% deep,
# dx-INDEPENDENT (p2d-sub-short FV: 23.8% at nx=100 vs 24.3% at nx=400) — so
# not a staircase-resolution artifact. Integrating the no-convective steady
# balance d(h+z)/dx = -Sf reproduces the right direction (throat depth
# 1.31 vs analytic 1.20 on p2d-sub-short, Fr_throat = 0.97) but the engines
# sit deeper still: junction chains transmit no momentum across nodes (bend
# study), and in a non-prismatic channel ALL convective acceleration + the
# wall-pressure work happen ACROSS junctions.
#
# ENGINE EXPLORATION 2026-08-13 (ExplicitFvSolver, uncommitted): the FV
# pass-through splice was being silently REVOKED at every width-varying
# junction — the two prismatic views of a spliced non-prismatic face
# disagree by O(ΔB) in mass flux, the residual filled node_carry_, and the
# carry != 0 test dropped the node to the lossy head solve. Disposing a
# pass node's residual into its incident cells keeps the splice alive
# (p2d-sub-short: 24.3% -> 16.5% at nx=400). Additive per-face momentum
# closures on top of the splice are a NEGATIVE RESULT: the symmetric
# convective term made it worse (18.6% -> 31.3% on the nx=20 probe), the
# wall-pressure term likewise (28.6%) — the raw spliced pair already
# carries the closest jump, and the remaining bias needs a designed
# single-flux junction treatment (one Riemann problem with an explicit
# wall term). Details in the engine source comment at the retired site.
# DW divergence trend is OPPOSITE: its head-solve bias GROWS with
# refinement (44.7% at nx=200 -> 55.4% at nx=400, smooth, steady;
# PARTIAL damping changes nothing) — more junctions, more per-junction
# split-Riemann loss.
# ============================================================================
# FV RESOLVED 2026-08-13 — the width-step single-flux fix (engine:
# mesh.face_geom + faceSide; plans/FV_WIDTH_STEP_SINGLE_FLUX_PLAN.md).
# Root cause was NOT resolution and NOT junction loss: each side of a width
# step was reconstructed in its OWN section, so the step's wall exerted no
# force. Giving the face ONE shared section makes the pair a single well-posed
# Riemann problem, and the existing hydrostatic correction becomes the
# wall-pressure term. Measured, all six cases at nx=400:
#     p2d-sub-short  16.53% -> 0.23%      p2d-sub-long    8.10% -> 0.17%
#     p2d-jump-long   5.42% -> 0.26%      (shock 7.50 m -> 0.50 m)
#     p2d-jump-short 12.64% -> 0.30%      (shock 0.75 m -> 0.25 m)
#     p2d-trans-short 12.07% -> 0.33%     p2d-sup-short  12.43% -> 0.60%
# The antisymmetric dB/dx signature is gone: contraction +0.135/+0.225 m ->
# +0.002/+0.004 m and expansion -0.266/-0.122 m -> -0.000/+0.001 m fell to
# zero TOGETHER, which is what separates removing the bias from moving it.
# Prismatic decks are bit-identical (verified on 4), and lake-at-rest over a
# width step still holds at machine precision. The 1d-fv cells below are now
# analytic PASSES; the DW cells keep the family mechanism note.
# ============================================================================
_MECH = ("non-prismatic momentum: DW junction chains drop the cross-junction "
         "convective + wall-pressure terms — dx-independent deep bias with "
         "exact q (see cases_pseudo2d.py header note). FV no longer shares "
         "this: the width-step single-flux fix (face_geom) closed it "
         "2026-08-13")


def _cells(dw_mode: str, tol: dict, dw_note: str = "",
           fv_tol: dict | None = None) -> dict:
    mk = {
        "1d-dynwave": CellPolicy("baseline", tol, baseline_tol=BASE_TOL,
                                 note=(dw_note + "; " if dw_note else "")
                                 + _MECH),
        "1d-dynwave-legacy": CellPolicy("baseline", tol,
                                        baseline_tol=BASE_TOL),
        "1d-fv": CellPolicy(
            "analytic", fv_tol or tol,
            note="FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the "
                 "width-step single-flux treatment — one shared face section, "
                 "so the step's wall finally exerts force — brings the family "
                 "to 0.17-0.60% and the jumps inside half a cell"),
    }
    return mk


PSEUDO2D_CASES = [
    CaseSpec(
        id="p2d-sub-short", swashes_ref="SWASHES 3.5.1",
        family="macdonald-p2d",
        title="Pseudo-2D subcritical, B1 rectangular, 200 m",
        dims=(1,), L=200.0, W1d=10.0, W2d=10.0, z=_z_sub_s, n_manning=_N,
        width_fn=an.p2d_B1, side_slope=0.0,
        upstream=BC("inflow_q", q=_Q),
        downstream=BC("stage", eta=_eta(an.p2d_sub_short_h, _zL_sub_s, 200.0)),
        h0=_puddle(an.p2d_sub_short_h, _z_sub_s, _zL_sub_s, 200.0),
        t_end=1800.0, dt_routing=0.015, report_step=10.0,  # c_max ~ 6.8 m/s
        compare_times=(1800.0,), nx=400, refine_nx=(200,),
        cells=_cells("analytic", {"l1_h": 0.04},
                     "non-prismatic conveyance: per-conduit local width"),
    ),
    CaseSpec(
        id="p2d-sup-short", swashes_ref="SWASHES 3.5.2",
        family="macdonald-p2d",
        title="Pseudo-2D supercritical, B1 rectangular, 200 m",
        dims=(1,), L=200.0, W1d=10.0, W2d=10.0, z=_z_sup_s, n_manning=_N,
        width_fn=an.p2d_B1, side_slope=0.0,
        upstream=BC("inflow_q", q=_Q), downstream=BC("free"),
        h0=None,
        t_end=1800.0, dt_routing=0.015, report_step=10.0,  # c_max ~ 7.1 m/s
        compare_times=(1800.0,), nx=400, refine_nx=(200,),
        interior_mask=(0.05, 1.0),      # upstream q+h cannot both be pinned
        cells=_cells("analytic", {"l1_h": 0.04},
                     "fully supercritical through the contraction"),
    ),
    CaseSpec(
        id="p2d-trans-short", swashes_ref="SWASHES 3.5.3",
        family="macdonald-p2d",
        title="Pseudo-2D smooth sub-to-supercritical, B1, 200 m",
        dims=(1,), L=200.0, W1d=10.0, W2d=10.0, z=_z_trans_s, n_manning=_N,
        width_fn=an.p2d_B1, side_slope=0.0,
        upstream=BC("inflow_q", q=_Q), downstream=BC("free"),
        h0=None,
        t_end=1800.0, dt_routing=0.015, report_step=10.0,
        compare_times=(1800.0,), nx=400, refine_nx=(200,),
        cells=_cells("baseline", {"l1_h": 0.04},
                     "transcritical choke precedent (bump-transcritical)"),
    ),
    CaseSpec(
        id="p2d-jump-short", swashes_ref="SWASHES 3.5.4",
        family="macdonald-p2d",
        title="Pseudo-2D hydraulic jump at x = 120 m, B1, 200 m",
        dims=(1,), L=200.0, W1d=10.0, W2d=10.0, z=_z_jump_s, n_manning=_N,
        width_fn=an.p2d_B1, side_slope=0.0,
        upstream=BC("inflow_q", q=_Q),
        downstream=BC("stage",
                      eta=_eta(an.p2d_jump_short_h, _zL_jump_s, 200.0)),
        h0=_puddle(an.p2d_jump_short_h, _z_jump_s, _zL_jump_s, 200.0),
        t_end=1800.0, dt_routing=0.015, report_step=10.0,  # c_max ~ 7.9 m/s
        compare_times=(1800.0,), nx=400, refine_nx=(200,),
        interior_mask=(0.05, 1.0),      # supercritical inflow: h unpinnable
        cells=_cells("baseline", {"l1_h": 0.05, "shock_err_m": 5.0},
                     "steady shock position precedent (bump-shock); "
                     "downstream eta is hex(200) of the RH-verified "
                     "construction (Table-2 hout differs — see provenance)",
                     fv_tol={"l1_h": 0.05, "shock_err_m": 5.0}),
    ),
    CaseSpec(
        id="p2d-sub-long", swashes_ref="SWASHES 3.5.5",
        family="macdonald-p2d",
        title="Pseudo-2D subcritical, B2 trapezoidal Z=2, 400 m",
        dims=(1,), L=400.0, W1d=10.0, W2d=10.0, z=_z_sub_l, n_manning=_N,
        width_fn=an.p2d_B2, side_slope=2.0,
        upstream=BC("inflow_q", q=_Q),
        downstream=BC("stage", eta=_eta(an.p2d_sub_long_h, _zL_sub_l, 400.0)),
        h0=_puddle(an.p2d_sub_long_h, _z_sub_l, _zL_sub_l, 400.0),
        t_end=1800.0, dt_routing=0.04, report_step=10.0,  # c_max ~ 5.2 m/s
        compare_times=(1800.0,), nx=400, refine_nx=(200,),
        cells=_cells("analytic", {"l1_h": 0.04},
                     "trapezoidal non-prismatic conveyance (Z = 2)"),
    ),
    CaseSpec(
        id="p2d-jump-long", swashes_ref="SWASHES 3.5.6",
        family="macdonald-p2d",
        title="Pseudo-2D transonic + jump at x = 120 m, B2 trapezoidal, 400 m",
        dims=(1,), L=400.0, W1d=10.0, W2d=10.0, z=_z_jump_l, n_manning=_N,
        width_fn=an.p2d_B2, side_slope=2.0,
        upstream=BC("inflow_q", q=_Q),
        downstream=BC("stage",
                      eta=_eta(an.p2d_jump_long_h, _zL_jump_l, 400.0)),
        h0=_puddle(an.p2d_jump_long_h, _z_jump_l, _zL_jump_l, 400.0),
        t_end=1800.0, dt_routing=0.04, report_step=10.0,  # c_max ~ 5.4 m/s
        compare_times=(1800.0,), nx=400, refine_nx=(200,),
        cells=_cells("baseline", {"l1_h": 0.05, "shock_err_m": 10.0},
                     "smooth transition then steady shock (bump-shock "
                     "precedent)",
                     fv_tol={"l1_h": 0.05, "shock_err_m": 10.0}),
    ),
]

mirror_dw_variants(PSEUDO2D_CASES)

_H_FNS = {
    "p2d-sub-short": an.p2d_sub_short_h,
    "p2d-sup-short": an.p2d_sup_short_h,
    "p2d-trans-short": an.p2d_trans_short_h,
    "p2d-jump-short": an.p2d_jump_short_h,
    "p2d-sub-long": an.p2d_sub_long_h,
    "p2d-jump-long": an.p2d_jump_long_h,
}


def reference_profile_p2d(case: CaseSpec, x: np.ndarray):
    """(h, q_unit) with q_unit = Q/B(x) — the local unit discharge (exact
    for the rectangular cases; informational for the trapezoids)."""
    h = _H_FNS[case.id](x)
    q = _Q / case.width_fn(x)
    return h, q
