# Multispecies network and wet-pool suite

Run `python run_regression.py --suite quality/reactions --exe /path/to/openswmm`.
It produces 24 analytic cells: three network quality solvers, four reaction time units,
and default versus per-node/link parameter overrides. Three rain-fed
wet-pool cells check conservation through each network solver. The suite is discovered
by the normal benchmark runner. Generated inputs, native output, hashes and
score records stay under `results/quality_reactions/`.

The shipped wet, level-pool deck isolates the parent/product equations:
A' = -k A, B' = k A, initially A=1, B=0. Equal declared mass units and unit
yield make A+B=1 an independent invariant. Every reported minute is checked
against exp(-kt) at Tank and Pipe. Override cases use 2k at Tank and k/2 at
Pipe, preventing a global-only implementation from passing. Reference curves
come from the closed form, not a saved engine result. The report gives the
concentration and invariant tolerances explicitly.

These are numerical verification examples, not calibrated chemical networks.
The wet-pool cases require A+B=tracer at the subcatchment outlet and receiving
node, with positive product B and finite nonnegative output. Their reference
class is self_consistency; they do not establish time-history accuracy.

The extended suite now totals **38 cells**:

| Profile | Cells | Reference |
| --- | ---: | --- |
| Network parent/product | 24 | Analytic exponential and conserved sum |
| Wet subcatchment | 3 | Conserved A+B=tracer, positive product |
| WALL geometry | 2 | Analytic decay, bulk plus attached mass invariant; ARD fallback |
| Dry buildup | 3 | Analytic remaining mass, conserved sum; report mass units |
| Fully covered bioretention | 3 | Conserved sum, positive surface/drain product, LEGACY routing continuity within 0.25% |
| SETPOINT | 3 | Analytic 2 mg/L mixed-store target |

Wall and SETPOINT inputs use a fixed 0.5 s routing step aligned to reporting
periods. Dry report tolerances include printed mass rounding (0.01 units for
the analytic curve, 0.002 for the sum). WALL tolerances are 2e-5 concentration
and 2e-6 normalized mass; SETPOINT is 2e-5. LID sum tolerance is 2e-5.
The bioretention input is deliberately saturated/overloaded to exercise both
surface and drain export; it is not a design recommendation.

Engine unit tests separately compare uninterrupted and restored checkpoints
and output bytes, including source clocks, all reaction integrators, wet/dry
pools, bioretention/permeable-pavement layers and bucket/Richards storage nodes.
Partial capture, covered barrels, WALL porous chemistry and active 2D chemistry
remain outside these qualified profiles. The suite checks explicit scopes;
shared species names alone do not qualify another domain.
