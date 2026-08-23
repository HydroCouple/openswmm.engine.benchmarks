#!/usr/bin/env python3
"""
Generate reference CSV for the infil-horton-constant-rainfall benchmark.

Horton infiltration under constant rainfall heavy enough to keep the surface
permanently ponded (capacity-limited throughout):

    f(t) = f_min + (f0 - f_min)*exp(-k*t)
    F(t) = f_min*t + (f0 - f_min)/k * (1 - exp(-k*t))

Internal solver units are ft/s (rate) and ft (depth); in/hr and in helper
columns are included for human review. Values are written at full
(round-trippable) double precision per shared/conventions.md.

Output: ../reference.csv
Columns: t_s, t_hr, f_ft_per_s, F_ft, f_in_per_hr, F_in
"""

import csv
import math
import pathlib

# ── parameters (US customary; 1 in/hr = 1/(12*3600) ft/s, 1 in = 1/12 ft) ─────
IN_PER_HR_TO_FT_PER_S = 1.0 / (12.0 * 3600.0)   # = 1/43200
F0   = 3.0 * IN_PER_HR_TO_FT_PER_S    # 3.0 in/hr -> ft/s
FMIN = 0.5 * IN_PER_HR_TO_FT_PER_S    # 0.5 in/hr -> ft/s
K    = 4.0 / 3600.0                   # 4.0 hr^-1 -> s^-1
TIMES_S = [0, 900, 1800, 2700, 3600, 7200, 14400]


def f_rate(t: float) -> float:
    return FMIN + (F0 - FMIN) * math.exp(-K * t)


def f_cumul(t: float) -> float:
    return FMIN * t + (F0 - FMIN) / K * (1.0 - math.exp(-K * t))


# ── generate + self-check ──────────────────────────────────────────────────────
rows = []
for t in TIMES_S:
    f = f_rate(t)
    F = f_cumul(t)
    rows.append((t, t / 3600.0, f, F, f * 43200.0, F * 12.0))

assert rows[0][3] == 0.0, "F(0) must be 0"
# rate decays monotonically toward f_min; cumulative grows monotonically.
for (_, _, f0_, F0_, _, _), (_, _, f1, F1, _, _) in zip(rows, rows[1:]):
    assert f1 <= f0_ and F1 > F0_, "monotonicity violated"
assert abs(rows[-1][2] - FMIN) < 1e-9, "rate must approach f_min by t=4 hr"

# ── write CSV ────────────────────────────────────────────────────────────────
out = pathlib.Path(__file__).parent.parent / "reference.csv"
with open(out, "w", newline="", encoding="utf-8") as fh:
    fh.write("# Horton infiltration, capacity-limited, constant rainfall (fully ponded)\n")
    fh.write("# f0=3.0 in/hr, f_min=0.5 in/hr, k=4.0 hr^-1\n")
    fh.write("# f(t) = f_min + (f0-f_min)*exp(-k*t)\n")
    fh.write("# F(t) = f_min*t + (f0-f_min)/k * (1 - exp(-k*t))\n")
    fh.write("# Internal units: ft/s for rate, ft for depth (full double precision)\n")
    fh.write("# t_s: time [s], t_hr: time [hr]\n")
    fh.write("# f_ft_per_s: rate [ft/s], F_ft: cumulative depth [ft]\n")
    fh.write("# f_in_per_hr: rate [in/hr], F_in: cumulative depth [in]\n")
    writer = csv.writer(fh)
    writer.writerow(["t_s", "t_hr", "f_ft_per_s", "F_ft", "f_in_per_hr", "F_in"])
    for (t_s, t_hr, f, F, f_inhr, F_in) in rows:
        writer.writerow([t_s, repr(t_hr), repr(f), repr(F), repr(f_inhr), repr(F_in)])

print(f"Wrote {len(rows)} rows to {out}")
print(f"f0 = {F0!r} ft/s, f_min = {FMIN!r} ft/s, k = {K!r} s^-1")
