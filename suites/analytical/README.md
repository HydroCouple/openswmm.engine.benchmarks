# analytical — benchmarks with known solutions

The three suites here are the platform's only source of **accuracy** claims.
Every case carries `reference.class: analytic` or `manufactured`, which is what
permits error norms (L1/L2/L∞) and observed convergence order to be computed
and what feeds the `verification` badge. Everywhere else in the platform,
"passing" means agreement or absence of drift — not correctness.

| suite | reference | source |
|---|---|---|
| `swashes/` | Delestre et al. (2013) shallow-water analytic solutions | `epaswmm5_qa/suites/swashes/` |
| `transitions/` | Open-channel ↔ pressurized transition analytics | `epaswmm5_qa/suites/transitions/` |
| `manufactured/` | Exact-by-construction (MMS, integrated ODEs) | `openswmm.engine/tests/benchmarks/manufactured/` (17 cases) |

Shared metric code (`profile_errors`, `front_error`, `shock_location`,
`observed_order`, `grade`) comes from `swasheslib/metrics.py` and moves into
`harness/` during migration.

## Migration status

**Not yet migrated** — plan step 2. The manufactured cases are already in the
target per-case format (`definition.md` + `provenance.yaml` + `reference.csv`),
so they move nearly as-is.
