#!/usr/bin/env python3
"""OpenSWMM Benchmarks — one entry point for CI and local sweeps.

    python run_regression.py --list
    python run_regression.py --suite all
    python run_regression.py --suite parity --tier pr
    python run_regression.py --suite analytical/swashes
    python run_regression.py --suite epa_qa --report-only
    python run_regression.py --suite all --badges badges/
    python run_regression.py --suite all --max-wall 300     # what CI runs

Extra arguments are forwarded to the suite. Exit code is the OR of every
executed suite's gate (harness.scoring.exit_code); a suite whose engines are
missing degrades to UNAVAILABLE cells, never to failure.

`--max-wall` is how CI stays inside its budget: every workflow passes
`--max-wall 300`, and a case MEASURED to cost more than that is skipped there
with a warning. Unset — the default, and how a local sweep runs — nothing is
skipped for runtime. See harness/runtime.py.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from harness import runinfo, scoring, suites  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", default="all",
                    help="suite name under suites/ (may be 'parent/child'), or 'all'")
    ap.add_argument("--exclude", default="", metavar="SUITES",
                    help="comma-separated suites to leave out (CI runs "
                         "'parity' in its own sharded jobs and the rest with "
                         "--suite all --exclude parity)")
    ap.add_argument("--list", action="store_true",
                    help="list available suites and exit")
    ap.add_argument("--ci-resolution", action="store_true",
                    help="run SWASHES cases with a CI grid at that resolution")
    ap.add_argument("--report-only", action="store_true",
                    help="regenerate reports without running sweeps")
    ap.add_argument("--summary", type=Path,
                    help="write the markdown job summary to this file "
                         "(use $GITHUB_STEP_SUMMARY in CI)")
    ap.add_argument("--badges", type=Path,
                    help="write shields.io endpoint JSON to this directory")
    ap.add_argument("--max-wall", type=float, metavar="SECONDS",
                    help="skip cases MEASURED to cost more than this, with a "
                         "warning and a SKIP cell (harness/runtimes.yaml holds "
                         "the measurements). CI passes 300; unset locally, "
                         "where long cases are meant to run.")
    ap.add_argument("--description", metavar="TEXT",
                    help="what this run is for, shown on the dashboard (default: "
                         "$BENCH_RUN_DESCRIPTION, else one generated from the "
                         "trigger, engine and platform)")
    args, passthrough = ap.parse_known_args(argv)
    # Declared here so --help documents it and a typo is rejected rather than
    # silently ignored, but the suites are what act on it — so hand it on.
    if args.max_wall:
        passthrough += ["--max-wall", str(args.max_wall)]

    available = suites.list_suites()
    if args.list:
        for name in available:
            print(name)
        return 0
    if not available:
        print("no suites found under suites/", file=sys.stderr)
        return 2

    names = available if args.suite == "all" else [args.suite]
    excluded = [n for n in args.exclude.split(",") if n]
    names = [n for n in names if n not in excluded]
    # A misspelled --exclude would quietly run the suite it meant to drop.
    unknown = [n for n in names + excluded if n not in available]
    if unknown:
        print(f"unknown suite(s): {', '.join(unknown)}; "
              f"available: {', '.join(available)}", file=sys.stderr)
        return 2

    registry = suites.discover(names)
    rc = 0
    envelopes: list[dict] = []
    crashed: list[str] = []
    # Written before the first suite and again after the last, so a run that
    # never ends still says what it was (see harness/runinfo.py).
    manifest = None
    if not args.report_only:
        manifest = runinfo.collect(
            argv=list(argv if argv is not None else sys.argv[1:]),
            description=args.description, max_wall=args.max_wall,
            tier=_option(passthrough, "--tier"))
        print(f"run: {manifest['description']}")
        runinfo.write(manifest)
    for name in names:
        mod = registry[name]
        suite_args = list(passthrough)
        if name == "analytical/swashes" and args.ci_resolution:
            suite_args.append("--ci-resolution")
        print(f"=== suite: {name} ===")
        try:
            if not args.report_only:
                envelope = mod.run(suite_args)
                if envelope is not None:
                    envelopes.append(envelope)
                    print(scoring.summary(envelope))
                    rc |= scoring.exit_code(envelope)
            for path in mod.report(suite_args) or []:
                print(f"  report: {path}")
        except (Exception, SystemExit) as exc:
            # A suite's argparse error exits through SystemExit. Keep its
            # failure visible and let the remaining suites publish their scores.
            if isinstance(exc, SystemExit) and (len(names) == 1 or exc.code in (None, 0)):
                raise
            import traceback
            traceback.print_exc()
            crashed.append(f"{name}: {type(exc).__name__}: {exc}"[:300])
            rc |= 1

    if envelopes and (args.summary or args.badges):
        from harness import report as report_mod
        if args.summary:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            with args.summary.open("a", encoding="utf-8") as fh:
                fh.write(report_mod.job_summary(envelopes, manifest) + "\n")
        if args.badges:
            written = scoring.write_badges(args.badges, scoring.badges(envelopes))
            print(f"wrote {len(written)} badge(s) to {args.badges}")

    if crashed:
        print(f"{len(crashed)} suite(s) crashed: " + "; ".join(crashed),
              file=sys.stderr)
        if args.summary:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            with args.summary.open("a", encoding="utf-8") as fh:
                fh.write("## Suites that crashed\n\n"
                         + "".join(f"- {c}\n" for c in crashed) + "\n")

    if manifest is not None:
        runinfo.write(runinfo.finish(manifest, exit_code=rc, crashed=crashed))
    return rc


def _option(argv: list[str], name: str) -> str | None:
    """The value of `name` in a forwarded argument list, if given."""
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return None


if __name__ == "__main__":
    from harness import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
