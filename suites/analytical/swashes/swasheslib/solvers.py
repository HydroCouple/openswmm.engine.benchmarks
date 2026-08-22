#!/usr/bin/env python3
"""The solver axis of the comparison matrix.

Adding a future 1D solver = one SolverSpec here (+ per-case CellPolicy entries
in cases_*.py). `1d-fv` is pre-registered as unavailable so the matrix shows
the column it will fill (plans/EXPLICIT_FV_KOKKOS_1D_SOLVER_PLAN.md).
"""
from __future__ import annotations

from .casespec import SolverSpec

SOLVERS: list[SolverSpec] = [
    SolverSpec(id="1d-dynwave", dim=1, exe="refact", flow_routing="DYNWAVE"),
    SolverSpec(id="1d-dynwave-legacy", dim=1, exe="legacy", flow_routing="DYNWAVE"),
    # ---- DW node-continuity column ----------------------------------------
    # SURCHARGE_METHOD (EXTRAN / SLOT / DYNAMIC_SLOT) is deliberately NOT on
    # the axis. Every SWASHES section is an OPEN channel
    # (RECT_OPEN/TRAPEZOIDAL) with no crown, so the slot machinery cannot
    # engage (DynamicWave.cpp getSlotWidth returns 0 for open shapes) and the
    # three methods are BIT-IDENTICAL per engine under both continuity modes —
    # byte-verified in runs/_surcharge_probe/. Carrying them as columns put
    # five provably duplicate series in every figure. RETIRED 2026-08-14.
    #
    # Where the three ever disagreed on this suite it was a DECK fault, not
    # physics: thacker-planar-1d and the bend family pegged at the conduit
    # MaxDepth (h == ymax == 3.500 m exactly), so an open channel was being
    # clipped as if it had a crown. Those decks need their MaxDepth raised;
    # that is tracked separately and is not a reason to keep the columns.
    #
    # NODE_CONTINUITY SEMI_IMPLICIT stays: it is genuinely different physics.
    SolverSpec(id="1d-dynwave-semi", dim=1, exe="refact",
               flow_routing="DYNWAVE",
               opts_1d={"NODE_CONTINUITY": "SEMI_IMPLICIT"}),
    # Same DW engine, but interior chain nodes are zero-storage virtual
    # junctions — isolates the value of momentum-preserving nodes vs the
    # junction-chain column. BASIC (default) = zero storage + direction-aware
    # cross-junction upwinding; FULL's extra dq4j flux term double-counts
    # v^2*dA/dx in EXTRAN's non-conservative form and destabilizes
    # frictionless chains (runs/_resolution_probe/VJ_FINDINGS.md) — not used.
    SolverSpec(id="1d-dynwave-vj", dim=1, exe="refact", flow_routing="DYNWAVE",
               virtual_interior=True),
    # RETIRED 2026-08-14: `1d-kinwave`. Kinematic wave carries no pressure
    # gradient, so it routes every case to normal depth and cannot represent a
    # backwater profile at all — on this suite it was a column of physics-limit
    # xfails rather than a comparison, and it cluttered every figure without
    # discriminating anything.
    #
    # The explicit FV solver — the settled configuration (2026-08-11):
    # FV_MIN_CELLS 1 for the like-for-like comparison (the harness already
    # discretizes into `nx` conduits, so this matches the DW columns' Δx), and
    # FV_JUNCTION_MODEL ALGEBRAIC: the junction is a zero-storage INTERFACE —
    # its head solves the instantaneous flux balance over its incident faces
    # each substep (both mass and momentum fluxes are the Riemann solutions at
    # the balancing head), so it carries no volume state, no dt bound and no
    # positivity bucket. Matches legacy DW's convention that a junction's own
    # surface area is zero. This is the configuration that first FINISHED the
    # MacDonald pair: the bucket model's crown-jam there was the transshipment
    # cap dt <= V_node/Q, not a scheme bias. Opt-in in the engine until the
    # pressurized gates pass.
    #
    # Retired diagnostic variants (superseded by ALGEBRAIC; see
    # runs/_coupled_node_study/RESULTS.md for their measured numbers):
    #   1d-fv-sub4   FV_MIN_CELLS 4 — subgrid resolution did not earn its cost
    #   1d-fv-nodedt FV_NODE_DT NONE + Picard 3 — symptom workaround
    #   1d-fv-vj     interior virtual junctions — symptom workaround
    # FV_JUNCTION_MODEL is retired engine-side: junctions are always
    # algebraic interfaces now, with degree-2 pass-through built in.
    SolverSpec(id="1d-fv", dim=1, exe="refact", flow_routing="FV",
               opts_1d={"FV_MIN_CELLS": "1"}),
    # The 2D axis is exactly two columns: the local-acceleration (local-
    # inertial) marcher as shipped, and the same marcher with the convective
    # momentum flux switched on. Everything else about the two decks is
    # identical, so any difference between the columns IS the advection term.
    #
    # Retired: the THETA sweep (2d-explicit-th07 / -th05). theta is the
    # q-centred de Almeida damping — the ONLY dissipation the scheme has at
    # n -> 0 — so it moves the sawtooth amplitude on frictionless plateaus and
    # nothing else. It cannot reach the plateau LEVEL or the shock position,
    # which follow from the missing convective flux (wrong Rankine-Hugoniot
    # conditions). Measured inert on the plateaus it was introduced for; the
    # advection column is the answer to the question theta was asking.
    SolverSpec(id="2d-explicit", dim=2, exe="refact"),
    # RETIRED at user request (2026-08-13): `2d-explicit-adv`, the opt-in
    # [2D_OPTIONS] ADVECTION column (Stelling-Duinmeijer convective flux).
    # The 2D axis is the local-inertial marcher ONLY. Its per-case CellPolicy
    # entries are left in cases_*.py, dormant (an unregistered solver id is
    # never run), so the measured advection findings stay on record and
    # re-registering this one SolverSpec restores the column intact.
]

BY_ID = {s.id: s for s in SOLVERS}
