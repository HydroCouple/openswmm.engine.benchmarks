#!/usr/bin/env python3
"""Case specifications for the open-channel <-> pressurized transition suite.

Each case is a linear chain of circular pipes between an upstream inflow node
and a downstream FIXED-stage outfall, subdivided into short conduits so every
solver column sees the same spatial resolution (SWASHES fairness precedent).
All quantities SI (m, m3/s, s).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass(frozen=True)
class Pipe:
    length: float        # m
    diam: float          # m (CIRCULAR Geom1)
    n: float             # Manning
    z_up: float          # invert at upstream end, m
    z_dn: float          # invert at downstream end, m
    nsplit: int          # number of equal conduits this pipe is split into


@dataclass(frozen=True)
class Case:
    id: str
    title: str
    pipes: tuple                       # tuple[Pipe, ...]
    outfall_stage: float               # FIXED stage at the terminal outfall, m
    t_end: float                       # s
    dt_routing: float                  # s
    report_step: float                 # s
    q_grade: float                     # discharge for the analytic pressurized HGL
    max_depth: float                   # junction MaxDepth (deep manholes, no flooding)
    init_depth: float = 0.0            # [JUNCTIONS] InitDepth everywhere
    inflow_const: float | None = None  # constant upstream inflow, m3/s
    inflow_ts: tuple | None = None     # ((minute, m3/s), ...) upstream hydrograph
    snapshot_times: tuple = ()         # s — HGL snapshot figure times
    front_stations: tuple = ()         # m — front-arrival grading stations (rapid-fill)
    peak_time: float | None = None     # s — pressurized-HGL grading time (surcharge-cycle)
    steady_window: float | None = None # s — final-window time-mean grading (siphon)
    timing_reps: int = 1               # best-of-N wall clock (LTS timing case)
    modes: dict = field(default_factory=dict)   # solver_id -> analytic|xfail
    tols: dict = field(default_factory=dict)
    tols_by_solver: dict = field(default_factory=dict)  # solver_id -> overrides
    notes: str = ""

    def tol_for(self, solver_id: str) -> dict:
        return {**self.tols, **self.tols_by_solver.get(solver_id, {})}

    # ── derived chain geometry ──────────────────────────────────────────
    def conduits(self):
        """Yield dicts {name, i_up, i_dn, length, n, diam} for the split chain."""
        out, i = [], 0
        for p in self.pipes:
            dx = p.length / p.nsplit
            for _ in range(p.nsplit):
                out.append({"name": f"C{len(out):03d}", "i_up": i, "i_dn": i + 1,
                            "length": dx, "n": p.n, "diam": p.diam})
                i += 1
        return out

    def node_x(self) -> np.ndarray:
        """Chainage of every node from the upstream end."""
        xs = [0.0]
        for p in self.pipes:
            dx = p.length / p.nsplit
            for _ in range(p.nsplit):
                xs.append(xs[-1] + dx)
        return np.asarray(xs)

    def node_z(self) -> np.ndarray:
        """Invert elevation of every node (linear within each pipe)."""
        zs = [self.pipes[0].z_up]
        for p in self.pipes:
            for k in range(1, p.nsplit + 1):
                zs.append(p.z_up + (p.z_dn - p.z_up) * k / p.nsplit)
        return np.asarray(zs)

    def node_diam(self) -> np.ndarray:
        """Diameter of the conduit downstream of each node (crown drawing)."""
        ds = []
        for p in self.pipes:
            ds.extend([p.diam] * p.nsplit)
        ds.append(ds[-1])
        return np.asarray(ds)

    @property
    def n_conduits(self) -> int:
        return sum(p.nsplit for p in self.pipes)

    @property
    def L(self) -> float:
        return sum(p.length for p in self.pipes)

    def joint_nodes(self) -> list[int]:
        """Global node indices at the original (unsplit) pipe joints, interior only."""
        out, i = [], 0
        for p in self.pipes[:-1]:
            i += p.nsplit
            out.append(i)
        return out


def node_id(i: int) -> str:
    return f"N{i:03d}"


def link_id(i: int) -> str:
    return f"C{i:03d}"


ANALYTIC_ALL = {"dw-legacy": "analytic", "dw": "analytic", "dw-slot": "analytic",
                "fv": "analytic", "fv-lts": "analytic"}

CASES: list[Case] = [
    # A — filling bore in a horizontal pipe. Mass conservation across the
    # moving pressurization front gives w = Q/(A_full - A0): friction-free to
    # leading order because the ambient water ahead of the bore is at rest
    # (Vasconcelos & Wiggert, JHE 2005 storage-tunnel filling bores).
    Case(
        id="rapid-fill",
        title="Rapid filling bore, horizontal pipe (analytic front trajectory)",
        pipes=(Pipe(500.0, 1.0, 0.010, 0.0, 0.0, 25),),
        outfall_stage=0.20,
        init_depth=0.20,
        inflow_const=2.0,
        t_end=600.0, dt_routing=0.5, report_step=5.0,
        snapshot_times=(60.0, 120.0, 168.0),
        front_stations=(250.0, 480.0),   # arrival times reported (informational)
        q_grade=2.0,
        max_depth=12.0,
        modes=dict(ANALYTIC_ALL),
        # Front SPEED is graded (least-squares x_f(t) over 150-450 m), not
        # absolute arrival: bore formation from the step inflow costs a ~50 s
        # intercept every solver shares, while the propagation speed is the
        # Rankine-Hugoniot quantity under test. The post-fill check is the
        # head DROP between x=0 and x=400 m (pure friction slope) — absolute
        # head depends on the sub-crown outfall boundary treatment.
        tols={"front_speed_frac": 0.10,
              "head_drop": 0.15,       # |Δh(0..400 m) - Sf*400|, m
              "mass_pct": 0.5},
        tols_by_solver={"dw": {"mass_pct": 2.0},
                        "dw-legacy": {"mass_pct": 2.0},
                        "dw-slot": {"mass_pct": 2.0}},
        notes="Ambient column at rest (outfall stage = initial depth); step "
              "inflow 2.0 m3/s pressurizes the pipe end-to-end in ~220 s "
              "(analytic bore speed 2.97 m/s after formation).",
    ),
    # B — surcharge onset + relief in a sloped chain, uniform 5 m conduits
    # (calibration probes showed 20 m cells bias the FV pressurized friction
    # slope low on sloped pipes — the 5 m deck is converged; the 20 m and
    # mixed-mesh probes are kept under runs/_probe as documented findings).
    # Junctions are made deep enough that NO transient can reach the flood
    # ceiling: with ALLOW_PONDING NO, flooding silently deletes water, which
    # conflates solver overshoot with conservation error.
    Case(
        id="surcharge-cycle",
        title="Surcharge onset and relief, sloped chain (peak-hold HGL analytic)",
        pipes=(Pipe(200.0, 1.0, 0.013, 1.2, 0.8, 40),
               Pipe(200.0, 1.0, 0.013, 0.8, 0.4, 40),
               Pipe(200.0, 1.0, 0.013, 0.4, 0.0, 40)),
        outfall_stage=1.0,             # crown at the outlet
        inflow_ts=((0, 0.3), (10, 0.3), (15, 2.0), (45, 2.0),
                   (50, 0.3), (120, 0.3)),
        t_end=7200.0, dt_routing=1.0, report_step=15.0,
        snapshot_times=(600.0, 2400.0, 4500.0),
        peak_time=2400.0,
        q_grade=2.0,                   # ~1.9x Manning full-pipe capacity
        max_depth=20.0,                # flood ceiling unreachable (see above)
        timing_reps=3,                 # the LTS wall-clock case
        # DW columns are expected-fail on conservation here (documented
        # characteristics, not harness noise): EXTRAN's surcharge iteration
        # leaks -6.1% through the cycle on BOTH engines (and the leak GROWS
        # with mesh refinement: -3.1% at 20 m cells, probe4), while the
        # static-slot method melts down at the fixed 1 s step on both
        # engines (refact -37235%, legacy-slot probes -208..-356%).
        modes={"fv": "analytic", "fv-lts": "analytic",
               "dw": "xfail", "dw-slot": "xfail", "dw-legacy": "xfail"},
        # Graded on the TIME-MEAN head over the 1500-2700 s peak hold; the
        # hold-window head range at the inflow node is reported alongside so
        # any ringing is never hidden.
        tols={"head_hold": 0.10,       # hold-mean node head vs analytic, m
              "mass_pct": 0.5},
        tols_by_solver={"dw": {"mass_pct": 2.0},
                        "dw-legacy": {"mass_pct": 2.0},
                        "dw-slot": {"mass_pct": 2.0}},
        notes="Hydrograph 0.3 -> 2.0 -> 0.3 m3/s; capacity ~1.07 m3/s, so the "
              "chain pressurizes on the rise and relieves on the recession.",
    ),
    # C — inverted siphon, permanently pressurized at steady state. Uniform
    # diameter end-to-end so velocity head is constant and the steady HGL is
    # exactly stage + Sf * (distance from outfall), pure Manning friction.
    Case(
        id="inverted-siphon",
        title="Inverted siphon, steady pressurized HGL (energy-balance analytic)",
        pipes=(Pipe(100.0, 0.8, 0.013, 8.0, 7.8, 5),
               Pipe(30.0, 0.8, 0.013, 7.8, 2.0, 2),
               Pipe(200.0, 0.8, 0.013, 2.0, 2.0, 10),
               Pipe(30.0, 0.8, 0.013, 2.0, 7.5, 2),
               Pipe(100.0, 0.8, 0.013, 7.5, 7.3, 5)),
        outfall_stage=8.6,             # above every crown: pressurized end-to-end
        inflow_const=0.7,
        t_end=7200.0, dt_routing=1.0, report_step=30.0,
        snapshot_times=(7200.0,),
        steady_window=1800.0,
        q_grade=0.7,
        max_depth=20.0,   # flood ceiling unreachable — see surcharge-cycle note
        # FV columns are expected-fail here (documented limitation): the
        # steep pressurized legs (19% drop / 18% rise over 15 m conduits)
        # excite spurious head transients — barrel heads spike to 20-60 m
        # intermittently. Probes: FV_CELL_LENGTH 2 reduces the error to
        # ~2.6 m (93 s wall), FV_ORDER 2 / RK2 to ~1.9-3.3 m; FV_LTS on the
        # 2 m cells breaks conservation (-3.8%). Under investigation.
        modes={"dw-legacy": "analytic", "dw": "analytic",
               "dw-slot": "analytic", "fv": "xfail", "fv-lts": "xfail"},
        tols={"head_steady": 0.05,     # final-window mean node head vs analytic, m
              "mass_pct": 0.5},
        # dw-slot carries the Sjoberg slot's artificial-storage head bias
        # (~0.13 m high on a 6.6 m surcharge) — characteristic of the
        # method, so its head tolerance is opened rather than hiding it.
        tols_by_solver={"dw": {"mass_pct": 2.0},
                        "dw-legacy": {"mass_pct": 2.0},
                        "dw-slot": {"mass_pct": 2.0, "head_steady": 0.20}},
        notes="Barrel sits 5.8 m below the hydraulic grade line; the whole "
              "system runs full once spun up.",
    ),
]


def case_by_id(case_id: str) -> Case:
    for c in CASES:
        if c.id == case_id:
            return c
    raise KeyError(case_id)
