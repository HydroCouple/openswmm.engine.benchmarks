# Hi-res DW surcharge × continuity matrix (2026-08-13)

User request: unify the SWASHES matrix at ~1 m resolution and run ONLY these
solver columns (user chose "all 9 as requested" + 1 m via AskUserQuestion):

| # | column id                 | engine | SURCHARGE_METHOD | NODE_CONTINUITY |
|---|---------------------------|--------|------------------|-----------------|
| 1 | 1d-dynwave-legacy         | legacy | EXTRAN           | (n/a — ignored) |
| 2 | 1d-dynwave-legacy-slot    | legacy | SLOT             | (n/a — ignored) |
| 3 | 1d-dynwave                | refact | EXTRAN           | EXPLICIT        |
| 4 | 1d-dynwave-slot           | refact | SLOT             | EXPLICIT        |
| 5 | 1d-dynwave-dynslot        | refact | DYNAMIC_SLOT     | EXPLICIT        |
| 6 | 1d-dynwave-semi           | refact | EXTRAN           | SEMI_IMPLICIT   |
| 7 | 1d-dynwave-semi-slot      | refact | SLOT             | SEMI_IMPLICIT   |
| 8 | 1d-dynwave-semi-dynslot   | refact | DYNAMIC_SLOT     | SEMI_IMPLICIT   |
| 9 | 2d-explicit               | refact | (2D)             | (2D)            |

2d-explicit-adv is EXCLUDED per user. FV / kinwave / VJ columns are not in
this sweep; their cells for re-resolved cases are pruned as stale (re-runnable
later on request).

## Pre-verified facts (runs/_surcharge_probe/, 16 runs, byte-compared)

- Every SWASHES section is an OPEN channel (RECT_OPEN / TRAPEZOIDAL); the
  fairness rules keep junctions below their crowns. Slot machinery only
  engages on closed conduits at/above the crown (DynamicWave.cpp
  getSlotWidth: "open shapes never use a slot — they have no crown").
- Measured: EXTRAN ≡ SLOT ≡ DYNAMIC_SLOT **bit-identical** per engine, under
  BOTH continuity modes (probed on macdonald-long-sub and
  macdonald-short-shock). Columns 1≡2, 3≡4≡5, 6≡7≡8 by construction; the
  matrix runs them anyway as loud in-matrix documentation (user's choice).
- Known from 2026-08-13 parity work: 3 ≡ 1 bit-identical (NODE_CONTINUITY
  EXPLICIT = legacy behaviour). So the only genuinely new physics column is
  the SEMI_IMPLICIT trio (6/7/8).

## Resolution changes (target 1 m; short channels stay at their finer 0.5 m)

| case                   | nx (old→new) | dx    | dt_routing (old→new)          |
|------------------------|--------------|-------|-------------------------------|
| macdonald-long-sub     | 400→1000     | 1.0 m | 0.1→0.04   (0.25·dx/c, c≈6.0) |
| macdonald-long-sup     | 400→1000     | 1.0 m | 0.08→0.035 (c≈7.0)            |
| macdonald-long-sub2sup | 400→1000     | 1.0 m | 0.1→0.04                      |
| macdonald-long-jump    | 400→1000     | 1.0 m | 0.1→0.04                      |
| macdonald-periodic     | 500→5000     | 1.0 m | 0.4→0.04   (c≈5.2)            |
| macdonald-rain-sub     | 400→1000     | 1.0 m | 0.1→0.04                      |
| macdonald-rain-sup     | 400→1000     | 1.0 m | 0.08→0.03                     |

Unchanged (already at/below target): short channels (dx 0.5), bumps (dx 1.0),
p2d (dx 0.5/1.0), lake-at-rest; transient + bend families untouched.
2D strips inherit edge = 1D dx automatically (gen2d).

## Execution

1. Snapshot engine binaries (runs/_engine_snapshot/) and point
   OPENSWMM_BUILD_DIR at it — the engine repo is shared with a concurrent
   foreign session; a mid-sweep rebuild would mix engine SHAs.
2. New SolverSpecs (solvers.py) + policy mirroring: every steady/pseudo-2D
   case's DW cell policies are cloned onto the variant ids
   (casespec.mirror_dw_variants, note replaced by a mirror tag).
3. Parallel streams with per-stream copies of swashes_scores.json (save_cell
   rewrites the whole file — concurrent writers WOULD clobber), merged after.
4. gen-refs for the 7 re-resolved cases (reference density + provenance
   follow nx).
5. After runs: merge scores → prune stale fv/kinwave/vj/adv cells of the 7
   re-resolved cases → pin baselines (identical-by-construction variants may
   copy the base column's pin AFTER byte-verifying the extracted profiles
   match; SEMI trio gets fresh pins, flagged for user review) → report.

## WHEN macdonald-periodic FINISHES (the only outstanding run)

Stream s1 (`runs/_hires_sweep/s1.log`, ~31 min per 1D column x 8, then the 1 m
2D strip). On completion:

```bash
cd suites/swashes
conda run -n openswmm python runs/_hires_sweep/merge_scores.py   # folds s1 in
conda run -n openswmm python run_swashes.py report               # md + figures
```

Until then macdonald-periodic's un-run cells are pruned (blank in the report)
rather than shown at the old dx=10 numbers under a "dx = 1 m" header.

## Estimated wall (measured bases; OMP_NUM_THREADS=1 per run)

Long-channel 1D ≈ 3.5 min/run × 8 × 4 cases; periodic 1D ≈ 12 min × 8; rain
≈ like long (+rain-sup t_end 12000 ⇒ ×2); 2D long ≈ 3 min each; 2D periodic
≈ 2 h. Serial ≈ 6–7 h → ~4 parallel streams ≈ 2.5–4 h.
