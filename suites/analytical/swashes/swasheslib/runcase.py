#!/usr/bin/env python3
"""Run one matrix cell: generate deck -> execute -> extract -> grade.

Verdict flow per cell policy mode (harness.scoring taxonomy):
  analytic  -> PASS / FAIL against CellPolicy.tol
  baseline  -> BASELINE-PASS / BASELINE-FAIL against the pinned profile
               (analytic metrics always computed; if they pass -> XPASS, the
               loud promotion signal). Missing pin -> BASELINE-FAIL with
               reason "no baseline pinned" so the pin step can't be skipped.
  xfail     -> XFAIL (or XPASS if the analytic grade passes)
"""
from __future__ import annotations

import dataclasses
import fnmatch
import shutil
import numpy as np

from . import config, extract, gen1d, metrics
from .casespec import CaseSpec, SolverSpec
from .cases_steady import STEADY_CASES, shock_x
from .cases_transient import TRANSIENT_CASES, TWO_D_ONLY_CASES
from .genrefs import (MissingReferenceError, all_cases, case_by_id,
                      reference_blocks)
from .solvers import SOLVERS

from harness import engines, rptparse, runner, runtime, scoring

MASS_GATE_PCT = 0.5
STEADY_GATE = 0.02   # relative drift of the window-MEAN (residual seiche wobble)


def _cell_dir(case_id: str, solver_id: str, nx: int | None = None):
    d = config.RUNS_DIR / case_id / (solver_id if nx is None
                                     else f"{solver_id}_nx{nx}")
    d.mkdir(parents=True, exist_ok=True)
    return d


def _exe_for(solver: SolverSpec):
    return engines.LEGACY_EXE if solver.exe == "legacy" else engines.REFACT_EXE


def _reference_at(case: CaseSpec, x: np.ndarray, t: float):
    """Dense vendored-formula reference interpolated to stations x."""
    blocks = reference_blocks(case)
    tt = min(blocks, key=lambda k: abs(k - t))
    xr, hr, qr = blocks[tt]
    return np.interp(x, xr, hr), np.interp(x, xr, qr)


def _analytic_metrics(case: CaseSpec, res: dict) -> dict:
    """Worst-over-compare-times profile errors vs the analytic reference."""
    a, b = case.interior_mask
    worst: dict = {}
    for t, prof in res["times"].items():
        x = prof["x_h"]
        h_ref, _ = _reference_at(case, x, t)
        q_ref_mid = _reference_at(case, prof["x_q"], t)[1]
        imask = (x >= a * case.L) & (x <= b * case.L)
        q_interp = np.interp(x, prof["x_q"], prof["q"])
        qr_interp = np.interp(x, prof["x_q"], q_ref_mid)
        m = metrics.profile_errors(x, prof["h"], h_ref,
                                   h_dry_frac=case.h_dry_frac,
                                   q=q_interp, q_ref=qr_interp, mask=imask)
        h_dry = case.h_dry_frac * float(np.max(h_ref)) if h_ref.size else 0.0
        if not case.steady and float(np.min(h_ref)) < h_dry:
            m["front_err_dx"] = metrics.front_error(
                x, prof["h"], h_ref, case.dx, h_dry)
        xs = shock_x(case) if case.steady else None
        if xs is not None:
            xm = metrics.shock_location(x, prof["h"], xs, 0.1, case.L)
            m["shock_err_m"] = abs(xm - xs) if np.isfinite(xm) else float("nan")
        for k, v in m.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                worst[k] = max(worst.get(k, -np.inf), v)
            else:
                worst.setdefault(k, v)
    return worst


def _baseline_metrics(case: CaseSpec, solver_id: str, res: dict,
                      ci: bool = False) -> dict | None:
    pin = (config.CASES_DIR / case.id / "baselines" / ("ci" if ci else "")
           / f"{solver_id}.csv")
    if not pin.exists():
        return None
    base = extract.read_extracted_csv(pin)
    worst: dict = {}
    for t, prof in res["times"].items():
        bt = min(base, key=lambda k: abs(k - t))
        b = base[bt]
        h_ref = np.interp(prof["x_h"], b["x"], b["h"])
        m = metrics.profile_errors(prof["x_h"], prof["h"], h_ref,
                                   h_dry_frac=case.h_dry_frac)
        for k, v in m.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                worst[k] = max(worst.get(k, -np.inf), v)
    return worst


def ci_regression(case: CaseSpec, solver_id: str, res: dict, policy,
                  mass_pct, mass_gate) -> tuple[str, list, dict | None]:
    """Grade a CI-resolution run against its CI-resolution pin.

    A coarse run is not an analytic verdict -- the documented 1 m findings
    move with resolution -- so it is a regression check only: same answer as
    the reviewed coarse run, or not.
    """
    bm = _baseline_metrics(case, solver_id, res, ci=True)
    if bm is None:
        return ("BASELINE-FAIL",
                [f"no CI-resolution baseline pinned — review run, then "
                 f"pin-baseline --ci --case {case.id} --solver {solver_id}"], None)
    v, r = metrics.grade(bm, "baseline", policy.baseline_tol or {"l1_h": 0.005},
                         mass_pct=mass_pct, mass_gate=mass_gate)
    return v, r, bm


def _ci_note(case: CaseSpec, full_nx: int) -> str:
    return (f"CI resolution nx={case.nx} (dx {case.L / case.nx:g} m, 1 m is "
            f"nx={full_nx}): regression against a CI-resolution pin; the "
            f"analytic verdict runs weekly at full resolution")


def run_cell(case: CaseSpec, solver: SolverSpec, *, force: bool = False,
             nx: int | None = None, ci: bool = False) -> dict:
    """``ci``: run a case that has ``ci_nx`` at that resolution, graded by
    ``ci_regression``; a case without ``ci_nx`` runs as usual."""
    full_nx = case.nx
    ci = ci and bool(case.ci_nx) and nx is None
    if ci:
        case = dataclasses.replace(case, nx=case.ci_nx)
    cell: dict = {"case": case.id, "solver": solver.id,
                  "nx": nx or case.nx, "dt": case.dt_routing,
                  "mode": None}
    policy = case.cells.get(solver.id)
    if policy is None or solver.dim not in case.dims:
        cell["verdict"] = "SKIP"
        cell["reason"] = "not applicable"
        return cell
    cell["mode"] = "ci-baseline" if ci else policy.mode
    if not solver.available:
        cell["verdict"] = "UNAVAILABLE"
        cell["reason"] = "solver not available in this engine build"
        return cell
    if solver.dim == 2:
        try:
            from . import runcase2d              # wired in step 8
        except ImportError:
            cell["verdict"] = "UNAVAILABLE"
            cell["reason"] = ("2D path pending engine [2D_TRIANGLES] "
                              "INIT_DEPTH support")
            return cell
        return runcase2d.run_cell_2d(case, solver, policy, cell, force=force,
                                     ci=ci, full_nx=full_nx)

    exe = _exe_for(solver)
    if not engines.available(exe):
        cell["verdict"] = "UNAVAILABLE"
        cell["reason"] = f"missing executable {exe}"
        return cell
    if solver.flow_routing == "KINWAVE":
        s_min = gen1d.min_conduit_slope(case, nx)
        if s_min <= 0.0:
            cell["verdict"] = "SKIP"
            cell["reason"] = f"adverse slope (min {s_min:.5f}) — KW inapplicable"
            return cell

    d = _cell_dir(case.id, solver.id, case.nx if ci else
                  None if (nx or case.nx) == case.nx else nx)
    inp = d / "model.inp"
    text = gen1d.build_inp(case, solver, nx)
    sha = None
    if inp.exists() and inp.read_text(encoding="utf-8") == text and not force \
            and (d / "model.out").exists():
        sha = runner.inp_sha(inp)
    else:
        inp.write_text(text, encoding="utf-8")
        sha = runner.inp_sha(inp)
        r = runner.run(exe, inp, d / "model.rpt", d / "model.out",
                       # macdonald-periodic at dx=1 (nx=5000, dt=0.04,
                       # t_end=12000) legitimately needs ~55 min/run
                       # (2026-08-13 hires sweep); 1800 s killed it.
                       timeout=10800.0)
        cell["wall"] = r["wall"]
        if not r["ok"]:
            cell["verdict"] = "ERROR"
            cell["reason"] = f"rc={r['returncode']}: {r['stderr'][:200]}"
            return cell
    cell["inp_sha"] = sha

    rpt = rptparse.parse(d / "model.rpt")
    mass_pct = rpt.get("routing_err")
    cell["mass_pct"] = mass_pct

    the_nx = nx or case.nx
    # pseudo-2D: divide link flows by the LOCAL width (unit discharge Q/B)
    W = (case.width_fn((np.arange(the_nx) + 0.5) * (case.L / the_nx))
         if case.width_fn is not None else case.W1d)
    try:
        res = extract.extract_1d(d / "model.out", the_nx, case.L / the_nx,
                                 W, case.compare_times, case.probes)
    except Exception as exc:                     # missing elements, NaNs…
        cell["verdict"] = "ERROR"
        cell["reason"] = f"extract: {exc}"
        return cell
    if any(not np.isfinite(p["h"]).all() for p in res["times"].values()):
        cell["verdict"] = "ERROR"
        cell["reason"] = "NaN/Inf in extracted profiles"
        return cell
    if case.steady:
        # steady cases are graded on the time-MEAN over the final 50% window
        # (residual seiche oscillates around the steady solution; project
        # precedent: 2D stage-BC tests gate on time-means)
        res["times"] = {max(case.compare_times): res["mean"]}
    extract.write_extracted_csv(d / "extracted.csv", res)

    try:
        am = _analytic_metrics(case, res)
    except MissingReferenceError as exc:
        # 1D results are already cached above — grading resumes once the
        # 2D reference is pinned.
        cell["verdict"] = "ERROR"
        cell["reason"] = str(exc)
        return cell
    cell["metrics"] = {k: (None if isinstance(v, float) and not np.isfinite(v)
                           else v) for k, v in am.items()}
    steady_resid = None
    if case.steady:
        t_end = max(case.compare_times)
        h_ref, _ = _reference_at(case, res["mean"]["x_h"], t_end)
        # drift of the window-mean = has the MEAN state stopped evolving?
        steady_resid = metrics.steady_residual(res["mean_prev"]["h"],
                                               res["mean"]["h"],
                                               float(np.max(h_ref)))
        cell["steady_resid"] = steady_resid

    mass_gate = policy.tol.get("mass_pct", MASS_GATE_PCT)
    a_verdict, a_reasons = metrics.grade(
        am, "analytic", policy.tol, mass_pct=mass_pct,
        mass_gate=mass_gate, steady_resid=steady_resid,
        steady_gate=case.steady_gate or STEADY_GATE)

    if ci:
        cell["analytic_verdict"] = a_verdict
        cell["verdict"], cell["reasons"], bm = ci_regression(
            case, solver.id, res, policy, mass_pct, mass_gate)
        if bm is not None:
            cell["baseline_metrics"] = bm
    elif policy.mode == "analytic":
        cell["verdict"], cell["reasons"] = a_verdict, a_reasons
    elif policy.mode == "xfail":
        cell["verdict"] = "XPASS" if a_verdict == "PASS" else "XFAIL"
        cell["reasons"] = a_reasons
    else:                                        # baseline
        if a_verdict == "PASS":
            cell["verdict"] = "XPASS"            # promotion candidate — loud
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
                                     mass_pct=mass_pct,
                                     mass_gate=mass_gate)
                cell["verdict"], cell["reasons"] = v, r
                cell["baseline_metrics"] = bm
    if ci:
        cell["note"] = _ci_note(case, full_nx)
    elif policy.note:
        cell["note"] = policy.note
    return cell


def run_matrix(case_glob: str | None = None,
               solver_ids: list[str] | None = None, *,
               force: bool = False, nx_sweep: bool = False,
               max_wall: float | None = None,
               ci_resolution: bool = False,
               shard: tuple[int, int] | None = None) -> dict:
    """``shard=(K, N)`` runs every Nth (case, solver) cell starting at the
    Kth, so one case's solvers spread across jobs (the weekly full-resolution
    sweep: macdonald-periodic alone is hours of solvers)."""
    scores_file = config.CI_SCORES_FILE if ci_resolution else config.SCORES_FILE
    envelope = scoring.load(scores_file) or scoring.new_envelope(
        "swashes", engines.engine_sha())
    envelope["engine_sha"] = engines.engine_sha()
    k, n = shard or (1, 1)
    if shard:
        envelope["shard"] = f"{k}/{n}"
    ledger = runtime.load()
    index = -1
    for case in all_cases():
        if case_glob and not fnmatch.fnmatch(case.id, case_glob):
            continue
        too_slow = runtime.skip_reason(ledger, "swashes", case.id, max_wall)
        if too_slow:
            if k != 1:
                continue                  # the first shard records the skip
            runtime.warn(f"{case.id}: {too_slow}")
            scoring.save_cell(scores_file, envelope,
                              {"case": case.id, "solver": "-",
                               "verdict": "SKIP", "note": too_slow})
            continue
        for solver in SOLVERS:
            if solver_ids and solver.id not in solver_ids:
                continue
            index += 1
            if index % n != k - 1:
                continue
            cell = run_cell(case, solver, force=force, ci=ci_resolution)
            scoring.save_cell(scores_file, envelope, cell)
            v = cell["verdict"]
            extras = "; ".join(cell.get("reasons", [])[:1])
            print(f"{case.id:<24s} {solver.id:<18s} {v:<14s} {extras}")
            if nx_sweep and case.refine_nx and solver.dim == 1 \
                    and v not in ("SKIP", "UNAVAILABLE", "ERROR"):
                for rnx in case.refine_nx:
                    if rnx == case.nx:
                        continue
                    sub = run_cell(case, solver, force=force, nx=rnx)
                    sub["case"] = f"{case.id}@nx{rnx}"
                    if sub["verdict"] not in ("ERROR",):
                        sub["verdict"] = "SKIP"   # refinement rows never gate
                        sub["reason"] = "nx-refinement sweep (informational)"
                    scoring.save_cell(scores_file, envelope, sub)
                    print(f"  nx={rnx:<5d} {solver.id:<18s} "
                          f"{sub['verdict']:<14s} "
                          f"l1_h={sub.get('metrics', {}).get('l1_h')}")
    return envelope


def pin_baseline(case_id: str, solver_id: str, ci: bool = False) -> str:
    """Pin a reviewed run's extracted profile. ``ci`` pins the CI-resolution
    run (``run --ci-resolution``) into baselines/ci/."""
    case = case_by_id(case_id)
    if ci and not case.ci_nx:
        raise SystemExit(f"{case_id} has no ci_nx; its CI run is its full run")
    src = _cell_dir(case.id, solver_id, case.ci_nx if ci else None) / "extracted.csv"
    if not src.exists():
        raise SystemExit(f"no extracted.csv for {case_id}/{solver_id} — "
                         "run the cell first")
    dst_dir = config.CASES_DIR / case.id / "baselines" / ("ci" if ci else "")
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / f"{solver_id}.csv"
    shutil.copyfile(src, dst)
    return f"pinned {dst}"
