#!/usr/bin/env python3
"""MiterPlanform geometry checks (bend family)."""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from swasheslib.planform import MiterPlanform  # noqa: E402


def _mk(theta):
    return MiterPlanform(theta_deg=theta, s_bend=60.0, L=120.0, W=4.0)


def test_theta0_is_identity():
    p = _mk(0.0)
    s = np.linspace(0.0, 120.0, 25)
    px, py = p.xy(s, 1.3)
    assert np.allclose(px, s) and np.allclose(py, 1.3)
    assert p.taper_rows(0.5) == 0
    rx, ry = p.row_map(30.0, np.array([-2.0, 0.0, 2.0]), 0.5)
    assert np.allclose(rx, 30.0) and np.allclose(ry, [-2.0, 0.0, 2.0])
    assert np.allclose(p.s_of(np.array([7.0]), np.array([1.0])), 7.0)
    tx, ty = p.tangent_of(np.array([7.0]), np.array([1.0]))
    assert np.allclose(tx, 1.0) and np.allclose(ty, 0.0)


def test_sof_inverts_xy_both_legs():
    for theta in (45.0, 90.0):
        p = _mk(theta)
        # centerline: exact inversion including immediately at the corner
        s = np.array([5.0, 40.0, 59.9, 60.1, 80.0, 119.0])
        px, py = p.xy(s, 0.0)
        assert np.allclose(p.s_of(px, py), s, atol=1e-12)
        # off-centerline: exact away from the miter wedge (|s-60| > W/2 covers
        # the wedge span; inside it points belong to the other leg's region
        # by construction — the mesh's miter split, not an inversion error)
        s = np.array([5.0, 40.0, 55.0, 65.0, 80.0, 119.0])
        px, py = p.xy(s, 1.5)
        assert np.allclose(p.s_of(px, py), s, atol=1e-12)


def test_corner_row_on_miter_line_and_conforming():
    p = _mk(90.0)
    w = np.linspace(-2.0, 2.0, 9)
    # corner row approached from each leg must coincide (shared miter line)
    ax, ay = p.row_map(60.0, w, 0.5)
    # leg B side: d = +0 — emulate by tiny positive offset with alpha at full
    bx, by = p.row_map(60.0 + 1e-12, w, 0.5)
    assert np.allclose(ax, bx, atol=1e-9) and np.allclose(ay, by, atol=1e-9)
    # theta=90: miter line points are (cx - w, w) relative to corner (60, 0)
    assert np.allclose(ax, 60.0 - w) and np.allclose(ay, w)


def test_wall_vertices_stay_on_straight_walls():
    p = _mk(90.0)
    dx = 0.5
    m = p.taper_rows(dx)
    assert m == 8
    for k in range(0, m + 1):
        s_i = 60.0 - k * dx
        px, py = p.row_map(s_i, np.array([-2.0, 2.0]), dx)
        # leg A walls are y = -2 and y = +2
        assert np.allclose(py, [-2.0, 2.0])
    for k in range(1, m + 1):
        s_i = 60.0 + k * dx
        px, py = p.row_map(s_i, np.array([-2.0, 2.0]), dx)
        # leg B (points +y): walls are x = corner_x + 2 and corner_x - 2
        assert np.allclose(px, [62.0, 58.0])


def test_inside_row_spacing_positive():
    for theta in (45.0, 90.0):
        p = _mk(theta)
        dx = 0.5
        m = p.taper_rows(dx)
        xs = []
        for k in range(m + 2, -1, -1):          # approach corner along leg A
            s_i = 60.0 - k * dx
            px, py = p.row_map(s_i, np.array([2.0]), dx)   # inner wall w=+W/2
            xs.append((float(px[0]), float(py[0])))
        d = [math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(xs, xs[1:])]
        assert min(d) > 0.4 * dx


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
