# Corrected-engine MUSCL diagnosis — 27 October 2026

The user authorized repeating native first order and reconstruction-disabled RK2 on
the corrected engine, followed by a controlled reconstruction/limiter study.

Stage 1 uses the immutable `pinned-clean` image from the reconstruction study:
library SHA256 `3cfc7aa091be45e1261052bab12cb0d1a57085c4563594d4537624fc479c0dad`.
Its solver matches commit `336ca729`; provenance records its earlier frozen base.
The same coarse and broad constrained meshes, n=.01, Cs=0, no Coriolis, free-slip
walls, initial depths, gauge coordinates and 0.1 s output are retained. Diagnostics
cover 30 s and are not new 120 s qualification or regression-anchor promotion.
The existing corrected second-order cases provide controls. Both the original
visibility-selected observations and the separately audited strict connected-marker
subset will be reported with their coverage; neither is a complete laboratory series.

Run from the benchmark checkout using `.venv/bin/python`. Execution order is
`run.py coarse-order1 coarse-muscl-off`, then `run.py broad-order1 broad-muscl-off`,
`prepare.py`, `qualify.py`, `finish_experiments.py`, review completed evidence and
write `interpretation.json`, then `report.py`. Independent work may overlap, but
the experimental driver requires completed qualification and a zero-change replay.
`progress.py` reads live binary-output timestamps without opening active HDF5.
The website copies of these scripts are an archive; run the originals, whose
paths resolve their local dependencies. Existing result directories are refused.

Stage 2 will use a separate source archive and binary, with a zero-change replay
and native/analytical qualification before hydraulic interpretation. Experimental
controls will be selected from the stage-1 outcome, recorded before execution,
and applied consistently to interior and reflective-wall reconstruction. Failed
controls remain evidence and will not become production options. Physical
parameters and geometry will not be fitted to the observations.

Assessment includes all six UK reporting panels (five have recovered measurements), local
front position and normal-flow diagnostics, conservation and stability. A better
G2 score alone is not a criterion for changing defaults. The known full-SWE
partially wet crest-isolation limitation is retained as an unresolved issue.

The first one-second replay completed natively but its extractor requested the
full Test 6 snapshots through 30 s. That rejected postprocessing attempt remains
under `rejected-snapshot-request-replay-1s`. The corrected short-preflight
classification requests no full-case snapshots and its rerun passes field
identity. Neither attempt changes the physical model or the assessed controls.
