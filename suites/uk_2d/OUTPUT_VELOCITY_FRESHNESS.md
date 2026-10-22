# Velocity output freshness finding — 22 October 2026

The Test 6A measured overlay exposed velocities held at zero for the first 30 seconds despite a propagating water-level wave. These values were excluded from the assessment after investigation.

## Cause

`SurfaceRouter2D::coAdvanceStep` computes `state.face_vx/face_vy` on a 30-second statistics cadence. HDF5 snapshots copy those cached values even when `REPORT_STEP` is 0.1, 1, 2 or 20 seconds. The render cache refresh already runs when snapshots are prepared, but previously did not refresh face velocity.

## Correction

`src/engine/2d/SurfaceRouter2D.cpp` now calls `computeFaceVelocity` inside `refreshRenderFields`. The header documents the expanded derived-cache refresh. This updates reported RT0 cell velocities from current edge fluxes when output is prepared. It does not change the solver advance. Cumulative engine envelopes still have their own statistics cadence, so the assessment computes and labels maxima over saved output times rather than claiming internal-step extrema.

Engine correction commit: `1397f7bc5e3756c501996771d617ab91ca0c691e`. The historical assessment retains its actual clean-base-plus-patch identity; this commit also includes later parent revisions and is not used to relabel those historical runs.

## Reproduction and verification

`tests/test_uk_2d_engine.py` runs a three-second, two-cell dam break with 0.1-second reporting. It checks that the first moving-water report has nonzero velocity, then independently reconstructs every reported RT0 velocity from the contemporaneous HDF5 edge flux, edge lengths/normals and depth. It fails on the clean original engine and passes with the correction. The native test is opt-in locally and required by the UK CI workflow after building the engine.

Visible evidence: `results/uk_2d/output-freshness-fix/{output-freshness.patch,regression-proof.json,before-test.log,after-test.log,build-provenance.json}`. The exact clean base source archive, copied changed sources and executed binaries are preserved there. Original-source SHA: `0ff03ce1ba06f23bd0ffe7077f9886ca04d4cea4`; the assessment identifies the output correction separately by patch SHA-256.

Before/after test commands use distinct complete binary identities. Test models, HDF5 output and logs are retained under `results/uk_2d/output-freshness-test/` for review.

The initial pre-correction pilot baselines were archived under `results/uk_2d/superseded-before-output-fix/`. Final initial baselines were reviewed from corrected-output runs; the standard promotion helper continues to refuse automatic replacement.

## Remaining limits

This is an output-path correction, not laboratory validation. The recovered laboratory dataset is a visibility-selected digitized subset. Original measurements, independent digitization review, terrain/mesh sensitivity and complete UK case coverage remain outstanding. The engine patch must be included in the engine revision used by remote benchmark CI; the new freshness test deliberately rejects a build without it.

## Canonical-water invariance check

For complete Tests 1, 2 and 3, the depth and water-level probe arrays were compared before/after the correction and were bit-for-bit unchanged. Reported speed changes were approximately 3.90e-7 m/s, 7.91e-8 m/s and 4.98 m/s respectively. The large Test 3 change demonstrates why sub-30-second velocity reports could not be used before correcting the cache. These differences concern reported derived fields, not a change to the advanced water solution.
