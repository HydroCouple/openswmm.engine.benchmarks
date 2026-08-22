#!/usr/bin/env python3
"""performance — SCAFFOLD STUB.

Wall-clock measurement across synthetic scale models (grid_10k..500k,
*_heavy) and representative real networks. Produces timing series for the
github-action-benchmark trend dashboard; correctness is not graded here.

Migration source and status: see README.md in this directory and
plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md (Migration inventory).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from harness import engines, scoring  # noqa: E402

SUITE = "performance"
RESULTS = REPO_ROOT / "results" / SUITE.replace("/", "_")


def run(argv: list[str] | None = None) -> dict | None:
    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    print(f"[{SUITE}] scaffold stub — not yet migrated; no cells produced",
          file=sys.stderr)
    return envelope


def report(argv: list[str] | None = None) -> list[Path]:
    return []


if __name__ == "__main__":
    env = run(sys.argv[1:])
    sys.exit(scoring.exit_code(env) if env else 0)
