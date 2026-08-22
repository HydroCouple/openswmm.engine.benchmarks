#!/usr/bin/env python3
"""2D matrix-cell runner: gen2d deck -> engine CLI -> UGRID h5 -> grade.

Shares the verdict flow of runcase (analytic / baseline / xfail); mass gate
uses the 2D mass-balance ledger's continuity_error (fraction -> percent).
"""
from __future__ import annotations

import numpy as np

from . import config, extract, gen2d, metrics
from .casespec import CaseSpec, SolverSpec, CellPolicy

from harness import engines, runner

MASS_GATE_PCT = 0.5
STEADY_GATE = 0.02


def extract_for_case(case: CaseSpec, h5) -> dict:
    """Case-aware 2D extraction: strip-mean bed for z2d cases, centerline
    arc-length binning + tangential flux for planform (bend) cases. Shared
    by run_cell_2d and the gen-2d-ref reference workflow."""
    if case.z2d is not None:
        def bed_fn(xm, _c=case):
            ys = np.linspace(0.0, _c.W2d, 41)
            X, Y = np.meshgrid(xm, ys)
            return _c.z2d(X, Y).mean(axis=0)
    else:
        bed_fn = case.z            # bend cases: z is s-parameterized
    kw = {}
    if case.planform is not None:
        kw = {"s_of": case.planform.s_of,
              "tangent_of": case.planform.tangent_of}
    return extract.extract_2d_strip(h5, case.L, case.nx, case.compare_times,
                                    case.probes, bed_fn=bed_fn, **kw)


def run_cell_2d(case: CaseSpec, solver: SolverSpec, policy: CellPolicy,
                cell: dict, *, force: bool = False) -> dict:
    from .runcase import (_analytic_metrics, _baseline_metrics, _cell_dir,
                          _reference_at)

    exe = engines.REFACT_EXE
    if not engines.available(exe):
        cell["verdict"] = "UNAVAILABLE"
        cell["reason"] = f"missing executable {exe}"
        return cell

    d = _cell_dir(case.id, solver.id)
    inp = d / "model.inp"
    h5 = d / "surface.h5"
    text = gen2d.build_inp(case, solver, "surface.h5")
    if inp.exists() and inp.read_text() == text and h5.exists() and not force:
        pass
    else:
        inp.write_text(text)
        r = runner.run(exe, inp, d / "model.rpt", d / "model.out",
                       # periodic 2D strip at 1 m edges (~50k cells, CFL dt)
                       # runs multi-hour (2026-08-13 hires sweep)
                       cwd=d, timeout=21600.0,
                       extra_env={k: v for k, v in solver.env.items()})
        cell["wall"] = r["wall"]
        if not r["ok"]:
            cell["verdict"] = "ERROR"
            cell["reason"] = f"rc={r['returncode']}: {r['stderr'][:200]}"
            return cell
    cell["inp_sha"] = runner.inp_sha(inp)

    try:
        res = extract_for_case(case, h5)
    except Exception as exc:
        cell["verdict"] = "ERROR"
        cell["reason"] = f"extract: {exc}"
        return cell
    if any(not np.isfinite(p["h"]).all() for p in res["times"].values()):
        cell["verdict"] = "ERROR"
        cell["reason"] = "NaN/Inf in extracted profiles"
        return cell

    mb = res.get("mass_balance") or {}
    mass_pct = None
    if "continuity_error" in mb:
        mass_pct = 100.0 * float(mb["continuity_error"])
    cell["mass_pct"] = mass_pct
    cell["avg_dt_2d"] = mb.get("solver_avg_h")

    if case.steady:
        res["times"] = {max(case.compare_times): res["mean"]}
    extract.write_extracted_csv(d / "extracted.csv", res)

    am = _analytic_metrics(case, res)
    cell["metrics"] = {k: (None if isinstance(v, float) and not np.isfinite(v)
                           else v) for k, v in am.items()}
    steady_resid = None
    if case.steady:
        t_end = max(case.compare_times)
        h_ref, _ = _reference_at(case, res["mean"]["x_h"], t_end)
        steady_resid = metrics.steady_residual(res["mean_prev"]["h"],
                                               res["mean"]["h"],
                                               float(np.max(h_ref)))
        cell["steady_resid"] = steady_resid

    mass_gate = policy.tol.get("mass_pct", MASS_GATE_PCT)
    a_verdict, a_reasons = metrics.grade(
        am, "analytic", policy.tol, mass_pct=mass_pct, mass_gate=mass_gate,
        steady_resid=steady_resid,
        steady_gate=case.steady_gate or STEADY_GATE)

    if policy.mode == "analytic":
        cell["verdict"], cell["reasons"] = a_verdict, a_reasons
    elif policy.mode == "xfail":
        cell["verdict"] = "XPASS" if a_verdict == "PASS" else "XFAIL"
        cell["reasons"] = a_reasons
    else:
        if a_verdict == "PASS":
            cell["verdict"] = "XPASS"
            cell["reasons"] = ["analytic tolerances met — promote this cell"]
        else:
            bm = _baseline_metrics(case, solver.id, res)
            if bm is None:
                cell["verdict"] = "BASELINE-FAIL"
                cell["reasons"] = ["no baseline pinned — review run, then "
                                   f"pin-baseline --case {case.id} "
                                   f"--solver {solver.id}"]
            else:
                v, r = metrics.grade(bm, "baseline",
                                     policy.baseline_tol or {"l1_h": 0.005},
                                     mass_pct=mass_pct, mass_gate=mass_gate)
                cell["verdict"], cell["reasons"] = v, r
                cell["baseline_metrics"] = bm
    if policy.note:
        cell["note"] = policy.note
    return cell
