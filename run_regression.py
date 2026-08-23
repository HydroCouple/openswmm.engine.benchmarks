#!/usr/bin/env python3
"""OpenSWMM Benchmarks — one entry point for CI and local sweeps.

    python run_regression.py --list
    python run_regression.py --suite all
    python run_regression.py --suite parity --tier pr
    python run_regression.py --suite analytical/swashes
    python run_regression.py --suite epa_qa --report-only
    python run_regression.py --suite all --badges badges/

Extra arguments are forwarded to the suite. Exit code is the OR of every
executed suite's gate (harness.scoring.exit_code); a suite whose engines are
missing degrades to UNAVAILABLE cells, never to failure.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from harness import scoring, suites  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suite", default="all",
                    help="suite name under suites/ (may be 'parent/child'), or 'all'")
    ap.add_argument("--list", action="store_true",
                    help="list available suites and exit")
    ap.add_argument("--report-only", action="store_true",
                    help="regenerate reports without running sweeps")
    ap.add_argument("--summary", type=Path,
                    help="write the markdown job summary to this file "
                         "(use $GITHUB_STEP_SUMMARY in CI)")
    ap.add_argument("--badges", type=Path,
                    help="write shields.io endpoint JSON to this directory")
    args, passthrough = ap.parse_known_args(argv)

    available = suites.list_suites()
    if args.list:
        for name in available:
            print(name)
        return 0
    if not available:
        print("no suites found under suites/", file=sys.stderr)
        return 2

    names = available if args.suite == "all" else [args.suite]
    unknown = [n for n in names if n not in available]
    if unknown:
        print(f"unknown suite(s): {', '.join(unknown)}; "
              f"available: {', '.join(available)}", file=sys.stderr)
        return 2

    registry = suites.discover(names)
    rc = 0
    envelopes: list[dict] = []
    for name in names:
        mod = registry[name]
        print(f"=== suite: {name} ===")
        if not args.report_only:
            envelope = mod.run(passthrough)
            if envelope is not None:
                envelopes.append(envelope)
                print(scoring.summary(envelope))
                rc |= scoring.exit_code(envelope)
        for path in mod.report(passthrough) or []:
            print(f"  report: {path}")

    if envelopes and (args.summary or args.badges):
        from harness import report as report_mod
        if args.summary:
            args.summary.parent.mkdir(parents=True, exist_ok=True)
            with args.summary.open("a", encoding="utf-8") as fh:
                fh.write(report_mod.job_summary(envelopes) + "\n")
        if args.badges:
            written = scoring.write_badges(args.badges, scoring.badges(envelopes))
            print(f"wrote {len(written)} badge(s) to {args.badges}")

    return rc


if __name__ == "__main__":
    from harness import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
