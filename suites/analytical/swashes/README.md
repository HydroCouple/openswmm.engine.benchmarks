# swashes — shallow-water analytic solutions

Benchmarks 1D routing solvers and the 2D shallow-water engine against analytic
solutions from **Delestre et al. (2013)**, "SWASHES: a compilation of Shallow
Water Analytic Solutions for Hydraulic and Environmental Studies"
(doi 10.1002/fld.3741), on a case × solver matrix.

Cases: steady bumps (subcritical, transcritical, with shock), MacDonald
channels, dam breaks (Ritter, Stoker, Dressler), Thacker oscillations, plus 2D
paraboloid cases. Solvers: `1d-dynwave`, `1d-dynwave-legacy`, `1d-kinwave`,
`1d-fv`, `2d-explicit`, and the DW surcharge × node-continuity variants.

`reference.class: analytic` — error norms and convergence order are meaningful.
Pinned baselines (`pin-baseline`) are graded separately as regression, never as
accuracy.

**Migrated** (2026-08-22) from `epaswmm5_qa/suites/swashes/`; `core.*` imports
rewritten to `harness.*`.

Verified engine-free: all 27 closed-form cases regenerate their committed
`reference.csv` with max deviation `0.00e+00`. The 6 `bend*` cases use
engine-generated 2D references and are excluded from that check.

```bash
python -c "from suites.analytical.swashes import suite; suite.gen_refs(check=True)"
```
