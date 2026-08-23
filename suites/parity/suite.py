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
import re
import shutil
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
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _skip_list() -> set[str]:
    import yaml
    path = MANIFESTS / "skip_list.yaml"
    if not path.exists():
        return set()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {e["case"] if isinstance(e, dict) else e
            for e in (doc.get("skip") or [])}


#: Free bytes that must remain after a case's outputs are written. A sweep of
#: the whole corpus writes ~167 GiB of .out across two engines, and a single
#: 500k-element case writes >11 GiB per engine — enough to fill a disk before
#: the first comparison runs. The sweep degrades to UNAVAILABLE (an environment
#: limit, not a result) rather than filling the volume it is running on.
DISK_FLOOR_BYTES = 3 * 1024 ** 3


def _free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def _est_out_bytes(case: corpus.Case) -> int:
    """Upper-bound .out size for one engine, from the deck's own geometry.

    period record = 8-byte datetime + 4 bytes per saved variable, where the
    saved-variable count is the .out format invariant used by harness.readers:
    (8+P) per subcatchment, (6+P) per node, (5+P) per link, plus 15 system
    variables. Reporting periods come from the simulation span / REPORT_STEP.
    """
    import datetime as _dt
    try:
        text = case.inp.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0

    def section(name: str) -> str:
        marker = f"[{name}]"
        upper = text.upper()
        i = upper.find(marker)
        if i < 0:
            return ""
        body = text[i + len(marker):]
        j = body.find("\n[")
        return body if j < 0 else body[:j]

    def count(name: str) -> int:
        return sum(1 for ln in section(name).splitlines()
                   if ln.strip() and not ln.strip().startswith(";"))

    opts = dict(re.findall(r"^\s*([A-Z_]+)\s+(\S.*?)\s*$", section("OPTIONS"), re.M))

    def hms(v: str, default: float) -> float:
        try:
            parts = [float(x) for x in v.split(":")] + [0.0, 0.0]
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        except ValueError:
            return default

    try:
        start = _dt.datetime.strptime(
            f"{opts.get('START_DATE', '1/1/2000')} {opts.get('START_TIME', '0:00:00')}",
            "%m/%d/%Y %H:%M:%S")
        end = _dt.datetime.strptime(
            f"{opts.get('END_DATE', opts.get('START_DATE', '1/1/2000'))} "
            f"{opts.get('END_TIME', '24:00:00')}", "%m/%d/%Y %H:%M:%S")
        span = (end - start).total_seconds()
    except ValueError:
        return 0
    step = hms(opts.get("REPORT_STEP", "0:15:00"), 900.0) or 900.0
    periods = max(int(span / step), 1)

    npoll = count("POLLUTANTS")
    nsub = count("SUBCATCHMENTS")
    nnode = sum(count(s) for s in ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS"))
    nlink = sum(count(s) for s in ("CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS"))
    per_period = (nsub * (8 + npoll) + nnode * (6 + npoll)
                  + nlink * (5 + npoll) + 15)
    return periods * (per_period * 4 + 8)


def _prune_outputs(runs: dict, keep: str, failed: bool) -> None:
    """Drop the bulk .out files a sweep no longer needs.

    keep='fail'  retain them only where a comparison did not pass — those are
                 the ones a human drills into. keep='all' retains everything;
                 keep='none' always drops. The .rpt is always kept: it is small
                 and it is the mass-balance and stability evidence.
    """
    if keep == "all" or (keep == "fail" and failed):
        return
    for info in runs.values():
        out = info.get("out")
        if out and Path(out).exists():
            Path(out).unlink()


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
    ap.add_argument("--keep-out", choices=("fail", "all", "none"), default="fail",
                    help="retain bulk .out files: only where a comparison did "
                         "not pass (default), always, or never. .rpt is always "
                         "kept.")
    ap.add_argument("--skip-list", dest="use_skip_list",
                    action=argparse.BooleanOptionalAction, default=True,
                    help="honour manifests/skip_list.yaml (--no-skip-list runs "
                         "the skipped cases, to confirm the listed reason)")
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
    skip = _skip_list() if args.use_skip_list else set()

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

        # Disk guard: refuse a case whose outputs would not fit rather than
        # filling the volume. This is an environment limit, so UNAVAILABLE.
        need = _est_out_bytes(case) * max(len(resolved), 1)
        free = _free_bytes(RESULTS)
        if resolved and free - need < DISK_FLOOR_BYTES:
            scoring.save_cell(scores, envelope, {
                "case": case.id, "solver": "-",
                "reference_class": case.reference_class,
                "verdict": "UNAVAILABLE",
                "note": f"insufficient disk: needs ~{need / 2**30:.1f} GiB, "
                        f"{free / 2**30:.1f} GiB free"})
            continue

        timeout = float(case.meta.get("timeout_s", default_timeout))
        runs: dict[str, dict] = {}
        case_failed = False
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
                # Carried onto the cell so the published mass-balance badge can
                # exclude models that never conserved mass in the first place
                # (see the tag's definition in harness/schemas/tags.yaml).
                "expected_high_continuity":
                    "expected_high_continuity" in case.tags,
                "note": info.get("stderr", "")[:200]})

        for pair in reg.active_comparisons():
            a, b = runs.get(pair.a), runs.get(pair.b)
            if not (a and b) or not (a["ok"] and b["ok"]):
                scoring.save_cell(scores, envelope, {
                    "case": case.id, "pair": f"{pair.a} vs {pair.b}",
                    "reference_class": case.reference_class,
                    "verdict": "UNAVAILABLE",
                    "note": "one or both engines did not produce output"})
                case_failed = True
                continue
            rtol, atol = case.tolerances(pair.rtol, pair.atol)
            res = compare.compare_full(a["out"], b["out"], rtol=rtol, atol=atol)
            gate = (case.meta.get("tolerances") or {}).get("gate", pair.gate)
            verdict = res["verdict"]
            if verdict != "PASS":
                case_failed = True
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

        _prune_outputs(runs, args.keep_out, case_failed)

    print(scoring.summary(envelope))
    return envelope


def report(argv: list[str] | None = None) -> list[Path]:
    """Regenerate the suite's markdown report — STUB (plan step 4)."""
    return []


if __name__ == "__main__":
    env = run(sys.argv[1:])
    sys.exit(scoring.exit_code(env) if env else 0)
