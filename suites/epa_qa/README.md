# epa_qa — EPA SWMM5 Quality Assurance suite

Replicates the Rossman (2006) QA methodology on the 21 canonical QA models
(`extran1`–`extran10` incl. `extran8a`/`8b`, `test1`–`test5`, `user1`–`user5`),
comparing engines against each other and against the original **SWMM4**
reference time series (`*_q.dat` flows, `*_y.dat` depths).

`reference.class: external_reference` — the SWMM4 series is another tool's
output, not ground truth, so it adjudicates disagreement but cannot prove an
engine right. Engine-vs-engine parity within this suite is graded strictly
(float32 bit parity in the legacy-equivalent mode).

## Migration status

**Not yet migrated.** Source: `epaswmm5_qa/suites/epa_qa/` — `harness/`
(run_parity, run_variants, outdiff, qalib, summarize, build_report, schematic,
hgl_profile), `data/` (models + `.dat` references), and `QA_COMPARISON_REPORT.md`.
Plan step 2. On promotion, `outdiff.py` collapses into `harness/compare.py` and
`qalib.parse_rpt` into `harness/rptparse.py` (both already done); what remains
is the sweep driver, the config matrix, and the report/figure generation.
