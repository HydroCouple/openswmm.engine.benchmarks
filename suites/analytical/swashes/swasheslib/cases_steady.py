#!/usr/bin/env python3
"""Steady-state Phase-A cases (plan Part 3 tables).

Timesteps follow fairness rule 3: dt = 0.25*dx/c_max with c_max from the
analytic solution (values noted per case). One dt per case for ALL 1D
solvers; the 2D marcher keeps its own CFL dt.
"""
from __future__ import annotations

import numpy as np

from . import analytic as an
from .casespec import BC, CaseSpec, CellPolicy, mirror_dw_variants

# Baseline-mode default: pinned profiles must be reproduced closely.
BASE_TOL = {"l1_h": 0.005, "linf_h": 0.01}


def _mac_sub_z(x):
    xd = np.linspace(0.0, 1000.0, 20001)
    _, _, z = an.macdonald_sub(xd)
    return np.interp(x, xd, z)


def _mac_sup_z(x):
    xd = np.linspace(0.0, 1000.0, 20001)
    _, _, z = an.macdonald_sup(xd)
    return np.interp(x, xd, z)


def _mac_sub_eta_L() -> float:
    return float(an.macdonald_sub_h(np.array([1000.0]))[0])   # z(L) = 0


def _dense_z(fn, L):
    """Interpolable bed from a (h, q, z) analytic function on a dense grid."""
    xd = np.linspace(0.0, L, 20001)
    _, _, z = fn(xd)

    def z_of(x):
        return np.interp(x, xd, z)
    return z_of, float(z[-1])


_mac_sub2sup_z, _mac_sub2sup_zL = _dense_z(an.macdonald_sub2sup, 1000.0)
_mac_jump_z, _mac_jump_zL = _dense_z(an.macdonald_jump, 1000.0)
_mac_ss_z, _mac_ss_zL = _dense_z(an.macdonald_short_shock, 100.0)
_mac_ssup_z, _mac_ssup_zL = _dense_z(an.macdonald_short_sup, 100.0)
_mac_s2s_z, _mac_s2s_zL = _dense_z(an.macdonald_short_sub2sup, 100.0)
_mac_per_z, _mac_per_zL = _dense_z(an.macdonald_periodic, 5000.0)
_mac_rsub_z, _mac_rsub_zL = _dense_z(an.macdonald_rain_sub, 1000.0)
_mac_rsup_z, _mac_rsup_zL = _dense_z(an.macdonald_rain_sup, 1000.0)


def _eta_L(h_fn, zL, L):
    return float(h_fn(np.array([L]))[0]) + zL


_mac_jump_eta = _eta_L(an.macdonald_jump_h, _mac_jump_zL, 1000.0)
_mac_ss_eta = _eta_L(an.macdonald_short_shock_h, _mac_ss_zL, 100.0)
_mac_per_eta = _eta_L(an.macdonald_periodic_h, _mac_per_zL, 5000.0)
_mac_rsub_eta = _eta_L(an.macdonald_sub_h, _mac_rsub_zL, 1000.0)


STEADY_CASES = [
    CaseSpec(
        id="lake-at-rest-immersed", swashes_ref="SWASHES 3.1.1",
        family="bumps", title="Lake at rest with an immersed bump",
        dims=(1, 2), L=25.0, W1d=1.0, W2d=2.0, z=an.bump_z, n_manning=0.0,
        upstream=BC("none"), downstream=BC("stage", eta=0.5),
        h0=lambda x: np.maximum(0.5 - an.bump_z(x), 0.0),
        t_end=200.0, dt_routing=0.05, report_step=5.0,   # c_max ~ sqrt(g*0.5)=2.2
        compare_times=(200.0,), nx=25, refine_nx=(50, 125),
        cells={
            "1d-dynwave": CellPolicy("analytic",
                                     {"linf_h": 1e-3, "l1_q": 1e-4}),
            "1d-dynwave-legacy": CellPolicy("analytic",
                                            {"linf_h": 1e-3, "l1_q": 1e-4}),
            "1d-fv": CellPolicy("analytic", {"linf_h": 1e-3, "l1_q": 1e-4}),
            "2d-explicit": CellPolicy("analytic",
                                      {"linf_h": 1e-3, "l1_q": 1e-6},
                                      note="well-balancedness (C-property)"),
            "2d-explicit-adv": CellPolicy("analytic",
                                      {"linf_h": 1e-3, "l1_q": 1e-6},
                                      note="well-balancedness (C-property)"),
        }),
    CaseSpec(
        id="lake-at-rest-emerged", swashes_ref="SWASHES 3.1.2",
        family="bumps", title="Lake at rest with an emerged bump",
        dims=(1, 2), L=25.0, W1d=1.0, W2d=2.0, z=an.bump_z, n_manning=0.0,
        upstream=BC("none"), downstream=BC("stage", eta=0.1),
        h0=lambda x: np.maximum(0.1 - an.bump_z(x), 0.0),
        t_end=200.0, dt_routing=0.05, report_step=5.0,
        compare_times=(200.0,), nx=25, refine_nx=(50, 125),
        cells={
            "1d-dynwave": CellPolicy("analytic", {"linf_h": 5e-3},
                                     note="wet/dry transition at the bump"),
            "1d-dynwave-legacy": CellPolicy("analytic", {"linf_h": 5e-3}),
            "1d-fv": CellPolicy("analytic", {"linf_h": 5e-3}),
            "2d-explicit": CellPolicy("analytic", {"linf_h": 5e-3},
                                      note="wet/dry transition"),
            "2d-explicit-adv": CellPolicy("analytic", {"linf_h": 5e-3},
                                      note="wet/dry transition"),
        }),
    CaseSpec(
        id="bump-subcritical", swashes_ref="SWASHES 3.1.3",
        family="bumps", title="Subcritical flow over a bump",
        dims=(1, 2), L=25.0, W1d=1.0, W2d=2.0, z=an.bump_z, n_manning=0.0,
        upstream=BC("inflow_q", q=4.42), downstream=BC("stage", eta=2.0),
        h0=lambda x: np.maximum(2.0 - an.bump_z(x), 0.0),
        t_end=1800.0, dt_routing=0.05, report_step=10.0,  # dx=1.0: Courant~0.35
        compare_times=(1800.0,), nx=25, refine_nx=(50, 125),
        cells={
            "1d-dynwave": CellPolicy("analytic", {"l1_h": 0.02}),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.02}),
            "1d-dynwave-vj": CellPolicy(
                "analytic", {"l1_h": 0.02},
                note="zero-storage VJ chain matches the junction chain "
                     "(l1 0.17%); at small fairness-scaled dt the VJ chain "
                     "keeps fine grids stable where junction chains seiche "
                     "(dx=0.2/dt=0.01: VJ 0.24% vs junctions 21%) — at the "
                     "case dt both refine cleanly (VJ_FINDINGS.md); interior "
                     "ICs not representable, dry-start spin-up"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.02}),
            "2d-explicit": CellPolicy(
                "analytic", {"l1_h": 0.03},
                note="PASSES since the inertial stage/inflow BC fix "
                     "(2026-08-03): the old 4.4% was a boundary-condition "
                     "stage offset (collapsed-Manning Dirichlet cell + "
                     "momentum-less inflow), NOT the Bernoulli dip; the "
                     "residual ~0.7% is the genuine no-advection limit "
                     "(steady, mass-exact). EXPECTED in the figure: eta is "
                     "dead FLAT over the crest (+7.7 cm depth residual at "
                     "x=8-12 m) — flat eta is the EXACT frictionless steady "
                     "state of the local-inertial equation (no q^2/h term; "
                     "the dip = Delta(v^2/2g) it cannot represent). OWNER "
                     "RULING 2026-08-04: keep local-inertial, document; "
                     "momentum-advection upgrade declined for now"),
            "2d-explicit-adv": CellPolicy(
                "analytic", {"l1_h": 0.03},
                note="PASSES since the inertial stage/inflow BC fix "
                     "(2026-08-03): the old 4.4% was a boundary-condition "
                     "stage offset (collapsed-Manning Dirichlet cell + "
                     "momentum-less inflow), NOT the Bernoulli dip; the "
                     "residual ~0.7% is the genuine no-advection limit "
                     "(steady, mass-exact). EXPECTED in the figure: eta is "
                     "dead FLAT over the crest (+7.7 cm depth residual at "
                     "x=8-12 m) — flat eta is the EXACT frictionless steady "
                     "state of the local-inertial equation (no q^2/h term; "
                     "the dip = Delta(v^2/2g) it cannot represent). OWNER "
                     "RULING 2026-08-04: keep local-inertial, document; "
                     "momentum-advection upgrade declined for now"),
        }),
    CaseSpec(
        id="bump-transcritical", swashes_ref="SWASHES 3.1.4",
        family="bumps", title="Transcritical flow without shock",
        dims=(1, 2), L=25.0, W1d=1.0, W2d=2.0, z=an.bump_z, n_manning=0.0,
        upstream=BC("inflow_q", q=1.53), downstream=BC("free"),
        h0=lambda x: np.maximum(0.66 - an.bump_z(x), 1e-3),
        t_end=1800.0, dt_routing=0.05, report_step=10.0,  # dx=1.0: Courant~0.23
        compare_times=(1800.0,), nx=25, refine_nx=(50, 125),
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", {"l1_h": 0.03, "mass_pct": 6.0},
                baseline_tol=BASE_TOL,
                note="implicit DW cannot establish the transcritical choke "
                     "at stable resolution (settles near critical flow); "
                     "analytic tols recorded for FV. Bit-identical to legacy "
                     "since the fixed-step MINIMUM_STEP floor fix (the "
                     "'short-conduit defect' was decks silently marching at "
                     "0.5 s; see lake-at-rest _debug/REPRO.md)"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", {"l1_h": 0.03, "mass_pct": 6.0},
                baseline_tol=BASE_TOL,
                note="same choke limitation as 1d-dynwave; observed legacy "
                     "continuity −4.5% on the free-outfall spin-up "
                     "(gate 6%)"),
            "1d-dynwave-vj": CellPolicy(
                "baseline", {"l1_h": 0.03, "mass_pct": 6.0},
                baseline_tol=BASE_TOL,
                note="same implicit-DW choke limitation as the junction "
                     "chain (l1 34% vs 32%) — VJ at parity"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.03}),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.03}, baseline_tol=BASE_TOL,
                note="passes Fr=1; local-inertial neglects convective inertia "
                     "— FROUDE_MAX raised to 3 (recorded). What that costs: q "
                     "is EXACT everywhere (1.5300) and mass is 7e-13, so "
                     "nothing is wrong with the fluxes or areas; only h is "
                     "wrong, and only upstream (0.5898 vs 1.0144). Critical "
                     "depth here is (q^2/g)^(1/3)=0.620, so the model sits at "
                     "Fr 1.08 where the truth is Fr 0.48 — the SUPERCRITICAL "
                     "BRANCH of the same specific energy, over the whole "
                     "domain; downstream, where the truth is supercritical "
                     "too, it matches to 0.2%. Without the advective term the "
                     "frictionless steady balance reduces to d(eta)/dx=0, and "
                     "the measured eta is indeed constant at 0.5898 from x=0.5 "
                     "through the crest, so the upstream pool can never build"),
            "2d-explicit-adv": CellPolicy(
                "baseline", {"l1_h": 0.03}, baseline_tol=BASE_TOL,
                note="passes Fr=1; local-inertial neglects convective inertia "
                     "— FROUDE_MAX raised to 3 (recorded). What that costs: q "
                     "is EXACT everywhere (1.5300) and mass is 7e-13, so "
                     "nothing is wrong with the fluxes or areas; only h is "
                     "wrong, and only upstream (0.5898 vs 1.0144). Critical "
                     "depth here is (q^2/g)^(1/3)=0.620, so the model sits at "
                     "Fr 1.08 where the truth is Fr 0.48 — the SUPERCRITICAL "
                     "BRANCH of the same specific energy, over the whole "
                     "domain; downstream, where the truth is supercritical "
                     "too, it matches to 0.2%. Without the advective term the "
                     "frictionless steady balance reduces to d(eta)/dx=0, and "
                     "the measured eta is indeed constant at 0.5898 from x=0.5 "
                     "through the crest, so the upstream pool can never build"),
        }),
    CaseSpec(
        id="bump-shock", swashes_ref="SWASHES 3.1.5",
        family="bumps", title="Transcritical flow with shock",
        dims=(1, 2), L=25.0, W1d=1.0, W2d=2.0, z=an.bump_z, n_manning=0.0,
        upstream=BC("inflow_q", q=0.18), downstream=BC("stage", eta=0.33),
        h0=lambda x: np.maximum(0.33 - an.bump_z(x), 1e-3),
        t_end=1800.0, dt_routing=0.05, report_step=10.0,  # dx=1.0: Courant~0.12
        compare_times=(1800.0,), nx=25, refine_nx=(50, 125),
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", {"l1_h": 0.08, "shock_err_m": 3.0,
                             "mass_pct": 3.0}, baseline_tol=BASE_TOL,
                note="transcritical choke + slow shock slosh — implicit DW "
                     "holds no steady shock position (mean drifts ~20%); "
                     "analytic tols recorded for FV; mass gate 3% "
                     "(storage:throughput inflation at q=0.18)"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", {"l1_h": 0.08, "shock_err_m": 3.0,
                             "mass_pct": 3.0}, baseline_tol=BASE_TOL,
                note="same shock-slosh limitation as 1d-dynwave"),
            "1d-dynwave-vj": CellPolicy(
                "baseline", {"l1_h": 0.08, "shock_err_m": 3.0,
                             "mass_pct": 3.0}, baseline_tol=BASE_TOL,
                note="same shock-slosh limitation as the junction chain "
                     "(l1 5.0% vs 4.1%) — VJ at parity"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.05, "shock_err_m": 3.0,
                                             "mass_pct": 3.0}),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.05, "shock_err_m": 3.0},
                baseline_tol=BASE_TOL,
                note="local-inertial through a hydraulic jump"),
            "2d-explicit-adv": CellPolicy(
                "baseline", {"l1_h": 0.05, "shock_err_m": 3.0},
                baseline_tol=BASE_TOL,
                note="local-inertial through a hydraulic jump"),
        }),
    CaseSpec(
        id="macdonald-long-sub", swashes_ref="SWASHES 3.2.1 (subcritical)",
        family="macdonald", title="MacDonald 1000 m channel, subcritical",
        dims=(1, 2), L=1000.0, W1d=500.0, W2d=10.0, z=_mac_sub_z,
        n_manning=0.033,
        upstream=BC("inflow_q", q=2.0),
        downstream=BC("stage", eta=_mac_sub_eta_L()),
        h0=None,                                     # dry start (paper)
        t_end=6000.0, dt_routing=0.04, report_step=60.0,  # c_max ~ 6.0 m/s
        compare_times=(6000.0,), nx=1000, refine_nx=(200,),  # dx=1.0 (2026-08-13 hires)
        # Recorded deviation (2026-08-13, dx=1.0): NONE was fine at dx=2.5 but
        # the undamped odd-even mode is CATASTROPHIC at dx=1.0 — every DW
        # column l1 6.6 (662%), never steady (drift 0.49), node continuity
        # -48% at the downstream stage BC. Same sharpens-with-refinement
        # mechanism recorded on macdonald-long-sup at dx=2.5.
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        cells={
            "1d-dynwave": CellPolicy("analytic", {"l1_h": 0.03}),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.03}),
            "1d-dynwave-vj": CellPolicy(
                "analytic", {"l1_h": 0.03},
                note="zero-storage VJ chain matches the junction chain on "
                     "frictional channels (l1 1.7%, mass 0.001%)"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.03}),
            "2d-explicit": CellPolicy("analytic", {"l1_h": 0.03},
                                      note="R=h native — no width correction"),
            "2d-explicit-adv": CellPolicy("analytic", {"l1_h": 0.03},
                                      note="R=h native — no width correction"),
        }),
    CaseSpec(
        id="macdonald-long-sup", swashes_ref="SWASHES 3.2.1 (supercritical)",
        family="macdonald", title="MacDonald 1000 m channel, supercritical",
        dims=(1, 2), L=1000.0, W1d=500.0, W2d=10.0, z=_mac_sup_z,
        n_manning=0.04,
        upstream=BC("inflow_q", q=2.5), downstream=BC("free"),
        h0=None,
        t_end=6000.0, dt_routing=0.035, report_step=60.0,  # c_max ~ 7.0 m/s
        compare_times=(6000.0,), nx=1000, refine_nx=(200,),  # dx=1.0 (2026-08-13 hires)
        interior_mask=(0.05, 1.0),
        # Recorded deviation (2026-08-13): at dx=2.5 the undamped NONE block
        # checkerboards this supercritical channel (DW l1 11.6%, VJ 15.6%,
        # q exact); PARTIAL restores 0.61%/0.60%. At the Phase-A dx=5 NONE
        # was fine — the odd-even mode sharpens with refinement.
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        # dx=1.0 (2026-08-13 hires): the grid now RESOLVES the physical
        # Vedernikov roll waves (Ve > 1) that dx=2.5 damped numerically —
        # every DW column oscillates forever (window-mean drift 0.20-0.22,
        # a max-norm metric dominated by moving crests) while the TIME-MEAN
        # profile is excellent (l1 1.9-2.0% vs the 4% gate). Gate sized to
        # the persistent oscillation (macdonald-rain-sup precedent). Also
        # observed here: EXTRAN vs SLOT/DYNAMIC_SLOT differ slightly
        # (l1 1.94% vs 1.99%, IDENTICALLY in both engines) — a sub-crown
        # methodological micro-difference that only chaotic roll-wave cases
        # amplify to visibility; steady cases are bit-identical.
        steady_gate=0.25,
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="upstream q+h cannot both be pinned — graded on "
                     "x in [0.05L, L]"),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.04}),
            # ENGINE FINDING (deliberate red, 2026-08-13, dx=1.0): the
            # SEMI_IMPLICIT trio loses 1.75% mass (gate 0.5%) on this
            # resolved roll-wave channel while the EXPLICIT columns conserve
            # to -0.005% — and semi's time-mean profile is slightly BETTER
            # (l1 1.78% vs 1.94%). Steady cases (long-sub2sup, long-jump)
            # show no such loss: the unified Crank-Nicolson node update
            # leaks volume only under sustained wave sweep. Kept red as
            # in-matrix documentation.
            "1d-dynwave-semi": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="ENGINE FINDING: SEMI_IMPLICIT loses 1.75% mass under "
                     "resolved roll waves (explicit: -0.005%); l1 1.78% is "
                     "fine — the red is the mass gate"),
            "1d-dynwave-vj": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="VJ chain ~matches the junction chain (l1 0.65% vs "
                     "0.60%) and is machine-steady (resid 1e-8)"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.04}),
            "2d-explicit": CellPolicy(
                "xfail", {"l1_h": 0.04},
                note="supercritical throughout; FROUDE_MAX 3. XFAIL: the "
                     "local-inertial scheme carries no convective advection "
                     "term, so the fully supercritical profile never "
                     "steadies (roll-wave-like unsteadiness, drift ~0.9, q "
                     "spikes with drying cells) — a physics limit, not a "
                     "defect; requires a full-SWE momentum solver "
                     "(investigated 2026-08-03: survives the inertial-BC, "
                     "dt0-refresh and hysteresis fixes)"),
            "2d-explicit-adv": CellPolicy(
                "xfail", {"l1_h": 0.04},
                note="supercritical throughout; FROUDE_MAX 3. XFAIL: the "
                     "local-inertial scheme carries no convective advection "
                     "term, so the fully supercritical profile never "
                     "steadies (roll-wave-like unsteadiness, drift ~0.9, q "
                     "spikes with drying cells) — a physics limit, not a "
                     "defect; requires a full-SWE momentum solver "
                     "(investigated 2026-08-03: survives the inertial-BC, "
                     "dt0-refresh and hysteresis fixes)"),
        }),
    CaseSpec(
        id="macdonald-long-sub2sup",
        swashes_ref="SWASHES 3.2.1 (sub-to-supercritical)",
        family="macdonald",
        title="MacDonald 1000 m channel, subcritical to supercritical",
        dims=(1, 2), L=1000.0, W1d=500.0, W2d=10.0, z=_mac_sub2sup_z,
        n_manning=0.0218,
        upstream=BC("inflow_q", q=2.0), downstream=BC("free"),
        h0=None,                                     # dry start (paper)
        t_end=6000.0, dt_routing=0.04, report_step=60.0,  # c_max ~ 5.7 m/s
        compare_times=(6000.0,), nx=1000, refine_nx=(200,),  # dx=1.0 (2026-08-13 hires)
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="MEETS analytic through the smooth transonic point "
                     "(unlike the frictionless bump-transcritical choke). "
                     "Recorded deviation: INERTIAL_DAMPING PARTIAL — under "
                     "the normalized NONE the VJ column carries a stationary "
                     "odd-even sawtooth (l1 4.5% -> 0.9% with PARTIAL; q "
                     "exact either way)"),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.04}),
            "1d-dynwave-vj": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="0.9% with PARTIAL damping; sawtoothed at 4.5% under "
                     "NONE (checkerboard mode of the undamped chain)"),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.04}),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL,
                note="downstream half is supercritical — the "
                     "macdonald-long-sup no-advection limit. The retired "
                     "THETA 0.7/0.5 columns met the analytic gate here purely "
                     "by adding q-centred smoothing over the residual "
                     "sawtooth; the 0.8 default does not. That is a "
                     "damping-tuning artefact, not a physics fix — the "
                     "advection column is the term this case is actually "
                     "missing"),
            "2d-explicit-adv": CellPolicy(
                "xfail", {"l1_h": 0.04},
                note="never steadies with ADVECTION on (drift 0.34): the "
                     "upwinded convective term sustains roll-waves on the "
                     "supercritical downstream half (macdonald-long-sup "
                     "mechanism) and first-order diffusion costs l1 6.7%"),
        }),
    CaseSpec(
        id="macdonald-long-jump",
        swashes_ref="SWASHES 3.2.1 (super-to-subcritical)",
        family="macdonald",
        title="MacDonald 1000 m channel, hydraulic jump at x = 500 m",
        dims=(1, 2), L=1000.0, W1d=500.0, W2d=10.0, z=_mac_jump_z,
        n_manning=0.0218,
        upstream=BC("inflow_q", q=2.0),
        downstream=BC("stage", eta=_mac_jump_eta),
        h0=None,
        t_end=6000.0, dt_routing=0.04, report_step=60.0,  # c_max ~ 6.0 m/s
        compare_times=(6000.0,), nx=1000, refine_nx=(200,),  # dx=1.0 (2026-08-13 hires)
        interior_mask=(0.05, 1.0),      # upstream q+h cannot both be pinned
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        # dx=1.0 (2026-08-13): the 2D strip's jump-toe seiche no longer
        # decays at 1 m edges (shock position oscillates; window-mean drift
        # 0.267 is a max-norm metric at the moving toe) while the time-mean
        # is good (2D l1 4.5%, 1D cells machine-steady at 5e-5). Gate sized
        # to the toe oscillation; the l1 + shock gates still bind, and the
        # checkerboard blow-up signature (drift ~0.5) is still caught.
        steady_gate=0.3,
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.05, "shock_err_m": 25.0},
                note="MEETS analytic ON A FRICTIONAL CHANNEL: l1 1.3%, "
                     "shock error 2.5 m (half a cell) with the recorded "
                     "INERTIAL_DAMPING PARTIAL deviation — under NONE the "
                     "shock region carries a stationary sawtooth (l1 3.5%). "
                     "Contrast bump-shock (frictionless): there the shock "
                     "position drifts and cells stay baseline"),
            "1d-dynwave-legacy": CellPolicy(
                "analytic", {"l1_h": 0.05, "shock_err_m": 25.0}),
            "1d-dynwave-vj": CellPolicy(
                "analytic", {"l1_h": 0.05, "shock_err_m": 25.0}),
            "1d-fv": CellPolicy("analytic",
                                {"l1_h": 0.05, "shock_err_m": 25.0},
                                note="l1 0.65%, shock error 2.5 m — the "
                                     "shock-capturing reference column"),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.05, "shock_err_m": 25.0},
                baseline_tol=BASE_TOL,
                note="MET analytic at dx=2.5 (l1 3.0%, shock 2.5 m); at 1 m "
                     "edges the jump-toe seiche no longer decays and the "
                     "time-mean shock smears over x 430-520 (shock_err 69 m, "
                     "l1 4.5%) — the local-inertial jump limitation "
                     "resolution re-reveals. Analytic gates stay recorded; "
                     "a better 2D scheme flips this cell loudly"),
            "2d-explicit-adv": CellPolicy(
                "xfail", {"l1_h": 0.05, "shock_err_m": 25.0},
                note="never steadies with ADVECTION on (drift 0.21, shock "
                     "smeared 55 m): roll-waves on the supercritical "
                     "upstream half + first-order upwind diffusion — the "
                     "advection-less columns pass this case exactly"),
        }),
    CaseSpec(
        id="macdonald-short-shock",
        swashes_ref="SWASHES 3.2.2 (smooth transition and shock)",
        family="macdonald",
        title="MacDonald 100 m channel, transonic then shock at x = 66.7 m",
        dims=(1, 2), L=100.0, W1d=500.0, W2d=5.0, z=_mac_ss_z,
        n_manning=0.0328,
        upstream=BC("inflow_q", q=2.0),
        downstream=BC("stage", eta=_mac_ss_eta),
        h0=lambda x: np.maximum(_mac_ss_eta - _mac_ss_z(x), 0.0),
        t_end=1800.0, dt_routing=0.02, report_step=10.0,  # c_max ~ 6.3 m/s
        compare_times=(1800.0,), nx=200, refine_nx=(100, 400),
        # Recorded deviation (2026-08-13): at dx=0.5 the NONE block sloshes
        # the shock unboundedly (steady_resid 0.157, mass −0.59%); PARTIAL
        # steadies it (resid 0.004, mass 0.0, shock 0.58 m) at a smooth
        # l1 5.7%. At dx=1 the preference was REVERSED (NONE 2.2% XPASS,
        # PARTIAL 5.2%) — the undamped scheme does not refine through a
        # transonic-plus-shock reach.
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", {"l1_h": 0.05, "shock_err_m": 5.0},
                baseline_tol=BASE_TOL,
                note="steady smooth 5.7% with PARTIAL (shock 0.58 m); the "
                     "damping smears the transonic drawdown past the 5% "
                     "gate — implicit-DW limit, analytic tols recorded "
                     "for promotion"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", {"l1_h": 0.05, "shock_err_m": 5.0},
                baseline_tol=BASE_TOL),
            "1d-fv": CellPolicy("analytic",
                                {"l1_h": 0.05, "shock_err_m": 5.0},
                                note="l1 0.38%, shock 0.08 m at dx=0.5"),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.05, "shock_err_m": 5.0},
                baseline_tol=BASE_TOL,
                note="local-inertial through a hydraulic jump"),
            "2d-explicit-adv": CellPolicy(
                "xfail", {"l1_h": 0.05, "shock_err_m": 5.0},
                note="never steadies with ADVECTION on (drift 0.057): "
                     "advective limit-cycle at the jump — the plain column "
                     "is steady at the same resolution"),
        }),
    CaseSpec(
        id="macdonald-short-sup",
        swashes_ref="SWASHES 3.2.2 (supercritical)",
        family="macdonald",
        title="MacDonald 100 m channel, supercritical throughout",
        dims=(1, 2), L=100.0, W1d=500.0, W2d=5.0, z=_mac_ssup_z,
        n_manning=0.03,
        upstream=BC("inflow_q", q=2.0), downstream=BC("free"),
        h0=None,
        t_end=1800.0, dt_routing=0.02, report_step=10.0,  # c_max ~ 5.9 m/s
        compare_times=(1800.0,), nx=200, refine_nx=(100, 400),
        interior_mask=(0.05, 1.0),
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL,
                note="smooth +6% bias with the recorded PARTIAL deviation "
                     "(under NONE a 0.18 m stationary sawtooth pushes l1 to "
                     "16.5% with q EXACT — the undamped checkerboard at "
                     "dx = 1 m); residual: shallow upstream, deep "
                     "downstream — the damped scheme under-tracks the "
                     "25 m-scale bed variation the long channel (dx = 5) "
                     "never sees"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL),
            "1d-dynwave-vj": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.04}),
            "2d-explicit": CellPolicy(
                "xfail", {"l1_h": 0.04},
                note="fully supercritical — macdonald-long-sup precedent: "
                     "local inertia never steadies without the convective "
                     "term"),
            "2d-explicit-adv": CellPolicy(
                "xfail", {"l1_h": 0.04},
                note="l1 41% at CFL 0.5 (drifting); NOT a CFL-margin issue "
                     "— the CFL 0.25 probe BLEW UP (l1 3.90, drift 2.5; "
                     "runs/_advprobe): the theta q-centred blend damps "
                     "per-STEP, so halving dt halves the dissipation per "
                     "unit time and the advective cycle grows. The "
                     "supercritical-reach instability needs scheme work "
                     "(dt-scaled damping or a dissipative advective flux), "
                     "not a tighter Courant number"),
        }),
    CaseSpec(
        id="macdonald-short-sub2sup",
        swashes_ref="SWASHES 3.2.2 (sub-to-supercritical)",
        family="macdonald",
        title="MacDonald 100 m channel, transonic at x = 50 m",
        dims=(1, 2), L=100.0, W1d=500.0, W2d=5.0, z=_mac_s2s_z,
        n_manning=0.0328,
        upstream=BC("inflow_q", q=2.0), downstream=BC("free"),
        h0=lambda x: np.maximum(
            float(an.macdonald_short_sub2sup_h(np.array([100.0]))[0])
            + _mac_s2s_zL - _mac_s2s_z(x), 0.0),      # downstream puddle
        t_end=1800.0, dt_routing=0.02, report_step=10.0,  # c_max ~ 5.7 m/s
        compare_times=(1800.0,), nx=200, refine_nx=(100, 400),
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        opts_2d={"FROUDE_MAX": "3"},
        cells={
            "1d-dynwave": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL,
                note="transcritical choke precedent (bump-transcritical): "
                     "6.0% smooth with the recorded PARTIAL deviation "
                     "(8.7% + sawtooth under NONE)"),
            "1d-dynwave-legacy": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.04}),
            "2d-explicit": CellPolicy(
                "baseline", {"l1_h": 0.04}, baseline_tol=BASE_TOL,
                note="supercritical downstream half — no-advection limit"),
            "2d-explicit-adv": CellPolicy(
                "xfail", {"l1_h": 0.04},
                note="never steadies with ADVECTION on (drift 0.10): "
                     "roll-wave-like cycle on the supercritical downstream "
                     "half (Vedernikov-stable, so numerical — the upwinded "
                     "convective term sustains it where the advection-less "
                     "scheme damps it)"),
        }),
    CaseSpec(
        id="macdonald-periodic",
        swashes_ref="SWASHES 3.2.3",
        family="macdonald",
        title="MacDonald 5000 m periodic channel, subcritical",
        dims=(1, 2), L=5000.0, W1d=500.0, W2d=10.0, z=_mac_per_z,
        n_manning=0.03,
        upstream=BC("inflow_q", q=2.0),
        downstream=BC("stage", eta=_mac_per_eta),
        h0=lambda x: np.maximum(_mac_per_eta - _mac_per_z(x), 0.0),
        t_end=12000.0, dt_routing=0.04, report_step=120.0,  # c_max ~ 5.2 m/s
        compare_times=(12000.0,), nx=5000, refine_nx=(250,),  # dx=1.0 (2026-08-13 hires)
        cells={
            # ENGINE FINDING (deliberate red, 2026-08-13, dx=1.0 — see
            # runs/_periodic_probe/FINDINGS.md): DW PASSED here at dx=10
            # (l1 0.141%) and FAILS at 15.5% once refined, i.e. it converges
            # AWAY from the analytic solution. Not dt (10x smaller dt moves
            # l1 by 0.012 pts) and not the case: FV solves the same decks at
            # the same dx and converges normally (0.357% -> 0.154%, ~2 mm from
            # analytic where DW is 120-175 mm off). The DW runs are otherwise
            # clean — mass 0.0%, q exact, no sawtooth, steady from t=4000.
            # The over-depth IS the velocity head: v=1.78 m/s => v²/2g =
            # 0.161 m, and the measured bias is 74%/109%/93% of it at
            # dx=5/2.5/1 — a junction chain that transmits no momentum
            # (bend-study precedent) loses the velocity head once and
            # saturates. Refining a DW model ADDS junctions, so subdividing
            # conduits moves the answer by a velocity head in the wrong
            # direction. Kept on the analytic gate: a momentum-transmitting
            # junction treatment would flip this cell loudly.
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.03},
                note="ENGINE FINDING: DW loses ~one velocity head (v²/2g = "
                     "0.161 m) to its 5000-junction chain — l1 0.141% at "
                     "dx=10 vs 15.5% at dx=1, while FV converges normally"),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.03}),
            "1d-fv": CellPolicy("analytic", {"l1_h": 0.03}),
            "2d-explicit": CellPolicy("analytic", {"l1_h": 0.03}),
            "2d-explicit-adv": CellPolicy("analytic", {"l1_h": 0.03}),
        }),
    CaseSpec(
        id="macdonald-rain-sub", swashes_ref="SWASHES 3.3.1",
        family="macdonald-rain",
        title="MacDonald 1000 m channel, subcritical with rain",
        dims=(1,), L=1000.0, W1d=500.0, W2d=10.0, z=_mac_rsub_z,
        n_manning=0.033,
        upstream=BC("inflow_q", q=1.0),
        downstream=BC("stage", eta=_mac_rsub_eta),
        h0=None, rain=0.001,
        t_end=6000.0, dt_routing=0.04, report_step=60.0,
        compare_times=(6000.0,), nx=1000, refine_nx=(200,),  # dx=1.0 (2026-08-13 hires)
        # Recorded deviation (2026-08-13, dx=1.0): same catastrophic undamped
        # checkerboard as macdonald-long-sub at this resolution (all DW
        # columns l1 4.65, and the violent oscillation drives depths above
        # conduit crowns — the surcharge trios even stopped being
        # bit-identical). PARTIAL is the macdonald-long-sup precedent.
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        cells={
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.035},
                note="rain R0 = 1 mm/s as per-node lateral inflows "
                     "R0·dx·W; depth profile is eq. (12) with "
                     "q(x) = 1 + 0.001x. Gate 3.5%: DW sits at 3.01% — the "
                     "same scheme error as macdonald-long-sub's 3% plus the "
                     "half-cell end-weight rain discretization"),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.035}),
            "1d-fv": CellPolicy(
                "analytic", {"l1_h": 0.03},
                note="ENGINE FINDING (deliberate red, 2026-08-12): FV runs "
                     "18.9% deep with q(x) EXACT and the profile smooth — "
                     "same signature at rain-sup (25%). DW on the identical "
                     "deck is at 3%, so the deck is sound: the FV algebraic "
                     "junction mishandles lateral inflow momentum (all 200 "
                     "junctions carry inflows here). Left red pending an "
                     "engine fix"),
        }),
    CaseSpec(
        id="macdonald-rain-sup", swashes_ref="SWASHES 3.3.2",
        family="macdonald-rain",
        title="MacDonald 1000 m channel, supercritical with rain",
        dims=(1,), L=1000.0, W1d=500.0, W2d=10.0, z=_mac_rsup_z,
        n_manning=0.04,
        upstream=BC("inflow_q", q=2.5), downstream=BC("free"),
        h0=None, rain=0.001, rain_start=1500.0,      # paper-recommended tR
        # t_end 12000 (not 6000): the steady-drift windows are [25,50]% vs
        # [50,100]% of t_end — they must not overlap the rain-onset
        # adjustment (at 6000 the drift window STARTED at tR, resid 0.021;
        # at 9000 the finer dx=2.5 grid still read its tail, resid 0.046)
        t_end=12000.0, dt_routing=0.03, report_step=60.0,
        compare_times=(12000.0,), nx=1000, refine_nx=(200,),  # dx=1.0 (2026-08-13 hires)
        interior_mask=(0.05, 1.0),
        # The rained steady state is Vedernikov-UNSTABLE over most of the
        # channel (q grows to 3.5 m²/s while h follows eq. 13: Fr up to 2.1,
        # Ve = (2/3)·Fr up to 1.4 > 1) — physical roll waves ride the mean
        # profile forever (N0300 oscillates ±0.06 m while upstream nodes sit
        # at 1e-4). The time-MEAN is graded (l1 1.7%); the drift gate is
        # sized to the oscillation. dx=1.0 (2026-08-13): the finer grid
        # resolves stronger roll waves — drift 0.163 (max-norm at moving
        # crests) while the time-mean stays l1 2.6%. All FIVE explicit
        # columns (legacy EXTRAN/SLOT + refact EXTRAN/SLOT/DYNAMIC_SLOT)
        # remain IDENTICAL to the last digit even on this chaotic case.
        # Gate re-sized to the dx=1 oscillation.
        steady_gate=0.2,
        opts_1d={"INERTIAL_DAMPING": "PARTIAL"},
        cells={
            "1d-dynwave": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="rain steps on at tR = 1500 s (unit time series riding "
                     "each node's Sfactor); graded on the final rained "
                     "state. 0.8% with the recorded PARTIAL deviation — "
                     "under NONE a 0.16 m stationary sawtooth pushes l1 to "
                     "11% (q exact)"),
            "1d-dynwave-legacy": CellPolicy("analytic", {"l1_h": 0.04}),
            # ENGINE FINDING (deliberate red, 2026-08-13, dx=1.0): same
            # SEMI_IMPLICIT mass leak as macdonald-long-sup, replicated on
            # the second resolved roll-wave case — semi loses 2.10% mass
            # (gate 0.5%) vs -0.003% explicit, with a slightly BETTER
            # time-mean (l1 2.36% vs 2.61%).
            "1d-dynwave-semi": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="ENGINE FINDING: SEMI_IMPLICIT loses 2.10% mass under "
                     "resolved roll waves (explicit: -0.003%); l1 2.36% is "
                     "fine — the red is the mass gate (replicates "
                     "macdonald-long-sup)"),
            "1d-fv": CellPolicy(
                "analytic", {"l1_h": 0.04},
                note="ENGINE FINDING (deliberate red, 2026-08-12): 25% deep "
                     "with exact q — the FV junction lateral-inflow momentum "
                     "defect (see macdonald-rain-sub)"),
        }),
]

mirror_dw_variants(STEADY_CASES)


def reference_profile(case: CaseSpec, x: np.ndarray):
    """(h, q) of the steady analytic solution on grid x."""
    if case.id == "lake-at-rest-immersed":
        return an.lake_at_rest(x, 0.5)
    if case.id == "lake-at-rest-emerged":
        return an.lake_at_rest(x, 0.1)
    if case.id == "bump-subcritical":
        return an.bump_subcritical(x)
    if case.id == "bump-transcritical":
        return an.bump_transcritical(x)
    if case.id == "bump-shock":
        h, q, _ = an.bump_shock(x)
        return h, q
    if case.id == "macdonald-long-sub":
        h, q, _ = an.macdonald_sub(x)
        return h, q
    if case.id == "macdonald-long-sup":
        h, q, _ = an.macdonald_sup(x)
        return h, q
    if case.id == "macdonald-long-sub2sup":
        h, q, _ = an.macdonald_sub2sup(x)
        return h, q
    if case.id == "macdonald-long-jump":
        h, q, _ = an.macdonald_jump(x)
        return h, q
    if case.id == "macdonald-short-shock":
        h, q, _ = an.macdonald_short_shock(x)
        return h, q
    if case.id == "macdonald-short-sup":
        h, q, _ = an.macdonald_short_sup(x)
        return h, q
    if case.id == "macdonald-short-sub2sup":
        h, q, _ = an.macdonald_short_sub2sup(x)
        return h, q
    if case.id == "macdonald-periodic":
        h, q, _ = an.macdonald_periodic(x)
        return h, q
    if case.id == "macdonald-rain-sub":
        h, q, _ = an.macdonald_rain_sub(x)
        return h, q
    if case.id == "macdonald-rain-sup":
        h, q, _ = an.macdonald_rain_sup(x)
        return h, q
    raise KeyError(case.id)


def shock_x(case: CaseSpec) -> float | None:
    if case.id == "bump-shock":
        return an.bump_shock_position()
    if case.id == "macdonald-long-jump":
        return 500.0
    if case.id == "macdonald-short-shock":
        return 200.0 / 3.0
    if case.id.startswith("p2d-"):
        from .cases_pseudo2d import SHOCK_X
        return SHOCK_X.get(case.id)
    return None
