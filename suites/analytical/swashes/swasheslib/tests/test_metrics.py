#!/usr/bin/env python3
"""Grader sanity tests (framework self-verification, plan §self-verification).

Run: python -m swasheslib.tests.test_metrics   (cwd = suites/swashes)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from swasheslib import metrics  # noqa: E402


def test_identity_zero_norms():
    x = np.linspace(0.0, 10.0, 51)
    h = 1.0 + 0.2 * np.sin(x)
    e = metrics.profile_errors(x, h, h.copy(), q=h * 2, q_ref=h * 2)
    assert e["l1_h"] == 0.0 and e["l2_h"] == 0.0 and e["linf_h"] == 0.0
    assert e["l1_q"] == 0.0
    print("identity_zero_norms ok")


def test_one_cell_shift_hand_computed():
    # 5 stations, ref = 1 everywhere; model differs by +0.1 at one station.
    x = np.arange(5, dtype=float)
    h_ref = np.ones(5)
    h = h_ref.copy()
    h[2] += 0.1
    e = metrics.profile_errors(x, h, h_ref)
    assert abs(e["l1_h"] - 0.1 / 5.0) < 1e-15          # 0.1 / sum(ref)=5
    assert abs(e["l2_h"] - np.sqrt(0.01 / 5.0)) < 1e-15
    assert abs(e["linf_h"] - 0.1) < 1e-15
    print("one_cell_shift ok")


def test_wet_mask_excludes_dry_tail():
    x = np.arange(10, dtype=float)
    h_ref = np.where(x < 5, 1.0, 0.0)      # dry tail
    h = h_ref + np.where(x >= 5, 99.0, 0.0)  # huge error only on DRY stations
    e = metrics.profile_errors(x, h, h_ref)
    assert e["l1_h"] == 0.0 and e["n_graded"] == 5
    print("wet_mask ok")


def test_front_error():
    x = np.arange(10, dtype=float)
    h_ref = np.where(x <= 4, 1.0, 0.0)
    h = np.where(x <= 6, 1.0, 0.0)         # model front 2 stations too far
    assert metrics.front_error(x, h, h_ref, dx=1.0, h_dry=1e-3) == 2.0
    print("front_error ok")


def test_shock_location():
    x = np.linspace(0.0, 10.0, 101)
    h = np.where(x < 6.0, 2.0, 1.0)        # jump at 6.0
    xs = metrics.shock_location(x, h, x_ref_shock=5.8, window_frac=0.1, L=10.0)
    assert abs(xs - 6.0) < 0.06
    print("shock_location ok")


def test_grade_gates():
    v, r = metrics.grade({"l1_h": 0.01}, "analytic", {"l1_h": 0.02},
                         mass_pct=0.1)
    assert v == "PASS" and not r
    v, r = metrics.grade({"l1_h": 0.05}, "analytic", {"l1_h": 0.02})
    assert v == "FAIL" and "l1_h" in r[0]
    v, r = metrics.grade({"l1_h": 0.01}, "analytic", {"l1_h": 0.02},
                         mass_pct=2.0)
    assert v == "FAIL" and "mass_pct" in r[0]
    v, r = metrics.grade({"l1_h": 0.01}, "analytic", {"l1_h": 0.02},
                         steady_resid=0.5)
    assert v == "FAIL" and "not steady" in r[0]
    v, r = metrics.grade({"l1_h": 0.01}, "baseline", {"l1_h": 0.02})
    assert v == "BASELINE-PASS"
    print("grade_gates ok")


def test_observed_order():
    p = metrics.observed_order(0.2, 0.04, 0.1, 0.01)   # second order
    assert abs(p - 2.0) < 1e-12
    print("observed_order ok")


if __name__ == "__main__":
    test_identity_zero_norms()
    test_one_cell_shift_hand_computed()
    test_wet_mask_excludes_dry_tail()
    test_front_error()
    test_shock_location()
    test_grade_gates()
    test_observed_order()
    print("ALL metrics tests passed")
