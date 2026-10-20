#!/usr/bin/env python3
"""Analytic network verification and rain-fed wet-pool invariants."""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))
from harness import engines, scoring, runner
from harness.readers import Out

SUITE = "quality/reactions"
RESULTS = REPO_ROOT / "results" / "quality_reactions"
HERE = Path(__file__).resolve().parent
SOLVERS = ("LEGACY", "EULERIAN_ARD", "LAGRANGIAN")
RATES = {"SEC": .3 / 3600, "MIN": .3 / 60, "HR": .3, "DAY": .3 * 24}


def run(argv=None):
    parser = argparse.ArgumentParser(prog=SUITE)
    parser.add_argument("--exe", type=Path, help="OpenSWMM 6 executable override")
    args, _ = parser.parse_known_args(argv or [])
    RESULTS.mkdir(parents=True, exist_ok=True)
    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    scores = RESULTS / "scores.json"
    if args.exe:
        exe = args.exe.resolve()
    else:
        engine = engines.load().engines["openswmm-v6"]
        engines.resolve(engine)
        exe = engine.exe
    template = (HERE / "pool.inp").read_text()
    reaction = (HERE / "parent_product.rxn").read_text()
    for solver in SOLVERS:
        for unit, rate in RATES.items():
            for override in (False, True):
                case = f"parent_product_{unit}" + ("_override" if override else "")
                cell = {"case": case, "solver": solver, "reference_class": "analytic"}
                if not engines.available(exe):
                    scoring.save_cell(scores, envelope, {**cell, "verdict": "UNAVAILABLE", "note": "OpenSWMM 6 executable missing"})
                    continue
                folder = RESULTS / case / solver
                folder.mkdir(parents=True, exist_ok=True)
                inp, rpt, out = (folder / name for name in ("pool.inp", "pool.rpt", "pool.out"))
                inp.write_text(template.replace("QUALITY_SOLVER LEGACY", f"QUALITY_SOLVER {solver}"))
                rx = reaction.replace("RATE_UNITS HR", f"RATE_UNITS {unit}").replace("PARAMETER k 0.3", f"PARAMETER k {rate:.17g}")
                if override:
                    rx += f"\n[REACTION_PARAMETERS]\nNODE Tank k {rate * 2:.17g}\nLINK Pipe k {rate / 2:.17g}\n"
                (folder / "parent_product.rxn").write_text(rx)
                cell["input_sha256"] = hashlib.sha256(inp.read_bytes() + rx.encode()).hexdigest()
                result = runner.run(exe, inp.resolve(), rpt.resolve(), out.resolve(), cwd=folder, timeout=60)
                if not result["ok"]:
                    scoring.save_cell(scores, envelope, {**cell, "verdict": "ERROR" if result["launched"] else "UNAVAILABLE", "note": result["stderr"]})
                    continue
                try:
                    data = Out(out)
                    if data.err_code or not data.n_periods or data.pollut_ids != ["A", "B"]:
                        raise ValueError("invalid native output or missing named species")
                    worst = 0.0
                    invariant = 0.0
                    for kind, name, base, multiplier in (("node", "Tank", 6, 2 if override else 1), ("link", "Pipe", 5, .5 if override else 1)):
                        a = data.series(kind, name, base)
                        b = data.series(kind, name, base + 1)
                        for i, (av, bv) in enumerate(zip(a, b)):
                            expected = math.exp(-.3 * multiplier * (i + 1) / 60)
                            if not math.isfinite(float(av)) or not math.isfinite(float(bv)):
                                raise ValueError("non-finite reported species")
                            worst = max(worst, abs(float(av) - expected), abs(float(bv) - (1 - expected)))
                            invariant = max(invariant, abs(float(av + bv) - 1))
                    cell.update(verdict="PASS" if worst <= 5.e-4 and invariant <= 2.e-6 else "FAIL",
                                max_abs_error=worst, max_mass_sum_error=invariant,
                                tolerance=5.e-4, periods=data.n_periods)
                except (ValueError, KeyError, IndexError, OSError) as error:
                    cell.update(verdict="ERROR", note=str(error))
                scoring.save_cell(scores, envelope, cell)
    run_wet_pools(exe, scores, envelope)
    return envelope


def run_wet_pools(exe, scores, envelope):
    template = (HERE / "wet_pool.inp").read_text()
    rx = (HERE / "wet_pool.rxn").read_text()
    for solver in SOLVERS:
        cell = {"case": "wet_pool", "solver": solver, "reference_class": "self_consistency"}
        if not engines.available(exe):
            scoring.save_cell(scores, envelope, {**cell, "verdict": "UNAVAILABLE", "note": "OpenSWMM 6 executable missing"})
            continue
        folder = RESULTS / "wet_pool" / solver
        folder.mkdir(parents=True, exist_ok=True)
        inp, rpt, out = (folder / name for name in ("wet_pool.inp", "wet_pool.rpt", "wet_pool.out"))
        inp.write_text(template.replace("QUALITY_SOLVER LEGACY", f"QUALITY_SOLVER {solver}"))
        (folder / "wet_pool.rxn").write_text(rx)
        cell["input_sha256"] = hashlib.sha256(inp.read_bytes() + rx.encode()).hexdigest()
        result = runner.run(exe, inp.resolve(), rpt.resolve(), out.resolve(), cwd=folder, timeout=60)
        if not result["ok"]:
            scoring.save_cell(scores, envelope, {**cell, "verdict": "ERROR" if result["launched"] else "UNAVAILABLE", "note": result["stderr"]})
            continue
        try:
            data = Out(out)
            if data.err_code or not data.n_periods or data.pollut_ids != ["A", "B", "tracer"]:
                raise ValueError("invalid native output or missing named species")
            invariant = {}
            product = {}
            for kind, name, base in (("subcatch", "Catchment", 8), ("node", "Tank", 6)):
                read = data.subcatch_series if kind == "subcatch" else data.node_series
                a, b, tracer = (read(name, base + m) for m in range(3))
                if any(not math.isfinite(float(v)) or v < -1.e-8 for series in (a, b, tracer) for v in series):
                    raise ValueError("non-finite or negative reported species")
                invariant[kind] = max(abs(float(av) + float(bv) - float(tv)) for av, bv, tv in zip(a, b, tracer))
                product[kind] = max(float(v) for v in b)
            ok = invariant["subcatch"] <= 2.e-6 and invariant["node"] <= 2.e-5 and min(product.values()) > .001
            cell.update(verdict="PASS" if ok else "FAIL", max_sum_residual=invariant,
                        peak_product=product, sum_tolerances={"subcatch": 2.e-6, "node": 2.e-5}, periods=data.n_periods)
        except (ValueError, KeyError, IndexError, OSError) as error:
            cell.update(verdict="ERROR", note=str(error))
        scoring.save_cell(scores, envelope, cell)


def report(argv=None):
    envelope = scoring.load(RESULTS / "scores.json")
    if envelope is None:
        return []
    lines = ["# Multispecies verification", "", f"Engine: `{envelope['engine_sha']}`", "",
             "Equal-unit parent/product conversion in an isolated wet pool. A(t) = exp(-kt), B(t) = 1 - A(t).",
             "Each case checks every native reporting period at the storage node and conduit, including the sum A+B.", "",
             "| Case | Quality solver | Result | Maximum concentration error | Sum error |", "| --- | --- | --- | --- | --- |"]
    for cell in envelope["cells"]:
        if cell["reference_class"] != "analytic":
            continue
        lines.append(f"| {cell['case']} | {cell['solver']} | {cell['verdict']} | {cell.get('max_abs_error', '')} | {cell.get('max_mass_sum_error', '')} |")
    lines += ["", "Tolerance: 5e-4 concentration units; 2e-6 for A+B. RATE_UNITS variants have the same physical rate.",
              "The override cases double Tank k and halve Pipe k. They must therefore have different analytic curves.",
              "", "Rain-fed wet-pool cases check the conserved sum A+B=tracer at Catchment and Tank and require positive product B.",
              "These are self-consistency checks, without a closed-form concentration history or accuracy claim.", "",
              "| Quality solver | Result | Catchment sum residual | Tank sum residual |", "| --- | --- | --- | --- |"]
    for cell in envelope["cells"]:
        if cell["reference_class"] != "self_consistency":
            continue
        residual = cell.get("max_sum_residual", {})
        lines.append(f"| {cell['solver']} | {cell['verdict']} | {residual.get('subcatch', '')} | {residual.get('node', '')} |")
    lines += ["", "Wet-pool tolerances: 2e-6 at Catchment; 2e-5 at Tank. Product B must exceed 0.001 in both.",
              "This suite does not qualify porous layers, dry buildup reactions, wall geometry, or checkpoint/output continuation.", ""]
    path = RESULTS / "report.md"
    path.write_text("\n".join(lines))
    return [path]


if __name__ == "__main__":
    envelope = run(sys.argv[1:])
    report()
    print(scoring.summary(envelope))
    raise SystemExit(scoring.exit_code(envelope))
