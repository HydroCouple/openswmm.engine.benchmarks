#!/usr/bin/env python3
"""SWASHES suite driver.

  python run_swashes.py run [--cases GLOB] [--solvers id,id] [--force] [--nx-sweep]
  python run_swashes.py report
  python run_swashes.py gen-refs [--cases GLOB] [--check]
  python run_swashes.py pin-baseline --case ID --solver ID
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from swasheslib import genrefs  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the case x solver matrix")
    p_run.add_argument("--cases", default=None, help="case-id glob")
    p_run.add_argument("--solvers", default=None, help="comma-separated ids")
    p_run.add_argument("--force", action="store_true")
    p_run.add_argument("--nx-sweep", action="store_true",
                       help="also run refine_nx resolutions (convergence)")

    sub.add_parser("report", help="regenerate SWASHES_REPORT.md + figures")

    p_ref = sub.add_parser("gen-refs", help="regenerate reference CSVs")
    p_ref.add_argument("--cases", default=None, help="case-id glob")
    p_ref.add_argument("--check", action="store_true",
                       help="2x-density self-consistency check")

    p_pin = sub.add_parser("pin-baseline",
                           help="pin current extracted profile as baseline")
    p_pin.add_argument("--case", required=True)
    p_pin.add_argument("--solver", required=True)

    p_2dr = sub.add_parser("gen-2d-ref",
                           help="build/run/pin 2D references (bend family)")
    p_2dr.add_argument("--cases", default=None, help="case-id glob")
    p_2dr.add_argument("--pin", action="store_true",
                       help="pin candidate to cases/<id>/reference_2d.csv")
    p_2dr.add_argument("--force", action="store_true")
    p_2dr.add_argument("--allow-unsteady", action="store_true")

    sub.add_parser("bend-study",
                   help="regenerate runs/_bend_study/BEND_FINDINGS.md")

    args = ap.parse_args(argv)

    if args.cmd == "gen-refs":
        genrefs.main(args.cases, check=args.check)
        return 0
    if args.cmd == "run":
        from swasheslib import runcase
        envelope = runcase.run_matrix(case_glob=args.cases,
                                      solver_ids=(args.solvers.split(",")
                                                  if args.solvers else None),
                                      force=args.force,
                                      nx_sweep=args.nx_sweep)
        from harness import scoring
        print(scoring.summary(envelope))
        return scoring.exit_code(envelope)
    if args.cmd == "report":
        from swasheslib import report
        print(report.build())
        return 0
    if args.cmd == "pin-baseline":
        from swasheslib import runcase
        print(runcase.pin_baseline(args.case, args.solver))
        return 0
    if args.cmd == "gen-2d-ref":
        from swasheslib import gen2dref
        return gen2dref.generate(args.cases, pin=args.pin, force=args.force,
                                 allow_unsteady=args.allow_unsteady)
    if args.cmd == "bend-study":
        from swasheslib import bendstudy
        print(bendstudy.build())
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
