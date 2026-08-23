#!/usr/bin/env python3
"""Analytic references for the transition cases (all SI).

rapid-fill      : filling-bore front trajectory from mass conservation across
                  the moving pressurization front, w = Q / (A_full - A0)
                  (Vasconcelos & Wiggert 2005 storage-tunnel filling bores;
                  friction-free to leading order — ambient water at rest).
surcharge-cycle : fully-pressurized peak-hold HGL, linear at the Manning
                  friction slope from the fixed outfall stage.
inverted-siphon : steady pressurized HGL = stage + Sf * (distance from
                  outfall); uniform diameter, so velocity head is constant
                  and drops out of the head difference.
"""
from __future__ import annotations

import math

import numpy as np

from . import config
from .cases import CASES, Case


def circle_area(h: float, d: float) -> float:
    """Flow area of a circular section at depth h (clamped to [0, d])."""
    h = min(max(h, 0.0), d)
    theta = 2.0 * math.acos(1.0 - 2.0 * h / d)
    return d * d / 8.0 * (theta - math.sin(theta))


def circle_full(d: float) -> tuple[float, float]:
    """(A_full, R_full) of a circular section."""
    a = math.pi * d * d / 4.0
    return a, d / 4.0


def friction_slope(q: float, n: float, d: float) -> float:
    """Manning friction slope of a full circular pipe (SI)."""
    a, r = circle_full(d)
    return (n * q / (a * r ** (2.0 / 3.0))) ** 2


def front_speed(case: Case) -> float:
    """Filling-bore speed w = Q / (A_full - A0) into water at rest."""
    p = case.pipes[0]
    a_full, _ = circle_full(p.diam)
    a0 = circle_area(case.init_depth, p.diam)
    return case.q_grade / (a_full - a0)


def front_trajectory(case: Case, t: np.ndarray) -> np.ndarray:
    """Analytic front position x(t), capped at the pipe length."""
    return np.minimum(front_speed(case) * np.asarray(t, dtype=float), case.L)


def front_arrival(case: Case, x: float) -> float:
    """Analytic arrival time of the front at chainage x."""
    return x / front_speed(case)


def pressurized_hgl(case: Case, q: float | None = None) -> np.ndarray:
    """Steady fully-pressurized head at every node: stage + sum(Sf*L)
    accumulated upstream from the outfall, per-conduit diameters."""
    q = case.q_grade if q is None else q
    heads = np.empty(len(case.node_x()))
    heads[-1] = case.outfall_stage
    for c in reversed(case.conduits()):
        sf = friction_slope(q, c["n"], c["diam"])
        heads[c["i_up"]] = heads[c["i_dn"]] + sf * c["length"]
    return heads


def gen_refs() -> list[str]:
    """Write cases/<id>/reference.csv (+ provenance.yaml) for every case."""
    written = []
    for case in CASES:
        d = config.CASES_DIR / case.id
        d.mkdir(parents=True, exist_ok=True)
        ref = d / "reference.csv"
        x = case.node_x()
        if case.id == "rapid-fill":
            t = np.arange(0.0, case.t_end + case.report_step, case.report_step)
            lines = ["t_s,x_front_m"]
            lines += [f"{ti:g},{xi:.4f}" for ti, xi in
                      zip(t, front_trajectory(case, t))]
            lines.append("")
            p = case.pipes[0]
            drop = friction_slope(case.q_grade, p.n, p.diam) * 400.0
            lines.append("front_speed_ms,head_drop_0_400m")
            lines.append(f"{front_speed(case):.4f},{drop:.4f}")
        else:
            h = pressurized_hgl(case)
            lines = ["node_x_m,head_pressurized_m"]
            lines += [f"{xi:g},{hi:.4f}" for xi, hi in zip(x, h)]
        ref.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(str(ref))
        prov = d / "provenance.yaml"
        prov.write_text(_provenance(case), encoding="utf-8")
        written.append(str(prov))
    return written


def _provenance(case: Case) -> str:
    cites = {
        "rapid-fill": (
            "Vasconcelos, J.G. & Wiggert, D.C. (2005). Numerical simulation of "
            "surges in stormwater storage tunnels. J. Hydraul. Eng. 131(10); "
            "front speed from mass conservation across the moving "
            "pressurization front, w = Q/(A_full - A0)."),
        "surcharge-cycle": (
            "Standard full-pipe energy balance: fully-pressurized HGL is "
            "linear at the Manning friction slope (e.g. SWMM Reference "
            "Manual Vol. II, Hydraulics)."),
        "inverted-siphon": (
            "Standard full-pipe energy balance along an inverted siphon; "
            "modeling precedent: EPA SWMM QA model test4 (INVERTED SIPHON "
            "EXAMPLE)."),
    }
    lines = [
        f"case: {case.id}",
        f"title: {case.title}",
        "family: open-channel/pressurized transition",
        "independent_implementation: true",
        f"citation: >-",
        f"  {cites[case.id]}",
        "parameters:",
        f"  total_length_m: {case.L:g}",
        f"  pipes: {[(p.length, p.diam, p.n, p.z_up, p.z_dn, p.nsplit) for p in case.pipes]}",
        f"  outfall_stage_m: {case.outfall_stage:g}",
        f"  init_depth_m: {case.init_depth:g}",
        f"  q_grade_m3s: {case.q_grade:g}",
        f"  inflow_const_m3s: {case.inflow_const}",
        f"  inflow_ts_min_m3s: {list(case.inflow_ts) if case.inflow_ts else None}",
        f"  t_end_s: {case.t_end:g}",
        f"  routing_step_s: {case.dt_routing:g}",
        f"  report_step_s: {case.report_step:g}",
        f"notes: >-",
        f"  {case.notes}",
    ]
    return "\n".join(lines) + "\n"
