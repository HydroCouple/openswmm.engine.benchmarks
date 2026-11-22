"""The SWASHES analytic references must evaluate on every platform.

The 2026-11-22 Nightly's Linux other-suites job died inside the bump-shock
reference: at the crest (z = 0.2) the depth cubic has a double root at the
critical depth, and np.roots on Linux x86-64 returned it as a conjugate pair a
few 1e-9 off the real axis, which a 1e-9 tolerance threw away as complex. The
same call was real on macOS, so no local run had seen it. The crash ended the
whole `--suite all` run before transitions and reactions.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from suites.analytical.swashes.swasheslib import analytic  # noqa: E402

G = analytic.G
Q_SHOCK, ZM = 0.18, 0.2
HC = (Q_SHOCK * Q_SHOCK / G) ** (1.0 / 3.0)
C_UP = Q_SHOCK * Q_SHOCK / (2.0 * G * HC * HC) + HC + ZM


def test_a_double_root_returned_as_a_near_real_pair_is_kept():
    """Exactly what Linux returned at the crest: the critical depth twice,
    ±3e-9 off the axis. Both copies are the root; neither may be dropped."""
    roots = np.array([HC + 3e-9j, HC - 3e-9j, -HC / 2])
    kept = analytic._positive_real(roots)
    assert kept.size == 2
    assert np.allclose(kept, HC, atol=1e-8)


def test_a_genuinely_complex_pair_is_still_rejected():
    roots = np.array([0.4 + 0.05j, 0.4 - 0.05j, 0.1])
    assert analytic._positive_real(roots).tolist() == [0.1]


@pytest.mark.parametrize("branch", ["sub", "sup"])
def test_the_crest_of_the_shock_profile_is_the_critical_depth(branch):
    h = analytic._bernoulli_h(ZM, Q_SHOCK, C_UP, branch)
    assert abs(h - HC) < 1e-6


def test_bump_shock_reference_evaluates_on_a_grid_that_hits_the_crest():
    x = np.unique(np.concatenate([np.linspace(0.0, 25.0, 501), [10.0]]))
    h, q, x_sh = analytic.bump_shock(x)
    assert np.all(np.isfinite(h)) and np.all(h > 0)
    assert 10.0 < x_sh < 25.0
    assert np.allclose(q, Q_SHOCK)
