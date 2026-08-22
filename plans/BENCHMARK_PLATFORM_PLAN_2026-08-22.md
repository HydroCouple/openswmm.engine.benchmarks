# OpenSWMM Benchmarks — First-Class Platform Plan — 2026-08-22

**Status:** Draft for review — no implementation yet.

## Vision

Transform `openswmm.engine.benchmarks` from a flat model corpus (1,589 `.inp`, 3.8 GB excl. `.git`, measured 2026-08-22; the 08-16 plan's 1,646/5.4 GB figures are superseded) into a
standalone, engine-agnostic **benchmarking and regression-testing platform for any SWMM-compatible
engine**. It becomes the *central pathway* for regression testing: the engine repo's CI clones this
repo (sparse, per tier) and runs the suites here instead of maintaining its own regression tests.
Engines are compared along explicit dimensions — **stability**, **mass balance**,
**element-by-element / timestep-by-timestep results**, **analytical accuracy**, and
**performance** — with results summarized into reports, dashboards, and README badges, and a
structured contribution pathway so the community can submit models.

## Relationship to prior work (vetted plans this builds on)

1. **`openswmm.engine/plans/BENCHMARK_REGRESSION_CI_PLAN_2026-08-16.md`** — supplies the engine
   registry (`engines.yaml`, engines-as-data), comparison-pair gating semantics, CI tiering
   (curated PR tier / nightly full tier), sparse-checkout strategy, `github-action-benchmark`
   perf publishing, and the 5.2.4 build-from-source approach. **Changed by this plan:** the
   harness moves from `openswmm.engine/tests/benchmark_sweep/` into *this* repo; everything else
   carries over. That plan should be marked superseded-in-part with a pointer here.
2. **`epaswmm5_qa` (`/Users/calebbuahin/Downloads/epaswmm5_qa/`)** — supplies the proven
   core/suites architecture (`core/engines.py runner.py readers.py scoring.py suites.py`;
   `suites/<name>/suite.py` with `run()`/`report()` protocol) and three working suites
   (`epa_qa`, `swashes`, `transitions`). Its README already states it is "organized to be
   promoted into a standalone repo consumed by the engine repo's GitHub Actions CI" — this plan
   is that promotion, with this repo as the destination.
3. **`openswmm.engine/tests/benchmarks/`** conventions (`provenance.yaml` + `reference.csv` +
   `definition.md` per case, `shared/conventions.md`) become the platform-wide case format.
4. **Prerequisite unchanged:** `ENGINE_524_BUILD_MODERNIZATION_PLAN_2026-08-16.md` still gates
   the 5.2.4 registry entry.

## Target repository layout

```text
openswmm.engine.benchmarks/
  README.md                  # badges, quickstart, taxonomy overview
  CONTRIBUTING.md            # submission process (§ Submissions)
  LICENSE                    # Unlicense (existing); per-case licenses may override via metadata
  run_regression.py          # CI entry point (promoted from epaswmm5_qa)
  harness/                   # promoted epaswmm5_qa/core + sweep additions
    engines.py               # registry resolution: in-tree, git-ref build, external binary
    engines.yaml             # THE engine registry (engines + comparison pairs, from 08-16 plan)
    runner.py                # deterministic execution, timing, timeouts, OMP pinning
    readers.py               # .out/.rpt readers + out_dialect adapters (swmm51/52/53)
    compare.py               # element × variable × period comparison, tolerances, gating
    scoring.py               # verdicts, scores envelopes, badge JSON emission
    suites.py                # suite discovery/protocol
    schemas/                 # metadata.yaml + provenance.yaml JSON Schemas
    validate.py              # corpus/schema/submission validator (CI + local)
  suites/
    parity/                  # engine-vs-engine sweep over the corpus (from 08-16 plan §A/B)
      suite.py
      manifests/tier_pr.yaml tier_nightly.yaml skip_list.yaml
    epa_qa/                  # promoted: 21 EPA QA models, SWMM4 .dat references, config matrix
    analytical/              # merged: swashes + transitions + engine manufactured/ (17 cases)
      swashes/  transitions/  manufactured/
    stability/               # stress cases (surcharge cycling, dry-bed, ponding, z1000Years)
    quality/                 # pollutant buildup/washoff/treatment/LID-pollutant cases
    performance/             # generated grids (grid_10k…500k, *_heavy) + wall-clock sweep
  corpus/                    # restructured model library (§ Taxonomy)
    <collection>/<case-id>/   # collection = organizational only; tags are canonical
      model.inp
      metadata.yaml          # REQUIRED (schema-validated)
      provenance.yaml        # REQUIRED (source, citation, license)
      reference/             # optional: reference.csv, SWMM4 .dat, observed data, blessed .out
      README.md              # optional narrative
  data/                      # shared external forcing files (rainfall .dat/.rff), deduplicated
  site/                      # static-site generator templates for the Pages dashboard
                             # (generated reports/badges are NEVER committed — see
                             #  § Reporting, artifacts & publishing)
  .github/
    workflows/               # validate.yml, nightly.yml, publish.yml
    ISSUE_TEMPLATE/model-submission.yml
    PULL_REQUEST_TEMPLATE/model-submission.md
```

## Taxonomy — multi-tag classification

Classification is by **tags, not a single category**: every case carries a `metadata.yaml`
with a `tags` list, and a model can carry as many tags as apply (a real-world LID network with
pollutants and a surcharging interceptor is *all* of those at once). Directory placement under
`corpus/<collection>/` is organizational convenience only (typically the source: `epa/`,
`owa/`, `contributed/`, …) and carries **no semantic weight** — tags are the canonical
classification, and suites, manifests, and reports select models by tag query, never by path.

```yaml
# corpus/<collection>/<case-id>/metadata.yaml
id: extran1-semi-circular
title: EXTRAN Manual Example 1, semi-circular conduits
tags: [hydraulics, dynamic_wave, surcharge, transition_pressurized,
       circular_xsect, regression, stability]        # multiple, namespaceless, controlled
size_class: S                    # XS(<10 elem) S(<100) M(<1k) L(<10k) XL(10k+)
runtime_class: fast              # fast(<30s) medium(<5min) slow | skip-list candidates
units: US                        # US | SI
routing: DYNWAVE                 # DYNWAVE | KINWAVE | STEADY
tiers: [pr, nightly]             # which CI tiers include it
reference:                       # see § Reference classes — verification vs regression
  class: external_reference      # analytic|manufactured|external_reference|observed|
                                 # blessed_baseline|self_consistency
  source: swmm4_dat
  files: [reference/extran1_q.dat]
tolerances: {rtol: 1e-9, atol: 1e-12, gate: fail}    # per-case override of pair defaults
```

**Tag vocabulary** lives in `harness/schemas/tags.yaml` — controlled (validator rejects unknown
tags, keeping search/census meaningful) but cheap to extend: adding a tag is a one-line PR with
a description. The vocabulary is organized in groups for documentation, though tags themselves
are flat:

- *Domain:* `hydrology`, `hydraulics`, `quality`, `lid`, `groundwater`, `snowmelt`,
  `controls`, `2d`, `interop`
- *Purpose:* `regression`, `analytical`, `stability`, `performance`, `calibration`
- *Features* (grows with the corpus): `dynamic_wave`, `kinematic_wave`, `surcharge`,
  `transition_pressurized`, `force_main`, `transient`, `pump`, `weir`, `orifice`, `rtc`,
  `pollutants`, `treatment`, `buildup_washoff`, `lid_pollutants`, `rdii`, `dual_drainage`, …
- *Provenance:* `real_world`, `synthetic`, `textbook`, `converted_xpswmm`, `converted_icm`

**Tag queries:** manifests and suite selectors accept boolean tag expressions
(`lid AND pollutants`, `transient AND NOT performance`), so curated tiers, suite scopes, and
report facets are all defined as queries rather than hand-kept file lists.

**Mapping of existing directories** (mechanical first pass — each old directory seeds initial
tags, refined during migration): `Hydrology/`→`hydrology`; `Hydraulics/`, `Weirs/`,
`Orifices/`, `Pumps/`, `OWA_EXTRAN/`, `NCIMM_ROUTING/`, `OWA_ROUTING/`→`hydraulics` + the
matching feature tag; `WQ/`→`quality, pollutants`; `LID/`→`lid`; `EPA/`+`Simon_EPA/`→split by
content (Extran examples→`hydraulics, textbook`; QA set→`suites/epa_qa`);
`Semi_Real_Models/`+`Greenville/`→`real_world`; `z1000Years/`+`Special/`→`stability`;
`SWMM5_NCIMM/`, `OWA_USER/`, `LEW_*`, `OWA_update_*`, `v12/`, `v13/`→triage (dedupe, then
tag); `XPSWMM/`+`ICM Import Log Files/`→`interop, converted_*`; `DataFiles/`→`data/`. A
migration script generates draft `metadata.yaml` from `.inp` section scans (routing method,
features present, element counts) so the ~1,600-model pass is automated with human review on
the curated subset only.

## Reference classes — verification vs. regression vs. parity

A case with a known analytical solution and a case that is "just a benchmark" answer different
questions, and the platform must never blur them: an analytic case identifies **which engine is
wrong**; a plain benchmark can only show **that engines differ**. Every case therefore declares
a `reference.class`, which determines what may be computed, what verdicts mean, and how it is
gated and reported.

| class | truth source | a failure means | default gate |
|---|---|---|---|
| `analytic` | closed-form exact solution (SWASHES, GVF, Ritter…) | the engine is wrong | fail |
| `manufactured` | exact by construction (MMS / integrated ODE) | the engine is wrong | fail |
| `external_reference` | SWMM4 `.dat`, EPA release binary, another tool | engines disagree; adjudicate | report |
| `observed` | field measurements | goodness-of-fit, not correctness | report |
| `blessed_baseline` | pinned prior output of a named engine @ SHA, human-reviewed | behavior changed (possibly intentionally) | fail-on-drift |
| `self_consistency` | none — invariants + cross-engine parity only | engines differ, or an invariant broke | parity gate only |

Consequences, enforced by `harness/scoring.py`:

- **Error norms and convergence order** (L1/L2/L∞, observed order under refinement) are computed
  **only** for `analytic` and `manufactured`. Reporting them against a baseline or another
  engine would imply an accuracy claim the reference cannot support.
- **Verification vs. regression are reported and badged separately:** a `verification` badge
  (analytic + manufactured cases passing / total) and a `regression` badge (parity + baseline
  drift across the corpus). "N models pass" is never presented as an accuracy claim — the
  dashboard states each figure's reference class inline.
- **`self_consistency` is the honest default** for the bulk of the migrated corpus: no external
  truth, validated by mass-balance and stability invariants plus engine-vs-engine parity. The
  migration script assigns it unless a reference file is found; upgrading a case to a higher
  class is a deliberate, reviewed act.
- **`blessed_baseline` requires provenance:** blessing engine id + git SHA + date + reviewer
  recorded in `reference.blessed_by`. Promoted from the SWASHES suite's `pin-baseline`
  mechanism ("user-reviewed pins only"). Re-blessing after an intentional behavior change is a
  PR that shows the diff.
- **Tags mirror the class** (`analytical`, `regression`, `calibration`) so tag queries can scope
  suites and reports to one epistemic category.

## Comparison dimensions (the scoring model)

Each suite run produces a **scores envelope** (JSON, engine git SHAs stamped) with per-case,
per-engine, per-pair metrics:

1. **Stability** — % routing steps not converged, avg iterations/step, min/avg timestep,
   flooding/instability counts from `.rpt`, oscillation index on selected series, crash/timeout.
2. **Mass balance** — runoff, routing (flow), and quality continuity errors from `.rpt`/API;
   gated thresholds per case class (default warn > 1 %, fail > 5 %, overridable in metadata).
3. **Element × timestep parity** — every subcatchment/node/link/system variable at every
   reported period via the `.out` API with `out_dialect` adapters; per-pair `rtol/atol` and
   `gate: fail|report` from `engines.yaml`, per-case overrides from metadata; report lists worst
   offenders (element, variable, period, rel-err) exactly as in the 08-16 plan.
4. **Analytical accuracy** — L1/L2/L∞ error norms and observed convergence order against
   `reference.csv`, computed **only** for `reference.class ∈ {analytic, manufactured}`
   (SWASHES + transitions + the 17 manufactured cases). Pinned-baseline drift detection
   (promoted from the swashes `pin-baseline` mechanism) is scored separately, as regression
   rather than accuracy.
5. **Performance** — wall-clock per model per engine (OMP_NUM_THREADS=1), historical trends via
   `github-action-benchmark` on gh-pages, PR alert at 120 %.

## Reporting, artifacts & publishing — where everything resides

Guiding rule: **generated results are never committed to `main` of either repo.** Three tiers
by lifetime:

1. **Per-run raw artifacts (ephemeral).** Scores envelopes, `.out`/`.rpt`, figures →
   `actions/upload-artifact` (30–90 day retention) + markdown `$GITHUB_STEP_SUMMARY`
   (per-model status, worst rel-err, continuity, timings, speed ratios — carried over from
   both prior plans). Local runs write to a user-reviewable, `.gitignore`d `results/` dir
   (CLAUDE.md 4.1).
2. **Published HTML dashboard (canonical, THIS repo's GitHub Pages).** `report.py` emits a
   static site — self-contained HTML with embedded JSON + charts — deployed via
   `actions/deploy-pages` (artifact-based Pages deploy; avoids gh-pages branch bloat).
   Site layout: `/` latest scoreboard + badges; `/runs/<date>_<engine>@<sha>/` immutable
   per-run reports (suite matrices/heatmaps in the epa_qa style); `/tags/<tag>/` per-tag
   facets + corpus census; `/dev/bench/` perf trends. `github-action-benchmark` keeps its
   perf-history JSON on a dedicated `benchmark-data` branch that the site build ingests.
   Retention: last N runs in full + JSON-only history beyond that.
3. **Committed to `main`:** nothing generated — only badge *links* in READMEs.

**Badges:** `scoring.py` emits shields.io *endpoint JSON* published with the Pages site —
consumable by this repo, the engine repo, and any registered engine's README: `verification`
(analytic + manufactured cases passing / total — the only accuracy claim), `regression`
(parity + baseline drift across the corpus), `parity` (pass/fail + max rel-err),
`mass-balance` (worst continuity %), `stability` (% cases stable), `models` (corpus count),
`perf` (link badge → dashboard). Plus standard workflow-status badges.

**Engine-repo trigger/publish flow** (`openswmm.engine` triggers and gates, never hosts):

- *PR / push CI (gating):* thin workflow — build engines → sparse-clone this repo at a pinned
  ref → run PR tier → gate on exit code. Results: step summary + workflow artifact only.
- *Push to `develop`/`main` (publishing):* after the gate passes, send `repository_dispatch`
  to this repo with the engine SHA; this repo's workflow builds that SHA, runs the fuller
  tier, and publishes to its own Pages. Cross-repo credential is one fine-grained PAT /
  GitHub App permission on the engine side (dispatch only); this repo publishes to itself
  with the default token.
- Engine README badges point at this repo's endpoints/dashboard — the engine repo displays
  results it doesn't host. Exception per the 08-16 plan: engine micro-benchmarks stay on the
  engine repo's gh-pages `/dev/bench/` (engine-internal).
- *External engines:* run the suite in their own CI against their binaries; results stay
  private, or are submitted via the same dispatch route for inclusion on the shared
  scoreboard.

## Migration inventory (into this repo)

| Source | Destination | Notes |
|---|---|---|
| `epaswmm5_qa/core/` + `run_regression.py` | `harness/` | rename core→harness; keep protocol |
| `epaswmm5_qa/suites/epa_qa` | `suites/epa_qa/` | models + SWMM4 `.dat` refs move under the suite |
| `epaswmm5_qa/suites/swashes` | `suites/analytical/swashes/` | keep case×solver matrix, pin-baseline |
| `epaswmm5_qa/suites/transitions` | `suites/analytical/transitions/` | |
| `engine tests/benchmarks/manufactured/` (17 cases) | `suites/analytical/manufactured/` | already in target per-case format |
| `engine tests/benchmarks/generated/` (grid_10k–500k, *_heavy) | `suites/performance/` | perf corpus |
| `engine tests/regression/data/` (Example1, cn_regen_parity, slot_*) | `corpus/` + parity manifests | C++ `test_regression_suite.cpp` semantics reimplemented in `suites/parity`; C++ test then retired |
| `engine tests/regression_testing/` (pytest placeholder + parity result dirs) | `suites/parity/` | placeholder absorbed |
| `engine tests/parity/snow`, `tests/qa/outfall_timeseries_bug` | `corpus/` (stability/hydrology) | with metadata |
| Existing corpus dirs | `corpus/<collection>/` + tags | per taxonomy mapping above |

**Stays in the engine repo:** unit tests, Google Benchmark micro-benchmarks
(`tests/benchmarks/bench_*.cpp` — compiled against engine internals), `tools/bench_2d`,
`parity_probe`. The engine's `regression_testing.yml` is replaced by a thin workflow that
clones this repo (sparse, PR tier) and calls `run_regression.py`.

**Coverage gaps (named explicitly in the LinkedIn call-out):**

- *Water quality / LID + pollutants:* existing `LID/` (25) and `WQ/` (9) models migrate, and
  `suites/quality/` targets LID-with-pollutants, treatment expressions, co-pollutants, street
  sweeping, and buildup/washoff over multi-event forcing.
- *Open-channel ↔ pressurized transitions:* the `transitions` suite seeds this (rapid-fill,
  surcharge-cycle, inverted-siphon), but real-world transition-heavy networks — surcharging
  interceptors, deep-tunnel fill events — are wanted for `suites/stability/` and the corpus.
- *Pressurized distribution / force-main systems with transients:* pump start/stop, valve and
  gate operations, filling bores — stress cases for the surcharge methods (EXTRAN vs slot vs
  dynamic slot) and prime candidates for the stability dimension.

All three are sourced first from community submissions.

## Engine registry (day one)

Per the 08-16 plan, engines are data in `harness/engines.yaml`:

- `openswmm-v6` (in-tree build of `openswmm.engine`) and `swmm-5.3.0`
  (`openswmm-legacy`) — the **gating parity pair** (`rtol 1e-9 / atol 1e-12`, `gate: fail`).
- `swmm-5.2.4` — git-ref build, **blocked** on `ENGINE_524_BUILD_MODERNIZATION_PLAN`;
  report-only pair vs 5.3.0.
- **External engines** — new spec type `{type: external-binary, path/env: ...}` +
  `out_dialect`: lets anyone benchmark EPA release binaries, OWA builds, or other
  SWMM-compatible engines locally. External engines are **report-only, never gating**, and are
  excluded from cross-engine *performance* claims unless flagged `comparable_build: true`
  (the 08-16 plan's comparable-configuration invariant). Engine discovery env vars
  (`OPENSWMM_ENGINE_DIR` etc.) carry over from `harness/engines.py`.

## Submissions — structured community contribution

- **`CONTRIBUTING.md`** documents the two routes:
  1. **PR route** (preferred): add `corpus/contributed/<case-id>/` with `model.inp`,
     `metadata.yaml`, `provenance.yaml`; PR template checklist (runs to completion on a public
     engine, no proprietary data, coordinates anonymized/offset if needed, license declared —
     Unlicense/CC0 preferred, must be redistributable).
  2. **Issue route**: `model-submission.yml` issue form (structured fields mirroring
     metadata.yaml) with file attachment, for contributors who don't PR; maintainers convert.
- **Validation CI (`validate.yml`)** on every PR: schema-validate metadata/provenance, run the
  model on `openswmm-v6` + legacy with a timeout, check continuity sanity, verify referenced
  data files resolve, reject absolute paths, report runtime/size classes back on the PR.
- **Curation tiers:** submissions land as `tiers: [nightly]`; promotion to the PR tier is a
  maintainer decision recorded in the manifest with rationale (per the 08-16 plan's manifest
  convention).
- **Provenance policy** extends the existing README note: Greenville/Simon_EPA/Special get
  provenance confirmation during migration; anything unconfirmed is marked
  `license: unverified` in metadata and excluded from redistribution claims.

## Model anonymization

Many of the most valuable models — real networks that break engines — cannot be shared as-is.
We will provide an anonymization tool (`harness/anonymize.py`) as a first-class part of the
submission pathway. **Honest framing: no tool can guarantee anonymity, and we make no such
claim; it provides a layer of anonymization** that, combined with the submitter's own review,
lets otherwise unshareable models join the corpus.

Planned transforms (each individually selectable):

- Systematic renaming of subcatchment/node/link/gage/curve/pattern/LID IDs via a consistent map
  (submitter keeps the map privately if they ever need to trace back).
- Coordinate offset/rotation to a neutral origin, or full removal of `[COORDINATES]`,
  `[VERTICES]`, `[POLYGONS]`, and map sections.
- Scrubbing of free text: `[TITLE]`, comments (`;` lines), `[TAGS]`, description fields,
  absolute file paths, and rain-gage station identifiers.
- Externalized forcing renamed and relocated under `data/` with generic names.

**Correctness invariant:** the tool re-runs the model before and after and requires the `.out`
results to be bit-identical — anonymization must never change physics. `validate.yml`
complements it by scanning every submission for likely identifying content (place names in
IDs/titles, lat/long-like coordinate ranges) and flagging findings on the PR for the submitter
to confirm. CONTRIBUTING.md states the layered-defense caveat explicitly and puts final
responsibility for data sensitivity on the submitter. Detailed design goes in a follow-up
`plans/MODEL_ANONYMIZATION_STRATEGY.md`; the tool lands with the submission pathway (step 5).

## CI/CD

**This repo:** `validate.yml` (PR validation, above); `nightly.yml` (full sweep, Linux +
Windows, all registered engines, skip-list for stragglers); `on_engine_push.yml`
(`repository_dispatch` receiver: builds the dispatched engine SHA, runs the fuller tier);
`publish.yml` (Pages site build + badges + perf, via `actions/deploy-pages`, invoked by the
two run workflows). Sparse-checkout friendly: harness + suites + one manifest's corpus paths ≈
small; only nightly needs the full corpus (cached on HEAD sha).

**Engine repo:** `regression_testing.yml` becomes: build engines → sparse-clone this repo
(pinned ref, PR tier manifest) → `python run_regression.py --suite parity,analytical
--tier pr` → gate on the envelope exit code; on `develop`/`main` pushes it additionally sends
the `repository_dispatch` (see § Reporting). Badges in the engine README point at this repo's
workflows/endpoints. Model-sweep perf publishing moves here; engine micro-benchmarks keep the
08-16 plan §D.3 arrangement on the engine repo's own gh-pages.

## Implementation order & verification

```
0. PREREQ (parallel, unblocking 5.2.4 only): ENGINE_524_BUILD_MODERNIZATION_PLAN.
1. Scaffold: harness/ (promote epaswmm5_qa core per Appendix A — one reader, one rpt parser,
   one compare), schemas, engines.yaml, validate.py; close Appendix A gaps 1–3 (subcatch/system/
   pollutant series + comparison coverage, out_dialect adapter)
   → verify: run_regression.py --suite swashes runs green from THIS repo against local builds;
     a WQ model's pollutant series is compared and reported (gap 2 closed).
2. Migrate suites (epa_qa, swashes, transitions, manufactured, performance)
   → verify: each suite's report regenerates and matches its last known-good report.
3. ~~Corpus restructure~~ **DONE 2026-08-22** (`tools/migrate_corpus.py`,
   `tools/cleanup_legacy.py`): 1,396 cases under `corpus/<collection>/`, each with
   evidence-derived tags, metadata, and provenance; 248 byte-identical duplicates left in
   place; 4 zero-byte files excluded; 663 legacy reports preserved as per-case
   `reference/legacy.rpt` (the evidence behind the surcharge/flooding/instability tags, not a
   grading reference); source material moved to `legacy/`, data files to `data/`, 1,658
   regenerable outputs (770 MB) deleted.
   → verified: `harness.validate` green over all 1,396 cases; tag census reviewed.
4. Parity suite: port 08-16 plan §A/B (sweep + compare + manifests) onto harness protocol
   → verify: 5-model local sweep reproduces scripts/compare_results.py conclusions;
     deliberate perturbation fails the gate.
5. This repo's CI: validate.yml + nightly.yml + gh-pages publishing + badges
   → verify: PR with a sample submission passes validation; badges render; dashboard live.
6. Engine repo switchover: thin regression workflow consuming this repo; retire
   tests/regression + tests/regression_testing; CHANGELOG entries both repos
   → verify: engine PR CI green via the new pathway; old workflows removed only after two
     consecutive green runs.
7. Curated PR-tier manifest from full-sweep timings (~50–100 models, <20 min/OS).
8. Nightly full-tier dispatch → verify completion; skip-list captures stragglers.
9. Publish LinkedIn article (plans/LINKEDIN_SUBMISSION_INVITE_2026-08-22.md) once
   CONTRIBUTING.md + submission templates are live on main.
```

## Appendix A — Existing parsing infrastructure (surveyed 2026-08-22)

Scope of step 1 is consolidation, not greenfield. What exists today:

### `.out` binary readers (three implementations — consolidate to one)

| implementation | lines | assessment |
|---|---|---|
| `epaswmm5_qa/core/readers.py::Out` | 218 | **Adopt as the base.** stdlib+numpy only, random-access, *derives* `sys_vars` from record geometry (survives the 14-vs-15 system-variable difference), raw-byte accessors (`results_bytes`, `body_after_version`) for true bit parity, independent of the Python binding by design. |
| `openswmm.engine/scripts/compare_results.py::SwmmOutReader` | 307 (whole file) | Retire as a reader — **hardcodes 15 system vars**, so it would silently misread 5.2.4 output. Its header/ID/period comparison logic is superseded by `outdiff.py`. |
| `openswmm.legacy.output.Output` (Cython) | — | Richest API (attribute enums, timeseries by element/attribute, property codes, datetimes) but requires a binding in sync with the engine (documented "Solver size changed" staleness failure) and **only reads openswmm** — unusable for grading external engines. Keep as optional enrichment. |

`core/readers.py::Surface2DOutput` — h5py UGRID reader for the 2D engine output,
including the `mass_balance_2d` group. Adopt as-is.

### `.rpt` parsing

- `core/runner.py::parse_rpt` and `suites/epa_qa/harness/qalib.py::parse_rpt` — near-duplicate
  regex scrapers (runoff/routing continuity, avg iterations, % not converging, min/avg/max Δt,
  nodes flooded, links surcharged, instability count; qalib adds external inflow). **Merge into
  one `harness/rptparse.py`.**
- `openswmm/engine/_report.py::get_report_snapshot` (497 ln) — structured dataclasses for nine
  report sections with no text parsing, but requires in-process execution through the binding.

**Architectural rule:** because the platform grades *any* SWMM engine, the `.rpt` text +
`.out` binary path is the only universal contract and is therefore **primary**; the Python
binding is an openswmm-only enrichment (richer diagnostics, `MassBalance.quality_continuity_error`,
`ReportSnapshot`) and must never be on the critical path for a registered external engine.

### Comparison & metrics (strongest existing assets — promote largely intact)

- `suites/epa_qa/harness/outdiff.py::compare` — element × period × variable diffs with
  float32-ULP-aware verdicts, first-divergence location, worst offender, and a graded ladder
  (`strict_identical` → `full_parity` → `series_parity` → `near` → `DIVERGE`) plus raw-byte
  equality checks. Becomes `harness/compare.py`.
- `suites/swashes/swasheslib/metrics.py` — `profile_errors` (L1/L2/L∞), `front_error`,
  `shock_location`, `steady_residual`, `observed_order`, `grade`. The analytic-accuracy core
  for `reference.class ∈ {analytic, manufactured}`.
- `core/scoring.py` — verdict taxonomy, incremental envelope, CI exit policy. Extend with the
  reference-class semantics and badge emission.
- `core/runner.py::run`, `core/engines.py` — deterministic CLI execution, timing (best-of-N),
  timeouts, `OMP_NUM_THREADS` pinning, dylib env, engine discovery. Extend with the
  registry-driven resolution (`in-tree` / `git-ref` / `external-binary`).

### Gaps to close in step 1 (scoped work, not discovery)

1. `Out` exposes **no `subcatch_series()` and no `sys_series()`** — only nodes and links; it
   reads the IDs and computes the offsets but has no accessor. Add both, plus pollutant-variable
   indexing (`node_vars = 6 + n_pollut` etc. are already computed).
2. `outdiff.compare` covers **only** link{FLOW,DEPTH,VELOCITY,VOLUME} + node{DEPTH,HEAD,VOLUME}
   — **no pollutant, subcatchment, or system variables.** This contradicts scoring dimension 3
   ("every subcatchment/node/link/system variable at every period") and blocks the water-quality
   and LID emphasis. Highest-priority extension.
3. **No `out_dialect` adapter** mapping 5.2 (14 system vars) → 5.3 (15, adds `SYS_PET`) onto a
   common namespace; comparisons must run over the intersection.
4. **LID Performance, Outfall Loading, and Flow Classification summaries are parsed by nothing**
   — absent from both regex scrapers, and `ReportSnapshot` documents them as unavailable through
   the C API. At minimum LID Performance needs a text parser for the `lid` + `quality` suites.
5. Quality continuity is available via the binding (`MassBalance.quality_continuity_error`,
   `ReportSnapshot.quality_continuity`) but **not** scraped from `.rpt` — needed for the
   universal path.
6. Stale references: `epaswmm5_qa/docs/plan.md` cites `compare_engines.py` and
   `sweep_anderson_implicit.py` at the engine root; neither file exists any more. Fix on
   promotion.

## Appendix B — Corpus migration outcome (2026-08-22)

| | |
|---|---|
| cases in `corpus/` | **1,396** across 22 collections, all schema-valid |
| duplicates left in place | 248 byte-identical copies (verified by hash), plus 4 zero-byte files excluded |
| legacy reports preserved | 663 as `reference/legacy.rpt` |
| skip-list entries | 145, each with a reason and a route back |
| repo size | 4.1 GB → 3.4 GB (`corpus/` 2.1 GB, `legacy/` 1.1 GB, `data/` 46 MB) |

**Tag census highlights** — `hydraulics` 1,315 · `dynamic_wave` 1,289 · `hydrology` 734 ·
`surcharge` ~390 · `flooding` ~280 · `flow_instability` ~270 · `force_main` ~265 ·
`pollutants` 114 · `lid` 92 · `lid_pollutants` 28 · `dual_drainage` 20.

**What the migration exposed**

- **57 models were invisible to a case-sensitive glob.** They ship as `.INP`, including
  `HALF_A_MiLLION.INP`. Nothing failed — the count was simply 57 short, which is only
  detectable by reconciling totals. The scanner is now case-insensitive.
- **The inherited surcharge/flooding regexes matched nothing on any real report.** SWMM writes
  a *table* (`Conduit Surcharge Summary`) or the sentence "No conduits were surcharged", never
  "N links were surcharged". Every model everywhere was silently reported as never surcharging.
  Replaced with a table row counter, which distinguishes *absent section* from *zero rows*.
- **134 models reference absolute paths** from their authoring machine (`P:\Active\…`,
  `C:\Users\Robert\…`), several leaking usernames and client project names. They cannot run
  anywhere else, so they are skip-listed with a stated reason rather than failing forever — and
  they are the concrete first workload for the anonymization tool.
- **`transition_pressurized` is deliberately untagged.** Surcharging proves a conduit
  pressurized, not that it transitioned back and forth. Tagging 390 models on that basis would
  make the tag useless to the suite it exists to feed. It stays a curation decision.

**Follow-on work this creates**

1. Curate the PR tier (step 7) — every case currently lands in `tiers: [nightly]`, and
   `runtime_class` is an estimate from element count, not a measurement.
2. Relocate or recover the data behind the 134 absolute-path models.
3. Confirm provenance for `greenville`, `simon-epa`, and `special` (marked `unverified`).
4. Refine `reference.class` where a case has a real reference — everything migrated as
   `self_consistency`, which is correct by default but understates the EPA QA models.

## Out of scope

- Modifying benchmark model physics/content during migration (moves + metadata only).
- Gating on 5.2.4 or external-engine differences (report-only).
- GPU/Kokkos benchmarking; `parity_probe`/`bench_2d` drivers; engine micro-benchmarks
  (remain in the engine repo per 08-16 plan §D.3).
- Observed-data calibration scoring (future suite; metadata schema already reserves
  `reference.type: observed`).

## Open questions

1. Repo rename? `openswmm.benchmarks` (drops `.engine.`) better signals engine-agnostic scope —
   GitHub redirects make this cheap, but do it before the engine CI switchover if at all.
2. History rewrite to shed deleted blobs after restructure (fresh-start branch vs keep 5.4 GB
   history)? Affects clone cost for contributors more than CI (sparse handles CI).
3. z1000Years and other multi-hour models: nightly with generous timeout, or a weekly tier?
4. Does epaswmm5_qa retire entirely after promotion, or remain a scratch/dev sandbox?
   (Recommend: archive with a pointer here.)
