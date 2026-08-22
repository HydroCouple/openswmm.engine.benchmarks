# quality — pollutants, treatment, and LID water quality

Covers the platform's largest coverage gap: water-quality behavior. Buildup and
washoff functions over multi-event forcing, treatment expressions at nodes,
co-pollutants, street sweeping, groundwater and RDII pollutant contributions,
and — the specific gap the submission call-out names — **LID controls acting on
pollutant loads**.

This suite is why `harness/compare.py` compares per-pollutant variables across
subcatchments, nodes, links, and system totals (Appendix A gap 2), and why
`harness/rptparse.py` scrapes quality continuity and the LID Performance
Summary from the text report (gaps 4–5) — the C API exposes neither for
arbitrary engines.

Seeded from the corpus's `WQ/` and `LID/` collections; the rest is expected
from community submissions.

**Scaffold stub** — plan step 3 populates it via tag query
(`quality OR lid_pollutants`).
