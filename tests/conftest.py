"""Pytest configuration for the harness test suite.

These tests deliberately require NO SWMM engine: the .out fixtures are
synthesized (tests/outfixture.py) and the .rpt fixtures are inline text. That
is what lets CI verify the readers and comparison logic on any runner, and
what lets a contributor validate a submission without building anything.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def outdir(tmp_path: Path) -> Path:
    d = tmp_path / "out"
    d.mkdir()
    return d
