# OpenSWMM Benchmarks

[![Validate](https://github.com/HydroCouple/openswmm.engine.benchmarks/actions/workflows/validate.yml/badge.svg)](https://github.com/HydroCouple/openswmm.engine.benchmarks/actions/workflows/validate.yml)
[![Nightly](https://github.com/HydroCouple/openswmm.engine.benchmarks/actions/workflows/nightly.yml/badge.svg)](https://github.com/HydroCouple/openswmm.engine.benchmarks/actions/workflows/nightly.yml)
<!-- Endpoint badges are published by the nightly run; they render once the
     Pages site is live (plan step 5). -->
[![Verification](https://img.shields.io/endpoint?url=https://hydrocouple.github.io/openswmm.engine.benchmarks/badges/verification.json)](https://hydrocouple.github.io/openswmm.engine.benchmarks/)
[![Regression](https://img.shields.io/endpoint?url=https://hydrocouple.github.io/openswmm.engine.benchmarks/badges/regression.json)](https://hydrocouple.github.io/openswmm.engine.benchmarks/)
[![Mass balance](https://img.shields.io/endpoint?url=https://hydrocouple.github.io/openswmm.engine.benchmarks/badges/mass-balance.json)](https://hydrocouple.github.io/openswmm.engine.benchmarks/)
[![Stability](https://img.shields.io/endpoint?url=https://hydrocouple.github.io/openswmm.engine.benchmarks/badges/stability.json)](https://hydrocouple.github.io/openswmm.engine.benchmarks/)
[![Models](https://img.shields.io/endpoint?url=https://hydrocouple.github.io/openswmm.engine.benchmarks/badges/models.json)](https://hydrocouple.github.io/openswmm.engine.benchmarks/)

An open, engine-agnostic **benchmarking and regression-testing platform for
SWMM-compatible engines**. 1,396 models — EPA and OWA regression
examples, the EXTRAN manual problems, the EPA QA suite with its original SWMM4
references, analytical test problems with exact solutions, and real-world
networks — run automatically against multiple engines and compared along
dimensions that matter to practitioners.

> **Status: under construction.** The harness is scaffolded and the corpus is
> migrated (1,396 tagged, schema-valid cases). Suite migrations, the published
> dashboard, and the engine-repo switchover are still to come.
>
> **No engine has been run through the harness yet** — everything verifiable
> without one is verified, and the rest is not. See
> [the agent handoff](plans/AGENT_HANDOFF_2026-08-22.md) for exactly what is
> and is not proven, and
> [the platform plan](plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md) for the
> design and implementation order.

## What gets measured

| dimension | what it answers |
|---|---|
| **Stability** | Does the solver converge? Does the timestep collapse? Does it crash? |
| **Mass balance** | Runoff, routing, and quality continuity error |
| **Result parity** | Every subcatchment, node, link, and system variable — including pollutants — at every reported timestep |
| **Analytical accuracy** | L1/L2/L∞ error norms and observed convergence order against exact solutions |
| **Performance** | Wall-clock per model per engine, tracked historically |

### Verification is not the same as regression

Only cases with a genuine exact solution (`reference.class: analytic` or
`manufactured`) can show an engine is **wrong**; the rest can only show that
engines **differ**. The platform keeps these apart deliberately — error norms
are computed for truth-class cases alone, and the `verification` and
`regression` badges are separate numbers. "1,396 models pass" is a regression
claim, not an accuracy claim, and is never presented as one.

## Quickstart

```bash
pip install -r requirements.txt

python -m pytest                                    # harness tests (no engine needed)
python run_regression.py --list                     # available suites
python run_regression.py --suite parity --tier pr   # the PR-tier sweep
python run_regression.py --suite all                # everything + reports

python -m harness.engines                           # what resolved, and where
python -m harness.corpus --census                   # models per tag
python -m harness.corpus "lid AND pollutants"       # tag query
python -m harness.validate                          # validate the corpus
```

Engines are located through environment variables — `OPENSWMM_ENGINE_DIR`,
`OPENSWMM_BUILD_DIR`, `OPENSWMM_EXE`, `OPENSWMM_LEGACY_EXE` — so the same
command runs locally and in CI. A missing engine degrades to `UNAVAILABLE`,
never a crash.

## Layout

```
harness/          engines · runner · readers · rptparse · compare · scoring · corpus · validate
  engines.yaml    THE engine registry — engines are data, not code
  schemas/        metadata + provenance schemas, tag vocabulary
suites/           parity · epa_qa · analytical/{swashes,transitions,manufactured}
                  · stability · quality · performance
corpus/           the model library: <collection>/<case>/{model.inp,metadata.yaml,provenance.yaml}
data/             shared forcing files (rainfall, timeseries)
legacy/           pre-migration source material (XPSWMM projects, summaries)
site/             dashboard templates (generated output is never committed)
plans/            design documents
```

## Adding an engine

Engines are declared in [`harness/engines.yaml`](harness/engines.yaml), not in
code. Three source types: `in-tree` (a local build), `git-ref` (built from a
ref, cached), and `external-binary` (any SWMM-compatible CLI). External engines
are **report-only** — never gating — and are excluded from cross-engine
performance claims unless their build configuration is asserted comparable.

## Contributing models

See [CONTRIBUTING.md](CONTRIBUTING.md). Models are classified by **multiple
tags**, carry provenance and a license, and can be run through an
anonymization tool if the network can't be shared as-is.

## License

The Unlicense (see [LICENSE](LICENSE)), matching EPA SWMM5's public-domain
status. Individual cases declare their own license in `provenance.yaml`;
anything marked `unverified` is excluded from redistribution claims. Three
collections — `greenville`, `simon-epa`, `special` — are contributed or
special-case models currently marked `unverified` pending provenance
confirmation.
