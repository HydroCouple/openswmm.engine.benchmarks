#!/usr/bin/env python3
"""Run one matrix cell: generate deck -> execute -> extract -> grade.

Verdicts (harness.scoring taxonomy): mode analytic -> PASS/FAIL against the
case tolerances; mode xfail -> XFAIL (XPASS if the analytic grade passes).
Timing: the case's timing_reps applies to every solver column (best-of-N)
so the fv vs fv-lts wall-clock comparison is fair.
"""
from __future__ import annotations

import fnmatch

import numpy as np

from . import analytic, config, extract, gen
from .cases import CASES, Case, case_by_id
from .solvers import SOLVERS, SolverSpec

from harness import engines, rptparse, runner, scoring


def _cell_dir(case_id: str, solver_id: str):
    d = config.RUNS_DIR / case_id / solver_id
    d.mkdir(parents=True, exist_ok=True)
    return d


def _exe_for(solver: SolverSpec):
    return engines.LEGACY_EXE if solver.exe == "legacy" else engines.REFACT_EXE


def _metrics(case: Case, res: dict, rpt: dict) -> dict:
    """Per-case comparison metrics vs the analytic reference."""
    m: dict = {}
    x = case.node_x()
    z = case.node_z()
    if case.id == "rapid-fill":
        xf = extract.front_series(res, case)
        for st in case.front_stations:            # informational
            m[f"front_t_x{st:g}"] = extract.arrival_time(res["t"], xf, st)
        w_ref = analytic.front_speed(case)
        fit = (xf >= 150.0) & (xf <= 450.0)
        if fit.sum() >= 3:
            w_fit = float(np.polyfit(res["t"][fit], xf[fit], 1)[0])
        else:
            w_fit = float("nan")
        m["front_speed"] = w_fit
        m["front_speed_err"] = (abs(w_fit - w_ref) / w_ref
                                if np.isfinite(w_fit) else float("inf"))
        # post-fill friction slope: head drop between x=0 and x=400 m
        i400 = int(np.argmin(np.abs(x - 400.0)))
        h_end = res["heads"][:, res["t"] >= case.t_end - 60.0].mean(axis=1)
        drop_ref = analytic.friction_slope(
            case.q_grade, case.pipes[0].n, case.pipes[0].diam) * 400.0
        m["head_drop"] = float(h_end[0] - h_end[i400])
        m["head_drop_err"] = float(abs(m["head_drop"] - drop_ref))
    elif case.id == "surcharge-cycle":
        h_ref = analytic.pressurized_hgl(case)
        t = res["t"]
        hold = (t >= 1500.0) & (t <= 2700.0)      # 2.0 m3/s peak hold
        h_mean = res["heads"][:, hold].mean(axis=1)
        grade_nodes = [0] + case.joint_nodes()
        m["head_hold_err"] = float(max(abs(h_mean[i] - h_ref[i])
                                       for i in grade_nodes))
        h0 = res["heads"][0, hold]
        m["head_hold_range"] = float(h0.max() - h0.min())   # ringing, disclosed
        crowns = z + case.node_diam()
        h_final = res["heads"][:, -1]
        m["relief_ok"] = bool(all(h_final[i] < crowns[i] + 0.05
                                  for i in case.joint_nodes()))
        # counted from the results, not the .rpt (legacy wording differs):
        # a link is surcharged when its reported depth reaches the barrel
        diam = np.array([c["diam"] for c in case.conduits()])
        m["links_surcharged"] = int(
            (res["depths"].max(axis=1) >= 0.999 * diam).sum())
    elif case.id == "inverted-siphon":
        h_ref = analytic.pressurized_hgl(case)
        h_mean = extract.mean_heads(res, case.steady_window)
        grade_nodes = case.joint_nodes()
        m["head_steady_err"] = float(max(abs(h_mean[i] - h_ref[i])
                                         for i in grade_nodes))
        # barrel = the level middle pipe; full when head clears its crown
        barrel_i = case.joint_nodes()[1]                # node at drop-leg base
        m["barrel_full"] = bool(h_mean[barrel_i] >
                                z[barrel_i] + case.node_diam()[barrel_i])
    return m


def _grade(case: Case, solver_id: str, m: dict,
           mass_pct: float | None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    tol = case.tol_for(solver_id)
    if case.id == "rapid-fill":
        if not (m["front_speed_err"] <= tol["front_speed_frac"]):
            reasons.append(f"front speed {m['front_speed']:.2f} m/s off by "
                           f"{m['front_speed_err']:.0%} "
                           f"(tol {tol['front_speed_frac']:.0%})")
        if not (m["head_drop_err"] <= tol["head_drop"]):
            reasons.append(f"post-fill friction head drop off by "
                           f"{m['head_drop_err']:.3f} m (tol {tol['head_drop']})")
    elif case.id == "surcharge-cycle":
        if not (m["head_hold_err"] <= tol["head_hold"]):
            reasons.append(f"hold-mean head off by {m['head_hold_err']:.3f} m "
                           f"(tol {tol['head_hold']})")
        if not m["links_surcharged"]:
            reasons.append("no links surcharged — case did not pressurize")
        if not m["relief_ok"]:
            reasons.append("heads still above crown at end — no relief")
    elif case.id == "inverted-siphon":
        if not (m["head_steady_err"] <= tol["head_steady"]):
            reasons.append(f"steady head off by {m['head_steady_err']:.3f} m "
                           f"(tol {tol['head_steady']})")
        if not m["barrel_full"]:
            reasons.append("siphon barrel not running full")
    gate = tol.get("mass_pct", 2.0)
    if mass_pct is None:
        reasons.append("no routing continuity in .rpt")
    elif abs(mass_pct) > gate:
        reasons.append(f"routing continuity {mass_pct:+.2f}% (gate {gate}%)")
    return ("PASS" if not reasons else "FAIL"), reasons


def run_cell(case: Case, solver: SolverSpec, *, force: bool = False) -> dict:
    cell: dict = {"case": case.id, "solver": solver.id,
                  "mode": case.modes.get(solver.id)}
    if cell["mode"] is None:
        cell["verdict"] = "SKIP"
        cell["reason"] = "not applicable"
        return cell
    exe = _exe_for(solver)
    if not engines.available(exe):
        cell["verdict"] = "UNAVAILABLE"
        cell["reason"] = f"missing executable {exe}"
        return cell

    d = _cell_dir(case.id, solver.id)
    inp = d / "model.inp"
    text = gen.build_inp(case, solver)
    cached = (inp.exists() and inp.read_text() == text and not force
              and (d / "model.out").exists())
    if not cached:
        inp.write_text(text)
        r = runner.run(exe, inp, d / "model.rpt", d / "model.out",
                       reps=case.timing_reps, timeout=600.0)
        cell["wall"] = r["wall"]
        if not r["ok"]:
            cell["verdict"] = "ERROR"
            cell["reason"] = f"rc={r['returncode']}: {r['stderr'][:200]}"
            return cell
    cell["inp_sha"] = runner.inp_sha(inp)

    rpt = rptparse.parse(d / "model.rpt")
    cell["mass_pct"] = rpt.get("routing_err")
    try:
        res = extract.read_run(d / "model.out", case)
    except Exception as exc:
        cell["verdict"] = "ERROR"
        cell["reason"] = f"extract: {exc}"
        return cell
    if not np.isfinite(res["heads"]).all():
        cell["verdict"] = "ERROR"
        cell["reason"] = "NaN/Inf in node heads"
        return cell
    extract.write_extracted_csv(d / "extracted.csv", res, case)

    m = _metrics(case, res, rpt)
    cell["metrics"] = {k: (None if isinstance(v, float) and not np.isfinite(v)
                           else v) for k, v in m.items()}
    verdict, reasons = _grade(case, solver.id, m, cell["mass_pct"])
    if cell["mode"] == "xfail":
        cell["verdict"] = "XPASS" if verdict == "PASS" else "XFAIL"
    else:
        cell["verdict"] = verdict
    cell["reasons"] = reasons
    return cell


def run_matrix(case_glob: str | None = None,
               solver_ids: list[str] | None = None, *,
               force: bool = False) -> dict:
    envelope = scoring.load(config.SCORES_FILE) or scoring.new_envelope(
        "transitions", engines.engine_sha())
    envelope["engine_sha"] = engines.engine_sha()
    for case in CASES:
        if case_glob and not fnmatch.fnmatch(case.id, case_glob):
            continue
        for solver in SOLVERS:
            if solver_ids and solver.id not in solver_ids:
                continue
            cell = run_cell(case, solver, force=force)
            scoring.save_cell(config.SCORES_FILE, envelope, cell)
            extras = "; ".join(cell.get("reasons", [])[:1]) or \
                cell.get("reason", "")
            print(f"{case.id:<18s} {solver.id:<12s} "
                  f"{cell['verdict']:<10s} {extras}")
    print(scoring.summary(envelope))
    return envelope
