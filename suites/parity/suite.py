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

from harness import compare, corpus, engines, readers, rptparse, runner, scoring  # noqa: E402

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


#: Files that describe a case rather than feed the engine.
_NON_MODEL = {"metadata.yaml", "provenance.yaml", "README.md"}


def _seed_run_dir(case: corpus.Case, run_dir: Path) -> Path:
    """Copy the model and its colocated data into an isolated run directory.

    Two problems solved at once:

    * **Relative references resolve.** Models write and read files by bare
      name (``SAVE RAINFALL "greenville.rff"``, ``USE RAINFALL "rain.dat"``),
      which resolve against the process working directory. Running from the
      repo root sent them somewhere the model never intended.
    * **The corpus stays read-only.** Running *in* the case directory would
      make every sweep write engine output into ``corpus/``, mutating the
      library it is supposed to be measuring.

    ``reference/`` is deliberately not copied: it holds evidence and reference
    data, never model inputs.
    """
    run_dir.mkdir(parents=True, exist_ok=True)
    for src in case.dir.iterdir():
        if src.is_dir() or src.name in _NON_MODEL:
            continue
        dst = run_dir / src.name
        if not dst.exists():
            shutil.copy2(src, dst)
    return run_dir / case.inp.name


def _usable_output(out: Path) -> tuple[bool, str]:
    """Did the engine actually produce a readable ``.out``?

    A zero exit status is not proof. SWMM can report a fatal input error in
    the ``.rpt`` and still exit 0, leaving no output file — which is exactly
    how a nightly sweep died mid-run with a FileNotFoundError deep inside the
    comparison code, losing every case after it.
    """
    if not out.exists():
        return False, "engine exited 0 but wrote no .out file"
    if out.stat().st_size < 32:
        return False, f"engine wrote a truncated .out ({out.stat().st_size} bytes)"
    try:
        readers.Out(out)
    except Exception as exc:
        return False, f"unreadable .out: {type(exc).__name__}: {exc}"
    return True, ""


def _run_case(case: corpus.Case, engine: engines.Engine, out_dir: Path,
              timeout: float | None) -> dict:
    """Run one case through one engine; return run info + .rpt metrics."""
    out_dir.mkdir(parents=True, exist_ok=True)
    model = _seed_run_dir(case, out_dir)
    rpt = out_dir / f"{case.id}.rpt"
    out = out_dir / f"{case.id}.out"

    # cwd is the seeded run directory so the model's own relative paths work.
    info = runner.run(engine.exe, model, rpt, out, timeout=timeout,
                      cwd=out_dir)
    info["rpt"] = rpt
    info["out"] = out

    parsed = rptparse.parse(rpt)
    info.update({k: v for k, v in parsed.items()
                 if k in ("runoff_err", "routing_err", "worst_quality_err",
                          "pct_not_converging", "avg_iter", "min_dt",
                          "nodes_flooded", "links_instability", "had_error")})

    produced, why = _usable_output(out) if info["launched"] else (False, "")
    info["produced_output"] = produced
    if info["ok"] and not produced:
        # The engine claimed success and did not deliver. Prefer the engine's
        # own explanation from the report over our generic one.
        engine_said = "; ".join(parsed.get("errors", [])[:2])
        info["ok"] = False
        info["stderr"] = (engine_said or why)[:500]
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
        # A sweep that selects nothing must NOT report success. An empty
        # envelope scores as green (exit_code sees no gating cells), so a
        # mis-set tier — or a tier no case has opted into — would publish a
        # clean bill of health for zero models. That is the most dangerous
        # failure a regression platform has, because nothing about the output
        # looks wrong. `tier_pr.yaml` selects 0 cases today for exactly this
        # reason: its query matches 1,361 models, but none list `pr` in their
        # metadata `tiers:` until the PR tier is curated from measured
        # runtimes.
        detail = f"tier {args.tier!r} selected no cases"
        if args.only:
            detail += f" matching --only {args.only!r}"
        print(detail, file=sys.stderr)
        scoring.save_cell(scores, envelope, {
            "case": "-", "solver": "-",
            "reference_class": "self_consistency",
            "verdict": "ERROR",
            "note": detail + " — a sweep over zero cases is not a pass"})
        print(scoring.summary(envelope))
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
        try:
            _sweep_case(case, resolved, reg, scores, envelope,
                        timeout, args.keep_out)
        except Exception as exc:
            # One malformed model, unreadable output, or unforeseen edge case
            # must not end the sweep. A nightly run died exactly this way and
            # took every case after it down with it — hours of work lost, and
            # the surviving partial envelope looked like a completed run.
            import traceback
            traceback.print_exc()
            scoring.save_cell(scores, envelope, {
                "case": case.id, "solver": "-",
                "reference_class": case.reference_class,
                "verdict": "ERROR",
                "note": f"harness error, sweep continued: "
                        f"{type(exc).__name__}: {exc}"[:300]})

    print(scoring.summary(envelope))
    return envelope


def _sweep_case(case, resolved, reg, scores, envelope, timeout,
                keep_out: str) -> bool:
    """Run one case through every engine and evaluate every pair.

    Returns True if anything about this case failed. Raising is allowed —
    `run()` isolates each case so a single failure cannot end the sweep.
    """
    runs: dict[str, dict] = {}
    case_failed = False
    if True:            # noqa: SIM103 — keeps the body's indentation stable
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
            # Require a readable .out from both, not merely a zero exit status
            # — the comparison reads these files and must never be handed a
            # path that does not exist.
            missing = [eid for eid, info in ((pair.a, a), (pair.b, b))
                       if not info or not info.get("produced_output")]
            if missing:
                scoring.save_cell(scores, envelope, {
                    "case": case.id, "pair": f"{pair.a} vs {pair.b}",
                    "reference_class": case.reference_class,
                    "verdict": "UNAVAILABLE",
                    "note": f"no usable output from {', '.join(missing)}"})
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

        _prune_outputs(runs, keep_out, case_failed)
    return case_failed


def report(argv: list[str] | None = None) -> list[Path]:
    """Regenerate the suite's markdown report — STUB (plan step 4)."""
    return []


if __name__ == "__main__":
    env = run(sys.argv[1:])
    sys.exit(scoring.exit_code(env) if env else 0)
