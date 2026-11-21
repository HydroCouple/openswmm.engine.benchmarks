# UK Environment Agency 2D assessment and regression

This suite runs SWMM2D against independent observations/analytical constraints and its own approved regression baselines. UK cases are excluded from engine-to-engine parity, including explicit `--only` requests. Ten historical scenarios remain visible in coverage; seven have executable source-derived decks. Tests 7, 8A and 8B remain unavailable pending faithful coupling implementation or authoritative source inputs. Test 6A has no original measured time series in the supplied archive; a conservative subset of isolated laboratory markers has been recovered from the source report.

## Run

Install the repository requirements and set `OPENSWMM_EXE` / `OPENSWMM_BUILD_DIR` as described in the root README, or provide an explicit `--exe`:

```bash
python run_regression.py --suite uk_2d --tier pr --require-complete --require-regression
python run_regression.py --suite uk_2d --tier nightly --max-wall 300
python run_regression.py --suite uk_2d --tier weekly --require-complete --max-wall 3600
python run_regression.py --suite uk_2d --report-only
```

The PR tier runs complete Tests 1/3. Nightly requests all ten and exposes unavailable cases. The manual weekly qualification requires every scenario: it currently fails complete coverage until Tests 7/8A/8B are implemented. The scheduled weekly evidence sweep instead requests all cases with a 600-second budget and keeps skips/unavailable cases visible; a successful scheduled job is not full qualification. The partial-coverage badge remains non-green. `--require-observed` additionally fails if Test 6A measured validation cannot be performed. No canonical simulation duration is shortened to meet the timeout. A timeout is an error, not a pass. A recorded runtime above the selected budget produces a visible SKIP; `--require-complete` then fails missing required coverage. Test 4 initially timed out at 1,200 seconds, then completed in 1,375 seconds with the corrected engine and a longer budget. Its full run remains visible in the dated assessment and its measured cost keeps it out of the 600-second scheduled sweep. Missing required engines/cases/baselines are errors; unavailable optional cases remain visible in coverage.

Outputs are under `results/uk_2d/`: score envelope, report Markdown/HTML, run/binary/source identities, logs, extracted probe/volume series, profiles and maps. `--output-dir` changes the destination. HDF5 output is removed after successful extraction unless `--retain-h5` is given; failed runs retain it. Peak maps are explicitly **output-sampled maxima** and require cadence qualification before they support a stronger peak claim.

The clean CI build enables the CPU 2D HDF5 writer. The final local assessment uses isolated clean base revision `0ff03ce1ba06f23bd0ffe7077f9886ca04d4cea4` plus the separately hashed output-cache correction described below. Source archive, patch, build commands and executed binary hashes are retained in `results/uk_2d/output-freshness-fix/`. Reviewed baselines cover the seven completed cases; Tests 1/3 and corrected Tests 6A/6B also passed separate full-duration repeated executions with zero probe change. These are preliminary local change-control anchors. Cross-platform repeatability and tolerance qualification remain outstanding.

The current technical report is `results/uk_2d/assessment-2026-10-24/report.html`. Its assembly history retains the unchanged 22 October executions of Tests 1–5 and replaces Test 6 with the constrained-mesh runs. It includes the analytical supplement and four repeated-run checks. Test 6A still shows material G2 discrepancies (level RMSE 0.05597 m; speed RMSE 0.81879 m/s); it does not establish successful laboratory validation. The final automated harness check passed 291 tests, including the native output-freshness integration test. That integration test was also demonstrated to fail before the engine correction and pass after it.

The independent 6B repeat completed before the first-run anchor review. Its saved probe series was compared after review, with zero change. `post-run-baseline-comparison.json` and `comparison-history/` retain that sequence and the original unavailable-baseline coverage error; no engine failure was changed to a pass and no execution was relabeled.

## Rebuild source-derived models

The original archive is not vendored. Its identity and all nested members are locked in `suites/uk_2d/specifications/source-inventory.json`. Source reads verify checksums and never extract archive paths onto the filesystem.

```bash
cmake -S suites/uk_2d/mesher -B results/uk_2d/gui-mesher \
  -DGUI_SOURCE=/path/to/openswmm.gui -DCMAKE_PREFIX_PATH=/path/to/Qt/6.x/platform \
  -DCMAKE_BUILD_TYPE=Release
cmake --build results/uk_2d/gui-mesher --parallel
python -m suites.uk_2d.tin --exe results/uk_2d/gui-mesher/uk_gui_mesher \
  --gui-source /path/to/openswmm.gui --output results/uk_2d/test6-mesh
python -m suites.uk_2d.build --archive /path/to/Benchmarking_Model_Data.zip \
  --only 6a,6b --tin-mesh results/uk_2d/test6-mesh/mesh.npz \
  --test6b-elevations specification
```

The source builder can rebuild Tests 1–5/6A/6B. Test 6B additionally requires an explicit `--test6b-elevations specification` or `--test6b-elevations dem` because of the source conflict below. Existing reference and baseline directories are preserved. Rebuilding changed inputs will make a prior baseline incompatible; it does not silently promote a new one. Source permissions remain `unverified` and are recorded per case.

Tests 1–5 currently use nominal Cartesian quad spacing and bilinear DEM sampling, exact unit-normalized forcing tables and containing-cell gauge extraction. The valley uses the source domain/inlet shapefiles, a documented nominal-grid boundary and total discharge normalized over mapped inlet edges. Its one excluded NODATA boundary cell is recorded in `case.json`. **All remaining scenarios require a domain/boundary/breakline meshing audit and correction; this stage corrects Test 6 only, as requested.** No existing numerical PASS exempts the other configurations from that work.

### Test 6 constrained mesh correction (24 October 2026)

The adapter calls the actual GUI `mesh::MeshGenerator` and its custom constrained Delaunay kernel, linked directly from the GUI sources. No alternate triangulation library or triangle splitting of the old quads is used. Qt Core/Gui/Concurrent and the vendored robust predicates are sufficient; the GUI application and engine are not dependencies of model generation. The mesh provenance records the GUI source hashes, adapter hashes, generator executable, exact PSLG request, array hashes, refinement diagnostics and independent constraint audit. Run the hydraulic cases with the normal suite; Qt is required only when rebuilding geometry.

The exact dimensioned drawing in `EA2DTest6 - May2010.pdf` defines a 99 m by 3.6 m flume, reservoir length 6.75 m, dam thickness 0.8 m, a 1 m opening, and a 0.8 m by 0.4 m building rotated 64°. Building corner b1 is (3.44, -0.05) m, using its 1.75 m offset from the lower wall. The domain is therefore X=-7.55..91.45, Y=-1.8..1.8 m, with dam abutments excluded. The building is an excluded hole. Side-bank strips are 0.34 m wide and 0.155 m high. Unlike the old flat-bed raster mask, the TIN represents those planar slopes with constrained bank toes. This is an explicit reconstruction from the specification drawing: the supplied DEM has pixelated wall transitions and slightly offset bank samples, so this is **not** a vertexwise reproduction of that raster. Both source identities remain locked. Sensitivity to the drawing/DEM interpretation remains a qualification task.

The GUI output has 31,890 vertices, 61,642 triangles, a minimum angle of 30°, and no refinement cap or reported below-angle triangles. The 0.1 m target is nominal: actual edge lengths are 0.05678–0.15573 m and the largest triangle area is 0.007240 m². All 2,138 exposed edges are explicit reflective walls. The X=0 release line and bank toes are constrained **internal** edges. Audits require complete segment coverage, correct one-/two-cell adjacency, positive area, exclusion of obstacles, and a total active area of 354 m². Triangles do not cross the prescribed initial-depth discontinuity. The initial volume is 16.618 m³. Test 6B uses the same connectivity with XY and initial depths multiplied by 20: area 141,600 m² and initial volume 132,944 m³; roughness, reporting interval and duration remain independently prescribed by its source specification.

**Test 6B source conflict:** checksum-locked `Test6ADEM.asc` and `Test6BDEM.asc` have numerically identical elevation matrices. Only their horizontal coordinates/cell sizes differ by 20. Both the May 2010 specification and the 2013 report say all physical dimensions are scaled by 20. The user explicitly selected **`specification` on 24 October 2026**, giving 3.1 m high side banks. The alternative `dem` retains 0.155 m side banks while still using exact drawing boundaries in XY; it is not vertexwise raster interpolation either. The builder refuses to choose silently. The per-case mesh provenance records the selected interpretation and a source cross-section comparison. The 6B reruns follow the selected written-specification interpretation; no elevations or parameters are fitted to hydraulic results.

The previous Cartesian/flat-bed anchors are retained under each case's `baselines/cartesian-2026-10-22/`, including their original identities and a supersession record. They are incompatible with the corrected geometry and are never used as accuracy references or accepted as the new regression target. The builder refuses a Cartesian fallback for Test 6. Replacement regression anchors require completed numerical checks and a separate reviewed repeated execution. The October 22 result cohort remains historical evidence; corrected executions use a new dated result directory and the same identified engine so that engine changes are not mixed into the comparison.

Initial conditions follow the **local depths** stated in Appendix A.6.3, including over the restored bank slopes. The main report summary also uses water-level wording. A flat water-surface initialization is a different interpretation and remains a sensitivity study; it has not been fitted or substituted to improve the recovered measurement comparison.

The supplemental workbook profile coordinates are imported separately by `suites.uk_2d.profiles.import_profiles`; they contain geometry, not hydraulic reference results. Profile samples outside the discretized domain remain gaps.

## Separate analytical supplement

```bash
python -m suites.uk_2d.analytical --exe /path/to/openswmm --output-dir results/uk_2d/analytical
```

This runs immersed and partially dry stationary lakes using the same CPU FULL_SWE second-order profile. Exact equilibrium is defined on the represented piecewise-flat bed; this is a well-balanced preservation check, not a smooth-bed convergence study or a UK scenario. Predeclared targets are 1 µm maximum depth drift, 1 µm/s spurious speed, and 0.5% continuity error. There is no comparator model.

## Observed reference contract

Provide `reference/observations.json` and `reference/observations.csv` in the Test 6A case only after identifying and verifying the experimental data. Do not substitute another isolated-building experiment. No observed reference is fabricated or inferred from other models.

The CSV is long-format:

```text
time_s,probe,quantity,value
```

`probe` must identify a source gauge; `quantity` is `level_m` (water elevation in meters in the declared datum) or `speed_mps` (scalar speed in m/s). Times are elapsed seconds from the documented gate release. Blank observations remain missing. CSV records for each gauge/quantity must have strictly increasing times. The manifest requires `kind` (`observed` or `digitized_observed`), `source`, `citation`, `quantity_definitions`, `datum`, `time_origin`, `csv_sha256` and positive `max_gap_s`. Include documented instrument/digitization uncertainty and acquisition rights as additional provenance. Missing uncertainty must be identified as unknown.

The comparison interpolates predictions only onto supported observation times, excludes extrapolation and separates intervals exceeding `max_gap_s`. It reports time-weighted bias, MAE and RMSE, maximum absolute residual, sample count and covered duration. Fit is report-only. It never enters the exact-solution verification badge. The observed comparison and publication view still need independent reference review before an article can claim laboratory validation.

## Explicit baseline review

```bash
python -m suites.uk_2d.baseline results/uk_2d/uk-ea-2013-t01 \
  --reviewer 'Actual reviewer' --reason 'Specific evidence and scope of acceptance'
```

Promotion refuses failing numerical checks or an existing baseline. A baseline includes input/probe/analysis and binary identities, reviewer/reason/date, data checksum, tolerances and qualification scope. There is no automatic replacement after a failure. Replacing an accepted baseline requires a separate reviewed change with before/after scientific evidence.

`PASS` means numerical checks passed. `BASELINE-PASS` means an accepted SWMM2D result was retained. Neither verdict means experimental validation. Full technical-report coverage is tracked against Chapter 4 Figures 4.1–4.48 and Tables 4.1–4.13 in the packaged `specifications/report-crosswalk.csv`. Each generated report also writes `report-output-register.csv`, with source pages and links to available counterparts. `figure-display-specs.json` records the visually transcribed source time units, per-gauge windows/axis limits and profile frames for Figures 4.3/4.5/4.8/4.10/4.11/4.16/4.17/4.25–4.28/4.20–4.23/4.30/4.31. Original-axis and full-range companions are both retained. Map extents and remaining panel layouts still require qualification. Required Appendix A snapshots are rendered separately from sampled peak maps. Missing views remain visible.

## Recover the published laboratory subset

```bash
python -m suites.uk_2d.digitize --pdf /path/to/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf
```

The source PDF hash is locked. The algorithm uses the exact isolated 5×5 magenta diamond marker from the UCL legend and excludes the legend region and continuous strokes. It recovers 611 isolated markers binned into 446 x-pixel samples across five series; no G6 markers survive conservative recovery. Source pixel coordinates, image hashes, axis calibration, per-series pixel uncertainty, visibility bias and extraction provenance are retained. Treat the resulting comparisons as exploratory fit to a selected digitized subset; original records and independent digitization review remain outstanding.

## Required engine output correction

The assessment exposed a 30-second velocity cache in the engine output path. `SurfaceRouter2D::refreshRenderFields` now refreshes RT0 face velocity when output is prepared. `tests/test_uk_2d_engine.py` fails on the original engine and passes after this correction, checking every 0.1-second velocity against current edge flux and depth. The UK workflow requires this native integration test; the engine fix (`1397f7bc5e3756c501996771d617ab91ca0c691e`) must be included in its engine revision. See [the output-freshness finding](OUTPUT_VELOCITY_FRESHNESS.md) and the visible evidence/patch in `results/uk_2d/output-freshness-fix/`.


The wall-sensitivity runner uses explicit fractional clock strings (`0:00:00.1`
for Test 6A) and performs native 0.1 s / 1 s report-grid and analytical-velocity
preflights before launching TIN runs. Bare decimal time-step tokens are
reader-dependent: the current legacy-compatible reader interprets them as
hours. A successful process with no saved gauge frames is rejected, and its
output cannot be used for a measured comparison. Sensitivity inputs are generated separately from the corpus. The canonical
Test 6A input now uses explicit `0:00:00.1` clocks for REPORT_STEP, WET_STEP
and DRY_STEP. Its full 120-second repeat matched every existing regression
probe value and time exactly; the baseline data and tolerances remain unchanged.
The original producing-engine identity is retained, with the spelling migration
and verification recorded in `baselines/cpu-full-swe-rk2/clock-migration-2026-10-25.json`.
Case preflight rejects ambiguous bare global clock values before execution.

The GUI mesher adapter also accepts optional `refinement_boxes` in its JSON
request. Each entry has `xmin`, `xmax`, `ymin`, `ymax`, `max_area` and a positive
`transition_width`. Its target area increases linearly with distance outside
the box to the background `max_area`; the GUI's existing size callback performs
the refinement. Omitted or empty boxes retain the original mesh exactly.
These are target sizes, not a bound on every final edge after quality work.
Run the native adapter checks with `UK_GUI_MESHER=/path/to/uk_gui_mesher pytest
tests/test_uk_2d_mesher_refinement.py`. The separate
`analytical/hydraulic_jumps` suite verifies jump states and wall reflection;
it does not establish the correct front location around the Test 6 building.
