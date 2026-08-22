# Contributing models

This repository is a benchmark and regression-testing platform for
SWMM-compatible engines. The models in it are the substance of the project —
every one of them tests every engine, on every change, forever.

**The models that break engines are the ones that improve them.** A suite built
only from textbook examples validates textbook behavior. If you have a
pathological network, a model that exposed a difference between two engines, or
one that simply refuses to converge, that is worth more here than a hundred
clean tutorials.

## What we're especially looking for

- **Water quality** — buildup/washoff, treatment expressions, co-pollutants,
  street sweeping
- **LID with pollutants** — the single largest coverage gap
- **Open-channel ↔ pressurized transitions** — surcharging interceptors,
  rapid-fill events, deep tunnels, inverted siphons
- **Pressurized distribution and force-main systems with transients** — pump
  starts and stops, valve and gate operation, filling bores
- **Real-time control rules**, groundwater and snowmelt interaction,
  dual-drainage and 2D-coupled systems
- **Anything that has ever exposed a difference between two SWMM engines or
  versions**

## Two ways to submit

### 1. Pull request (preferred)

Copy the template and fill it in:

```bash
cp -r corpus/_template corpus/contributed/my-case-id
# add your model as corpus/contributed/my-case-id/model.inp
$EDITOR corpus/contributed/my-case-id/metadata.yaml
$EDITOR corpus/contributed/my-case-id/provenance.yaml
python -m harness.validate corpus/contributed/my-case-id
```

Then open a PR using the model-submission template. Automated checks validate
the metadata, run the model on the reference engines, and report back on the PR
with runtime, size class, and any warnings.

### 2. Issue form

If you'd rather not use git, open a
[model submission issue](../../issues/new?template=model-submission.yml) with
your file attached and the same information in structured fields. A maintainer
will convert it.

## What a submission needs

| file | purpose |
|---|---|
| `model.inp` | the model itself |
| `metadata.yaml` | what it is — tags, units, routing, reference class ([schema](harness/schemas/metadata.schema.yaml)) |
| `provenance.yaml` | where it came from and its license ([schema](harness/schemas/provenance.schema.yaml)) |
| `reference/` | optional — reference data, if you have any |

### Tags, not categories

Classification is by **tags**, and a model carries as many as apply — a real
network with LID, pollutants, and a surcharging interceptor is all of those at
once. The vocabulary is in
[`harness/schemas/tags.yaml`](harness/schemas/tags.yaml); unknown tags fail
validation, but adding a genuinely new one is a one-line change in the same PR.

Directory placement is organizational only. Suites and CI tiers select models
by tag query (`lid AND pollutants`), never by path.

### Reference class — be honest about what your model proves

`metadata.yaml` declares what truth the model is graded against:

| class | use when |
|---|---|
| `analytic` | a closed-form exact solution exists |
| `manufactured` | the solution is exact by construction (MMS) |
| `external_reference` | you have results from another tool |
| `observed` | you have field measurements |
| `blessed_baseline` | a reviewed, pinned prior engine output |
| `self_consistency` | **no external reference — the normal case** |

Most real-world models are `self_consistency`: they are validated by mass
balance, stability, and engine-vs-engine agreement, not by correctness against
truth. Declaring that honestly is what keeps the platform's accuracy claims
meaningful.

## Licensing and sensitive data

Models must be **redistributable**. Public domain or CC0 is preferred; state
the license in `provenance.yaml`. If you can't verify it, mark it
`unverified` — the case is then excluded from redistribution claims rather than
silently assumed to be free.

Models must be free of sensitive data. You are responsible for that
determination.

### Anonymization

If you can't share a network as-is, `harness/anonymize.py` (in development)
will rename every element, offset or strip coordinates, and scrub identifying
text, while verifying that results stay **bit-identical** so the physics you're
contributing is untouched.

**No tool can guarantee anonymity, and we don't claim this one does.** It
provides a layer of protection that, combined with your own review, can make an
otherwise unshareable model shareable. Review the output before you submit it.
The PR checks also scan for likely identifying content — real-looking
coordinates, absolute file paths — and flag findings for you to confirm.

## What happens after you submit

1. **Validation** — schema checks, the model runs on the reference engines,
   continuity sanity, referenced files resolve.
2. **Landing** — accepted submissions enter the corpus at `tiers: [nightly]`.
3. **Promotion** — a maintainer may promote a case to the PR tier (run on
   every pull request) if it earns its runtime; the rationale is recorded in
   the manifest.
4. **Attribution** — your `provenance.yaml` entry is permanent, and the model
   appears on the public dashboard with its provenance.

## Code contributions

Harness changes follow the same PR flow. Please read
[the platform plan](plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md) first — it
records the architecture and the reasoning behind it, including which
decisions are deliberate.
