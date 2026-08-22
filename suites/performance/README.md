# performance — wall-clock measurement

Runtime only; correctness is graded elsewhere. Runs synthetic scale models
(`grid_10k` … `grid_500k`, `*_heavy` forcing stress models) and representative
real networks through every registered engine under `OMP_NUM_THREADS=1`,
best-of-N.

Output feeds `github-action-benchmark` (`customSmallerIsBetter`) on the Pages
dashboard, with metric names `<case> [<engine-id>]` so every engine — current,
historical, or newly registered — gets its own trend line without a workflow
change. PR runs compare and alert; only pushes publish.

**Fairness rule:** an engine is included in cross-engine timing comparisons
only when its registry entry asserts `comparable_build: true` (same presets,
same FP policy). External binaries built with unknown flags are timed but
reported separately.

**Scaffold stub** — source `openswmm.engine/tests/benchmarks/generated/`,
plan step 2.
