#!/usr/bin/env python3
"""2D-reference workflow for ref_source='2d' cases (bend family).

`run_swashes.py gen-2d-ref --cases 'bend*' [--pin] [--force]
                           [--allow-unsteady]`

Per case: build the 2D deck for the true bent geometry into
runs/<id>/_2d_reference/, run the refactored engine, extract the steady
final-50% time-mean centerline profile, and write candidate.csv + a meta
line. --pin is the review gate (mirrors pin-baseline): refuse unsteady
(resid > 0.02) or leaky (|mass| > 1%) candidates unless --allow-unsteady,
report the max |dh| against any existing pin before overwriting, then copy
to cases/<id>/reference_2d.csv and write provenance
(verification_class: cross-solver-2d).
"""
from __future__ import annotations

import fnmatch
import shutil

import numpy as np

from . import config, extract, gen2d, genrefs, metrics
from .runcase2d import STEADY_GATE, extract_for_case
from .solvers import BY_ID

from harness import engines, runner

PIN_MASS_GATE_PCT = 1.0


def _candidate(case, *, force: bool) -> dict:
    d = config.RUNS_DIR / case.id / "_2d_reference"
    d.mkdir(parents=True, exist_ok=True)
    inp = d / "model.inp"
    h5 = d / "surface.h5"
    text = gen2d.build_inp(case, BY_ID["2d-explicit"], "surface.h5")
    ran = False
    if not (inp.exists() and inp.read_text(encoding="utf-8") == text and h5.exists()
            and not force):
        inp.write_text(text, encoding="utf-8")
        r = runner.run(engines.REFACT_EXE, inp, d / "model.rpt",
                       d / "model.out", cwd=d, timeout=3600.0)
        if not r["ok"]:
            raise RuntimeError(f"{case.id}: 2D reference run failed "
                               f"rc={r['returncode']}: {r['stderr'][:200]}")
        ran = True

    res = extract_for_case(case, h5)
    t_end = max(case.compare_times)
    resid = metrics.steady_residual(res["mean_prev"]["h"], res["mean"]["h"],
                                    float(np.nanmax(res["mean"]["h"])))
    mb = res.get("mass_balance") or {}
    mass_pct = (100.0 * float(mb["continuity_error"])
                if "continuity_error" in mb else None)

    cand = d / "candidate.csv"
    extract.write_extracted_csv(cand, {"times": {t_end: res["mean"]}})
    meta = {"case": case.id, "engine_sha": engines.engine_sha(),
            "inp_sha": runner.inp_sha(inp), "steady_resid": resid,
            "mass_pct": mass_pct, "ran": ran, "candidate": cand}
    (d / "candidate_meta.txt").write_text(
        "\n".join(f"{k}: {v}" for k, v in meta.items()) + "\n",
        encoding="utf-8")
    return meta


def generate(case_glob: str | None, *, pin: bool = False, force: bool = False,
             allow_unsteady: bool = False) -> int:
    rc = 0
    for case in genrefs.all_cases():
        if getattr(case, "ref_source", "analytic") != "2d":
            continue
        if case_glob and not fnmatch.fnmatch(case.id, case_glob):
            continue
        try:
            meta = _candidate(case, force=force)
        except RuntimeError as exc:
            print(f"{case.id}: ERROR {exc}")
            rc = 1
            continue
        resid = meta["steady_resid"]
        mass = meta["mass_pct"]
        print(f"{case.id}: candidate resid={resid:.3g} mass={mass} "
              f"engine={meta['engine_sha']}")
        if not pin:
            continue
        problems = []
        if resid > STEADY_GATE:
            problems.append(f"steady_resid {resid:.3g} > {STEADY_GATE}")
        if mass is not None and abs(mass) > PIN_MASS_GATE_PCT:
            problems.append(f"|mass| {mass:.3g}% > {PIN_MASS_GATE_PCT}%")
        if problems and not allow_unsteady:
            print(f"  REFUSED pin: {'; '.join(problems)} "
                  "(--allow-unsteady to override)")
            rc = 1
            continue
        dst = config.CASES_DIR / case.id / "reference_2d.csv"
        if dst.exists():
            old = extract.read_extracted_csv(dst)
            new = extract.read_extracted_csv(meta["candidate"])
            t = max(new)
            dmax = float(np.max(np.abs(
                np.interp(new[t]["x"], old[max(old)]["x"],
                          old[max(old)]["h"]) - new[t]["h"])))
            print(f"  replacing existing pin (max |dh| vs old: {dmax:.3g} m)")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(meta["candidate"], dst)
        genrefs.write_provenance(
            case, verification_class="cross-solver-2d (local-inertial "
                                     "reference — lower-bound bend loss)",
            extra=[f"  engine_sha: {meta['engine_sha']}",
                   f"  inp_sha: {meta['inp_sha']}",
                   "  cfl_number: 0.3",
                   f"  steady_resid: {resid:.6g}",
                   f"  mass_pct: {mass}",
                   f"  planform: theta={case.planform.theta_deg:g} deg, "
                   f"s_bend={case.planform.s_bend:g} m, W={case.planform.W:g} m"])
        print(f"  pinned {dst}")
    return rc
