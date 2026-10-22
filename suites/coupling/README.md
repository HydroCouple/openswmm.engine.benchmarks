# Rubinato 2017 coupling comparison

This suite runs the 36 observed steady rows, 15 legacy-orifice anchors,
36 physical-shaft sensitivities, the existing fine-mesh anti-choking check,
and 27 synthetic events (nine Table 1 constraints, three coefficient presets).
The synthetic events are not measured hydrographs or validation of Figure 11.

Build these targets in a 2D-enabled native engine checkout:

```sh
cmake --build ../openswmm.engine/build/1d2d-fine --target \
  test_engine_2d_exchange_rubinato_steady \
  test_engine_2d_exchange_rubinato_model
python -m harness.validate "$PWD/corpus/rubinato-2017"
python corpus/rubinato-2017/_tools/make_decks.py \
  --engine-ref ../openswmm.engine/tests/benchmarks/rubinato2017 --check
python run_regression.py --suite coupling \
  --native-bin ../openswmm.engine/build/1d2d-fine/bin/Release \
  --library ../openswmm.engine/build/1d2d-fine/bin/Release/libopenswmm.engine.6.0.0.dylib \
  --output-dir results/coupling/my-review
```

Python needs PyYAML for corpus validation; the sweep uses the standard library
and native shared library. Supply the corresponding `.so` or `.dll` on other
platforms, with its runtime dependencies available. Native tests require the
updated engine sources that export `shaft_vs_table2.csv`. Missing executables
produce `UNAVAILABLE`; execution failures produce `ERROR`.

Observed fit is report-only. `PASS` means completion, transfer direction,
successive-minute drift <= 2%, and absolute ordinary 1D continuity <= 2%; it
does **not** mean the measurements agree. The anti-choking check is a separate
self-consistency test and does not check mesh convergence. Synthetic checks
also require nonnegative depths, spill and drainback, and a pulse-induced
return in exchange direction. A nonzero exit preserves real numerical
failures even though the discharge goodness-of-fit is report-only.

`comparison.md`, `scores.json`, the two native logs, all generated inputs and
reports, transient series, and `binary_manifest.json` remain in the output
directory. Each execution starts a fresh envelope; use a new directory when
preserving an earlier sweep. The manifest identifies the binaries actually
used; a dirty repository identifier alone is not a reproducible release.

For the illustrated review, use the engine's `summarize.py` (numpy and
matplotlib) followed by `render_review.py` (reportlab and Pillow):

```sh
python ../openswmm.engine/tests/benchmarks/rubinato2017/summarize.py \
  --run-dir results/coupling/my-review \
  --output ../openswmm.engine/docs/validation/rubinato2017
python ../openswmm.engine/tests/benchmarks/rubinato2017/render_review.py \
  ../openswmm.engine/docs/validation/rubinato2017/review.md \
  ../openswmm.engine/docs/validation/rubinato2017/review.pdf
```

The six corpus cases include four steady reconstruction seeds, a legacy
comparison and a synthetic seed. They are metadata-complete; they are not
six independently validated experiments. The suite exports the physical
shaft alternative separately rather than silently replacing the earlier
junction model. The engine reference tables remain the source of truth;
`make_decks.py --check` checks the mirrored tables and generated seeds.

Q3 is reconstructed from `100 (Q3-Q4)/Q3`, the percentage column in Table 2.
Using `Re_p` as the inlet flow was an earlier reconstruction error. Synthetic
times are `HH:MM:SS`; `MM:SS` is interpreted as hours/minutes by SWMM and had
placed the pulse beyond the simulated interval. The synthetic shaft area,
MIN_SURFAREA and assumed 0.45 m downstream stage are explicit demonstration
choices, not measured boundary conditions.

Reference: [Rubinato et al. (2017)](https://doi.org/10.1016/j.jhydrol.2017.06.024),
*Journal of Hydrology* 552, 421-432. Reference tables: CC-BY-4.0. Original
numerical decks: CC0-1.0.
