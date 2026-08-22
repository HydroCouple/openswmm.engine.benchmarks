# Agent Handoff — build, run, and verify the benchmark machinery

**Date:** 2026-08-22 · **Branch:** `dev` · **Last commit:** `f6bf952`

## Why this document exists

Everything in this repository that can be verified **without a SWMM engine** has
been verified. Everything that needs a *running engine* has not, because the
work was done in a Linux sandbox and the available binaries are macOS arm64:

```
$ python -m harness.engines
openswmm-v6   RESOLVED   .../build/darwin-parity/bin/Release/openswmm
$ ./openswmm ...
OSError: [Errno 8] Exec format error
```

So the harness is written, unit-tested, and wired, but **no engine has ever been
run through it.** That is the gap you are picking up. Read this whole document
before starting; the plan is `plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md`.

**Ground rule inherited from `CLAUDE.md`:** write test artifacts to
user-reviewable locations (`results/`), never temp dirs. Follow preconfigured
plans rather than inventing new strategies.

---

## 1. Current state — what is true today

| | |
|---|---|
| corpus | **1,396** cases in `corpus/<collection>/<case-id>/`, 22 collections, all schema-valid |
| analytical | **53** cases: swashes 33, manufactured 17, transitions 3 |
| skip list | **92** entries, each with a stated reason and a route back |
| tests | **122**, none requiring an engine; `python -m pytest` is green |
| suites registered | `parity`, `epa_qa`, `quality`, `stability`, `performance`, `analytical/{swashes,transitions,manufactured}` |
| engines registered | `openswmm-v6`, `swmm-5.3.0` (both in-tree), `swmm-5.2.4` (blocked) |

### Verified without an engine

- Every `.out` reader path: subcatchment, node, link, system, and per-pollutant
  series; both output dialects; malformed-file rejection. Fixtures are
  synthesized byte-for-byte by `tests/outfixture.py`.
- `compare_full()` detects planted differences in **every** element kind
  including pollutants, matches variables by name across dialects and across
  reordered pollutant lists, and respects tolerances.
- `.rpt` parsing against real reports: 26/26 quality-continuity sections, LID
  performance tables, surcharge/flooding/instability table counts.
- All 27 closed-form SWASHES cases regenerate their committed `reference.csv`
  with max deviation `0.00e+00`; all 3 transitions cases regenerate; 6 of 17
  manufactured cases reproduce byte-exactly.
- Anonymization preserves topology and every non-coordinate number (checked on
  a 2,092-node network: 4,407 renames, zero topology breakage).
- Dashboard renders, escapes HTML, and reports verification separately from
  regression.

### NOT verified — needs you

- **No engine has been run through the harness. Not once.**
- The parity suite has never produced a real comparison cell.
- No suite report has been generated from real results.
- CI has never executed (workflows are committed but unrun).
- `runtime_class` on all 1,396 cases is an *estimate from element count*, not a
  measurement.
- The 90 skip-listed models have never been confirmed to actually fail.

---

## 2. Your task list, in order

Each task states its **acceptance criterion**. Do not mark one done without it.

### Task 1 — Build the engines and confirm the harness sees them

```bash
cd <engine-repo>
cmake --preset=Darwin -B build/darwin-parity          # or your platform preset
cmake --build build/darwin-parity --config Release \
      --target openswmm_cli openswmm_legacy

cd <benchmarks-repo>
export OPENSWMM_ENGINE_DIR=<engine-repo>
export OPENSWMM_BUILD_DIR=<engine-repo>/build/darwin-parity
python -m harness.engines
```

**Accept when:** both engines print `RESOLVED`, and the line
`swmm-5.3.0 vs openswmm-v6  rtol=1e-09 atol=1e-12 gate=fail` appears under
"comparisons". `swmm-5.2.4` printing `UNAVAILABLE` is expected and correct — it
is blocked on `ENGINE_524_BUILD_MODERNIZATION_PLAN_2026-08-16.md`.

### Task 2 — First real parity run (the moment of truth)

```bash
python -m suites.parity.suite --tier nightly \
    --only extran1,extran2,test1 2>&1 | tee results/first_parity.log
```

**Accept when:** cells carry verdicts other than `UNAVAILABLE`, and
`results/parity/scores_nightly.json` contains a `pair` cell with a real
`max_rel`, `total_cells`, and `worst_var`.

**What to watch for.** These are the specific things most likely to be wrong,
because they have never executed:

1. `_run_case` writes `<case-id>.rpt` / `.out` into
   `results/parity/<case>/<engine>/`, but runs the engine with the **repo root
   as cwd**. Models with relative data references (`USE RAINFALL "rain.dat"`)
   resolve relative to cwd, not to the model. If such cases fail, pass
   `cwd=case.dir` to `runner.run` in `suites/parity/suite.py:60` and re-test.
   14 cases have colocated data files and will expose this immediately.
2. Engines may need `DYLD_LIBRARY_PATH` beyond what `harness/engines.py:_dylib_dirs`
   supplies. If you see loader errors, extend that list — do not work around it
   in the suite.
3. `compare_full` has only ever seen synthetic and pre-existing `.out` files.
   Confirm `n_elements` and `total_cells` look sane for a known model before
   trusting any verdict.

### Task 3 — Full nightly sweep, and honest triage

```bash
python -m suites.parity.suite --tier nightly 2>&1 | tee results/sweep.log
```

Expect this to take hours and to surface failures. **Triage them by cause, and
do not "fix" a failure by loosening a tolerance without understanding it.**

- *Engine crash / timeout* → is the model pathological, or the engine wrong?
  Genuinely unrunnable models go on the skip list **with a reason**.
- *Parity FAIL* → this is the gate doing its job. Record the worst offender
  (element, variable, period, rel-err) and investigate in the engine repo.
- *Mass-balance excursion* → check against the case's `reference/legacy.rpt`
  where one exists; a case that always had 30 % continuity error is a property
  of the model, not a regression.

**Accept when:** every non-PASS cell is explained in
`results/SWEEP_TRIAGE.md` — cause, and either a fix or a skip-list entry.

### Task 4 — Confirm or clear the 90 skip-listed models

`suites/parity/manifests/skip_list.yaml` says these cannot run because input
data was never in the repository. That was inferred from static analysis,
**not observed**.

```bash
python -m suites.parity.suite --tier nightly \
    --only $(python -c "import yaml;print(','.join(e['case'] for e in yaml.safe_load(open('suites/parity/manifests/skip_list.yaml'))['skip'][:20]))")
```

(You will need to temporarily bypass the skip check to do this.)

**Accept when:** each entry is either confirmed failing for the stated reason,
or removed from the list because it actually runs.

### Task 5 — Measure runtimes and curate the PR tier (plan step 7)

Every case is `tiers: [nightly]` with an estimated `runtime_class`. Replace
both with measurements from Task 3's `wall` values.

Target: 50–100 cases, broad tag coverage, **under ~20 minutes per OS**.

```bash
# after the sweep, rank by measured wall time and tag coverage
python -m harness.corpus --census      # see what needs representation
```

Add `pr` to the chosen cases' `tiers:` and correct their `runtime_class`.
Record the selection rationale in `suites/parity/manifests/tier_pr.yaml`.

**Accept when:** `python -m suites.parity.suite --tier pr` completes in under
20 minutes and covers at least: `hydrology`, `hydraulics`, `quality`, `lid`,
`lid_pollutants`, `surcharge`, `force_main`, `rtc`, `groundwater`, `snowmelt`,
`dual_drainage`, `irregular_xsect`.

### Task 6 — Prove the gate actually fails

A gate nobody has seen fail is not known to work.

```bash
# perturb one engine's output deliberately, or bump a tolerance to 0
python -m suites.parity.suite --tier pr --only <a-passing-case>
```

**Accept when:** a deliberate perturbation produces a `FAIL` cell and a nonzero
exit code, and reverting restores green.

### Task 7 — Run the analytical suites against real engines

```bash
python run_regression.py --suite analytical/swashes
python run_regression.py --suite analytical/transitions
python run_regression.py --suite analytical/manufactured
```

The manufactured suite already passes (it checks reference reproducibility, not
engine output). Swashes and transitions have never graded a real run here.

**Accept when:** the swashes matrix produces PASS/FAIL cells per case × solver,
including the `1d-fv` and `2d-explicit` columns, and `SWASHES_REPORT.md`
regenerates.

**Note:** `1d-fv` is registered but was pre-marked unavailable in the source
repo. Confirm whether the engine's FV solver now runs; if it does, that column
becomes real and is the first FV coverage the platform has.

### Task 8 — Generate the dashboard from real data

```bash
python -m harness.report results/ --site site/build
python -m http.server -d site/build 8000     # inspect it
```

**Accept when:** the scoreboard shows real verdicts, the verification badge
reflects real analytical results, and per-run pages are keyed by the engine SHA
you built.

### Task 9 — Make CI real (plan steps 5–6)

Four workflows are committed with engine-build steps stubbed:

| file | what to replace |
|---|---|
| `.github/workflows/validate.yml` | the `smoke` job — build engines, run changed cases, comment on the PR |
| `.github/workflows/nightly.yml` | `Build engines` step |
| `.github/workflows/on_engine_push.yml` | `Build dispatched engine` step |
| `.github/workflows/publish.yml` | already real; verify the Pages deploy |

Then the engine-repo switchover: replace `regression_testing.yml` with a thin
workflow that sparse-clones this repo at a pinned ref and calls
`run_regression.py --suite parity --tier pr`. **Retire
`openswmm.engine/tests/regression` and `tests/regression_testing` only after
two consecutive green runs through the new pathway.**

### Task 10 — Cleanup decisions left open

1. **Legacy directories.** 15 remain at the repo root holding 250 `.inp` files
   that are byte-identical duplicates of migrated cases (verified by hash), plus
   ~20 stray files. Kept deliberately at the user's request. If that changes,
   deleting them is information-free — git history retains everything.
2. **Loose root files:** `bc_sncb.txt`, `bc_srg.txt`, `cho.txt`, `pp_s1.txt`,
   `runswmm.bat`, `swmm5_history_2017.md`. Unclassified; decide whether they go
   to `legacy/` or `data/`.
3. **`readme.md` vs `README.md`** are the same file on macOS. The original
   content is preserved at `docs/LEGACY_REPO_OVERVIEW.md`. On a case-sensitive
   filesystem this may appear as two files — reconcile to one.
4. **`epaswmm5_qa`** should be archived with a pointer here now that its suites
   are promoted. Its `docs/plan.md` cites `compare_engines.py` and
   `sweep_anderson_implicit.py` at the engine root; neither exists.

---

## 3. Known issues, ranked

**Blocking real use**

1. Nothing in the harness has run an engine (Tasks 1–3).
2. `cwd` handling for models with relative data references — see Task 2 note 1.

**Data debt**

3. **7 manufactured cases assert `reproducible: true` but ship no generator**
   (`dynwave-gvf-backwater-m1`, `exfil-cylindrical-storage-greenampt`,
   `exfil-storage-constant-area`, `kinwave-normal-depth-rect-open`,
   `odesolve-exponential-decay`, `odesolve-sir-epidemic`,
   `quality-cstr-first-order-decay`). The suite reports the unmet claim rather
   than skipping quietly. Writing those generators closes it.
4. **90 models reference input data never committed.** Skip-listed, unconfirmed.
5. **~126 models still carry absolute paths** in `USE` references — these leak
   usernames and client project names (`C:\Users\Robert\…`,
   `D:\IM\Projects\SC_Greenville_CI\…`). They belong to the broken-input set and
   are the first workload for `harness/anonymize.py`.
6. **3 collections marked `license: unverified`** — `greenville`, `simon-epa`,
   `special`. Excluded from redistribution claims until confirmed.
7. **Every case is `reference.class: self_consistency`.** Correct as a default,
   but it understates the EPA QA models, which have SWMM4 `.dat` references and
   should be `external_reference`. Upgrading a case is a deliberate, reviewed act.

**Upstream (report to `openswmm.engine`)**

8. Two manufactured-case `provenance.yaml` files shipped unparseable and were
   fixed here — absolute-value notation `|h(x)-…|` read as a YAML block scalar,
   and a list item containing a colon. The originals under
   `openswmm.engine/tests/benchmarks/manufactured/` still have the defect.

---

## 4. Things that are deliberate — do not "fix" them

Changing any of these without cause will make the platform dishonest.

- **`transition_pressurized` is untagged on every case.** Surcharging proves a
  conduit pressurized, not that it transitioned. Tagging ~390 models on that
  basis would make the tag useless to the suite it feeds. It is a curation
  decision, not an inference.
- **Skipped cases are excluded from the verification badge numerator** and
  disclosed separately (`6/6 checked · 11 unchecked`, yellow). Counting SKIP as
  a pass produced a green "17/17" for a suite that checked 6.
- **Accuracy metrics are refused for non-truth reference classes.**
  `scoring.check_accuracy_allowed` raises on purpose.
- **External engines are never gating.** `harness/engines.py` downgrades any
  `gate: fail` pair involving one.
- **A launch failure is `UNAVAILABLE`, not `ERROR`.** "This machine cannot run
  the engine" must not fail CI; "the engine ran and failed" must.
- **Legacy `reference/legacy.rpt` files are evidence, not references.** They
  came from an unrecorded engine and version. Cases stay `self_consistency`.
- **Duplicate `.inp` files left in legacy directories** — kept at user request.

---

## 5. Fast orientation commands

```bash
python -m pytest                          # 122 tests, no engine needed
python run_regression.py --list           # registered suites
python -m harness.engines                 # what resolved, and where
python -m harness.corpus --census         # models per tag
python -m harness.corpus "lid AND pollutants"        # tag query
python -m harness.validate --quiet        # validate all 1,396 cases
python -m harness.validate --changed      # only what a PR touched
python tools/repair_references.py         # audit file references (dry run)
python -m harness.anonymize <inp> -o <out> --map ids.json --verify
```

Reading order for the code: `harness/readers.py` → `compare.py` →
`rptparse.py` → `engines.py` → `suites/parity/suite.py`. Appendix A of the
plan explains why each exists and what it replaced.

---

## 6. What "done" looks like

The platform is real when a push to the engine repo's `develop` branch causes
this repository to run the PR tier, gate on parity, publish a dashboard whose
verification and regression numbers are separately true, and display badges the
engine README can link — with every skip and every failure carrying a stated
reason. Nothing above that line has been demonstrated yet.
