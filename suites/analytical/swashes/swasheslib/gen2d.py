#!/usr/bin/env python3
"""CaseSpec -> pure-2D SWMM .inp deck (SI mesh, union-jack strip/plane).

Adapted from openswmm.engine/examples/imex_scaling/gen_scaling_mesh.py
(union-jack triangulation, dummy dry 1D network, edge conventions:
edge 0 = v1-v2, edge 1 = v2-v0, edge 2 = v0-v1; MeshBuilder.cpp).

Strip runs of 1D cases: bed z(x) extruded across y, target edge = the 1D dx
(fairness rule 4). 2D-only cases (Thacker paraboloids) use z2d(x, y) on a
square plane. Initial depths ride the [2D_TRIANGLES] INIT_DEPTH column
(before TAG; engine default 0 = dry).

Boundary realization: WALL everywhere by default; upstream `inflow_q` ->
SPECIFIED_FLOW with PARAM_1 = -q (per-metre, outward-negative = inflow);
downstream `stage` -> SPECIFIED_STAGE at eta; downstream `free` ->
SPECIFIED_STAGE at the ANALYTIC eta(L) (documented in provenance — a true
free/normal boundary is ill-posed on the flat-bedded cases).
"""
from __future__ import annotations

import numpy as np

from .casespec import CaseSpec, SolverSpec
from .genrefs import reference_blocks


def _hms(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 3600}:{(s % 3600) // 60:02d}:{s % 60:02d}"


def _step(seconds: float) -> str:
    """Timestep token: H:MM:SS for whole seconds, else plain seconds (the
    refactored engine's parse_time_seconds accepts a bare number; H:MM:SS
    cannot carry the sub-second report steps the Thacker cases need)."""
    if abs(seconds - round(seconds)) < 1e-9:
        return _hms(seconds)
    return f"{seconds:g}"


def strip_ny(case: CaseSpec) -> int:
    return max(1, int(round(case.W2d / case.dx)))


def _eta_downstream(case: CaseSpec) -> float:
    """Analytic water-surface elevation at x = L (for stage/free BCs)."""
    if case.downstream.kind == "stage":
        return case.downstream.eta
    blocks = reference_blocks(case, density=1)
    t = max(blocks)
    x, h, _ = blocks[t]
    zL = float(case.z(np.array([case.L]))[0])
    return zL + float(h[-1])


def build_inp(case: CaseSpec, solver: SolverSpec, h5_name: str) -> str:
    nx = case.nx
    dx = case.dx
    ny = strip_ny(case)
    dy = case.W2d / ny
    nvx, nvy = nx + 1, ny + 1

    xs = np.arange(nvx) * dx
    ys = np.arange(nvy) * dy
    if case.z2d is not None:
        X, Y = np.meshgrid(xs, ys)          # [nvy, nvx]
        Z = case.z2d(X, Y)
    else:
        Z = np.tile(case.z(xs), (nvy, 1))

    # Vertex plan coordinates. Default: tensor grid (xs x ys) — byte-identical
    # to the historical emission. Bend family: mapped mitered-shear grid — the
    # same iy/ix topology, union-jack diagonals and BC bookkeeping, with rows
    # near the corner sheared into the miter half-angle plane (planform.py).
    # xs are centerline arc-length stations; ys map to lateral offsets
    # w = ys - W2d/2; bed z(s) is constant along each station row.
    if case.planform is not None:
        assert case.h0 is None and case.h02d is None, \
            "bend cases are dry-start (init-depth sampling is x-based)"
        assert case.downstream.kind == "stage", \
            "bend cases use a stage downstream BC (no analytic eta exists)"
        PX = np.empty((nvy, nvx))
        PY = np.empty((nvy, nvx))
        w_off = ys - case.W2d / 2.0
        for ix in range(nvx):
            px, py = case.planform.row_map(float(xs[ix]), w_off, dx)
            PX[:, ix] = px
            PY[:, ix] = py
        VX, VY = PX.ravel(), PY.ravel()
    else:
        VX = np.tile(xs, nvy)
        VY = np.repeat(ys, nvx)

    def vid(ix: int, iy: int) -> int:
        return iy * nvx + ix

    # per-triangle centroids + init depths
    tri_rows: list[str] = []
    bc_up: list[str] = []
    bc_dn: list[str] = []
    n_man = case.n_manning if case.n_manning > 0.0 else 1e-8

    def centroid(vids):
        cx = sum(VX[v] for v in vids) / 3.0
        cy = sum(VY[v] for v in vids) / 3.0
        return cx, cy

    def signed_area(vids) -> float:
        x0, y0 = VX[vids[0]], VY[vids[0]]
        x1, y1 = VX[vids[1]], VY[vids[1]]
        x2, y2 = VX[vids[2]], VY[vids[2]]
        return 0.5 * ((x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0))

    def init_depth(cx: float, cy: float, zc_deck: float) -> float:
        """Depth against the DISCRETE cell bed (mean of the 3 deck vertex
        z's — the engine's FLAT-closure datum), from the analytic initial
        SURFACE eta = h0 + z at the centroid. Evaluating h0 alone against the
        analytic bed leaves a few-cm eta ripple over curved beds that
        launches a permanent seiche in the frictionless basins."""
        if case.h02d is not None:
            h = float(case.h02d(np.array([cx]), np.array([cy]))[0])
            z = float(case.z2d(np.array([cx]), np.array([cy]))[0])
        elif case.h0 is not None:
            h = float(case.h0(np.array([cx]))[0])
            z = float(case.z(np.array([cx]))[0])
        else:
            return 0.0
        if h <= 0.0:
            return 0.0
        return max(0.0, (h + z) - zc_deck)

    tri_idx = 0
    any_depth = False
    uv_rows: list[str] = []
    for iy in range(ny):
        for ix in range(nx):
            sw, se = vid(ix, iy), vid(ix + 1, iy)
            nw, ne = vid(ix, iy + 1), vid(ix + 1, iy + 1)
            if (ix + iy) % 2 == 0:            # SW-NE diagonal
                tris = [(sw, se, ne), (sw, ne, nw)]
                up_local, dn_local = (1, 1), (0, 0)   # (tri offset, edge)
            else:                             # NW-SE diagonal
                tris = [(sw, se, nw), (se, ne, nw)]
                up_local, dn_local = (0, 1), (1, 2)
            for k, tv in enumerate(tris):
                if case.planform is not None:
                    a = signed_area(tv)
                    assert a > 1e-9, (
                        f"degenerate/inverted cell at ix={ix} iy={iy} "
                        f"(area {a:.3g}) — miter taper too aggressive")
                cx, cy = centroid(tv)
                zc_deck = sum(Z[v // nvx, v % nvx] for v in tv) / 3.0
                d = max(0.0, init_depth(cx, cy, zc_deck))
                if d > 0.0:
                    any_depth = True
                tri_rows.append(
                    f"{tv[0]} {tv[1]} {tv[2]} {n_man:g} {d:.6g}")
                # Velocity IC only where there is water to carry it.
                if case.uv02d is not None and d > 0.0:
                    u0, v0 = case.uv02d(np.array([cx]), np.array([cy]))
                    u0, v0 = float(u0[0]), float(v0[0])
                    if u0 != 0.0 or v0 != 0.0:
                        uv_rows.append(
                            f"{tri_idx + k} {u0:.6g} {v0:.6g}")
            if ix == 0 and case.upstream.kind == "inflow_q":
                bc_up.append(f"{tri_idx + up_local[0]}    {up_local[1]}    "
                             f"SPECIFIED_FLOW   {-case.upstream.q:g}")
            if ix == nx - 1 and case.downstream.kind in ("stage", "free") \
                    and case.upstream.kind == "inflow_q":
                # (closed lakes keep WALL everywhere: a stage BC on an
                # already-at-stage basin only re-excites the known stage-BC
                # ringing; mass stays exactly conserved behind walls)
                bc_dn.append(f"{tri_idx + dn_local[0]}    {dn_local[1]}    "
                             f"SPECIFIED_STAGE  {_eta_downstream(case):.6f}")
            tri_idx += 2

    opts_2d = {
        "INTEGRATOR": "EXPLICIT",
        # RESOLVED 2026-08-04: the historical "CFL 0.7 unstable on union-jack"
        # finding was a length-scale accounting error in the engine, not a
        # scheme limit — cell_lchar (2A/xi_max) overstated the stable dt by
        # sqrt(3) on this triangulation (predicted critical nominal 0.577;
        # measured 0.5 flat / 0.6 seiche). The engine now derives L_char from
        # the discrete wave operator, making CFL_NUMBER a true Courant
        # fraction (lake machine-flat at 0.7, stable through 0.95; see
        # runs/lake-at-rest-immersed/_debug_cfl07/FINDINGS_CFL_2026-08-03.md).
        # The suite pins 0.5 for ACCURACY, not stability: it reproduces the
        # truncation error every tolerance/baseline was calibrated at
        # (macdonald-long-sub sits at 2.0% vs its 3% gate there, 3.1% at
        # 0.7), while the engine default 0.7 remains the production choice.
        "CFL_NUMBER": "0.5",
        "REPORT_2D": "NO",
        "OUTPUT_FILE": h5_name,
        "MAX_TIMESTEP": "1.0",
        "RAINFALL_MODE": "NONE",
    }
    opts_2d.update(case.opts_2d)
    # Solver last: a sweep column exists precisely to override the case default.
    opts_2d.update(solver.opts_2d)

    routing_step = min(case.report_step, 1.0)

    L: list[str] = []
    L.append("[TITLE]")
    L.append(f";; SWASHES {case.id} — {case.title} ({case.swashes_ref}) — "
             f"2D strip {nx}x{ny} (edge ~{dx:g} m) for solver {solver.id}")
    L.append("")
    L.append("[OPTIONS]")
    for k, v in {
        "FLOW_UNITS": "CMS", "INFILTRATION": "HORTON",
        "FLOW_ROUTING": "DYNWAVE", "LINK_OFFSETS": "DEPTH",
        "MIN_SLOPE": "0", "ALLOW_PONDING": "NO",
        "SKIP_STEADY_STATE": "NO", "THREADS": "1",
        "START_DATE": "01/01/2026", "START_TIME": "00:00:00",
        "REPORT_START_DATE": "01/01/2026", "REPORT_START_TIME": "00:00:00",
        "END_DATE": "01/01/2026", "END_TIME": _hms(case.t_end),
        "REPORT_STEP": _step(case.report_step),
        "WET_STEP": _step(case.report_step),
        "DRY_STEP": _step(case.report_step),
        "ROUTING_STEP": f"{routing_step:g}",
    }.items():
        L.append(f"{k:<20s} {v}")
    L.append("")
    # Trivial DRY uncoupled 1D network (routing parser needs one); far away.
    L.append("[JUNCTIONS]")
    L.append("JD1     0     10        0          0         0")
    L.append("")
    L.append("[OUTFALLS]")
    L.append("OD1     0     FREE          NO")
    L.append("")
    L.append("[CONDUITS]")
    L.append("CD1     JD1   OD1  100     0.01   0   0   0")
    L.append("")
    L.append("[XSECTIONS]")
    L.append("CD1     CIRCULAR  1.0    0      0      0      1")
    L.append("")
    L.append("[COORDINATES]")
    L.append(f"JD1     {-5 * dx:.1f}   {-5 * dy:.1f}")
    L.append(f"OD1     {-6 * dx:.1f}   {-5 * dy:.1f}")
    L.append("")
    L.append("[2D_OPTIONS]")
    for k, v in opts_2d.items():
        L.append(f"{k:<22s} {v}")
    L.append("")
    L.append("[2D_VERTICES]")
    L.append(";; UNITS: SI (m)")
    L.append(";;X  Y  Z")
    for iy in range(nvy):
        for ix in range(nvx):
            L.append(f"{VX[vid(ix, iy)]:.6g} {VY[vid(ix, iy)]:.6g} "
                     f"{Z[iy, ix]:.8g}")
    L.append("")
    L.append("[2D_TRIANGLES]")
    L.append(";;V1 V2 V3 MANNINGS_N INIT_DEPTH")
    L.extend(tri_rows)
    L.append("")
    if uv_rows:
        L.append("[2D_INITIAL_VELOCITY]")
        L.append(";;TRI  U  V")
        L.extend(uv_rows)
        L.append("")
    if bc_up or bc_dn:
        L.append("[2D_BOUNDARY_CONDITIONS]")
        L.append(";;TRI  EDGE TYPE            PARAM_1")
        L.extend(bc_up)
        L.extend(bc_dn)
        L.append("")
    return "\n".join(L) + "\n"
