# What runs when

How a change to `openswmm.engine` reaches this repository, and what each
workflow actually does. Written because the answer was not obvious from the
workflow files: a receiver existed with nothing sending to it.

## The paths

```
openswmm.engine                          openswmm.engine.benchmarks
───────────────                          ──────────────────────────

push to main/develop
   └─> Unit Testing ─success─┐
                             │
        benchmark_dispatch.yml
        POST /dispatches ────┼────────>  on_engine_push.yml
        (needs a PAT)        │             build THAT sha
                             │             sweep + publish
                             │
                    (no gate: fire-and-forget)

                      07:00 UTC daily ─>  nightly.yml
                                            build engine `develop`
                                            sweep + publish

              push/PR to dev|main ──────>  validate.yml
                                            harness tests (3 OS)
                                            schema validation
                                            smoke-run changed cases
```

## Trigger table

| Event | Workflow | Engine built | Scope |
|---|---|---|---|
| engine push to `main`/`develop`, **after Unit Testing passes** | `on_engine_push.yml` | the dispatched SHA | `client_payload.tier`, default `nightly` |
| 07:00 UTC daily | `nightly.yml` | `develop` (or `engine_ref` input) | `nightly` |
| push/PR to this repo's `dev`/`main` | `validate.yml` | `develop`, and only if the PR touched cases | just the changed cases |
| manual | any, via `workflow_dispatch` | as chosen | as chosen |

`publish.yml` is `workflow_call` only — the nightly and engine-push sweeps
invoke it to deploy the dashboard to Pages.

## Setup required for the per-push path

`benchmark_dispatch.yml` lives in **`openswmm.engine`** and needs one secret
there:

* **`BENCHMARKS_DISPATCH_TOKEN`** — cross-repository `repository_dispatch`
  cannot use the default `GITHUB_TOKEN`, which is scoped to its own repository.
  * fine-grained PAT → repository access `HydroCouple/openswmm.engine.benchmarks`,
    permission **Contents: Read and write**
  * classic PAT → scope **`repo`**
  * a GitHub App installation token also works, and is preferable for a shared
    org since it is not tied to one person's account

Without it the workflow **fails loudly** with those instructions rather than
skipping silently, so a broken link is visible instead of looking like "the
benchmarks just didn't find anything".

## What this does NOT do

**It does not gate an engine merge.** `repository_dispatch` is fire-and-forget:
the engine workflow finishes as soon as the POST returns, so a parity failure
shows up on the dashboard and the badges, not as a failed check on the engine
commit. Gating requires the engine's own PR workflow to run
`run_regression.py --suite parity --tier pr` synchronously and wait for it —
which needs the PR tier curated first (a 50-100 case, <20 min subset chosen
from measured runtimes).

**Pull requests to the engine are not dispatched.** A fork PR cannot read
secrets, and a full sweep per PR costs more than it tells us until that PR tier
exists.

## The trap this design has already hit

`parity` defaults to `--tier pr`, and **no case lists `pr` in its metadata
`tiers:` yet**, so that tier selects zero models. The suite used to return an
empty envelope, which scored as green: a dispatched sweep would have built the
engine, run nothing, and published a clean bill of health with nothing in the
output looking wrong.

An empty selection is now a gating `ERROR`
(`suites/parity/suite.py`), and `on_engine_push.yml` passes the tier explicitly
instead of inheriting that default. Pinned by
`tests/test_gate.py::test_parity_suite_errors_when_a_tier_selects_no_cases`.
