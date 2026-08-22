#!/usr/bin/env python3
"""Extract SI profiles from run outputs.

1D: node depths + link flows from the .out (CMS decks report metric units
directly) → (x, h) at node stations and (x_mid, q) at link midpoints, per
compare time. 2D: face depth/vx from the UGRID HDF5, strip-averaged into
1D-station bins.

Element naming must match gen1d (node_id/link_id helpers there).
"""
from __future__ import annotations

import numpy as np

from . import config  # noqa: F401  (bootstraps repo root onto sys.path)
from harness.readers import Out, Surface2DOutput, NODE_DEPTH, LINK_FLOW


def node_id(i: int) -> str:
    return f"N{i:04d}"


def link_id(i: int) -> str:
    return f"C{i:04d}"


# ── 1D ──────────────────────────────────────────────────────────────────────
def out_elapsed_seconds(out: Out) -> np.ndarray:
    """Elapsed seconds since the first reporting period (SWMM datetimes are
    days since 1899-12-30)."""
    dt = out.datetimes()
    return (dt - dt[0]) * 86400.0 + _report_step_seconds(dt)


def _report_step_seconds(dt: np.ndarray) -> float:
    # SWMM's first reporting period is at t = report_step (not 0).
    return float((dt[1] - dt[0]) * 86400.0) if dt.size > 1 else 0.0


def _period_index(elapsed: np.ndarray, t: float) -> int:
    return int(np.argmin(np.abs(elapsed - t)))


def extract_1d(out_path, nx: int, dx: float, W: float,
               compare_times: tuple, probes: tuple = ()) -> dict:
    """Returns {t: {"x_h", "h", "x_q", "q"}} for each compare time (h in m,
    q in m2/s), plus "late" (the profile at 0.95*t_max, for the steady-state
    residual) and probe depth time series."""
    out = Out(out_path)
    elapsed = out_elapsed_seconds(out)
    x_h = np.arange(nx + 1) * dx
    x_q = (np.arange(nx) + 0.5) * dx

    def profile(p: int) -> dict:
        h = np.array([out.node_series(node_id(i), NODE_DEPTH)[p]
                      for i in range(nx + 1)], dtype=float)
        q = np.array([out.link_series(link_id(i), LINK_FLOW)[p]
                      for i in range(nx)], dtype=float) / W
        return {"x_h": x_h, "h": h, "x_q": x_q, "q": q,
                "t": float(elapsed[p])}

    res: dict = {"times": {}, "elapsed": elapsed}
    for t in compare_times:
        res["times"][t] = profile(_period_index(elapsed, t))
    t_max = max(compare_times)
    res["late"] = profile(_period_index(elapsed, 0.95 * t_max))
    res["mean"] = _window_mean(profile, elapsed, 0.5 * t_max, t_max)
    res["mean_prev"] = _window_mean(profile, elapsed, 0.25 * t_max, 0.5 * t_max)
    res["probes"] = {}
    for xp in probes:
        i = int(round(xp / dx))
        res["probes"][xp] = {
            "t": elapsed,
            "h": out.node_series(node_id(i), NODE_DEPTH).astype(float),
        }
    return res


def _window_mean(profile, elapsed: np.ndarray, t0: float, t1: float) -> dict:
    """Time-mean profile over reporting periods in [t0, t1] — steady cases are
    graded on the mean because undamped reflective flumes retain a residual
    seiche around the steady solution (project precedent: 2D stage-BC tests
    gate on time-means). Mean window = final 50%; drift window = 25-50%."""
    idx = [p for p, t in enumerate(elapsed) if t0 <= t <= t1]
    if not idx:
        idx = [len(elapsed) - 1]
    profs = [profile(p) for p in idx]
    out = dict(profs[-1])
    out["h"] = np.mean([p["h"] for p in profs], axis=0)
    out["q"] = np.mean([p["q"] for p in profs], axis=0)
    out["t"] = float(np.mean([p["t"] for p in profs]))
    return out


# ── 2D (strip-averaged) ─────────────────────────────────────────────────────
def extract_2d_strip(h5_path, L: float, nx: int,
                     compare_times: tuple, probes: tuple = (),
                     bed_fn=None, s_of=None, tangent_of=None) -> dict:
    """Bin faces by centroid x into nx bins; unweighted mean per bin (meshes
    are quasi-uniform). Returns same shape as extract_1d plus mass balance.

    When ``bed_fn`` (analytic strip-mean bed z(x)) is given, the graded depth
    is derived from the binned water-SURFACE elevation minus the ANALYTIC
    bed — this removes the piecewise-linear bed-sampling quadrature error
    (~dx^2 z'' /12) that would otherwise contaminate depth comparisons on
    curved beds (a machine-exact lake at rest then grades exactly).

    Bent domains (bend family): pass ``s_of(x, y)`` and ``tangent_of(x, y)``
    from the case planform — faces are binned by centerline arc length s and
    the unit discharge uses the tangential velocity component
    q = h*(vx*tx + vy*ty). Everything downstream treats s as "x"."""
    with Surface2DOutput(h5_path) as srf:
        times = np.asarray(srf.times, dtype=float)
        # /time is absolute SWMM datetime in DAYS; convert to elapsed seconds
        # (first reporting period is at t = report_step, mirroring the .out).
        if times.size and times[0] > 1e4:
            step = (times[1] - times[0]) * 86400.0 if times.size > 1 else 0.0
            times = (times - times[0]) * 86400.0 + step
        fx = srf.face_x
        fz = srf.face_z
        depth = srf.face_series("depth")
        vx = srf.face_series("vx")
        if s_of is not None:
            fy = srf.face_y
            vy = srf.face_series("vy")
        mass = srf.mass_balance()

    if s_of is not None:
        fs = np.asarray(s_of(fx, fy), dtype=float)
        tx, ty = tangent_of(fx, fy)
        tx = np.asarray(tx, dtype=float)
        ty = np.asarray(ty, dtype=float)
    else:
        fs = fx

    edges = np.linspace(0.0, L, nx + 1)
    which = np.clip(np.digitize(fs, edges) - 1, 0, nx - 1)
    x_mid = 0.5 * (edges[:-1] + edges[1:])
    counts = np.bincount(which, minlength=nx).astype(float)
    counts[counts == 0] = np.nan

    def binmean(v: np.ndarray) -> np.ndarray:
        return np.bincount(which, weights=v, minlength=nx) / counts

    z_ref = bed_fn(x_mid) if bed_fn is not None else None

    def profile(p: int) -> dict:
        if z_ref is not None:
            # eta-based depth vs the analytic bed (see docstring); dry bins
            # (eta == local bed) clamp at 0.
            eta = binmean(fz + depth[p])
            wet = binmean((depth[p] > 1e-10).astype(float))
            h = np.where(wet > 0.0, np.maximum(eta - z_ref, 0.0), 0.0)
        else:
            h = binmean(depth[p])
        if s_of is not None:
            q = binmean(depth[p] * (vx[p] * tx + vy[p] * ty))
        else:
            q = binmean(depth[p] * vx[p])      # unit discharge h*u (m2/s)
        return {"x_h": x_mid, "h": h, "x_q": x_mid, "q": q,
                "t": float(times[p])}

    res: dict = {"times": {}, "elapsed": times, "mass_balance": mass}
    for t in compare_times:
        res["times"][t] = profile(_period_index(times, t))
    t_max = max(compare_times)
    res["late"] = profile(_period_index(times, 0.95 * t_max))
    res["mean"] = _window_mean(profile, times, 0.5 * t_max, t_max)
    res["mean_prev"] = _window_mean(profile, times, 0.25 * t_max, 0.5 * t_max)
    res["probes"] = {}
    for xp in probes:
        b = int(np.clip(np.digitize(xp, edges) - 1, 0, nx - 1))
        sel = which == b
        res["probes"][xp] = {"t": times,
                             "h": depth[:, sel].mean(axis=1)}
    return res


def write_extracted_csv(path, res: dict) -> None:
    """Persist per-time profiles for review + baseline pinning."""
    rows = ["t_s,x_m,h_m,q_m2_per_s"]
    for t, prof in sorted(res["times"].items()):
        q_at_h = np.interp(prof["x_h"], prof["x_q"], prof["q"])
        for x, h, q in zip(prof["x_h"], prof["h"], q_at_h):
            rows.append(f"{t:.6g},{x:.6g},{h:.9g},{q:.9g}")
    with open(path, "w") as f:
        f.write("\n".join(rows) + "\n")


def read_extracted_csv(path) -> dict:
    """Inverse of write_extracted_csv: {t: {'x','h','q'}} arrays."""
    data = np.genfromtxt(path, delimiter=",", names=True)
    res: dict = {}
    for t in np.unique(data["t_s"]):
        sel = data["t_s"] == t
        res[float(t)] = {"x": data["x_m"][sel], "h": data["h_m"][sel],
                         "q": data["q_m2_per_s"][sel]}
    return res
