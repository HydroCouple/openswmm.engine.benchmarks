#!/usr/bin/env python3
"""Analytic reference solutions — independent Python implementations of the
formulas published in Delestre et al. (2013), doi 10.1002/fld.3741 (SWASHES).
All SI; every function takes a caller-supplied dense grid so references can be
sampled far finer than any tested model (paper Remark 1).

NOTE (license): these are implementations of open-literature equations; no
output of the CeCILL-V2 SWASHES C++ tool is used or vendored.
"""
from __future__ import annotations

import numpy as np

from .config import GRAVITY as G


# ═══════════════════════════════════════════════════════════════════════════
# §3.1 — bumps (L = 25 m, frictionless)
# ═══════════════════════════════════════════════════════════════════════════
def bump_z(x: np.ndarray) -> np.ndarray:
    z = 0.2 - 0.05 * (x - 10.0) ** 2
    return np.where((x > 8.0) & (x < 12.0), np.maximum(z, 0.0), 0.0)


def lake_at_rest(x: np.ndarray, eta: float,
                 z_fn=bump_z) -> tuple[np.ndarray, np.ndarray]:
    """§3.1.1/3.1.2 — h = max(eta − z, 0), q = 0."""
    h = np.maximum(eta - z_fn(x), 0.0)
    return h, np.zeros_like(h)


def _positive_real_roots(coeffs) -> np.ndarray:
    r = np.roots(coeffs)
    r = r[np.abs(r.imag) < 1e-9].real
    return np.sort(r[r > 1e-12])


def _bernoulli_h(z: float, q: float, const: float, branch: str) -> float:
    """Root of h^3 + (z − const) h^2 + q^2/(2g) = 0.
    const = q²/(2g h_ref²) + h_ref (+ zM for the transcritical form).
    branch: 'sub' (largest positive root) or 'sup' (smallest)."""
    roots = _positive_real_roots([1.0, z - const, 0.0, q * q / (2.0 * G)])
    if roots.size == 0:
        raise ValueError(f"no positive root (z={z}, q={q}, const={const})")
    return float(roots[-1] if branch == "sub" else roots[0])


def bump_subcritical(x: np.ndarray, q: float = 4.42,
                     hL: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """§3.1.3 — subcritical flow over the bump."""
    z = bump_z(x)
    const = q * q / (2.0 * G * hL * hL) + hL
    h = np.array([_bernoulli_h(zi, q, const, "sub") for zi in z])
    return h, np.full_like(h, q)


def bump_transcritical(x: np.ndarray,
                       q: float = 1.53) -> tuple[np.ndarray, np.ndarray]:
    """§3.1.4 — transcritical without shock (critical at the crest x = 10)."""
    z = bump_z(x)
    zM = 0.2
    hc = (q * q / G) ** (1.0 / 3.0)
    const = q * q / (2.0 * G * hc * hc) + hc + zM
    h = np.array([_bernoulli_h(zi, q, const,
                               "sub" if xi <= 10.0 else "sup")
                  for xi, zi in zip(x, z)])
    return h, np.full_like(h, q)


def bump_shock_position(q: float = 0.18, hL: float = 0.33) -> float:
    """§3.1.5 — Rankine–Hugoniot shock location on (10, 25)."""
    zM = 0.2
    hc = (q * q / G) ** (1.0 / 3.0)
    c_up = q * q / (2.0 * G * hc * hc) + hc + zM     # transcritical branch
    c_dn = q * q / (2.0 * G * hL * hL) + hL          # downstream subcritical

    def rh(xs: float) -> float | None:
        """RH residual, or None where the downstream subcritical branch does
        not exist yet (near the crest the downstream energy is insufficient —
        the shock necessarily sits further downhill)."""
        z = float(bump_z(np.array([xs]))[0])
        try:
            h1 = _bernoulli_h(z, q, c_up, "sup")
            h2 = _bernoulli_h(z, q, c_dn, "sub")
        except ValueError:
            return None
        return q * q * (1.0 / h1 - 1.0 / h2) + 0.5 * G * (h1 * h1 - h2 * h2)

    bracket = None
    prev = None
    for xr in np.linspace(10.0 + 1e-6, 25.0 - 1e-6, 4001):
        fr = rh(xr)
        if fr is None:
            prev = None
            continue
        if prev is not None and prev[1] * fr <= 0.0:
            bracket = (prev[0], xr)
            break
        prev = (xr, fr)
    if bracket is None:
        raise ValueError("no RH sign change — shock not bracketed")
    a, b = bracket
    for _ in range(200):
        m = 0.5 * (a + b)
        fa, fm = rh(a), rh(m)
        if fa is not None and fm is not None and fa * fm <= 0.0:
            b = m
        else:
            a = m
    return 0.5 * (a + b)


def bump_shock(x: np.ndarray, q: float = 0.18,
               hL: float = 0.33) -> tuple[np.ndarray, np.ndarray, float]:
    """§3.1.5 — transcritical with shock; returns (h, q, x_shock)."""
    z = bump_z(x)
    zM = 0.2
    hc = (q * q / G) ** (1.0 / 3.0)
    c_up = q * q / (2.0 * G * hc * hc) + hc + zM
    c_dn = q * q / (2.0 * G * hL * hL) + hL
    x_sh = bump_shock_position(q, hL)
    h = np.empty_like(x, dtype=float)
    for k, (xi, zi) in enumerate(zip(x, z)):
        if xi <= 10.0:
            h[k] = _bernoulli_h(zi, q, c_up, "sub")
        elif xi < x_sh:
            h[k] = _bernoulli_h(zi, q, c_up, "sup")
        else:
            h[k] = _bernoulli_h(zi, q, c_dn, "sub")
    return h, np.full_like(h, q), x_sh


# ═══════════════════════════════════════════════════════════════════════════
# §3.2.1 — MacDonald long channels (L = 1000 m, Manning friction, R = h)
# ═══════════════════════════════════════════════════════════════════════════
_C13 = (4.0 / G) ** (1.0 / 3.0)


def macdonald_sub_h(x: np.ndarray) -> np.ndarray:
    """Eq. (12): subcritical depth profile, q = 2, n = 0.033."""
    return _C13 * (1.0 + 0.5 * np.exp(-16.0 * (x / 1000.0 - 0.5) ** 2))


def _macdonald_sub_dh(x: np.ndarray) -> np.ndarray:
    u = x / 1000.0 - 0.5
    return _C13 * 0.5 * np.exp(-16.0 * u * u) * (-32.0 * u) / 1000.0


def macdonald_sup_h(x: np.ndarray) -> np.ndarray:
    """Eq. (13): supercritical depth profile, q = 2.5, n = 0.04."""
    return _C13 * (1.0 - 0.2 * np.exp(-36.0 * (x / 1000.0 - 0.5) ** 2))


def _macdonald_sup_dh(x: np.ndarray) -> np.ndarray:
    u = x / 1000.0 - 0.5
    return _C13 * (-0.2) * np.exp(-36.0 * u * u) * (-72.0 * u) / 1000.0


def macdonald_bed(x: np.ndarray, h_fn, dh_fn, q: float,
                  n: float) -> np.ndarray:
    """Integrate eq. (11): dz/dx = (q²/(g h³) − 1) h'(x) − Sf, with Manning
    Sf = n² q² / h^(10/3) (wide channel, R = h). Trapezoid on the caller's
    (dense) grid; datum-anchored so min z = 0."""
    h = h_fn(x)
    dz = (q * q / (G * h ** 3) - 1.0) * dh_fn(x) - n * n * q * q / h ** (10.0 / 3.0)
    z = np.concatenate([[0.0], np.cumsum(0.5 * (dz[1:] + dz[:-1]) * np.diff(x))])
    return z - z.min()


def macdonald_sub(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """§3.2.1 subcritical: (h, q, z). q = 2 m²/s, n = 0.033."""
    h = macdonald_sub_h(x)
    z = macdonald_bed(x, macdonald_sub_h, _macdonald_sub_dh, 2.0, 0.033)
    return h, np.full_like(h, 2.0), z


def macdonald_sup(x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """§3.2.1 supercritical: (h, q, z). q = 2.5 m²/s, n = 0.04."""
    h = macdonald_sup_h(x)
    z = macdonald_bed(x, macdonald_sup_h, _macdonald_sup_dh, 2.5, 0.04)
    return h, np.full_like(h, 2.5), z


# ── §3.2.1 remaining long-channel variants (q = 2 m²/s, n = 0.0218) ─────────
def macdonald_sub2sup_h(x: np.ndarray) -> np.ndarray:
    """§3.2.1 subcritical-to-supercritical: smooth transonic at x = 500."""
    u = x / 1000.0 - 0.5
    return np.where(x <= 500.0,
                    _C13 * (1.0 - np.tanh(3.0 * u) / 3.0),
                    _C13 * (1.0 - np.tanh(6.0 * u) / 6.0))


def _macdonald_sub2sup_dh(x: np.ndarray) -> np.ndarray:
    u = x / 1000.0 - 0.5
    d1 = -_C13 / 1000.0 / np.cosh(3.0 * u) ** 2
    d2 = -_C13 / 1000.0 / np.cosh(6.0 * u) ** 2
    return np.where(x <= 500.0, d1, d2)


_JUMP_A = (-0.348427, 0.552264, -0.55558)


def macdonald_jump_h(x: np.ndarray) -> np.ndarray:
    """§3.2.1 supercritical-to-subcritical: hydraulic jump at x = 500
    (discontinuous depth; Rankine–Hugoniot verified in tests)."""
    u = x / 1000.0 - 0.5
    h_sup = _C13 * (0.9 - np.exp(-x / 250.0) / 6.0)
    poly = np.zeros_like(np.asarray(x, dtype=float))
    for k, a in enumerate(_JUMP_A, start=1):
        poly = poly + a * np.exp(-20.0 * k * u)
    h_sub = _C13 * (1.0 + poly + 0.8 * np.exp(x / 1000.0 - 1.0))
    return np.where(x < 500.0, h_sup, h_sub)


def _macdonald_jump_dh(x: np.ndarray) -> np.ndarray:
    u = x / 1000.0 - 0.5
    d_sup = _C13 * np.exp(-x / 250.0) / 1500.0
    d_poly = np.zeros_like(np.asarray(x, dtype=float))
    for k, a in enumerate(_JUMP_A, start=1):
        d_poly = d_poly + a * (-20.0 * k / 1000.0) * np.exp(-20.0 * k * u)
    d_sub = _C13 * (d_poly + 0.8 / 1000.0 * np.exp(x / 1000.0 - 1.0))
    return np.where(x < 500.0, d_sup, d_sub)


def macdonald_sub2sup(x: np.ndarray) -> tuple[np.ndarray, np.ndarray,
                                              np.ndarray]:
    h = macdonald_sub2sup_h(x)
    z = macdonald_bed(x, macdonald_sub2sup_h, _macdonald_sub2sup_dh,
                      2.0, 0.0218)
    return h, np.full_like(h, 2.0), z


def macdonald_jump(x: np.ndarray) -> tuple[np.ndarray, np.ndarray,
                                           np.ndarray]:
    h = macdonald_jump_h(x)
    z = macdonald_bed(x, macdonald_jump_h, _macdonald_jump_dh, 2.0, 0.0218)
    return h, np.full_like(h, 2.0), z


# ── §3.2.2 MacDonald short channels (L = 100 m, q = 2 m²/s) ─────────────────
_SS_A = (0.674202, 21.7112, 14.492, 1.4305)     # a1, a2, a3, a4 (§3.2.2 shock)
_X_SS = 200.0 / 3.0                             # shock station


def macdonald_short_shock_h(x: np.ndarray) -> np.ndarray:
    """§3.2.2 'smooth transition and shock': subcritical → transonic →
    shock at x = 200/3 → subcritical. n = 0.0328."""
    a1, a2, a3, a4 = _SS_A
    u = x / 100.0 - 2.0 / 3.0
    h_up = _C13 * (4.0 / 3.0 - x / 100.0) - 9.0 * x / 1000.0 * u
    h_dn = _C13 * (a1 * u ** 4 + a1 * u ** 3 - a2 * u ** 2 + a3 * u + a4)
    return np.where(x < _X_SS, h_up, h_dn)


def _macdonald_short_shock_dh(x: np.ndarray) -> np.ndarray:
    a1, a2, a3, a4 = _SS_A
    u = x / 100.0 - 2.0 / 3.0
    d_up = -_C13 / 100.0 - 9.0 / 1000.0 * u - 9.0 * x / 1000.0 / 100.0
    d_dn = _C13 * (4.0 * a1 * u ** 3 + 3.0 * a1 * u ** 2 - 2.0 * a2 * u
                   + a3) / 100.0
    return np.where(x < _X_SS, d_up, d_dn)


def macdonald_short_sup_h(x: np.ndarray) -> np.ndarray:
    """§3.2.2 supercritical throughout. n = 0.03."""
    return _C13 * (1.0 - np.exp(-4.0 * (x / 100.0 - 0.5) ** 2) / 4.0)


def _macdonald_short_sup_dh(x: np.ndarray) -> np.ndarray:
    u = x / 100.0 - 0.5
    return _C13 * (-0.25) * np.exp(-4.0 * u * u) * (-8.0 * u) / 100.0


def macdonald_short_sub2sup_h(x: np.ndarray) -> np.ndarray:
    """§3.2.2 subcritical-to-supercritical (sonic at x = 50). n = 0.0328."""
    return _C13 * (1.0 - (x - 50.0) / 200.0 + (x - 50.0) ** 2 / 30000.0)


def _macdonald_short_sub2sup_dh(x: np.ndarray) -> np.ndarray:
    return _C13 * (-1.0 / 200.0 + 2.0 * (x - 50.0) / 30000.0)


def macdonald_short_shock(x):
    h = macdonald_short_shock_h(x)
    z = macdonald_bed(x, macdonald_short_shock_h, _macdonald_short_shock_dh,
                      2.0, 0.0328)
    return h, np.full_like(h, 2.0), z


def macdonald_short_sup(x):
    h = macdonald_short_sup_h(x)
    z = macdonald_bed(x, macdonald_short_sup_h, _macdonald_short_sup_dh,
                      2.0, 0.03)
    return h, np.full_like(h, 2.0), z


def macdonald_short_sub2sup(x):
    h = macdonald_short_sub2sup_h(x)
    z = macdonald_bed(x, macdonald_short_sub2sup_h,
                      _macdonald_short_sub2sup_dh, 2.0, 0.0328)
    return h, np.full_like(h, 2.0), z


# ── §3.2.3 periodic long channel (L = 5000 m, q = 2 m²/s, n = 0.03) ─────────
def macdonald_periodic_h(x: np.ndarray) -> np.ndarray:
    return 9.0 / 8.0 + np.sin(np.pi * x / 500.0) / 4.0


def _macdonald_periodic_dh(x: np.ndarray) -> np.ndarray:
    return np.pi / 2000.0 * np.cos(np.pi * x / 500.0)


def macdonald_periodic(x):
    h = macdonald_periodic_h(x)
    z = macdonald_bed(x, macdonald_periodic_h, _macdonald_periodic_dh,
                      2.0, 0.03)
    return h, np.full_like(h, 2.0), z


# ── §3.3 MacDonald with rain (L = 1000 m, R0 = 0.001 m/s) ───────────────────
def macdonald_rain_bed(x: np.ndarray, h_fn, dh_fn, q0: float, R0: float,
                       n: float) -> np.ndarray:
    """Eq. (7) with rain: dz/dx = (q²/(gh³) − 1) h' − 2 q R0/(g h²) − Sf,
    with q(x) = q0 + R0·x (eq. 14) and Manning Sf (wide channel, R = h)."""
    h = h_fn(x)
    q = q0 + R0 * x
    dz = ((q * q / (G * h ** 3) - 1.0) * dh_fn(x)
          - 2.0 * q * R0 / (G * h * h)
          - n * n * q * q / h ** (10.0 / 3.0))
    z = np.concatenate([[0.0], np.cumsum(0.5 * (dz[1:] + dz[:-1]) * np.diff(x))])
    return z - z.min()


def macdonald_rain_sub(x):
    """§3.3.1 subcritical with rain: h = eq. (12), q0 = 1, n = 0.033."""
    h = macdonald_sub_h(x)
    q = 1.0 + 0.001 * x
    z = macdonald_rain_bed(x, macdonald_sub_h, _macdonald_sub_dh,
                           1.0, 0.001, 0.033)
    return h, q, z


def macdonald_rain_sup(x):
    """§3.3.2 supercritical with rain: h = eq. (13), q0 = 2.5, n = 0.04."""
    h = macdonald_sup_h(x)
    q = 2.5 + 0.001 * x
    z = macdonald_rain_bed(x, macdonald_sup_h, _macdonald_sup_dh,
                           2.5, 0.001, 0.04)
    return h, q, z


# ═══════════════════════════════════════════════════════════════════════════
# §4.1 — dam breaks (flat bed, frictionless; L = 10 m, x0 = 5 m)
# ═══════════════════════════════════════════════════════════════════════════
def stoker_middle_state(hl: float, hr: float) -> tuple[float, float, float]:
    """Middle depth h_m, velocity u_m, shock speed s for the wet dam break."""
    def f(h):
        return (2.0 * (np.sqrt(G * hl) - np.sqrt(G * h))
                - (h - hr) * np.sqrt(G * (h + hr) / (2.0 * h * hr)))
    a, b = hr * (1.0 + 1e-12), hl
    for _ in range(200):
        m = 0.5 * (a + b)
        if f(a) * f(m) <= 0.0:
            b = m
        else:
            a = m
    hm = 0.5 * (a + b)
    um = 2.0 * (np.sqrt(G * hl) - np.sqrt(G * hm))
    s = um * hm / (hm - hr)
    return hm, um, s


def stoker(x: np.ndarray, t: float, hl: float = 0.005, hr: float = 0.001,
           x0: float = 5.0) -> tuple[np.ndarray, np.ndarray]:
    """§4.1.1 — Stoker's wet-bed dam break; returns (h, u)."""
    if t <= 0:
        h = np.where(x <= x0, hl, hr)
        return h, np.zeros_like(h)
    hm, um, s = stoker_middle_state(hl, hr)
    c0, cm = np.sqrt(G * hl), np.sqrt(G * hm)
    xi = (x - x0) / t
    h = np.empty_like(x, dtype=float)
    u = np.empty_like(x, dtype=float)
    for k, v in enumerate(xi):
        if v <= -c0:
            h[k], u[k] = hl, 0.0
        elif v < um - cm:
            c = (2.0 * c0 - v) / 3.0
            h[k], u[k] = c * c / G, 2.0 * (v + c0) / 3.0
        elif v < s:
            h[k], u[k] = hm, um
        else:
            h[k], u[k] = hr, 0.0
    return h, u


def ritter(x: np.ndarray, t: float, hl: float = 0.005,
           x0: float = 5.0) -> tuple[np.ndarray, np.ndarray]:
    """§4.1.2 — Ritter's dry-bed dam break; returns (h, u)."""
    if t <= 0:
        h = np.where(x <= x0, hl, 0.0)
        return h, np.zeros_like(h)
    c0 = np.sqrt(G * hl)
    xi = (x - x0) / t
    h = np.empty_like(x, dtype=float)
    u = np.empty_like(x, dtype=float)
    for k, v in enumerate(xi):
        if v <= -c0:
            h[k], u[k] = hl, 0.0
        elif v < 2.0 * c0:
            c = (2.0 * c0 - v) / 3.0
            h[k], u[k] = c * c / G, 2.0 * (v + c0) / 3.0
        else:
            h[k], u[k] = 0.0, 0.0
    return h, u


# ═══════════════════════════════════════════════════════════════════════════
# §4.1.3 — Dressler dry dam break with Chézy friction
#   hl = 6 m, x0 = 1000 m, L = 2000 m, C = 40 m^(1/2)/s, T = 40 s
# ═══════════════════════════════════════════════════════════════════════════
DR_HL, DR_X0, DR_L, DR_CHEZY = 6.0, 1000.0, 2000.0, 40.0


def dressler_manning_equiv(h_char: float | None = None,
                           C: float = DR_CHEZY) -> float:
    """Equivalent Manning n for the Chézy C at a characteristic depth
    (n = h^(1/6)/C, R = h). Default h_char = Ritter star depth 4/9·hl —
    the plateau the corrected region rides on."""
    if h_char is None:
        h_char = 4.0 * DR_HL / 9.0
    return h_char ** (1.0 / 6.0) / C


def _dressler_alpha(xi: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """First-order resistance shape functions α1(ξ), α2(ξ), ξ = (x−x0)/(t√(g hl)).
    Both vanish at ξ = −1 (the still-water edge xA) — verified in tests."""
    s = 2.0 - xi
    a1 = 1.2 / s - 2.0 / 3.0 + 4.0 * np.sqrt(3.0) / 135.0 * s ** 1.5
    a2 = (12.0 / s - 8.0 / 3.0 + 8.0 * np.sqrt(3.0) / 189.0 * s ** 1.5
          - 108.0 / (7.0 * s * s))
    return a1, a2


def dressler(x: np.ndarray, t: float, hl: float = DR_HL, x0: float = DR_X0,
             C: float = DR_CHEZY) -> tuple[np.ndarray, np.ndarray]:
    """§4.1.3 — Dressler's dam break on a dry bed with Chézy friction;
    returns (h, u). Four regions: still (hl, 0) | corrected (hco, uco) |
    tip (u = utip = max uco, constant in space) | dry beyond xB.

    Tip depth: Dressler's first-order hco is invalid (divergent) in the tip
    — the paper substitutes an undetailed second-order interpolation
    [Valiani/Caleffi]. Here the tip depth is the continuity-preserving
    quadratic ramp hco(xT)·((xB−x)/(xB−xT))² → 0 at the exact front xB
    (recorded as an approximation in provenance; the front position and the
    corrected region are Dressler's own)."""
    if t <= 0:
        h = np.where(x <= x0, hl, 0.0)
        return h, np.zeros_like(h)
    c0 = np.sqrt(G * hl)
    Cf = G * G / (C * C)                    # g²/C² prefactor of the corrections
    xa = x0 - t * c0
    xb = x0 + 2.0 * t * c0
    xi = (x - x0) / (t * c0)
    a1, a2 = _dressler_alpha(np.clip(xi, -1.0, 2.0 - 1e-9))
    root = 2.0 * c0 / 3.0 - (x - x0) / (3.0 * t) + Cf * a1 * t
    hco = np.maximum(root, 0.0) ** 2 / G
    uco = 2.0 * c0 / 3.0 + 2.0 * (x - x0) / (3.0 * t) + Cf * a2 * t
    # tip start xT: velocity maximum of the corrected profile (dense search)
    xis = np.linspace(-1.0, 2.0 - 1e-6, 4001)
    a1s, a2s = _dressler_alpha(xis)
    us = 2.0 * c0 / 3.0 + 2.0 * xis * c0 / 3.0 + Cf * a2s * t
    k = int(np.argmax(us))
    xi_tip, u_tip = float(xis[k]), float(us[k])
    x_tip = x0 + xi_tip * t * c0
    root_tip = 2.0 * c0 / 3.0 - xi_tip * c0 / 3.0 + Cf * float(a1s[k]) * t
    h_tip0 = max(root_tip, 0.0) ** 2 / G
    ramp = np.clip((xb - x) / max(xb - x_tip, 1e-12), 0.0, 1.0)
    h = np.where(x <= xa, hl,
                 np.where(xi <= xi_tip, hco,
                          np.where(x <= xb, h_tip0 * ramp * ramp, 0.0)))
    u = np.where(x <= xa, 0.0,
                 np.where(xi <= xi_tip, uco,
                          np.where(x <= xb, u_tip, 0.0)))
    u = np.where(h > 0.0, u, 0.0)
    return h, u


# ═══════════════════════════════════════════════════════════════════════════
# §3.5 — MacDonald pseudo-2D channels (variable width B(x), side slope Z)
#   q = 20 m³/s total, n = 0.03 everywhere; z(x) = ∫_x^L S0 dX (z(L) = 0)
# ═══════════════════════════════════════════════════════════════════════════
P2D_Q, P2D_N = 20.0, 0.03


def p2d_B1(x: np.ndarray) -> np.ndarray:
    return 10.0 - 5.0 * np.exp(-10.0 * (x / 200.0 - 0.5) ** 2)


def _p2d_dB1(x: np.ndarray) -> np.ndarray:
    u = x / 200.0 - 0.5
    return -5.0 * np.exp(-10.0 * u * u) * (-20.0 * u) / 200.0


def p2d_B2(x: np.ndarray) -> np.ndarray:
    return (10.0 - 5.0 * np.exp(-50.0 * (x / 400.0 - 1.0 / 3.0) ** 2)
            - 5.0 * np.exp(-50.0 * (x / 400.0 - 2.0 / 3.0) ** 2))


def _p2d_dB2(x: np.ndarray) -> np.ndarray:
    u1 = x / 400.0 - 1.0 / 3.0
    u2 = x / 400.0 - 2.0 / 3.0
    return (-5.0 * np.exp(-50.0 * u1 * u1) * (-100.0 * u1) / 400.0
            - 5.0 * np.exp(-50.0 * u2 * u2) * (-100.0 * u2) / 400.0)


def p2d_sub_short_h(x: np.ndarray) -> np.ndarray:
    """§3.5.1 subcritical, B1, rectangular, L = 200."""
    return 0.9 + 0.3 * np.exp(-20.0 * (x / 200.0 - 0.5) ** 2)


def _p2d_sub_short_dh(x: np.ndarray) -> np.ndarray:
    u = x / 200.0 - 0.5
    return 0.3 * np.exp(-20.0 * u * u) * (-40.0 * u) / 200.0


def p2d_sup_short_h(x: np.ndarray) -> np.ndarray:
    """§3.5.2 supercritical, B1, rectangular, L = 200."""
    return 0.5 + 0.5 * np.exp(-20.0 * (x / 200.0 - 0.5) ** 2)


def _p2d_sup_short_dh(x: np.ndarray) -> np.ndarray:
    u = x / 200.0 - 0.5
    return 0.5 * np.exp(-20.0 * u * u) * (-40.0 * u) / 200.0


def p2d_trans_short_h(x: np.ndarray) -> np.ndarray:
    """§3.5.3 smooth sub→super transition, B1, rectangular, L = 200."""
    return 1.0 - 0.3 * np.tanh(4.0 * (x / 200.0 - 1.0 / 3.0))


def _p2d_trans_short_dh(x: np.ndarray) -> np.ndarray:
    u = 4.0 * (x / 200.0 - 1.0 / 3.0)
    return -0.3 * 4.0 / 200.0 / np.cosh(u) ** 2


_P2D_JS_K = (-0.154375, -0.108189, -2.014310)       # §3.5.4 k0..k2
_P2D_JL_K = (-0.183691, 1.519577, -18.234429)       # §3.5.6 k0..k2


def _p2d_poly_branch(x, ks, p, xstar, xstarstar, phi, dphi):
    """exp(−p(x−x*))·Σ k_i ((x−x*)/(x**−x*))^i + φ(x) and its derivative."""
    s = (x - xstar) / (xstarstar - xstar)
    poly = sum(k * s ** i for i, k in enumerate(ks))
    dpoly = sum(k * i * s ** (i - 1) for i, k in enumerate(ks)
                if i > 0) / (xstarstar - xstar)
    e = np.exp(-p * (x - xstar))
    h = e * poly + phi(x)
    dh = e * (dpoly - p * poly) + dphi(x)
    return h, dh


def p2d_jump_short_h(x: np.ndarray) -> np.ndarray:
    """§3.5.4 hydraulic jump at x = 120, B1, rectangular, L = 200.
    (Rankine–Hugoniot balance at the jump verified in tests.)"""
    x = np.asarray(x, dtype=float)
    h_up = 0.7 + 0.3 * (np.exp(x / 200.0) - 1.0)
    phi = lambda xx: 1.5 * np.exp(0.1 * (xx / 200.0 - 1.0))       # noqa: E731
    dphi = lambda xx: 1.5 * 0.1 / 200.0 * np.exp(0.1 * (xx / 200.0 - 1.0))  # noqa: E731
    h_dn, _ = _p2d_poly_branch(x, _P2D_JS_K, 0.1, 120.0, 200.0, phi, dphi)
    return np.where(x < 120.0, h_up, h_dn)


def _p2d_jump_short_dh(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    d_up = 0.3 / 200.0 * np.exp(x / 200.0)
    phi = lambda xx: 1.5 * np.exp(0.1 * (xx / 200.0 - 1.0))       # noqa: E731
    dphi = lambda xx: 1.5 * 0.1 / 200.0 * np.exp(0.1 * (xx / 200.0 - 1.0))  # noqa: E731
    _, d_dn = _p2d_poly_branch(x, _P2D_JS_K, 0.1, 120.0, 200.0, phi, dphi)
    return np.where(x < 120.0, d_up, d_dn)


def p2d_sub_long_h(x: np.ndarray) -> np.ndarray:
    """§3.5.5 subcritical, B2, trapezoidal Z = 2, L = 400."""
    u1 = x / 400.0 - 1.0 / 3.0
    u2 = x / 400.0 - 2.0 / 3.0
    return (0.9 + 0.3 * np.exp(-40.0 * u1 * u1)
            + 0.2 * np.exp(-35.0 * u2 * u2))


def _p2d_sub_long_dh(x: np.ndarray) -> np.ndarray:
    u1 = x / 400.0 - 1.0 / 3.0
    u2 = x / 400.0 - 2.0 / 3.0
    return (0.3 * np.exp(-40.0 * u1 * u1) * (-80.0 * u1) / 400.0
            + 0.2 * np.exp(-35.0 * u2 * u2) * (-70.0 * u2) / 400.0)


def p2d_jump_long_h(x: np.ndarray) -> np.ndarray:
    """§3.5.6 smooth transition then hydraulic jump at x = 120, B2,
    trapezoidal Z = 2, L = 400. (RH balance verified in tests.)"""
    x = np.asarray(x, dtype=float)
    h_up = (0.9 + 0.25 * (np.exp(-x / 40.0) - 1.0)
            + 0.25 * np.exp(15.0 * (x / 400.0 - 0.3)))
    phi = lambda xx: (1.5 * np.exp(0.16 * (xx / 400.0 - 1.0))      # noqa: E731
                      - 0.3 * np.exp(2.0 * (xx / 400.0 - 1.0)))
    dphi = lambda xx: (1.5 * 0.16 / 400.0 * np.exp(0.16 * (xx / 400.0 - 1.0))  # noqa: E731
                       - 0.3 * 2.0 / 400.0 * np.exp(2.0 * (xx / 400.0 - 1.0)))
    h_dn, _ = _p2d_poly_branch(x, _P2D_JL_K, 0.09, 120.0, 400.0, phi, dphi)
    return np.where(x < 120.0, h_up, h_dn)


def _p2d_jump_long_dh(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    d_up = (-0.25 / 40.0 * np.exp(-x / 40.0)
            + 0.25 * 15.0 / 400.0 * np.exp(15.0 * (x / 400.0 - 0.3)))
    phi = lambda xx: (1.5 * np.exp(0.16 * (xx / 400.0 - 1.0))      # noqa: E731
                      - 0.3 * np.exp(2.0 * (xx / 400.0 - 1.0)))
    dphi = lambda xx: (1.5 * 0.16 / 400.0 * np.exp(0.16 * (xx / 400.0 - 1.0))  # noqa: E731
                       - 0.3 * 2.0 / 400.0 * np.exp(2.0 * (xx / 400.0 - 1.0)))
    _, d_dn = _p2d_poly_branch(x, _P2D_JL_K, 0.09, 120.0, 400.0, phi, dphi)
    return np.where(x < 120.0, d_up, d_dn)


def p2d_bed(x: np.ndarray, h_fn, dh_fn, B_fn, dB_fn, Z: float,
            q: float = P2D_Q, n: float = P2D_N) -> np.ndarray:
    """§3.5 slope formula integrated to a bed: S0 = (1 − q²T/(gA³))h′ + Sf
    − q²B′h/(gA³·h... ) with T = B+2Zh, A = h(B+Zh), P = B+2h√(1+Z²),
    Sf = q²n²P^(4/3)/A^(10/3); z(x) = ∫_x^L S0 dX (so z(L) = 0, dz/dx = −S0).
    The steady-momentum identity of (h, z, B, Z) is verified in tests."""
    h = h_fn(x)
    dh = dh_fn(x)
    B = B_fn(x)
    dB = dB_fn(x)
    T = B + 2.0 * Z * h
    A3 = (h * (B + Z * h)) ** 3
    P = B + 2.0 * h * np.sqrt(1.0 + Z * Z)
    Sf = (q * q * n * n * P ** (4.0 / 3.0)
          / (h ** (10.0 / 3.0) * (B + Z * h) ** (10.0 / 3.0)))
    S0 = ((1.0 - q * q * T / (G * A3)) * dh + Sf
          - q * q * dB / (G * h * h * (B + Z * h) ** 3))
    # z(x) = ∫_x^L S0: reverse cumulative trapezoid, anchored z(L) = 0
    seg = 0.5 * (S0[1:] + S0[:-1]) * np.diff(x)
    z = np.concatenate([[0.0], np.cumsum(seg)])
    return z[-1] - z


# ═══════════════════════════════════════════════════════════════════════════
# §4.2.1 — Thacker planar surface in a parabola (1D, frictionless)
#   a = 1 m, h0 = 0.5 m, L = 4 m; omega = sqrt(2 g h0)/a; period = 2*pi/omega
# ═══════════════════════════════════════════════════════════════════════════
TH_A, TH_H0, TH_L = 1.0, 0.5, 4.0


def thacker_omega(a: float = TH_A, h0: float = TH_H0) -> float:
    return np.sqrt(2.0 * G * h0) / a


def thacker_z_raw(x: np.ndarray, a: float = TH_A, h0: float = TH_H0,
                  L: float = TH_L) -> np.ndarray:
    """Paper form: z = h0((x−L/2)²/a² − 1); min = −h0 at the centre."""
    return h0 * (((x - L / 2.0) / a) ** 2 - 1.0)


def thacker_z(x: np.ndarray, a: float = TH_A, h0: float = TH_H0,
              L: float = TH_L) -> np.ndarray:
    """Datum-anchored (+h0): min z = 0, so decks carry non-negative inverts.
    Depth h is unchanged by the shift."""
    return thacker_z_raw(x, a, h0, L) + h0


def thacker_planar_1d(x: np.ndarray, t: float, a: float = TH_A,
                      h0: float = TH_H0,
                      L: float = TH_L) -> tuple[np.ndarray, np.ndarray]:
    """§4.2.1 — returns (h, u). u(x, 0) = 0 (valid depth-only IC)."""
    w = thacker_omega(a, h0)
    B = np.sqrt(2.0 * G * h0) / (2.0 * a)
    cos_wt = np.cos(w * t)
    s = (x - L / 2.0) / a + cos_wt / (2.0 * a)
    h = np.maximum(-h0 * (s * s - 1.0), 0.0)
    u = np.where(h > 0.0, B * np.sin(w * t), 0.0)
    return h, u


# ═══════════════════════════════════════════════════════════════════════════
# §4.2.2 — Thacker 2D (paraboloid of revolution), L = 4 m, a = 1 m
# ═══════════════════════════════════════════════════════════════════════════
def thacker2d_z_raw(x: np.ndarray, y: np.ndarray, a: float = 1.0,
                    h0: float = 0.1, L: float = 4.0) -> np.ndarray:
    r2 = (x - L / 2.0) ** 2 + (y - L / 2.0) ** 2
    return -h0 * (1.0 - r2 / (a * a))


def thacker2d_z(x: np.ndarray, y: np.ndarray, a: float = 1.0,
                h0: float = 0.1, L: float = 4.0) -> np.ndarray:
    """Datum-anchored (+h0): min z = 0 at the centre."""
    return thacker2d_z_raw(x, y, a, h0, L) + h0


def thacker2d_radial(x: np.ndarray, y: np.ndarray, t: float,
                     a: float = 1.0, r0: float = 0.8, h0: float = 0.1,
                     L: float = 4.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """§4.2.2 radially-symmetric oscillation — returns (h, u, v).
    u = v = 0 at t = 0 (valid depth-only IC)."""
    w = np.sqrt(8.0 * G * h0) / a
    # Thacker's constant uses FOURTH powers (Thacker 1981; the PDF text
    # extraction drops the exponents). Verified: with A=(a^4-r0^4)/(a^4+r0^4)
    # the initial shoreline sits exactly at r0; the squared form puts it at
    # a*((1-A)/(1+A))^(1/4) != r0.
    A = (a ** 4 - r0 ** 4) / (a ** 4 + r0 ** 4)
    z_raw = thacker2d_z_raw(x, y, a, h0, L)
    r2 = (x - L / 2.0) ** 2 + (y - L / 2.0) ** 2
    cwt = np.cos(w * t)
    sq = np.sqrt(np.maximum(1.0 - A * A, 0.0))
    denom = 1.0 - A * cwt
    eta = h0 * (sq / denom - 1.0
                - r2 / (a * a) * ((1.0 - A * A) / (denom * denom) - 1.0))
    h = np.maximum(eta - z_raw, 0.0)
    fac = (0.5 * w * A * np.sin(w * t)) / denom
    u = np.where(h > 0.0, fac * (x - L / 2.0), 0.0)
    v = np.where(h > 0.0, fac * (y - L / 2.0), 0.0)
    return h, u, v


def thacker2d_planar(x: np.ndarray, y: np.ndarray, t: float,
                     a: float = 1.0, h0: float = 0.1, eta_p: float = 0.5,
                     L: float = 4.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """§4.2.2 planar surface in a paraboloid — returns (h, u, v).
    NOTE v(t=0) = eta_p * omega != 0: NOT representable by a depth-only IC."""
    w = np.sqrt(2.0 * G * h0) / a
    z_raw = thacker2d_z_raw(x, y, a, h0, L)
    hh = (eta_p * h0 / (a * a)
          * (2.0 * (x - L / 2.0) * np.cos(w * t)
             + 2.0 * (y - L / 2.0) * np.sin(w * t) - eta_p)) - z_raw
    h = np.maximum(hh, 0.0)
    u = np.where(h > 0.0, -eta_p * w * np.sin(w * t), 0.0)
    v = np.where(h > 0.0, eta_p * w * np.cos(w * t), 0.0)
    return h, u, v
