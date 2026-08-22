#!/usr/bin/env python3
"""analytical/transitions — open-channel <-> pressurized flow transitions.

run/report protocol adapter (see harness/suites.py). Cases are graded against
closed-form references — filling-bore front speed, energy-balance HGL — so
`reference.class` is ``analytic`` and these cells feed the `verification`
badge.

This suite is the accuracy anchor for the transition behavior the platform
solicits real-world models of; contributed transition-heavy networks land in
the corpus tagged `transition_pressurized`, graded by parity, not by truth.

    python run_regression.py --suite analytical/transitions
"""
from __future__ import annotations

import sys
from pathlib import Path

SUITE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUITE_DIR.parents[2]
sys.path.insert(0, str(SUITE_DIR))
sys.path.insert(0, str(REPO_ROOT))

SUITE = "analytical/transitions"
REFERENCE_CLASS = "analytic"


def _stamp(envelope: dict) -> dict:
    if envelope:
        for cell in envelope.get("cells", []):
            cell.setdefault("reference_class", REFERENCE_CLASS)
    return envelope


def run(argv: list[str] | None = None) -> dict | None:
    from translib import runcase
    argv = argv or []
    case_glob = solver_ids = None
    if "--cases" in argv:
        case_glob = argv[argv.index("--cases") + 1]
    if "--solvers" in argv:
        solver_ids = argv[argv.index("--solvers") + 1].split(",")
    return _stamp(runcase.run_matrix(case_glob=case_glob,
                                     solver_ids=solver_ids,
                                     force="--force" in argv))


def report(argv: list[str] | None = None) -> list[Path]:
    from translib import report as rep
    return [Path(p) for p in [rep.build()] if p]


def gen_refs(check: bool = False) -> list[str]:
    """Regenerate every case reference from the analytic formulas (engine-free)."""
    from translib import analytic
    return analytic.gen_refs()


if __name__ == "__main__":
    from harness import scoring
    env = run(sys.argv[1:])
    print(scoring.summary(env) if env else "no cells")
    sys.exit(scoring.exit_code(env) if env else 0)
