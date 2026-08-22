#!/usr/bin/env python3
"""Solver columns for the transitions suite.

Per-solver [OPTIONS] are injected at deck-generation time so FV_* keys never
appear in legacy decks. LTS is ON by engine default (FV_LTS YES), so the
plain `fv` column must disable it explicitly — the pair isolates local
timestepping as the only difference.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SolverSpec:
    id: str
    exe: str                 # "legacy" | "refact"
    flow_routing: str        # DYNWAVE | FV
    opts: dict = field(default_factory=dict)
    label: str = ""          # figure/legend label


SOLVERS: list[SolverSpec] = [
    SolverSpec("fv", "refact", "FV",
               {"FV_MIN_CELLS": "1", "FV_LTS": "NO"},
               label="FV (no LTS)"),
    # MAX_TIERS 4, not the engine default 6: the tier-cap probe ladder on
    # surcharge-cycle (runs/_probe/surcharge_lts_t*) measured tiers<=4 clean
    # (t4: hold-mean 5.22 vs 5.18 analytic, continuity -0.001%, 2.4x faster
    # than FV_LTS NO), tiers=5 ringing to 21 m, tiers=6 catastrophic
    # (continuity -687%). The default-6 breakage is reported as a finding.
    SolverSpec("fv-lts", "refact", "FV",
               {"FV_MIN_CELLS": "1", "FV_LTS": "YES", "FV_LTS_MAX_TIERS": "4"},
               label="FV + LTS"),
    SolverSpec("dw", "refact", "DYNWAVE", {},
               label="DW (EXTRAN)"),
    SolverSpec("dw-slot", "refact", "DYNWAVE",
               {"SURCHARGE_METHOD": "SLOT"},
               label="DW (SLOT)"),
    SolverSpec("dw-legacy", "legacy", "DYNWAVE", {},
               label="Legacy DW (EXTRAN)"),
]


def solver_by_id(solver_id: str) -> SolverSpec:
    for s in SOLVERS:
        if s.id == solver_id:
            return s
    raise KeyError(solver_id)
