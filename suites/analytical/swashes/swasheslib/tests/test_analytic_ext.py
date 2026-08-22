#!/usr/bin/env python3
"""Internal-consistency checks for the Phase-B analytic solutions.

The hydraulic-jump constructions are validated by the steady weak-solution
requirement: with z (and B) continuous at the jump, the momentum flux
F = q²/A + g·I1 must be continuous across it (Rankine–Hugoniot).
The pseudo-2D bed integration is validated against the full steady momentum
identity on a dense grid. Dressler is validated by its limits (corrections
vanish at the still edge; C → ∞ recovers Ritter).
"""
from __future__ import annotations

import numpy as np
import pytest

from swasheslib import analytic as an

G = an.G


# ── Rankine–Hugoniot at the 1D jumps (rectangular, unit width) ─────────────
def _rh_residual_1d(h1: float, h2: float, q: float) -> float:
    f = lambda h: q * q / h + 0.5 * G * h * h            # noqa: E731
    return abs(f(h1) - f(h2)) / f(h2)


def test_macdonald_jump_rh():
    h1 = float(an.macdonald_jump_h(np.array([500.0 - 1e-9]))[0])
    h2 = float(an.macdonald_jump_h(np.array([500.0 + 1e-9]))[0])
    assert h1 < h2                                       # sup → sub
    assert _rh_residual_1d(h1, h2, 2.0) < 2e-3


def test_macdonald_short_shock_rh():
    xs = 200.0 / 3.0
    h1 = float(an.macdonald_short_shock_h(np.array([xs - 1e-9]))[0])
    h2 = float(an.macdonald_short_shock_h(np.array([xs + 1e-9]))[0])
    assert h1 < h2
    assert _rh_residual_1d(h1, h2, 2.0) < 2e-3


# ── sonic points sit at critical depth ─────────────────────────────────────
def test_sonic_points():
    hc = (4.0 / G) ** (1.0 / 3.0)
    assert abs(float(an.macdonald_sub2sup_h(np.array([500.0]))[0]) - hc) < 1e-12
    assert abs(float(an.macdonald_short_sub2sup_h(np.array([50.0]))[0]) - hc) < 1e-12


# ── pseudo-2D: boundary depths quoted in Table 2 ───────────────────────────
def test_p2d_table2_values():
    assert abs(float(an.p2d_sup_short_h(np.array([0.0]))[0]) - 0.503369) < 1e-6
    assert abs(float(an.p2d_sub_long_h(np.array([400.0]))[0]) - 0.904094) < 1e-5
    assert abs(float(an.p2d_jump_long_h(np.array([400.0]))[0]) - 1.2) < 1e-6
    assert abs(float(an.p2d_jump_short_h(np.array([0.0]))[0]) - 0.7) < 1e-12


# ── pseudo-2D: RH balance at the jumps (variable width, trapezoid) ─────────
def _rh_residual_p2d(x_jump: float, h_fn, B_fn, Z: float,
                     q: float = an.P2D_Q) -> float:
    B = float(B_fn(np.array([x_jump]))[0])
    h1 = float(h_fn(np.array([x_jump - 1e-9]))[0])
    h2 = float(h_fn(np.array([x_jump + 1e-9]))[0])
    assert h1 < h2

    def F(h):
        A = h * (B + Z * h)
        I1 = B * h * h / 2.0 + Z * h ** 3 / 3.0
        return q * q / A + G * I1
    return abs(F(h1) - F(h2)) / F(h2)


def test_p2d_jump_short_rh():
    assert _rh_residual_p2d(120.0, an.p2d_jump_short_h, an.p2d_B1, 0.0) < 2e-3


def test_p2d_jump_long_rh():
    assert _rh_residual_p2d(120.0, an.p2d_jump_long_h, an.p2d_B2, 2.0) < 2e-3


# ── pseudo-2D: steady momentum identity of (h, z, B, Z) ────────────────────
P2D_SMOOTH = [
    ("sub-short", an.p2d_sub_short_h, an._p2d_sub_short_dh,
     an.p2d_B1, an._p2d_dB1, 0.0, 200.0, ()),
    ("sup-short", an.p2d_sup_short_h, an._p2d_sup_short_dh,
     an.p2d_B1, an._p2d_dB1, 0.0, 200.0, ()),
    ("trans-short", an.p2d_trans_short_h, an._p2d_trans_short_dh,
     an.p2d_B1, an._p2d_dB1, 0.0, 200.0, ()),
    ("jump-short", an.p2d_jump_short_h, an._p2d_jump_short_dh,
     an.p2d_B1, an._p2d_dB1, 0.0, 200.0, (120.0,)),
    ("sub-long", an.p2d_sub_long_h, an._p2d_sub_long_dh,
     an.p2d_B2, an._p2d_dB2, 2.0, 400.0, ()),
    ("jump-long", an.p2d_jump_long_h, an._p2d_jump_long_dh,
     an.p2d_B2, an._p2d_dB2, 2.0, 400.0, (120.0,)),
]


@pytest.mark.parametrize("name,h_fn,dh_fn,B_fn,dB_fn,Z,L,jumps", P2D_SMOOTH,
                         ids=[c[0] for c in P2D_SMOOTH])
def test_p2d_momentum_identity(name, h_fn, dh_fn, B_fn, dB_fn, Z, L, jumps):
    """d/dx(q²/A + g I1) + g A d(z)/dx + g Sf A − g I2 = 0 away from jumps,
    with I1 = B h²/2 + Z h³/3 and I2 = z-independent wall term h²/2 · B'."""
    q, n = an.P2D_Q, an.P2D_N
    x = np.linspace(0.0, L, 40001)
    h = h_fn(x)
    B = B_fn(x)
    z = an.p2d_bed(x, h_fn, dh_fn, B_fn, dB_fn, Z)
    A = h * (B + Z * h)
    I1 = B * h * h / 2.0 + Z * h ** 3 / 3.0
    P = B + 2.0 * h * np.sqrt(1.0 + Z * Z)
    Sf = q * q * n * n * P ** (4.0 / 3.0) / A ** (10.0 / 3.0)
    Fm = q * q / A + G * I1
    dF = np.gradient(Fm, x)
    dz = np.gradient(z, x)
    I2 = h * h / 2.0 * dB_fn(x)
    resid = dF + G * A * dz + G * Sf * A - G * I2
    scale = float(np.max(np.abs(dF))) or 1.0
    mask = np.ones_like(x, dtype=bool)
    for xj in jumps:                        # exclude the discontinuity stencil
        mask &= np.abs(x - xj) > 3.0 * (x[1] - x[0])
    mask &= (x > x[1]) & (x < x[-2])        # np.gradient one-sided ends
    assert float(np.max(np.abs(resid[mask]))) / scale < 5e-3


# ── 1D MacDonald variants: same identity, wide-channel form ────────────────
MAC1D = [
    ("sub2sup", an.macdonald_sub2sup, 2.0, 0.0218, 1000.0, ()),
    ("jump", an.macdonald_jump, 2.0, 0.0218, 1000.0, (500.0,)),
    ("short-shock", an.macdonald_short_shock, 2.0, 0.0328, 100.0,
     (200.0 / 3.0,)),
    ("short-sup", an.macdonald_short_sup, 2.0, 0.03, 100.0, ()),
    ("short-sub2sup", an.macdonald_short_sub2sup, 2.0, 0.0328, 100.0, ()),
    ("periodic", an.macdonald_periodic, 2.0, 0.03, 5000.0, ()),
]


@pytest.mark.parametrize("name,fn,q,n,L,jumps", MAC1D,
                         ids=[c[0] for c in MAC1D])
def test_macdonald_variant_identity(name, fn, q, n, L, jumps):
    x = np.linspace(0.0, L, 40001)
    h, _, z = fn(x)
    Fm = q * q / h + 0.5 * G * h * h
    dF = np.gradient(Fm, x)
    dz = np.gradient(z, x)
    Sf = n * n * q * q / h ** (10.0 / 3.0)
    resid = dF + G * h * dz + G * Sf * h
    scale = max(float(np.max(np.abs(dF))), G * float(np.max(Sf * h)))
    mask = np.ones_like(x, dtype=bool)
    for xj in jumps:
        mask &= np.abs(x - xj) > 3.0 * (x[1] - x[0])
    mask &= (x > x[1]) & (x < x[-2])
    assert float(np.max(np.abs(resid[mask]))) / scale < 5e-3


def test_macdonald_rain_identity():
    """Rain enters with zero streamwise momentum, so the conservative-form
    identity carries NO extra source: d/dx(q(x)²/h + g h²/2) + g h z' +
    g Sf h = 0 with q(x) = q0 + R0·x. (The −2qR0/(gh²) term in the paper's
    slope expression is exactly the d(q²/h)/dx mass-growth contribution.)"""
    for h_fn, dh_fn, q0, n in [(an.macdonald_sub_h, an._macdonald_sub_dh,
                                1.0, 0.033),
                               (an.macdonald_sup_h, an._macdonald_sup_dh,
                                2.5, 0.04)]:
        x = np.linspace(0.0, 1000.0, 40001)
        h = h_fn(x)
        q = q0 + 0.001 * x
        z = an.macdonald_rain_bed(x, h_fn, dh_fn, q0, 0.001, n)
        Fm = q * q / h + 0.5 * G * h * h
        dF = np.gradient(Fm, x)
        dz = np.gradient(z, x)
        Sf = n * n * q * q / h ** (10.0 / 3.0)
        resid = dF + G * h * dz + G * Sf * h
        scale = float(np.max(np.abs(dF)))
        mask = (x > x[1]) & (x < x[-2])
        assert float(np.max(np.abs(resid[mask]))) / scale < 5e-3


# ── Dressler ───────────────────────────────────────────────────────────────
def test_dressler_alpha_vanish_at_still_edge():
    a1, a2 = an._dressler_alpha(np.array([-1.0]))
    assert abs(float(a1[0])) < 1e-3
    assert abs(float(a2[0])) < 1e-3


def test_dressler_ritter_limit():
    """C → ∞ (frictionless) must recover Ritter in the corrected region."""
    x = np.linspace(0.0, 2000.0, 2001)
    t = 20.0
    hd, ud = an.dressler(x, t, C=1e9)
    hr, ur = an.ritter(x, t, hl=an.DR_HL, x0=an.DR_X0)
    sel = (x > 400.0) & (x < an.DR_X0 + 1.9 * t * np.sqrt(G * an.DR_HL))
    assert float(np.max(np.abs(hd[sel] - hr[sel]))) < 1e-3
    assert float(np.max(np.abs(ud[sel] - ur[sel]))) < 1e-2


def test_dressler_shape():
    x = np.linspace(0.0, 2000.0, 4001)
    for t in (10.0, 20.0, 40.0):
        h, u = an.dressler(x, t)
        c0 = np.sqrt(G * an.DR_HL)
        xb = an.DR_X0 + 2.0 * t * c0
        assert np.all(h >= 0.0)
        assert np.all(h[x > xb] == 0.0)
        wet_front = x[h > 0][-1]
        assert abs(wet_front - xb) < 2.0          # front at xB (grid res)
        assert np.all(np.isfinite(h)) and np.all(np.isfinite(u))
        # depth monotone non-increasing through corrected+tip (no divergence)
        sel = (x > an.DR_X0 - t * c0) & (x < xb)
        dh = np.diff(h[sel])
        assert float(np.max(dh)) < 1e-3
