#!/usr/bin/env python3
"""parity — engine-vs-engine sweep over the model corpus.

The central regression pathway: every case in the tier is run through every
resolved engine in the registry, then every declared comparison pair is
evaluated element-by-element and period-by-period.

Graded on three of the platform's five dimensions:
  * parity      every subcatchment/node/link/system variable (incl. pollutants)
                at every reported period, against the pair's tolerances
  * mass balance runoff / routing / quality continuity from the .rpt
  * stability    % steps not converging, iterations, timestep collapse, crashes

Cases are selected by TAG QUERY from manifests/tier_*.yaml, never by path.

    python run_regression.py --suite parity --tier pr
    python -m suites.parity.suite --tier nightly --only extran1,test1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from harness import compare, corpus, engines, rptparse, runner, scoring  # noqa: E402

SUITE = "parity"
SUITE_DIR = Path(__file__).resolve().parent
MANIFESTS = SUITE_DIR / "manifests"
RESULTS = REPO_ROOT / "results" / SUITE


def _manifest(tier: str) -> dict:
    import yaml
    path = MANIFESTS / f"tier_{tier}.yaml"
    if not path.exists():
        raise SystemExit(f"no manifest for tier {tier!r} ({path})")
    return yaml.safe_load(path.read_text()) or {}


def _skip_list() -> set[str]:
    import yaml
    path = MANIFESTS / "skip_list.yaml"
    if not path.exists():
        return set()
    doc = yaml.safe_load(path.read_text()) or {}
    return {e["case"] if isinstance(e, dict) else e
            for e in (doc.get("skip") or [])}


def _run_case(case: corpus.Case, engine: engines.Engine, out_dir: Path,
              timeout: float | None) -> dict:
    """Run one case through one engine; return run info + .rpt metrics."""
    out_dir.mkdir(parents=True, exist_ok=True)
    rpt = out_dir / f"{case.id}.rpt"
    out = out_dir / f"{case.id}.out"
    info = runner.run(engine.exe, case.inp, rpt, out, timeout=timeout)
    info["rpt"] = rpt
    info["out"] = out
    info.update({k: v for k, v in rptparse.parse(rpt).items()
                 if k in ("runoff_err", "routing_err", "worst_quality_err",
                          "pct_not_converging", "avg_iter", "min_dt",
                          "nodes_flooded", "links_instability", "had_error")})
    return info


def run(argv: list[str] | None = None) -> dict | None:
    ap = argparse.ArgumentParser(prog="parity")
    ap.add_argument("--tier", default="pr")
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--engines", help="comma-separated engine ids to resolve")
    args, _ = ap.parse_known_args(argv or [])

    manifest = _manifest(args.tier)
    reg = engines.resolve_all(
        engines.load(),
        only=args.engines.split(",") if args.engines else None)

    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    RESULTS.mkdir(parents=True, exist_ok=True)
    scores = RESULTS / f"scores_{args.tier}.json"

    cases = corpus.select(corpus.load(), manifest.get("select"), tier=args.tier)
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c.id in wanted]
    skip = _skip_list()

    resolved = reg.resolved()
    if not resolved:
        print("no engines resolved — every cell UNAVAILABLE", file=sys.stderr)
    if not cases:
        print(f"no cases selected for tier {args.tier!r} "
              "(corpus migration is plan step 3)", file=sys.stderr)
        return envelope

    default_timeout = float(manifest.get("timeout_s", 600))
    for case in cases:
        if case.id in skip:
            scoring.save_cell(scores, envelope,
                              {"case": case.id, "solver": "-",
                               "reference_class": case.reference_class,
                               "verdict": "SKIP", "note": "skip-list"})
            continue

        timeout = float(case.meta.get("timeout_s", default_timeout))
        runs: dict[str, dict] = {}
        for eid, engine in resolved.items():
            info = _run_case(case, engine, RESULTS / case.id / eid, timeout)
            runs[eid] = info
            scoring.save_cell(scores, envelope, {
                "case": case.id, "solver": eid,
                "reference_class": case.reference_class,
                # a launch failure is an environment problem, not a
                # result: UNAVAILABLE, which does not gate CI
                "verdict": ("PASS" if info["ok"]
                            else "ERROR" if info.get("launched", True)
                            else "UNAVAILABLE"),
                "wall": info.get("wall"),
                "continuity_err": info.get("routing_err"),
                "runoff_err": info.get("runoff_err"),
                "quality_err": info.get("worst_quality_err"),
                "pct_not_converging": info.get("pct_not_converging"),
                "note": info.get("stderr", "")[:200]})

        for pair in reg.active_comparisons():
            a, b = runs.get(pair.a), runs.get(pair.b)
            if not (a and b) or not (a["ok"] and b["ok"]):
                scoring.save_cell(scores, envelope, {
                    "case": case.id, "pair": f"{pair.a} vs {pair.b}",
                    "reference_class": case.reference_class,
                    "verdict": "UNAVAILABLE",
                    "note": "one or both engines did not produce output"})
                continue
            rtol, atol = case.tolerances(pair.rtol, pair.atol)
            res = compare.compare_full(a["out"], b["out"], rtol=rtol, atol=atol)
            gate = (case.meta.get("tolerances") or {}).get("gate", pair.gate)
            verdict = res["verdict"]
            if verdict == "FAIL" and gate != "fail":
                verdict = "BASELINE-PASS"     # differences recorded, not gated
            worst = res["worst_offenders"][0] if res["worst_offenders"] else {}
            scoring.save_cell(scores, envelope, {
                "case": case.id, "pair": f"{pair.a} vs {pair.b}",
                "reference_class": case.reference_class,
                "verdict": verdict, "gate": gate,
                "max_rel": worst.get("max_rel", 0.0),
                "worst_var": worst.get("var"),
                "worst_element": worst.get("element"),
                "first_div_period": worst.get("first_div_period"),
                "total_cells": res["total_cells"],
                "total_over_tol": res["total_over_tol"],
                "dialects": res["dialects"],
                "note": "; ".join(res["fault"])})

    print(scoring.summary(envelope))
    return envelope


def report(argv: list[str] | None = None) -> list[Path]:
    """Regenerate the suite's markdown report — STUB (plan step 4)."""
    return []


if __name__ == "__main__":
    env = run(sys.argv[1:])
    sys.exit(scoring.exit_code(env) if env else 0)
