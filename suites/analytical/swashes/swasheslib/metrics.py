#!/usr/bin/env python3
"""Error metrics and cell grading.

Conventions (README "Metrics"): the reference profile is sampled much denser
than the model and linearly interpolated to the model stations; a wet mask
(reference depth > h_dry_frac * max reference depth) restricts every norm;
`interior_mask=(a, b)` further restricts grading to x in [a*L, b*L].
"""
from __future__ import annotations

import numpy as np


def wet_mask(h_ref: np.ndarray, h_dry_frac: float) -> np.ndarray:
    hmax = float(np.max(h_ref)) if h_ref.size else 0.0
    return h_ref > h_dry_frac * hmax


def interp_ref(x_model: np.ndarray, x_ref: np.ndarray,
               v_ref: np.ndarray) -> np.ndarray:
    return np.interp(x_model, x_ref, v_ref)


def profile_errors(x: np.ndarray, h: np.ndarray, h_ref: np.ndarray,
                   *, h_dry_frac: float = 1e-3,
                   q: np.ndarray | None = None,
                   q_ref: np.ndarray | None = None,
                   mask: np.ndarray | None = None) -> dict:
    """L1/L2/Linf errors of depth (and optionally unit discharge) on the wet,
    interior-masked stations. All relative to the reference magnitude."""
    m = wet_mask(h_ref, h_dry_frac)
    if mask is not None:
        m &= mask
    out: dict = {"n_graded": int(m.sum())}
    if not m.any():
        out.update(l1_h=np.nan, l2_h=np.nan, linf_h=np.nan)
        return out
    dh = np.abs(h[m] - h_ref[m])
    href_max = float(np.max(h_ref[m]))
    out["l1_h"] = float(dh.sum() / np.abs(h_ref[m]).sum())
    out["l2_h"] = float(np.sqrt((dh ** 2).sum() / (h_ref[m] ** 2).sum()))
    out["linf_h"] = float(dh.max() / href_max) if href_max > 0 else np.nan
    if q is not None and q_ref is not None:
        dq = np.abs(q[m] - q_ref[m])
        qsum = np.abs(q_ref[m]).sum()
        qmax = float(np.max(np.abs(q_ref[m])))
        # steady lake-at-rest has q_ref == 0: report absolute maxima instead
        out["l1_q"] = float(dq.sum() / qsum) if qsum > 0 else float(dq.max())
        out["linf_q"] = (float(dq.max() / qmax) if qmax > 0
                         else float(dq.max()))
        out["l1_q_absolute"] = bool(qsum == 0)
    return out


def front_error(x: np.ndarray, h: np.ndarray, h_ref: np.ndarray,
                dx: float, h_dry: float) -> float:
    """|x_front(model) − x_front(reference)| / dx, fronts = farthest wet station."""
    def front(v):
        wet = np.nonzero(v > h_dry)[0]
        return x[wet[-1]] if wet.size else x[0]
    return float(abs(front(h) - front(h_ref)) / dx)


def shock_location(x: np.ndarray, h: np.ndarray, x_ref_shock: float,
                   window_frac: float, L: float) -> float:
    """x of steepest |dh/dx| within ±window_frac*L of the analytic shock."""
    lo, hi = x_ref_shock - window_frac * L, x_ref_shock + window_frac * L
    sel = (x >= lo) & (x <= hi)
    if sel.sum() < 3:
        return float("nan")
    xs, hs = x[sel], h[sel]
    grad = np.abs(np.diff(hs) / np.diff(xs))
    k = int(np.argmax(grad))
    return float(0.5 * (xs[k] + xs[k + 1]))


def steady_residual(h_late: np.ndarray, h_end: np.ndarray,
                    h_ref_max: float) -> float:
    """max |h(t_end) − h(0.95 t_end)| / max(h_ref) — must be tiny for steady cases."""
    if h_ref_max <= 0:
        return float("nan")
    return float(np.max(np.abs(h_end - h_late)) / h_ref_max)


# ── grading ─────────────────────────────────────────────────────────────────
def grade(metrics: dict, mode: str, tol: dict, *,
          mass_pct: float | None = None, mass_gate: float = 0.5,
          steady_resid: float | None = None,
          steady_gate: float = 1e-3) -> tuple[str, list[str]]:
    """Return (verdict, reasons). `metrics` keys are compared against `tol`
    keys of the same name (metric must be <= threshold). Hard gates: mass
    continuity and (for steady cases) the steady-state residual.

    mode: "analytic" -> PASS/FAIL; "baseline" -> BASELINE-PASS/BASELINE-FAIL
    (caller passes the baseline-relative metrics + tolerances); "xfail" is
    resolved by the caller (XFAIL, or XPASS if the analytic grade passes).
    """
    reasons: list[str] = []
    ok = True
    for key, thresh in tol.items():
        if key == "mass_pct":        # handled by the mass gate below
            continue
        val = metrics.get(key)
        if val is None or (isinstance(val, float) and np.isnan(val)):
            ok = False
            reasons.append(f"{key}: missing")
        elif val > thresh:
            ok = False
            reasons.append(f"{key}={val:.4g} > {thresh:g}")
    if mass_pct is not None and abs(mass_pct) > mass_gate:
        ok = False
        reasons.append(f"mass_pct={mass_pct:.3g} > {mass_gate:g}")
    if steady_resid is not None and steady_resid > steady_gate:
        ok = False
        reasons.append(f"steady_resid={steady_resid:.3g} > {steady_gate:g} (not steady)")
    if mode == "baseline":
        return ("BASELINE-PASS" if ok else "BASELINE-FAIL"), reasons
    return ("PASS" if ok else "FAIL"), reasons


def observed_order(dx_coarse: float, err_coarse: float,
                   dx_fine: float, err_fine: float) -> float:
    """log-ratio observed convergence order (informational only)."""
    if min(err_coarse, err_fine) <= 0 or dx_coarse == dx_fine:
        return float("nan")
    return float(np.log(err_coarse / err_fine) / np.log(dx_coarse / dx_fine))
