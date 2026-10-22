# UK hydraulic river benchmark supplement

This dedicated suite reproduces the earlier EA W5-105 river benchmarks with SWMM2D CPU FULL_SWE, second-order reconstruction, one time tier, CFL 0.4 and one thread. It is separate from `uk_2d` and excluded from engine-to-engine parity, including explicit case requests.

The imported references contain **no competitor prediction**:

- A1–A5: all 101 analytical water elevations per part, W5-105/TR1 Appendix A, PDF pages 77–78. Geometry is imported from source rectangular cross sections, independently of the reference elevations.
- L: 251 original tabulated water elevations per gauge S1–S4 at 0.04 s, Appendix C, PDF pages 89–92. No chart digitization or time alignment is needed. The specification's prose says “4s intervals” once, but its table unambiguously lists 0.04 s. The importer validates the entire table grid rather than adopting that typo.
- J: four measured bridge afflux values from TR2J Table 4.1. A faithful bridge plus paired no-bridge implementation is pending. These targets are never used with an arbitrary loss coefficient or a projected opening surrogate.
- F: source-declared analytical initial depth/discharge profile, translated at the prescribed celerity. The source report explicitly declares the initial state analytical. Linear interpolation of its 5 km table is disclosed. The two report Manning values are compared separately with the constant-Chézy reference; errors include this law mismatch.
- E: the full four-hour, 500 m-spacing scenario is executable. The analytical accuracy comparison remains unavailable: TR2E identifies a sine/cosine phase conflict, and the linear-friction formula leaves its representative velocity unspecified. No phase or parameter is fitted to force agreement.

## Rebuild inputs

The supplied reports and source decks are locked in `sources.json`. The additional official [W5-105/TR1 specification](https://assets.publishing.service.gov.uk/media/602ac6a2d3bf7f031e1bdcea/_Benchmarking_of_Hydraulic_River_Modelling_Software_Packages_-_Test_Specifications.pdf) contains the A and L tables absent from the supplied result reports. It is a distinct retrieved source, not a newly discovered attachment in those reports.

```sh
python -m suites.uk_river.references --source-root /path/to/UKBenchmarking
python -m suites.uk_river.build
python run_regression.py --suite uk_river --exe /path/to/openswmm --output-dir results/uk_river/assessment --max-wall 600
```

The importer verifies the original bytes and fails altered sources, incomplete time grids and mismatched geometry. Output CSVs use explicit LF endings. Generated cases and references are self-contained for clean checkouts; execution does not require the local source PDFs, audit folder or plans.

## What passes mean

Numerical PASS requires full-duration output at every required time, finite fields, nonnegative water depth, the confirmed requested CPU/full-SWE solver, and absolute continuity error at most 0.5%. Numerical cells retain `reference_class=self_consistency`; a numerical pass must not be counted as passed analytical verification. Independent dimensional residuals are report-only because these source reproductions include declared representation differences. The suite does not grade itself by competitor agreement.

Test A maintains the 1 m longitudinal spacing and full one-hour quasi-steady duration. Two cells span its uniform 10 m width. No sidewall friction is added to the 2D bed-friction model. Test F retains the full 30-hour run. Test L uses the physical 19.3 m laboratory geometry, exact fitted 45-degree taper walls, and instantaneous release; the source result report instead extended its reservoir and used delayed analytical initialization. Both configurations and the physical 0.2 s gate opening are distinguished in every report. The 0.025 m grid is a sensitivity companion to the 0.05 m grid, not an additional historical scenario or a demonstrated convergence order.

The reporting register maps available source quantities to generated panels. It does not claim that every original figure, table, panel layout or direct steady-solver result has been reproduced.

## Numerical regression anchors

Initial anchors require an explicit review record and cannot overwrite an existing baseline:

```sh
python -m suites.uk_river.baseline --results results/uk_river/assessment --only a1,l --review 'Review of source identities, numerical checks, sampling and baseline scope'
python run_regression.py --suite uk_river --tier pr --require-complete --require-regression
```

Baseline identity binds model bytes, the extraction/comparison implementation and reference metadata; the metadata binds the reference CSV. Changing any of them requires a separate review. The original executed binary identities remain in each anchor. Baseline agreement detects changes; it does not convert a measured discrepancy into successful validation. Cross-platform tolerances still need qualification.

Full coverage explicitly includes J, which remains unavailable. `--require-complete` fails that full request. The PR pilot requests only A1/L and requires both numerical anchors. Scheduled/full evidence runs preserve J and E's qualification gaps in their output. Neither the article nor a successful partial job claims full scientific validation.
