#!/usr/bin/env python3
"""Case / solver / policy dataclasses — these ARE the suite's schema.

A matrix cell = (CaseSpec, SolverSpec). The cell's grading policy comes from
CaseSpec.cells[solver_id]; an unlisted solver is SKIP for that case.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

Array = "np.ndarray"


@dataclass(frozen=True)
class BC:
    """Boundary condition. kinds: inflow_q(q m2/s per unit width) | stage(eta m)
    | free | normal | wall | none."""
    kind: str
    q: float = 0.0        # unit discharge (m2/s), inflow_q
    eta: float = 0.0      # water-surface elevation (m), stage


@dataclass(frozen=True)
class CellPolicy:
    mode: str                       # "analytic" | "baseline" | "xfail"
    tol: dict = field(default_factory=dict)   # analytic thresholds (always recorded)
    baseline_tol: dict = field(default_factory=dict)  # thresholds vs pinned baseline
    note: str = ""


@dataclass(frozen=True)
class CaseSpec:
    id: str
    swashes_ref: str                # e.g. "SWASHES 3.1.3"
    family: str                     # report grouping
    title: str
    dims: tuple                     # (1,), (2,) or (1, 2)
    L: float                        # domain length (m)
    W1d: float                      # 1D channel width (m); wide for friction cases
    W2d: float                      # 2D strip width (m)
    z: Callable                     # bed elevation z(x) -> ndarray (datum-anchored min 0)
    n_manning: float                # 0.0 = frictionless (legal in both engines)
    upstream: BC
    downstream: BC
    h0: Callable | None             # initial depth h(x) (1D + 2D strip); None = dry
    t_end: float                    # s
    dt_routing: float               # s (shared by ALL 1D solvers — fairness rule 3)
    report_step: float              # s
    compare_times: tuple            # s; steady cases: (t_end,)
    probes: tuple = ()              # x stations for transient time series
    interior_mask: tuple = (0.0, 1.0)   # grade x in [a*L, b*L]
    # Per-case override of the steady-drift gate (runcase.STEADY_GATE default
    # 0.02). For cases whose analytic steady state is Vedernikov-unstable
    # (roll waves), the window means never fully converge — the gate must be
    # sized to the persistent oscillation, not to numerical drift.
    steady_gate: float | None = None
    nx: int = 100
    refine_nx: tuple = ()
    h_dry_frac: float = 1e-3
    steady: bool = True
    rain: float | None = None       # m/s — uniform rain, emitted as per-node
                                    # lateral inflows R0*dx*W (§3.3 cases)
    rain_start: float = 0.0         # s — rain onset (0 = from t0; §3.3.2
                                    # recommends tR=1500 s for the sup case)
    # ---- pseudo-2D family (§3.5): variable width / trapezoid channels ----
    # width_fn(x) -> bottom width B (m). When set, upstream BC.q is the TOTAL
    # discharge (m³/s), per-conduit widths come from B at link midpoints and
    # extraction divides link flow by the local width.
    width_fn: Callable | None = None
    side_slope: float = 0.0         # trapezoid side slope Z (horiz:vert)
    opts_1d: dict = field(default_factory=dict)   # [OPTIONS] overrides
    opts_2d: dict = field(default_factory=dict)   # [2D_OPTIONS] overrides
    cells: dict = field(default_factory=dict)     # solver_id -> CellPolicy
    # 2D-only cases define z2d(x, y) instead of extruding z(x); optional h02d(x, y)
    z2d: Callable | None = None
    h02d: Callable | None = None
    # Optional initial velocity field uv02d(x, y) -> (u, v) in m/s, emitted as
    # sparse [2D_INITIAL_VELOCITY] rows (solutions with v(t=0) != 0, e.g. the
    # Thacker planar oscillation, are not representable by a depth-only IC).
    uv02d: Callable | None = None
    # ---- bend family (planform-blindness study) ----
    # planform maps centerline arc length s (and lateral offset w) to plan XY:
    # a MiterPlanform (planform.py). None = straight along +x (all existing
    # cases; every planform-aware code path is bypassed).
    planform: object | None = None
    # Max expected flow depth (m). When set, gen1d.max_depth uses it directly
    # instead of sampling the analytic reference — required for cases whose
    # reference is a pinned 2D run that may not exist yet.
    h_max: float | None = None
    # Miter-bend minor-loss coefficient applied as Kentry on the conduit
    # leaving the corner node ([LOSSES] row emitted by gen1d when > 0).
    bend_k: float = 0.0
    # "analytic" = vendored formula reference (reference_blocks by case.id);
    # "2d" = pinned 2D-engine profile at cases/<id>/reference_2d.csv.
    ref_source: str = "analytic"

    @property
    def dx(self) -> float:
        return self.L / self.nx


# DW surcharge x continuity variant columns (solvers.py, 2026-08-13): each
# variant inherits the grading policy of the base DW column it re-runs.
# Tolerances/mode/baseline_tol are inherited; the note is replaced by a mirror
# tag — the base column's measured numbers belong to the base column. Applied
# at module bottom of cases_steady.py / cases_pseudo2d.py (the case families
# in the hires DW matrix; transient + bend families are out of scope).
# The SURCHARGE_METHOD variants were retired 2026-08-14: on an all-open-channel
# suite they are bit-identical to their base column (see solvers.py), so they
# only duplicated series in the figures. SEMI_IMPLICIT remains — different
# physics — and still inherits its base column's grading policy.
DW_VARIANT_BASE = {
    "1d-dynwave-semi": "1d-dynwave",
}


def mirror_dw_variants(cases) -> None:
    for case in cases:
        for vid, base in DW_VARIANT_BASE.items():
            p = case.cells.get(base)
            if p is None or vid in case.cells:
                continue
            case.cells[vid] = CellPolicy(
                p.mode, p.tol, p.baseline_tol,
                note=f"policy mirrored from {base}")


@dataclass(frozen=True)
class SolverSpec:
    id: str                 # "1d-dynwave" | "1d-kinwave" | "1d-dynwave-legacy" | "1d-fv" | "2d-explicit"
    dim: int                # 1 or 2
    exe: str                # "refact" | "legacy" (resolved via harness.engines)
    flow_routing: str = ""  # [OPTIONS] FLOW_ROUTING token (1D solvers)
    env: dict = field(default_factory=dict)
    available: bool = True  # False = registered placeholder (e.g. future FV)
    opts_1d: dict = field(default_factory=dict)  # per-solver [OPTIONS] overrides
    # per-solver [2D_OPTIONS] overrides, applied on top of the case's own.
    # Lets one scheme knob be swept as its own matrix column (e.g. THETA) so
    # the sweep is scored by the same extract/grade path as everything else.
    opts_2d: dict = field(default_factory=dict)
    # Emit interior chain nodes as [VIRTUAL_JUNCTIONS] (zero-storage, momentum-
    # coupled; refactored engine only). Interior InitDepths are NOT
    # representable (Name+Elev format) — list this solver only on dry-start /
    # inflow-driven cases.
    virtual_interior: bool = False
