#!/usr/bin/env python3
"""
Generate reference CSV for the groundwater-linearized-recession benchmark.

Two-zone aquifer draining by linear lateral flow with no inputs. With b1=1 and
zero infiltration/evaporation/deep-loss the lower-zone head decays exponentially:

    dH/dt = -lambda*(H - h_star),   lambda = a1 / (ucf_gwflow*(phi - theta))
    H(t)  = h_star + (H_0 - h_star)*exp(-lambda*t)

Reference is the continuous analytic solution (NOT the RKF45 solution). Values
are written at full (round-trippable) double precision per
shared/conventions.md (the prior CSV rounded to 6 decimals).

Output: ../reference.csv
Columns: t_s, H_ft
"""

import csv
import math
import pathlib

# ── parameters (US customary) ────────────────────────────────────────────────
H_0     = 3.0
H_STAR  = 0.5
A1      = 10.0       # cfs per acre per ft
PHI     = 0.4
THETA   = 0.2
UCF_GW  = 43560.0    # ft^2 per acre
LAMBDA  = A1 / (UCF_GW * (PHI - THETA))   # = 10 / 8712 = 1/871.2 s^-1
TIMES_S = [0, 200, 400, 600, 800, 1000, 1200]


def H(t: float) -> float:
    return H_STAR + (H_0 - H_STAR) * math.exp(-LAMBDA * t)


# ── generate + self-check ──────────────────────────────────────────────────────
rows = [(t, H(t)) for t in TIMES_S]

assert rows[0][1] == H_0, "H(0) must equal H_0"
for (_, h0), (_, h1) in zip(rows, rows[1:]):
    assert H_STAR < h1 < h0, "recession must be monotone toward h_star"

# ── write CSV ────────────────────────────────────────────────────────────────
out = pathlib.Path(__file__).parent.parent / "reference.csv"
with open(out, "w", newline="") as fh:
    fh.write("# Linearized groundwater recession (lower-zone head)\n")
    fh.write("# H(t) = h_star + (H_0 - h_star)*exp(-lambda*t)\n")
    fh.write("# lambda = a1/(ucf_gwflow*(phi-theta)) = 10/(43560*0.2) = 1/871.2 s^-1\n")
    fh.write("# H_0 = 3.0 ft, h_star = 0.5 ft.  Full double precision.\n")
    fh.write("# Columns: t_s [seconds], H_ft [ft analytic lower-zone head]\n")
    writer = csv.writer(fh)
    writer.writerow(["t_s", "H_ft"])
    for (t, h) in rows:
        writer.writerow([t, repr(h)])

print(f"Wrote {len(rows)} rows to {out}")
print(f"lambda = {LAMBDA!r} s^-1, tau = {1.0/LAMBDA!r} s")
print(f"H(1200) = {H(1200)!r} ft")
