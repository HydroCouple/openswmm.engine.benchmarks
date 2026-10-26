# Test 6A bank resolution and momentum diagnostic

This dated study holds physical settings and drawing dimensions fixed. It uses
the GUI constrained mesher, the corrected FLAT/MEAN solver, two bank targets
(0.05 and 0.025 m), and 30-second histories. It does not promote regression
anchors or establish spatial convergence. The protected editable corpus input
is never used as a scratch deck.

Run scripts with the benchmark repository's Python environment and from their
original location in this directory. They depend on the preceding dated
reconstruction controls, pinned binaries and local GUI mesher; the website
copies are an archive, not a standalone executable distribution. Scientific
outputs are under `results/uk_2d/g2-bank-momentum-2026-10-26/`.

Execution order:

1. Preserve the declared `design.json`, completed corrected original and broad
   controls, and immutable corrected solver images from the reconstruction
   study. `bank_runs.py` creates the two new meshes, checks area/initial volume,
   runs both cases, and extracts results only after native completion.
2. `instrument.py` copies the frozen corrected source into the engine's
   `tests/verification/g2_bank_momentum_2026-10-26/source` and adds observational
   receipts. It refuses to overwrite an existing source tree. Build this copy
   in the sibling `build` directory using CMake Release, LTO ON, 2D/HDF5 ON,
   and GPU, Python, HydroCouple, benchmarks and unit tests OFF. The resulting
   CLI and engine library paths are checked by `audit_runs.py`.
3. `audit_runs.py` pins the diagnostic binaries, runs enabled/disabled 1-second
   cases and compares their fields with the original corrected control. Only
   after identity passes does it run the 30-second audit and verify all depth
   and velocity frames again. Native output and all failed attempts are retained.
4. Run `check_ledger.py audit-enabled-1` and
   `check_ledger.py audit-enabled-30`. Both compare accumulated receipts with
   independent momentum reconstructed from saved fields. The face-flux split
   is a diagnostic decomposition, not a numerical energy-loss measurement.
5. Run `test_front.py` and `cross_sections.py`. Review completed-case metrics,
   front diagnostics and momentum receipts before writing `interpretation.json`
   with `reviewed: true`. `report.py` then generates all four-case plots, exact
   input archives and the sealed publication manifest. The site publisher
   independently checks that manifest and fixed-input identities.

The scripts refuse existing run directories. Do not delete evidence to force a
rerun; use a new dated study and update its declared paths. `progress.py` uses
the public binary-output interface while a run is live. Analysis scripts require
completed cases before opening HDF5 files.

This study's two bank runs and momentum audit completed successfully. An early
1-second extraction requested unavailable 2–30-second UK snapshots; only that
postprocessing was repaired. Both native short runs were retained and passed
equivalence. The first report-build attempt had a Python syntax error; it did
not alter any simulation and its log was retained.
