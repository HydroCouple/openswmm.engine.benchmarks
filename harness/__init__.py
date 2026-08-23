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

def use_utf8_stdio() -> None:
    """Make this process's stdout/stderr able to carry the text we print.

    Console encoding is environment-dependent — cp1252 on a Windows runner,
    US-ASCII under a bare LC_ALL=C — while the messages here are ordinary
    prose containing em dashes and the like. A validator that raises
    UnicodeEncodeError *while reporting warnings* fails for a reason that has
    nothing to do with the corpus it was asked to check.

    Called from CLI entry points only; importing the harness as a library must
    not reach into a host application's streams.
    """
    import sys
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError, OSError):
            pass          # already wrapped, or not reconfigurable — not fatal


__all__ = ["engines", "runner", "readers", "rptparse", "compare", "scoring",
           "suites", "validate", "anonymize", "report", "site", "corpus",
           "use_utf8_stdio"]
