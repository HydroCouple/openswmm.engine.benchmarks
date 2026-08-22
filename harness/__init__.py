"""Engine-agnostic benchmarking harness for SWMM-compatible engines.

Modules:
  engines    engine registry (engines.yaml) resolution: in-tree / git-ref / external
  runner     deterministic CLI execution, timing, timeouts
  readers    .out binary reader (+ 2D HDF5), dialect adapter
  rptparse   .rpt text parsing — the universal, engine-agnostic contract
  compare    element x variable x period comparison, incl. pollutants + system
  scoring    verdicts, reference classes, scores envelope, badge emission
  suites     suite discovery (suites/<name>/suite.py exposing run/report)
  validate   corpus metadata/provenance schema validation
  anonymize  best-effort model anonymization for contributed models
  report     job summaries; delegates site rendering to harness.site
  site       static dashboard (scoreboard, per-run pages, tag facets)

See plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md.
"""

__all__ = ["engines", "runner", "readers", "rptparse", "compare", "scoring",
           "suites", "validate", "anonymize", "report", "site", "corpus"]
