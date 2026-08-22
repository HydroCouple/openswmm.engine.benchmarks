#!/usr/bin/env python3
"""The CI gate itself: prove that a real difference FAILS and clean output PASSES.

Every other test here checks that the readers and the comparison see what is in
a file. This one checks the consequence: that a difference big enough to matter
actually turns into a nonzero exit code, and that one small enough does not.

A gate nobody has watched fail is not known to work, and the parity gate is the
whole point of the platform — so its behaviour is pinned here, engine-free, and
runs on every PR.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from harness import compare, scoring
from tests.outfixture import expected, write_out


def _envelope(a: Path, b: Path, *, rtol=1e-9, atol=1e-12, gate="fail") -> dict:
    """Grade one pair exactly as suites/parity/suite.py does, and score it."""
    res = compare.compare_full(a, b, rtol=rtol, atol=atol)
    verdict = res["verdict"]
    if verdict == "FAIL" and gate != "fail":
        verdict = "BASELINE-PASS"
    env = scoring.new_envelope("parity", "test-sha")
    env["cells"].append({
        "case": "synthetic", "pair": "a vs b", "verdict": verdict,
        "reference_class": "self_consistency", "gate": gate,
        "max_rel": (res["worst_offenders"][0]["max_rel"]
                    if res["worst_offenders"] else 0.0),
        "total_over_tol": res["total_over_tol"],
        "total_cells": res["total_cells"]})
    return env


def test_identical_output_passes_and_exits_zero(outdir: Path):
    a = write_out(outdir / "a.out")
    b = write_out(outdir / "b.out")
    env = _envelope(a, b)
    cell = env["cells"][0]
    assert cell["verdict"] == "PASS"
    assert cell["total_over_tol"] == 0
    assert cell["total_cells"] > 0, "a gate over zero cells proves nothing"
    assert scoring.exit_code(env) == 0


def test_planted_difference_fails_and_exits_nonzero(outdir: Path):
    """One cell moved well past tolerance must fail the job."""
    target = ("node", 1, 2, 3)
    a = write_out(outdir / "a.out")
    b = write_out(outdir / "b.out",
                  perturb={target: expected(*target) + 1.0})
    env = _envelope(a, b)
    cell = env["cells"][0]
    assert cell["verdict"] == "FAIL"
    assert cell["total_over_tol"] == 1, "exactly one cell was perturbed"
    assert scoring.exit_code(env) == 1


def test_reverting_the_perturbation_restores_green(outdir: Path):
    """The same comparison goes back to PASS once the difference is removed."""
    target = ("node", 1, 2, 3)
    a = write_out(outdir / "a.out")
    bad = write_out(outdir / "bad.out",
                    perturb={target: expected(*target) + 1.0})
    assert scoring.exit_code(_envelope(a, bad)) == 1
    good = write_out(outdir / "good.out")           # perturbation reverted
    assert scoring.exit_code(_envelope(a, good)) == 0


def test_difference_inside_tolerance_does_not_fail(outdir: Path):
    """The gate must not fire on a difference the tolerances admit."""
    target = ("node", 1, 2, 3)
    base = expected(*target)
    a = write_out(outdir / "a.out")
    b = write_out(outdir / "b.out", perturb={target: base})   # identical value
    env = _envelope(a, b, rtol=1e-3, atol=1e-6)
    assert env["cells"][0]["verdict"] == "PASS"
    assert scoring.exit_code(env) == 0


def test_non_gating_pair_records_the_difference_without_failing(outdir: Path):
    """gate='report' downgrades a real FAIL to BASELINE-PASS, not to silence."""
    target = ("link", 0, 1, 2)
    a = write_out(outdir / "a.out")
    b = write_out(outdir / "b.out",
                  perturb={target: expected(*target) + 5.0})
    env = _envelope(a, b, gate="report")
    cell = env["cells"][0]
    assert cell["verdict"] == "BASELINE-PASS"
    assert cell["total_over_tol"] == 1, "the difference is still recorded"
    assert scoring.exit_code(env) == 0


@pytest.mark.parametrize("verdict, expect", [
    ("PASS", 0), ("SKIP", 0), ("UNAVAILABLE", 0), ("XFAIL", 0),
    ("FAIL", 1), ("BASELINE-FAIL", 1), ("ERROR", 1), ("XPASS", 1),
])
def test_exit_policy_per_verdict(verdict, expect):
    """UNAVAILABLE must never gate; ERROR and XPASS always must."""
    env = scoring.new_envelope("parity", "sha")
    env["cells"].append({"case": "c", "solver": "e", "verdict": verdict})
    assert scoring.exit_code(env) == expect


# ── mass-balance badge ─────────────────────────────────────────────────────

def _mb_cell(case: str, err: float, *, by_design: bool = False) -> dict:
    return {"case": case, "solver": "openswmm-v6", "verdict": "PASS",
            "reference_class": "self_consistency", "continuity_err": err,
            "expected_high_continuity": by_design}


def _mb_badge(cells: list[dict]) -> dict:
    env = scoring.new_envelope("parity", "sha")
    env["cells"] = cells
    return scoring.badges([env])["mass-balance"]


def test_mass_balance_badge_reports_the_worst_graded_case():
    b = _mb_badge([_mb_cell("a", -0.4), _mb_cell("b", 3.2)])
    assert b["message"] == "worst 3.20%"
    assert b["color"] == scoring.BADGE_YELLOW


def test_expected_high_continuity_does_not_set_the_badge():
    """A model that never conserved mass must not define the engine's number."""
    b = _mb_badge([_mb_cell("ok", -0.4),
                   _mb_cell("allow-ponding-high-ce", -104835.884, by_design=True)])
    assert "104835" not in b["message"], "a by-design case set the badge"
    assert b["message"] == "worst 0.40% · 1 by design"
    assert b["color"] == scoring.BADGE_GREEN


def test_the_exclusion_is_disclosed_not_hidden():
    """Excluded cases are counted on the badge, the way `unchecked` is."""
    b = _mb_badge([_mb_cell("ok", 0.1),
                   _mb_cell("x", -300.0, by_design=True),
                   _mb_cell("y", -200.0, by_design=True)])
    assert b["message"].endswith("· 2 by design")


def test_all_cases_excluded_is_grey_not_green():
    """Excluding everything must not read as a clean bill of health."""
    b = _mb_badge([_mb_cell("x", -300.0, by_design=True)])
    assert b["color"] == scoring.BADGE_GREY
    assert b["message"] == "none graded · 1 by design"
