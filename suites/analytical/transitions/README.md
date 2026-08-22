# transitions — open-channel ↔ pressurized flow

Purpose-built benchmarks for the moment a sewer stops being an open channel and
becomes a pipe under pressure — the regime change that stresses every routing
scheme differently.

| case | tests | analytic reference |
|---|---|---|
| `rapid-fill` | filling bore in a horizontal pipe from rest | front speed w = Q/(A_full−A₀) (Vasconcelos & Wiggert 2005) |
| `surcharge-cycle` | surcharge onset + relief under a hydrograph ~1.9× capacity | fully-pressurized peak-hold HGL at the friction slope |
| `inverted-siphon` | permanently pressurized siphon | steady energy balance HGL = stage + ΣSf·L |

This is the suite the LinkedIn call-out points at when asking for
transition-heavy and transient force-main models: contributed real-world cases
land in the corpus tagged `transition_pressurized` / `transient`, while the
analytic cases here stay the accuracy reference.

**Not yet migrated** — source `epaswmm5_qa/suites/transitions/`, plan step 2.
