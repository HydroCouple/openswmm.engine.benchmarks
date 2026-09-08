#!/usr/bin/env python3
"""analytical/swashes — shallow-water analytic solutions.

run/report protocol adapter (see harness/suites.py). Cases are graded against
closed-form solutions from Delestre et al. (2013), so `reference.class` is
``analytic``: error norms and observed convergence order are meaningful here,
and these cells are the ones that feed the `verification` badge.

    python run_regression.py --suite analytical/swashes
    python -m suites.analytical.swashes.suite --cases 'bump-*' --solvers 1d-dynwave
"""
from __future__ import annotations

import sys
from pathlib import Path

SUITE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUITE_DIR.parents[2]
sys.path.insert(0, str(SUITE_DIR))
sys.path.insert(0, str(REPO_ROOT))

SUITE = "analytical/swashes"
REFERENCE_CLASS = "analytic"


def _stamp(envelope: dict) -> dict:
    """Mark every cell with its reference class.

    harness.scoring uses this to decide what may be computed from a cell and
    which badge it feeds; a cell without it would silently fall out of the
    verification count.
    """
    if envelope:
        for cell in envelope.get("cells", []):
            cell.setdefault("reference_class", REFERENCE_CLASS)
    return envelope


def run(argv: list[str] | None = None) -> dict | None:
    from swasheslib import runcase
    argv = argv or []
    case_glob = solver_ids = max_wall = None
    if "--cases" in argv:
        case_glob = argv[argv.index("--cases") + 1]
    if "--solvers" in argv:
        solver_ids = argv[argv.index("--solvers") + 1].split(",")
    # Honoured for uniformity with the rest of the platform, though no case
    # here comes close: the slowest cell in this suite is bend00-gentle on
    # 1d-dynwave-vj at ~50 s, a sixth of the 300 s CI threshold. Every case
    # therefore keeps running on Actions and keeps being graded against the
    # Delestre closed-form solutions, which is the whole point of the suite —
    # a SKIP here would silently drop cells out of the verification badge.
    if "--max-wall" in argv:
        max_wall = float(argv[argv.index("--max-wall") + 1])
    return _stamp(runcase.run_matrix(case_glob=case_glob,
                                     solver_ids=solver_ids,
                                     force="--force" in argv,
                                     max_wall=max_wall))


def report(argv: list[str] | None = None) -> list[Path]:
    from swasheslib import report as rep
    return [Path(p) for p in [rep.build()] if p]


def gen_refs(check: bool = False) -> int:
    """Regenerate every case's reference.csv from the analytic formulas.

    Engine-free, and the strongest check available without a build: if the
    published closed-form solutions still reproduce the committed reference
    data, the analytic layer is intact.
    """
    from swasheslib import genrefs
    return genrefs.main(check=check)


if __name__ == "__main__":
    from harness import scoring
    env = run(sys.argv[1:])
    print(scoring.summary(env) if env else "no cells")
    sys.exit(scoring.exit_code(env) if env else 0)
