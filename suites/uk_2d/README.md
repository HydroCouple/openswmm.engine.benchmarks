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

The clean CI build enables the CPU 2D HDF5 writer. The final local assessment uses isolated clean base revision `0ff03ce1ba06f23bd0ffe7077f9886ca04d4cea4` plus the separately hashed output-cache correction described below. Source archive, patch, build commands and executed binary hashes are retained in `results/uk_2d/output-freshness-fix/`. Reviewed initial baselines cover the seven completed cases; Tests 1/3 also passed separate repeated executions with zero probe change. These are preliminary local change-control anchors. Cross-platform repeatability and tolerance qualification remain outstanding.

The dated technical report is `results/uk_2d/assessment-2026-10-22/report.html`. It includes the analytical supplement and links to repeated-run evidence. Test 6A shows material G2 level/speed discrepancies against the recovered subset; it does not establish successful laboratory validation. The final automated harness check passed 267 tests, including the native output-freshness integration test. That integration test was also demonstrated to fail before the engine correction and pass after it.

## Rebuild source-derived models

The original archive is not vendored. Its identity and all nested members are locked in `suites/uk_2d/specifications/source-inventory.json`. Source reads verify checksums and never extract archive paths onto the filesystem.

```bash
python -m suites.uk_2d.build --archive /path/to/Benchmarking_Model_Data.zip
```

This deterministically rebuilds Tests 1–5/6A/6B. Existing reference and baseline directories are preserved. Rebuilding changed inputs will make a prior baseline incompatible; it does not silently promote a new one. Source permissions remain `unverified` and are recorded per case.

Models use nominal Cartesian quad spacing and bilinear DEM sampling, exact unit-normalized forcing tables and containing-cell gauge extraction. Source walls/buildings in 6A/6B are masked as barriers; the horizontal flume bed is set to zero. This stair-step representation needs geometry sensitivity assessment. The valley uses the source domain/inlet shapefiles, a documented nominal-grid boundary and total discharge normalized over mapped inlet edges. Its one excluded NODATA boundary cell is recorded in `case.json`. None of these representation choices is a measured-validation finding.

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

`probe` must identify a source gauge; `quantity` is `level_m` (water elevation in metres in the declared datum) or `speed_mps` (scalar speed in m/s). Times are elapsed seconds from the documented gate release. Blank observations remain missing. CSV records for each gauge/quantity must have strictly increasing times. The manifest requires `kind` (`observed` or `digitized_observed`), `source`, `citation`, `quantity_definitions`, `datum`, `time_origin`, `csv_sha256` and positive `max_gap_s`. Include documented instrument/digitization uncertainty and acquisition rights as additional provenance. Missing uncertainty must be identified as unknown.

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
