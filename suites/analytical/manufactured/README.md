# manufactured — exact-by-construction solutions

17 cases whose reference is exact by construction (method of manufactured
solutions, or an analytically integrated ODE) rather than measured or
simulated: Horton and modified-Horton infiltration, Green-Ampt trajectories,
storage exfiltration, groundwater recession, kinematic-wave normal depth,
GVF backwater, Ritter dry-bed, force-main friction, ODE solvers (exponential
decay, logistic, SIR), CSTR first-order quality decay, and cross-section
geometry references.

Each case already follows the platform's per-case format — `definition.md`,
`provenance.yaml`, `reference.csv` — so migration is close to a move.

**Migrated** (2026-08-22) from `openswmm.engine/tests/benchmarks/manufactured/`.

6 of the 17 cases ship a generator script and are verified here by
regenerating `reference.csv` and requiring a byte-exact match — a check that
needs no engine and runs in CI. The other 11 are reported SKIP; **7 of those
assert `reproducible: true` in provenance while shipping no generator**, so
that claim cannot be checked. Writing those 7 generators is open work.
