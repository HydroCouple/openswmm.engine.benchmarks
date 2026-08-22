#!/usr/bin/env python3
"""
Generate reference CSV for the odesolve-logistic-growth benchmark.

Closed-form solution of the logistic ODE

    dy/dt = r*y*(1 - y/K),   y(0) = y0
    y(t)  = K / (1 + (K/y0 - 1)*exp(-r*t))
          = 1 / (1 + 9*exp(-0.5*t))     [for r=0.5, K=1, y0=0.1]

evaluated in double precision and written at full (round-trippable) precision.

This regenerates the prior reference.csv, which had been populated with an
adaptive-RK45 *numerical* solution (deviating up to ~2.75e-5 from the closed
form) despite being documented as the exact analytic solution. The values
below are the genuine closed form, restoring the manufactured-solution
property the consuming test relies on.

Output: ../reference.csv
Columns: t_s, y_exact
"""

import csv
import math
import pathlib

# ── parameters ───────────────────────────────────────────────────────────────
R  = 0.5    # s^-1  growth rate
K  = 1.0    # carrying capacity (dimensionless)
Y0 = 0.1    # initial condition
TIMES = [0.0, 2.0, 4.0, 6.0, 8.0, 10.0, 12.0, 14.0]  # s, uniform 2 s spacing


def y_exact(t: float) -> float:
    """Closed-form logistic solution."""
    return K / (1.0 + (K / Y0 - 1.0) * math.exp(-R * t))


# ── generate + self-check ──────────────────────────────────────────────────────
rows = [(t, y_exact(t)) for t in TIMES]

# Sanity: monotone increasing, endpoints, bounded in (0, K).
assert abs(rows[0][1] - Y0) < 1e-15, "y(0) must equal y0"
for (t0, y0), (t1, y1) in zip(rows, rows[1:]):
    assert 0.0 < y0 < K and y1 > y0, f"monotonicity/bounds violated near t={t1}"

# ── write CSV ────────────────────────────────────────────────────────────────
out = pathlib.Path(__file__).parent.parent / "reference.csv"
with open(out, "w", newline="") as f:
    f.write("# Exact solution for logistic ODE: dy/dt = r*y*(1 - y/K)\n")
    f.write("# Parameters: r = 0.5 s^-1, K = 1.0, y(0) = 0.1\n")
    f.write("# y(t) = K / (1 + (K/y0 - 1) * exp(-r*t)) = 1 / (1 + 9 * exp(-0.5*t))\n")
    f.write("# Closed-form analytic reference, full double precision.\n")
    f.write("# Columns: t_s [seconds], y_exact [dimensionless]\n")
    writer = csv.writer(f)
    writer.writerow(["t_s", "y_exact"])
    for (t, y) in rows:
        writer.writerow([repr(t), repr(y)])

print(f"Wrote {len(rows)} rows to {out}")
print(f"y(8)  = {y_exact(8.0)!r}   (closed form)")
print(f"y(14) = {y_exact(14.0)!r}")
