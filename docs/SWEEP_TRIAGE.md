# Parity sweep triage

**Engine SHA:** `421e95c2` + one uncommitted fix (see F1) · **Platform:** macOS arm64
· **Build:** `build/darwin-parity` (`-ffp-contract=off -fno-fast-math`, LTO)
· **Pair under gate:** `swmm-5.3.0 vs openswmm-v6`, `rtol=1e-9 atol=1e-12 gate=fail`

This is the honest record required by Task 3 of `AGENT_HANDOFF_2026-08-22.md`:
every non-PASS bucket gets a cause, and either a fix or a skip-list entry.
(The handoff names `results/SWEEP_TRIAGE.md`; it lives here instead because
`results/` is gitignored by design — "Generated results are NEVER committed" —
and this is authored analysis, which has to survive a clone.)
Failures are grouped by **mechanism**, not listed per case — a sweep of 1,396
models produces thousands of cells, and a per-case list is not triage.

Bucketing is mechanical (`tools/triage_sweep.py`), so the counts below can be
regenerated from the scores envelope rather than being hand-maintained:

```bash
python tools/triage_sweep.py results/parity/scores_nightly.json
python tools/triage_sweep.py results/parity/scores_nightly.json --markdown
```

---

## What was actually established

Before this pass, **no engine had ever been run through the harness**. It has
now graded real runs, and the machinery works: real cells, real metrics, a gate
that has been watched fail and recover (F6).

Two engine-level defects were found that no unit test caught, one of them
affecting a quarter of the corpus. Both were found by the sweep on its first
real outing, which is the platform justifying itself.

---

## F1 — `MAX_TRIALS 0` / `HEAD_TOLERANCE 0` ran ZERO routing iterations · **FIXED**

**Severity: critical. 362 of 1,396 corpus decks (26%) carry these values.**

Legacy treats a zero in either option as "use the compiled default"
(`dynwave.c:182-184`):

```c
if (HeadTol   == 0.0) HeadTol   = DEFAULT_HEADTOL;    /* 0.005 ft */
if (MaxTrials == 0)   MaxTrials = DEFAULT_MAXTRIALS;  /* 8 */
```

SWMM itself *writes* those zeros — `project.c:897-898` sets them to 0 precisely
to "force use of default" — so decks saved by the GUI ship them routinely.

`Routing.cpp` handled the same substitution for `MIN_SURFAREA` but not for
these two. With `max_trials = 0`, `while (t_steps < max_trials)` runs **zero**
Picard iterations: every link flow and node depth stays at its initial value
for the entire simulation. Silently — no error, no warning, and a clean mass
balance, because nothing moved.

**Evidence** (`extran2`, cells over tolerance out of 3,840):

| deck variant | over tol | worst non-temperature offender |
|---|---:|---|
| as shipped (`MAX_TRIALS 0`, `HEAD_TOLERANCE 0`) | 2382 | `link.VOLUME` max_rel 1.00e+00 |
| `MAX_TRIALS 8` only | 2232 | `link.VELOCITY` max_rel 2.32e+00 |
| `HEAD_TOLERANCE 0.005` only | 2382 | `link.VOLUME` max_rel 1.00e+00 |
| **both defaults restored** | **49** | `sys.STORAGE_VOLUME` max_rel 1.56e-07 |

Link `1030` carried 0.0 cfs for all 32 periods against legacy's peak of 122 cfs;
node `82309` never wetted. Both options must be substituted — either alone still
fails.

**Fix:** `openswmm.engine/src/engine/hydraulics/Routing.cpp`, mirroring
`dynwave.c:182-184`. **Uncommitted, in the engine working tree.**

**Verification:** engine ctest 159/160 before and after; the single failure
(`test_engine_2d_infil_integration`) was confirmed pre-existing by reverting the
fix and rebuilding. `extran1` and `test1` — decks *without* zeroed options — are
bit-for-bit unchanged, so the fix is inert where it should be.

---

## F2 — `sys.TEMPERATURE` differed on every deck with no `[TEMPERATURE]` section · **FIXED (match legacy)**

Legacy leaves `Temp.ta` at the zero-initialised value of its `Temp` struct when
`Temp.dataSource == NO_TEMP` — `climate.c`'s `setTemp` assigns it only for
`FILE_TEMP` or `TSERIES_TEMP` — and writes it straight out
(`output.c:629-631`). The refactored engine defaulted
`ClimateState::temperature` to **70.0 °F**, so legacy reported 0 °F and
openswmm-v6 reported 70 °F on every deck without temperature data:
`max_rel = 7.0e+07`, every period. It was the single largest contributor to the
FAIL count and it masked everything else.

**Resolved by matching legacy.** `SWMMEngine.cpp` now zeroes both
`temperature` and `temperature_src` when there is no temperature source
(`temp_source == 0` and no resolved timeseries). An API-prescribed temperature
still overrides, exactly as legacy's `Temp.apiTemp` does (`climate.c:1222`).

70 °F is the more sensible number, and this deliberately does not keep it: the
divergence was not confined to reporting. `Temp.ea`, the saturation vapour
pressure, is derived from `ta` and feeds evaporation, so the two engines also
disagreed on `ea` wherever no temperature source existed. Reproducing legacy is
what the parity gate is for; a better default belongs in a documented,
deliberate deviation rather than a silent 70-vs-0 disagreement.

**Effect** — `sys.TEMPERATURE` disappears from the offender lists entirely:

| case | over tol, before | after | worst offender now |
|---|---:|---:|---|
| `extran1` | 40 / 3840 | **8** | `sys.STORAGE_VOLUME` 8.4e-08 |
| `extran2` | 49 / 3840 | **17** | `sys.STORAGE_VOLUME` 1.6e-07 |
| `test1` | 735 / 78600 | **135** | `sys.STORAGE_VOLUME` 1.8e-07 |

What remains on those three decks is only the float32 ULP floor (see the
`f32-rounding` bucket) — they are otherwise at parity.

### F2b — the same variable, a second mechanism: SI decks with no subcatchments

Matching the default was not sufficient. Two cases (`akanyen`,
`10000footsurchargedepth`) still diverged, now by **−17.78** rather than 70 —
i.e. `(5/9)(0 − 32)`, a correct °F→°C conversion of the new zero. Legacy on the
same decks writes a plain **0**.

The reason is structural. Legacy assigns `SYS_TEMPERATURE` and `SYS_PET`, *and
applies the SI conversion*, at the end of `output_saveSubcatchResults` — which
is called only behind a guard (`output.c:489-490`):

```c
if (Nobjects[SUBCATCH] > 0)
    output_saveSubcatchResults(reportTime, Fout.file);
```

So on a deck with **no subcatchments** — the entire extran family and every
other pipe-only network — both stay at the zero-initialised value of
`SysResults` and are never converted. A raw 0 is reported whatever the unit
system.

The subtlety is that the °F→°C conversion is **affine**, so it is not enough to
feed the conversion a zero — it must be *skipped*. The fix carries
`has_subcatchments` on `SimulationSnapshot` and honours it both where the system
scalars are filled and in `convertSnapshotToDisplay`.

| case | over tol, before F2 | after F2 | after F2b |
|---|---:|---:|---:|
| `akanyen` (SI, 0 subcatchments) | 960 | 960 | **480** |
| `10000footsurchargedepth` (SI) | 47,524 | 47,524 | **4** — of 3,088,800 cells |

`sys.TEMPERATURE` no longer appears in any offender list.

**Verification:** engine ctest **159/160 run serially**, the single failure being
the same pre-existing `test_engine_2d_infil_integration`. The heat and snowmelt
suites pass, which was the risk worth checking: 70 °F was a deliberate default
with `temperature_src` / forcing machinery built around it.

> A `-j4` run additionally failed `test_engine_massbalance`, which **passes on
> its own and passes serially** — the known shared-fixture race (every engine
> unit test uses `data/` as its cwd, so same-named scratch files collide under
> parallel ctest). Not related to these changes, but worth knowing before
> trusting a parallel run's failure list.

## F3 — rain files finer than the gage interval lose most of their rainfall · **OPEN**

**Severity: high on continuous-simulation decks.**

`horton-continuous-model` declares a 15-minute `VOLUME` gage reading
`RAIN_GW.DAT`, but the file holds **5-minute** records. Over the exact
simulation window (2008-01-01 00:00 → 2008-01-30 00:00):

| source | inches |
|---|---:|
| every record in the file | 3.8800 |
| only records at `minute % 15 == 0` | **1.3600** |
| **openswmm-v6 reports** | **1.360** |
| **swmm-5.3.0 reports** | **2.633** |

openswmm-v6 matches the "sample every 15th minute" figure to three decimals: it
**samples** the file at the gage interval and discards the intervening records,
losing 65% of the rainfall. Legacy aggregates them (its 2.633 matches neither a
plain sum nor a sample, so its own binning convention still needs pinning down).

Everything downstream inherits the error — infiltration 2.051 → 1.059 in, surface
runoff 0.584 → 0.301 in. Not caught by unit tests because they use gages whose
interval matches their data.

**Next step:** engine-side, in the FILE-gage reader. Not attempted here: it needs
legacy's exact binning convention established first, which is a study in its own
right.

---

## F4 — the harness could not run either analytical suite · **FIXED**

`analytical/swashes` and `analytical/transitions` were migrated against a
pre-registry `harness.engines` and still called `engines.REFACT_EXE`,
`engines.LEGACY_EXE`, `engines.ENGINE`, and `runner.parse_rpt` — all removed
when the engine registry and `harness.rptparse` landed. Both suites raised
`AttributeError` before grading a single cell, which is why the handoff could
record them as "never graded a real run here".

**Fix:**
* `harness/engines.py` — the three names are back as *registry-derived* lazy
  attributes (PEP 562 `__getattr__`), so the registry stays the single source
  of truth rather than each suite re-implementing resolution.
* the two `runcase.py` files now call `rptparse.parse`. A shim on `runner` was
  deliberately **not** added: the refactor removed a second, divergent report
  parser on purpose ("one parser, one place").

`matplotlib` and `h5py` are declared in `requirements.txt` but were absent from
this environment; report generation needs them.

---

## F5 — comparison, not simulation, was the sweep's cost · **FIXED**

The first full-sweep attempt spent **855 s of 4,800 s wall in the engines** — 82%
of the time was `compare_full`.

`Out._series` gathered one element-variable series with `struct.unpack_from` in a
Python loop, one interpreter round-trip per period. The corpus holds roughly
**22 billion** float cells; at the measured 268k cells/s that is ~22 hours of
pure comparison — longer than the nightly window, and far longer than a CI job
is allowed to run. The nightly workflow could not have completed on a runner.

**Fix:** `harness/readers.py` gathers the strided bytes with numpy and views them
as float32. Same arithmetic, vectorised.

| | cells/s | full corpus |
|---|---:|---:|
| before | 267,948 | ~22 h |
| after | 7,964,164 | ~45 min |

**30×**, byte-identical results (`test1`: 735 cells over tolerance, same worst
offender, same `max_rel` before and after) and all 135 harness tests green.

---

## F6 — the gate has now been watched fail and recover · **DONE**

Task 6's requirement. Real engines, real `.out` files, the real scoring path:

| step | verdict | cells over tol | exit |
|---|---|---:|---:|
| 1. `extran1`, engine vs itself | PASS | 0 / 3840 | 0 |
| 2. one float perturbed by +1.0 | **FAIL** | 1 / 3840 | **1** |
| 3. perturbation reverted | PASS | 0 / 3840 | 0 |
| 4. same perturbation, `gate: report` | BASELINE-PASS | 1 (still recorded) | 0 |

Step 1 also establishes that the engine is **deterministic**: two runs of the same
deck produce byte-identical output.

This is now pinned permanently and engine-free in `tests/test_gate.py` (13 tests),
so it runs on every PR rather than being a one-off observation. That file also
pins the exit policy per verdict — in particular that `UNAVAILABLE` never gates
and that `ERROR` and `XPASS` always do.

---

## F7 — the sweep would have filled the disk · **FIXED**

A full sweep writes ~**167 GiB** of `.out` across two engines (estimated from
each deck's own geometry; the estimator is accurate to ~4% against real output).
This machine had **14 GiB** free. A single case — `half-a-million` — writes
>11 GiB per engine.

`suites/parity/suite.py` now:
* prunes bulk `.out` files once a case has been compared — `--keep-out
  fail|all|none`, default `fail` (retain only where a comparison did not pass,
  which are the ones a human drills into). `.rpt` is **always** kept: it is small
  and it is the mass-balance and stability evidence.
* refuses a case whose predicted output would not fit, recording
  **UNAVAILABLE** with the shortfall in the note — an environment limit, which
  per the platform's own taxonomy must not gate CI.

The sweeps recorded here ran `--keep-out none`; steady-state `results/` stayed
at ~50 MB. To drill into any single case, re-run that case alone.

---

## Environment caveat affecting measured runtimes

Other sessions were running heavy jobs on this machine throughout the sweep —
`SWMMVis` at ~700% CPU plus two concurrent `perf2d` engine runs. **The `wall`
values in this envelope are inflated and are not a sound basis for PR-tier
curation (Task 5).** Tier selection needs a re-timing run on a quiet machine.
The verdicts are unaffected: the engine is deterministic (F6, step 1).

---

## F8 — the corpus mutated itself on every sweep · **FIXED**

Three cases `SAVE HOTSTART` onto a path that resolves inside their own case
directory, and those files were **committed**:

* `corpus/owa-extran/extran8a/extran8.hsf`
* `corpus/owa-extran/extran8a-slot/extran8.hsf`
* `corpus/simon-epa/session43-clocktime-pump-rules/hotStart.HSF`

So every sweep rewrote three tracked files. Nothing reads them — no deck `USE`s
them by a relative path — so they are pure run output that came along with the
migration. A sweep that dirties the working tree breaks reproducibility, would
show up as spurious diffs in every contributor's PR, and defeats any
`git diff --exit-code` check in CI.

**Fix:** untracked (`git rm --cached`; the files stay on disk and are
regenerated by running the case) and `*.hsf` / `*.HSF` added to `.gitignore`.

## F9 — decks with absolute paths write junk into the working directory · **CONTAINED**

The ~126 models carrying absolute Windows paths in `USE`/`SAVE` (handoff
known-issue #5) do more than fail to read. On POSIX a *write* target like
`D:\SWMMandSoftware\...\CA-11_RB.txt` is not a path — it is a single literal
**filename**, created in the process's working directory. A sweep therefore
littered the repository root with files named
`D:\SWMMandSoftware\SWMM5.013_June2018\...\CA-1_TRENCH.txt`, and dropped
`OUTPUT.MST` into several corpus case directories.

Contained via `.gitignore` (`/[A-Za-z]:\\*`, `OUTPUT.MST`) so a sweep no longer
dirties the tree. **This is containment, not a fix** — the real repair is to
anonymize those decks, which is the first workload for `harness/anonymize.py`
and is also what makes the corpus safe to redistribute (the paths leak usernames
and client project names).

## F10 — `[FILES] USE RAINFALL` is not implemented · **OPEN, engine-side (minor)**

openswmm-v6 emits, on any deck carrying the directive:

```
WARNING 103: [FILES] USE RAINFALL is not supported by this engine and was ignored.
```

9 corpus decks use `[FILES] USE RAINFALL` and 6 use `SAVE RAINFALL`.

On the two decks checked (`1000yearsimulation-case3`, `test7-continuous`) this
is **harmless**: both engines report identical precipitation (29.000 in and
215.951 in respectively) because the rain actually arrives through
`[RAINGAGES]`, and legacy does not use the interface file either. So the
directive being dropped changed nothing there — but it is unimplemented, and a
deck that genuinely depends on the binary rainfall interface file would run with
the wrong forcing and only a warning to show for it.

## F11 — the mass-balance badge was set by decks that exist to have bad mass balance · **FIXED (tagged)**

The published badge read **`mass balance: worst 150287.15%` (red)** — a number
contributed entirely by `allow-ponding-high-ce`. The badge reports the worst
continuity error in the corpus, so it is set by whichever model is most
pathological, and some models are pathological on purpose.

**The evidence is independent of this engine.** Each such case ships a committed
`reference/legacy.rpt`, written by an earlier, unrecorded engine long before any
of this work: `allow-ponding-high-ce`'s own committed report already shows
**−104,835.884%**. That is a property of the model, exactly as the handoff
anticipates ("a case that always had 30% continuity error is a property of the
model, not a regression").

**Resolved by tagging on that evidence, not on this engine's output** — which
would have been circular. A new controlled tag, `expected_high_continuity`
(`harness/schemas/tags.yaml`), is applied to the **38** cases whose *committed
legacy report* shows a routing continuity error worse than 10%. The threshold and
the source are both stated in the tag's own definition, so the basis travels with
the vocabulary rather than living in a commit message.

Tagged cases are **still run and still gated on parity** — the tag buys exactly
one thing: exclusion from the published mass-balance badge, with the count
**disclosed** the way the verification badge already discloses its unchecked
cases:

```
before:  mass balance: worst 150287.15%          [red]
after:   mass balance: worst 4.05% · 4 by design [yellow]
```

Four behaviours are pinned in `tests/test_gate.py`: the badge reports the worst
*graded* case; a by-design case cannot set it; the exclusion is disclosed; and
excluding everything yields **grey — "none graded"**, never a green clean bill of
health.

## F12 — recorded engine SHAs did not describe the binary · **FIXED**

`engine_sha()` returned `git rev-parse HEAD`. During this session the engine tree
carried ~65 files of uncommitted work (pre-existing, plus the F1 fix), and a
concurrent session pushed two commits mid-run — so the first swashes envelope was
stamped `29cbc361`, a commit that describes neither the source nor the binary
that produced it. Task 8 requires per-run pages "keyed by the engine SHA you
built"; that key was not true.

**Fix:** `engine_sha()` now appends `-dirty` when the checkout has uncommitted
tracked changes. This session's runs correctly report `880e239c-dirty`.

---

## Buckets, mechanically

Regenerate with `python tools/triage_sweep.py results/parity/scores_nightly.json`.
Bucket meanings:

| bucket | meaning | action |
|---|---|---|
| `sys-temperature-default` | F2 is the only offender — the case is otherwise at parity | decide F2 |
| `f32-rounding` | worst `max_rel` ≤ ~2 float32 ULP; the `.out` stores float32, whose epsilon (~1.19e-7) is **100× looser than the pair's `rtol=1e-9`** | expected; a 1-ULP summation-order difference cannot pass this gate |
| `numeric-divergence` | real but bounded disagreement | investigate per mechanism |
| `gross-divergence` | `max_rel ≥ 0.5` — one side is effectively zero | investigate first; this is where F1 lived |
| `engine-error` | the engine ran and failed | real result; gates CI |
| `env-launch` / `env-disk` | this machine could not run it | **UNAVAILABLE**; never gates |

`f32-rounding` deserves emphasis: `rtol=1e-9` against float32 storage means the
gate demands **bit-identical** output. That is the stated intent ("near-bit
parity"), but it means any difference in double-precision summation *order*
before the float32 store is a failure. `sys.STORAGE_VOLUME` — a sum over every
node and link — fails this way on decks that are otherwise exact.

---

## F13 — interface-file failures produce NO diagnostic · **OPEN, engine-side**

Found by running the skip list (F14) rather than trusting it. On a deck whose
hotstart or routing-interface file cannot be opened:

| case | swmm-5.3.0 | openswmm-v6 |
|---|---|---|
| `two-outfalls` | rc=0, report says `ERROR 351: cannot open routing interface file C:\Documents and Settings\Robert E…` | **rc=11, no ERROR line in the report** |
| `1042-elements-dw-si-units` | rc=0, report says `ERROR 331: cannot open hot start interface file D:\2016PC\NovDec2009\aaa.HSF.` | **rc=12, no report file written at all** |

Each engine has half of the right behaviour:

* **openswmm-v6 is right to exit nonzero.** Legacy returning **rc=0** on a fatal
  input error is how a broken run passes for a successful one — the same class
  of trap as the silent dry run.
* **legacy is right to say what failed.** openswmm-v6 gives the user an exit
  code and nothing else: no message, no report, no indication of *which* file
  could not be opened. For a deck with several interface files that is not a
  diagnosable failure.

Note the contrast with a missing **rainfall** file, which openswmm-v6 reports
properly (`ERROR 317: cannot open rainfall data file …`, in the report, rc=5).
So this is specific to the hotstart/routing-interface path, not general error
handling.

**Wanted:** openswmm-v6's exit code *and* legacy's message. 17 of the 92
skip-listed cases are in this state.

## F14 — the skip list, confirmed by running it · **DONE (Task 4)**

All 92 entries were executed rather than inferred (`tools/confirm_skips.py`,
full results in `results/skip_list_confirmation.json`):

| outcome | count | meaning |
|---|---:|---|
| **CONFIRMED** | 73 | failed for the stated reason (`ERROR 317`/`361`, named file) |
| **MISMATCH** | 17 | failed, but not diagnosably for the stated reason — **all of them are F13**: the reason names a `.HSF`/interface file and the engine exits 11/12 silently. The reasons are substantively right; the engine just cannot be made to say so. |
| **RUNS** | 2 | **the engine succeeded — entries removed** |

The two removed:

* **`test7-continuous`** — runs on both engines with **215.951 in** of
  precipitation. Its stated missing file (`IDS_2005_V2_Mod.rff`) is a `[FILES]
  USE RAINFALL` reference that neither engine needs; the rain comes from
  `[RAINGAGES]`. It also exposes a **large parity failure** — `node.DEPTH`
  `max_rel=3.0e+06`, 1,124,143 of 5,136,480 cells over tolerance — that the skip
  list was hiding. This is the single best argument for having run Task 4.
* **`1000yearsimulation-case3`** — same shape: both engines report **29.000 in**;
  the named `.rff` is not needed.

`skip_list.yaml` is now **90 entries**. One caveat recorded honestly: two entries
(`319-h-h-elements`, `usgs-nurp-browardcounty-wq`, reason "no hydraulic or
hydrologic elements") exit rc=5 with no report, so their reason is *plausible but
still unconfirmed* — they are counted under MISMATCH, not CONFIRMED.

---

## Status of the full sweep

**The nightly sweep did not finish in this session, and the reason is the
machine, not the platform.** Other sessions held this host at a **load average
of 116-147** throughout (a `SWMMVis` process at ~700% CPU plus two concurrent
`perf2d` engine runs), so the sweep's own engine processes were getting 8-10%
of a core. It is running in the background and writes
`results/parity/scores_nightly.json` incrementally after every cell, so it can
be inspected at any point and resumed by re-running.

What this does **not** cast doubt on: the verdicts. The engine is deterministic
(F6), and every finding above was established by direct, reproducible experiment
rather than by the sweep's aggregate.

What it **does** invalidate: the `wall` timings, and therefore **Task 5 (PR-tier
curation) cannot be completed from this data**. Tier selection needs a re-timing
run on a quiet machine. Everything else Task 5 needs is in place — the tag
census confirms all twelve required tags are represented in the corpus
(`hydrology` 734, `hydraulics` 1315, `quality` 121, `lid` 97, `lid_pollutants`
31, `surcharge` 386, `force_main` 261, `rtc` 285, `groundwater` 69, `snowmelt`
33, `dual_drainage` 20, `irregular_xsect` 204).

---

## F15 — half the registered suites are empty scaffolds · **recorded, not fixed**

`run_regression.py --list` shows eight suites. Four produce **no cells at all**:

```
epa_qa       [epa_qa] scaffold stub — not yet migrated; no cells produced
quality      [quality] scaffold stub — not yet migrated; no cells produced
stability    [stability] scaffold stub — not yet migrated; no cells produced
performance  [performance] scaffold stub — not yet migrated; no cells produced
```

Only `parity` and the three `analytical/*` suites grade anything. This is
disclosed in each suite's own README ("Not yet migrated", plan step 2) and is
not a defect — but it means `run_regression.py --suite all`, which is what the
nightly and engine-push workflows invoke, silently covers half of what its name
implies. Migrating them is plan step 2 work, well outside this handoff's task
list.

**Consequence for Task 10, item 4:** the handoff proposes archiving
`epaswmm5_qa` "now that its suites are promoted". Its `epa_qa` suite has **not**
been promoted — `suites/epa_qa/` here is a stub whose README still names
`epaswmm5_qa/suites/epa_qa/` as the source for the sweep driver, config matrix,
and report generation. Archiving it now would strand the only copy of code this
repository still needs. **Recommendation: do not archive until `epa_qa` is
actually migrated.** (The stale citations in its `docs/plan.md` —
`compare_engines.py`, `sweep_anderson_implicit.py` — are real and worth
correcting, but they are a note in that repo, not a reason to retire it.)

---

## F16 — the 15 root-level legacy directories, consolidated · **DONE (Task 10.1)**

The repository root held 15 directories from the original SWMM test repo
(`EPA/`, `Hydraulics/`, `Semi_Real_Models/`, `XPSWMM/`, …) — **269 tracked
files** — alongside the platform's own directories. The handoff recorded them as
"byte-identical duplicates of migrated cases (verified by hash)" and kept
deliberately.

**Re-verifying the claim first was worth it: it was not quite true.** By SHA-256
against every file under `corpus/` and `legacy/`:

| | files |
|---|---:|
| byte-identical to a `corpus/` file | 237 |
| byte-identical to a `legacy/` file | 4 |
| **unique — no copy anywhere** | **28** |

A blanket delete would have destroyed 28 files, **9 of them `.inp` models**. Each
of those 9 turned out to differ from its corpus counterpart by exactly the
reference repair `tools/repair_references.py` applied — they are the *pre-repair
originals*:

```
-SAVE RUNOFF "C:\swmm_crada_files\OUTPUT.MST"      (Hydraulics/EXAM80A_SW5.inp)
+SAVE RUNOFF "OUTPUT.MST"                          (corpus/epa/exam80a-sw5/model.inp)
```

The other 19 were genuinely unhoused content: InfoWorks `.icmt` transportables,
seven XPSWMM project/terrain files, an ArcGIS `.mxd`, a climate `.prn`, and
**`Simon_EPA/LICENSE`** — an MIT license, © 2022 dickinsonre, which is direct
evidence for the `simon-epa` collection the handoff lists as `license:
unverified` (known-issue #6).

**So this was a consolidation, not a deletion:**

* **25 unique files moved** under `legacy/`, keeping their original layout
  (`legacy/XPSWMM/dbinfo.xpd`, `legacy/Simon_EPA/LICENSE`, …), via `git mv` so
  history follows them.
* **241 byte-identical duplicates removed** — genuinely information-free.
* **3 Visual Studio cache files deleted** (`.vs/*.vsidx`, `.wsuo`,
  `slnx.sqlite`) and `.vs/` added to `.gitignore`.
* the 15 now-empty root directories removed.

**Verified after the fact**, by replaying every one of the 269 blobs from `HEAD`
and searching the working tree for its content: exactly **3 files** — the three
IDE-cache files — no longer exist anywhere. All 266 others are present.

The root is now only the platform: `corpus/ data/ docs/ harness/ legacy/ plans/
results/ site/ suites/ tests/ tools/` plus `README.md`, `LICENSE`,
`CONTRIBUTING.md`, `pytest.ini`, `requirements.txt`, `run_regression.py`.
`python -m harness.validate --quiet` still reports **1396 ok, 0 failed**.


---

## F17 — the harness test suite could never have passed in CI · **FIXED**

`validate.yml`'s `harness` job runs `python -m pytest` on a fresh checkout across
three runners. It would have failed on its first run, on all three.

`test_manufactured_reference_is_reproducible` asserts that a case's generator
still reproduces its committed `reference.csv` **byte for byte**. The generators
write with `csv.writer`, whose default `lineterminator` is **CRLF**; the repo's
`* text=auto` then normalises the committed blob to **LF**. A clone checks out
LF, the generator re-emits CRLF, and the comparison fails on the first line
ending — six cases, and at the pre-existing commit `495f8e3` it was six of
seventeen.

What made this invisible: running the generator once leaves CRLF on disk, so the
test passes locally afterwards — and because `text=auto` makes git compare the
*normalised* form, the working tree still reports clean. Every signal available
without cloning says the repo is fine.

**Fix:** `.gitattributes` marks the analytical reference data `-text`, so those
exact bytes are stored and restored on every platform, and the six blobs are
re-added with their true content. That is what "byte-exact" has to mean for a
file whose entire purpose is to be compared byte-exactly.

**Verified by cloning the repository and running the suite from the clone** —
139 passed — rather than from the working tree. Worth doing for anything whose
correctness depends on what is *committed*: see also
`registered/referenced source never git-added`, the same class of trap.
