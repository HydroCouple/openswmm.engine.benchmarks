# Analytic multispecies network suite

Run `python run_regression.py --suite quality/reactions --exe /path/to/openswmm`.
It produces 24 cells: three network quality solvers, four reaction time units,
and default versus per-node/link parameter overrides. The suite is discovered
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
The suite does not establish LID-layer, wet-subcatchment, wall geometry or
checkpoint/output-continuation support. Shared species names do not qualify
those domains. Reusable temperature and attached-wall decks are also shipped
in `openswmm.engine/examples/reactions/`.
