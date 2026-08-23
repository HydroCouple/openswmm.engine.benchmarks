#!/usr/bin/env python3
"""
Generate reference CSV for the grnampt-saturated-trajectory benchmark.

Exact implicit Green-Ampt relation on the saturated branch, parametrised by
cumulative infiltration F:

    dF/dt = Ks * (1 + c1/F),   c1 = (S + depth)*IMD
    t(F)  = [F - c1*ln(1 + F/c1)] / Ks,    F(0) = 0

A column of F values is chosen and the exact time t(F) is evaluated for each.
Values are written at full (round-trippable) double precision per
shared/conventions.md (the prior CSV rounded t to 0.5 s, which dominated the
test's measured error).

Output: ../reference.csv
Columns: t_s, F_ft
"""

import csv
import math
import pathlib

# ── parameters (sandy loam, US customary) ─────────────────────────────────────
S     = 1.93 / 12.0        # 1.93 in suction head -> ft
KS    = 0.43 / 43200.0     # 0.43 in/hr saturated conductivity -> ft/s
IMD   = 0.25               # initial moisture deficit
DEPTH = 0.0                # no ponded water
C1    = (S + DEPTH) * IMD  # = 1.93/48 ft
F_VALUES = [0.0, 0.01, 0.02, 0.05, 0.10, 0.15]  # ft


def t_of_F(F: float) -> float:
    if F == 0.0:
        return 0.0
    return (F - C1 * math.log(1.0 + F / C1)) / KS


# ── generate + self-check ──────────────────────────────────────────────────────
rows = [(t_of_F(F), F) for F in F_VALUES]

# Self-check: t(F) must be strictly increasing in F and round-trip the ODE,
# i.e. dt/dF = (1/Ks)*(F/(F+c1)) > 0 and the relation holds to machine eps.
for (t0, F0), (t1, F1) in zip(rows, rows[1:]):
    assert t1 > t0 and F1 > F0, "monotonicity violated"
for (t, F) in rows:
    if F > 0.0:
        resid = (F - C1 * math.log(1.0 + F / C1)) - KS * t
        assert abs(resid) < 1e-15, f"relation residual {resid} at F={F}"

# ── write CSV ────────────────────────────────────────────────────────────────
out = pathlib.Path(__file__).parent.parent / "reference.csv"
with open(out, "w", newline="", encoding="utf-8") as fh:
    fh.write("# Green-Ampt saturated-phase cumulative infiltration trajectory\n")
    fh.write("# Parameters: S = 1.93/12 ft, Ks = 0.43/43200 ft/s, IMD = 0.25, depth = 0\n")
    fh.write("# c1 = (S + depth) * IMD = (1.93/12) * 0.25 = 1.93/48 ft\n")
    fh.write("# Formula: t(F) = [F - c1 * ln(1 + F/c1)] / Ks  (implicit Green-Ampt, F(0)=0)\n")
    fh.write("# Full double precision; F is the chosen parameter, t(F) is exact.\n")
    fh.write("# Columns: t_s [seconds], F_ft [ft cumulative infiltration]\n")
    writer = csv.writer(fh)
    writer.writerow(["t_s", "F_ft"])
    for (t, F) in rows:
        writer.writerow([repr(t), repr(F)])

print(f"Wrote {len(rows)} rows to {out}")
print(f"c1 = {C1!r} ft, Ks = {KS!r} ft/s")
print(f"t(0.15) = {t_of_F(0.15)!r} s")
