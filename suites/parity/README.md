# parity — engine-vs-engine regression sweep

The central regression pathway that replaces the engine repo's own regression
tests. Runs every case in a tier through every resolved engine, then evaluates
each declared comparison pair element-by-element and period-by-period.

## What it grades

| dimension | source | gate |
|---|---|---|
| result parity | `.out`, all element kinds + pollutants + system vars, every period | pair's `gate` in `harness/engines.yaml`, overridable per case |
| mass balance | `.rpt` runoff / routing / quality continuity | thresholds from case metadata (default warn 1 %, fail 5 %) |
| stability | `.rpt` % steps not converging, iterations, Δt, crashes, timeouts | crash/timeout are always ERROR |

Cases carrying `reference.class: self_consistency` — most of the corpus — are
graded here and nowhere else: no external truth exists for them, so parity and
the invariants are the whole story. Accuracy claims come from the `analytical`
suite instead.

## Running

```bash
python run_regression.py --suite parity --tier pr
python -m suites.parity.suite --tier nightly --only extran1,test1
python -m suites.parity.suite --tier pr --engines openswmm-v6,swmm-5.3.0
```

Results land in `results/parity/` — user-reviewable, never temp dirs.

## Manifests

`manifests/tier_pr.yaml` and `tier_nightly.yaml` define each tier as a **tag
query** plus a timeout; `skip_list.yaml` excludes cases with a stated reason.
A case must both match the query and list the tier in its `metadata.yaml`.

## Status

Skeleton complete; `report()` is a stub. Blocked on the corpus migration
(plan step 3) for cases to run against.
