#!/usr/bin/env python3
"""Suite-local paths + repo-root bootstrap. Engine discovery lives in
core/engines.py — this module only adds transitions-suite locations."""
from __future__ import annotations

import sys
from pathlib import Path

SUITE_ROOT = Path(__file__).resolve().parents[1]      # suites/transitions/
REPO_ROOT = SUITE_ROOT.parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CASES_DIR = SUITE_ROOT / "cases"
RUNS_DIR = SUITE_ROOT / "runs"
FIGURES_DIR = SUITE_ROOT / "figures"
SCORES_FILE = SUITE_ROOT / "transitions_scores.json"
REPORT_FILE = SUITE_ROOT / "TRANSITIONS_REPORT.md"

GRAVITY = 9.81  # m/s^2 — all suite math is SI
