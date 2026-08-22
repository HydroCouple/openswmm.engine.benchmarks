#!/usr/bin/env python3
"""Suite protocol reference — copy this to suites/<name>/suite.py.

A suite exposes exactly two entry points:

    run(argv: list[str]) -> dict | None      # execute the sweep, return a
                                             # harness.scoring envelope
    report(argv: list[str]) -> list[Path]    # regenerate reports/figures

`run_regression.py` discovers suites by scanning for suite.py (one level of
nesting is supported, e.g. suites/analytical/swashes/suite.py -> the suite is
named "analytical/swashes"). No plugin machinery, no registration step.

Conventions every suite follows:
  * every result cell carries `case`, `solver` (or `pair`), `verdict`, and
    `reference_class` — the last one decides whether accuracy metrics are
    meaningful and which badge the cell feeds (see harness.scoring)
  * envelopes are written incrementally via scoring.save_cell so an
    interrupted sweep resumes
  * a missing engine yields UNAVAILABLE cells, never a crash
  * all output goes under results/<suite>/ — user-reviewable, never temp dirs
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from harness import engines, scoring  # noqa: E402

SUITE = "template"
RESULTS = REPO_ROOT / "results" / SUITE


def run(argv: list[str] | None = None) -> dict | None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    scores = RESULTS / "scores.json"
    print(f"[{SUITE}] writing cells to {scores}", file=sys.stderr)

    # for case in cases:
    #     for engine in registry.resolved().values():
    #         cell = {"case": case.id, "solver": engine.id,
    #                 "reference_class": case.reference_class,
    #                 "verdict": ..., ...metrics}
    #         scoring.save_cell(scores, envelope, cell)

    return envelope


def report(argv: list[str] | None = None) -> list[Path]:
    return []


if __name__ == "__main__":
    env = run(sys.argv[1:])
    print(scoring.summary(env))
    sys.exit(scoring.exit_code(env))
