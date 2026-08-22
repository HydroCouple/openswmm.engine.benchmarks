# LinkedIn Article Draft — Call for SWMM Model Submissions

**Status:** Draft. Publish after CONTRIBUTING.md and submission templates are live (plan step 9).

---

## Help Us Build the Open Benchmark Suite for SWMM Engines

Every SWMM modeler has *that* model. The one that surcharges violently at 2 a.m. of simulation
time. The pump station that cycles like a metronome. The LID network whose pollutant mass
balance never quite closes. The converted XPSWMM or ICM model that runs beautifully in one
engine and falls apart in another.

We want them.

**What we're building.** We are transforming the OpenSWMM benchmarks repository into an open,
engine-agnostic benchmarking and regression-testing platform for SWMM-compatible engines. It
already holds nearly 1,600 models — EPA and OWA regression examples, the classic EXTRAN manual
problems, the 2006 EPA QA suite with its original SWMM4 references, analytical test problems
with exact solutions, and real-world networks. Every model is run automatically against
multiple engines, and the results are compared along dimensions that matter to practitioners:

- **Stability** — convergence behavior, timestep collapse, oscillation, crashes
- **Mass balance** — runoff, routing, and water-quality continuity
- **Result parity** — every node, link, and subcatchment variable, at every reported timestep,
  across engine versions
- **Analytical accuracy** — error norms against exact solutions (SWASHES shallow-water cases,
  manufactured infiltration/groundwater/quality solutions, flow-regime transition problems)
- **Performance** — wall-clock trends tracked historically on a public dashboard

Every run feeds a public scoreboard with badges any engine project can display. When an engine
claims it reproduces SWMM results, this suite is where that claim gets tested — openly,
reproducibly, and on models the community actually cares about.

**Why submit a model?** Because the models that break engines are the ones that improve them.
A benchmark suite built only from textbook examples validates textbook behavior. Your
hard-won, pathological, oddly-shaped real network is worth more to engine developers than a
hundred clean tutorials. Contributed models get:

- A permanent, citable home with provenance and attribution recorded per model
- Automatic regression coverage — every future engine change is tested against your case
- A structured, searchable metadata record — models carry multiple tags (domain, features,
  purpose) so others can find and learn from them

**What we're especially looking for.** Water-quality and pollutant-transport models
(buildup/washoff, treatment, co-pollutants); LID models — especially LID *with* pollutants;
models with transitions between open-channel and pressurized flow — surcharging interceptors,
rapid-fill events, inverted siphons; pressurized distribution and force-main systems,
particularly those exhibiting transient behavior — pump starts and stops, valve and gate
operations, filling bores; real-time control rules; groundwater and snowmelt interactions;
dual-drainage and 2D-coupled systems; and any model that has ever exposed a difference between
two SWMM engines or versions.

**How it works.** Submission is structured and simple: one folder containing your `.inp` file,
a short `metadata.yaml` (tags, units — a template is provided), and a
`provenance.yaml` stating where the model came from and its license. Open a pull request, or
use the submission form if you'd rather not touch git. Automated checks validate the metadata,
run your model on the reference engines, and report back on the spot. We ask that models be
redistributable (public-domain or CC0 preferred) and free of sensitive data. Can't share your
network as-is? We provide an anonymization tool that renames every element, offsets or strips
coordinates, and scrubs identifying text — while verifying the simulation results stay
bit-identical, so the physics you're contributing is untouched. No tool can guarantee
anonymity, and we don't claim this one does — but it adds a real layer of protection that,
with your own review, can make otherwise unshareable models shareable.

**The ask.** If you have a model — or a folder of them — that you can share, the repository
and contribution guide are here: *(link)*. If you maintain or develop a SWMM-compatible
engine, the engine registry is open too: registering your engine gets you the full suite,
the scoreboard, and the badges.

Stormwater software gets better when its tests are shared. Send us your worst.

*#SWMM #stormwater #hydraulics #hydrology #openSource #waterResources #benchmarking*

---

## Publishing notes (not part of the article)

- Insert the repo URL and CONTRIBUTING.md link at *(link)* before posting.
- Optional hero image: heatmap figure from the epa_qa report or the parity dashboard.
- Tone matches prior drafts in `openswmm.engine/plans/` (dynamic_preissmann_slot_linkedin_draft,
  anderson_acceleration_linkedin_post); trim to ~600 words if posting as a plain post rather
  than an article.
