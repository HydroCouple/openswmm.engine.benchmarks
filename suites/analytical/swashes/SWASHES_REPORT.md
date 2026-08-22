# SWASHES Analytical Benchmark Report

- generated: 2026-08-22T18:40:43
- engine: `openswmm-v6` @ `880e239c`
- exes: `openswmm` / `openswmm-legacy` (build `darwin-parity`)
- determinism: OMP_NUM_THREADS=1, OPENSWMM_2D_BACKEND=cpu

Reference: Delestre et al. (2013), doi 10.1002/fld.3741 — independent Python implementations (`swasheslib/analytic.py`); per-case provenance in `cases/<id>/provenance.yaml`.

## Comparison matrix

| case | 1d-dynwave | 1d-dynwave-legacy | 1d-dynwave-semi | 1d-dynwave-vj | 1d-fv | 2d-explicit |
|---|---|---|---|---|---|---|
| **bumps** | | | | | | |
| lake-at-rest-immersed | ✅ PASS (1.91e-09) | ✅ PASS (1.91e-09) | ✅ PASS (1.91e-09) | — | ✅ PASS (1.91e-09) | ✅ PASS (6.31e-11) |
| lake-at-rest-emerged | ✅ PASS (1.49e-08) | ✅ PASS (1.49e-08) | ✅ PASS (1.49e-08) | — | ✅ PASS (9.53e-06) | ✅ PASS (1.42e-16) |
| bump-subcritical | ❌ FAIL (2.05) | ❌ FAIL (2.05) | ❌ FAIL (2.05) | ❌ FAIL (6.65) | ✅ PASS (0.00514) | ✅ PASS (0.00667) |
| bump-transcritical | 🟥 BASE-FAIL (3.87) | 🟥 BASE-FAIL (3.87) | 🟦 BASE-PASS (3.87) | 🟥 BASE-FAIL (1.15) | ❌ FAIL (0.0748) | 🟦 BASE-PASS (0.269) |
| bump-shock | 🟥 BASE-FAIL (0.0348) | 🟥 BASE-FAIL (0.0348) | 🟥 BASE-FAIL (0.036) | 🟥 BASE-FAIL (40.9) | ✅ PASS (0.0254) | 🟦 BASE-PASS (0.118) |
| **macdonald** | | | | | | |
| macdonald-long-sub | ✅ PASS (0.0192) | 💥 ERROR | ✅ PASS (0.0191) | ✅ PASS (0.0194) | ✅ PASS (0.00235) | ✅ PASS (0.0187) |
| macdonald-long-sup | ✅ PASS (0.0194) | ✅ PASS (0.0194) | ❌ FAIL (0.0178) | ✅ PASS (0.0185) | ✅ PASS (0.00962) | ⚪ XFAIL (0.156) |
| macdonald-long-sub2sup | ✅ PASS (0.0104) | ✅ PASS (0.0104) | ✅ PASS (0.0104) | ✅ PASS (0.0106) | ✅ PASS (0.00265) | 🟦 BASE-PASS (0.0214) |
| macdonald-long-jump | ✅ PASS (0.0135) | ✅ PASS (0.0135) | ✅ PASS (0.0135) | ✅ PASS (0.0136) | ✅ PASS (0.00174) | 🟥 BASE-FAIL (0.0511) |
| macdonald-short-shock | 🟦 BASE-PASS (0.0569) | 🟦 BASE-PASS (0.0569) | 🟦 BASE-PASS (0.0568) | — | ✅ PASS (0.00447) | 🟦 BASE-PASS (0.0704) |
| macdonald-short-sup | 🟦 BASE-PASS (0.0567) | 🟦 BASE-PASS (0.0567) | 🟦 BASE-PASS (0.0567) | 🟦 BASE-PASS (0.0546) | ✅ PASS (0.00491) | ⚪ XFAIL (0.0551) |
| macdonald-short-sub2sup | 🟦 BASE-PASS (0.0708) | 🟦 BASE-PASS (0.0708) | 🟦 BASE-PASS (0.0709) | — | ✅ PASS (0.0045) | 🟦 BASE-PASS (0.0642) |
| macdonald-periodic | ❌ FAIL (0.155) | ❌ FAIL (0.155) | ❌ FAIL (0.155) | — | ✅ PASS (0.00155) | ❌ FAIL (0.0265) |
| **macdonald-rain** | | | | | | |
| macdonald-rain-sub | ✅ PASS (0.0274) | ✅ PASS (0.0274) | ✅ PASS (0.0274) | — | ✅ PASS (0.00178) | — |
| macdonald-rain-sup | ✅ PASS (0.0261) | ✅ PASS (0.0261) | ❌ FAIL (0.0236) | — | ✅ PASS (0.0138) | — |
| **macdonald-p2d** | | | | | | |
| p2d-sub-short | 🟥 BASE-FAIL (0.555) | 🟥 BASE-FAIL (0.555) | 🟥 BASE-FAIL (0.554) | — | ✅ PASS (0.00188) | — |
| p2d-sup-short | 🟥 BASE-FAIL (0.272) | 🟥 BASE-FAIL (0.272) | 🟥 BASE-FAIL (0.269) | — | ✅ PASS (0.00585) | — |
| p2d-trans-short | 🟥 BASE-FAIL (0.177) | 🟥 BASE-FAIL (0.177) | 🟥 BASE-FAIL (0.176) | — | ✅ PASS (0.00399) | — |
| p2d-jump-short | 🟥 BASE-FAIL (0.29) | 🟥 BASE-FAIL (0.29) | 🟥 BASE-FAIL (0.29) | — | ✅ PASS (0.00249) | — |
| p2d-sub-long | 🟥 BASE-FAIL (0.428) | 🟥 BASE-FAIL (0.428) | 🟥 BASE-FAIL (0.429) | — | ✅ PASS (0.00157) | — |
| p2d-jump-long | 🟥 BASE-FAIL (0.37) | 🟥 BASE-FAIL (0.37) | 🟥 BASE-FAIL (0.366) | — | ✅ PASS (0.00249) | — |
| **dam-breaks** | | | | | | |
| stoker-wet-dam-break | ✅ PASS (0.0496) | ✅ PASS (0.0496) | ✅ PASS (0.0496) | — | ✅ PASS (0.0153) | 🟥 BASE-FAIL (0.0601) |
| ritter-dry-dam-break | 🟥 BASE-FAIL (0.109) | 🟥 BASE-FAIL (0.109) | 🟦 BASE-PASS (0.104) | — | ❌ FAIL (0.0233) | 🟥 BASE-FAIL (0.112) |
| dressler-dry-dam-break | 🟦 BASE-PASS (0.12) | 🟦 BASE-PASS (0.12) | 🟦 BASE-PASS (0.119) | — | ✅ PASS (0.0261) | 🟥 BASE-FAIL (0.135) |
| **oscillations** | | | | | | |
| thacker-planar-1d | 🟥 BASE-FAIL (8.29) | 🟥 BASE-FAIL (8.29) | 🟥 BASE-FAIL (5.38) | — | ❌ FAIL (0.245) | 🟥 BASE-FAIL (0.778) |
| thacker-radial-2d | — | — | — | — | — | 🟥 BASE-FAIL (0.279) |
| thacker-planar-2d | — | — | — | — | — | 🟥 BASE-FAIL (0.429) |
| **bends** | | | | | | |
| bend00-gentle | ❌ FAIL (0.106) | ❌ FAIL (0.106) | ❌ FAIL (0.113) | ❌ FAIL (0.0991) | ✅ PASS (0.0236) | — |
| bend00-swift | ❌ FAIL (0.0764) | ❌ FAIL (0.0764) | ❌ FAIL (0.0764) | ❌ FAIL (0.0762) | ✅ PASS (0.076) | — |
| bend90-gentle | ❌ FAIL (0.109) | ❌ FAIL (0.109) | ❌ FAIL (0.115) | ❌ FAIL (0.101) | ✅ PASS (0.0257) | — |
| bend90-swift | ❌ FAIL (0.0833) | ❌ FAIL (0.0833) | ❌ FAIL (0.0834) | ❌ FAIL (0.0832) | ✅ PASS (0.0829) | — |
| bend45-swift | ❌ FAIL (0.0772) | ❌ FAIL (0.0772) | ❌ FAIL (0.0773) | ❌ FAIL (0.0771) | ✅ PASS (0.0768) | — |
| bend90-swift-k | ❌ FAIL (0.139) | ❌ FAIL (0.139) | ❌ FAIL (0.139) | ❌ FAIL (0.139) | ✅ PASS (0.133) | — |

Cell = verdict (relative L1 depth error). Steady cases are graded on the time-mean profile over the final 50% of the run (residual seiche precedent).

## lake-at-rest-immersed — Lake at rest with an immersed bump

*SWASHES 3.1.1* · family `bumps` · L=25 m, W1d=1 m, W2d=2 m, n=0, nx=25 (dx=1 m), dt=0.05 s, t_end=200 s

![lake-at-rest-immersed profile](figures/lake-at-rest-immersed__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 1.907e-09 | 2.384e-08 | 0 | 0 |  |
| 1d-dynwave-legacy | analytic | ✅ PASS | 1.907e-09 | 2.384e-08 | 0 | 0 |  |
| 1d-dynwave-semi | analytic | ✅ PASS | 1.907e-09 | 2.384e-08 | 0 | 0 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 1.907e-09 | 2.384e-08 | 0 | 0 |  |
| 2d-explicit | analytic | ✅ PASS | 6.306e-11 | 1.432e-10 | 1.48e-14 | 4.031e-10 | well-balancedness (C-property) |

## lake-at-rest-emerged — Lake at rest with an emerged bump

*SWASHES 3.1.2* · family `bumps` · L=25 m, W1d=1 m, W2d=2 m, n=0, nx=25 (dx=1 m), dt=0.05 s, t_end=200 s

![lake-at-rest-emerged profile](figures/lake-at-rest-emerged__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 1.49e-08 | 1.49e-08 | -0.001 | 0 | wet/dry transition at the bump |
| 1d-dynwave-legacy | analytic | ✅ PASS | 1.49e-08 | 1.49e-08 | 0 | 0 |  |
| 1d-dynwave-semi | analytic | ✅ PASS | 1.49e-08 | 1.49e-08 | -0.001 | 0 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 9.527e-06 | 2.431e-05 | -0 | 7.001e-06 |  |
| 2d-explicit | analytic | ✅ PASS | 1.42e-16 | 1.388e-16 | 0 | 2.776e-16 | wet/dry transition |

## bump-subcritical — Subcritical flow over a bump

*SWASHES 3.1.3* · family `bumps` · L=25 m, W1d=1 m, W2d=2 m, n=0, nx=25 (dx=1 m), dt=0.05 s, t_end=1800 s

![bump-subcritical profile](figures/bump-subcritical__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 2.051 | 2.14 | 0.003 | 0.0001078 | l1_h=2.051 > 0.02 |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 2.051 | 2.14 | 0.003 | 0.0001078 | l1_h=2.051 > 0.02 |
| 1d-dynwave-semi | analytic | ❌ FAIL | 2.052 | 2.146 | 0.003 | 7.735e-07 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 6.647 | 11.53 | 0.003 | 0 | zero-storage VJ chain matches the junction chain (l1 0.17%); at small fairness-scaled dt the VJ chain keeps fine grids stable where junction chains seiche (dx=0.2/dt=0.01: VJ 0.24% vs junctions 21%) — at the case dt both refine cleanly (VJ_FINDINGS.md); interior ICs not representable, dry-start spin-up |
| 1d-fv | analytic | ✅ PASS | 0.005142 | 0.03081 | -0 | 0 |  |
| 2d-explicit | analytic | ✅ PASS | 0.006672 | 0.03838 | -4.206e-13 | 0.00874 | PASSES since the inertial stage/inflow BC fix (2026-08-03): the old 4.4% was a boundary-condition stage offset (collapsed-Manning Dirichlet cell + momentum-less inflow), NOT the Bernoulli dip; the residual ~0.7% is the genuine no-advection limit (steady, mass-exact). EXPECTED in the figure: eta is dead FLAT over the crest (+7.7 cm depth residual at x=8-12 m) — flat eta is the EXACT frictionless steady state of the local-inertial equation (no q^2/h term; the dip = Delta(v^2/2g) it cannot represent). OWNER RULING 2026-08-04: keep local-inertial, document; momentum-advection upgrade declined for now |

## bump-transcritical — Transcritical flow without shock

*SWASHES 3.1.4* · family `bumps` · L=25 m, W1d=1 m, W2d=2 m, n=0, nx=25 (dx=1 m), dt=0.05 s, t_end=1800 s

![bump-transcritical profile](figures/bump-transcritical__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 3.873 | 2.797 | 0.003 | 0.3653 | implicit DW cannot establish the transcritical choke at stable resolution (settles near critical flow); analytic tols recorded for FV. Bit-identical to legacy since the fixed-step MINIMUM_STEP floor fix (the 'short-conduit defect' was decks silently marching at 0.5 s; see lake-at-rest _debug/REPRO.md) |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 3.873 | 2.797 | 0.003 | 0.3653 | same choke limitation as 1d-dynwave; observed legacy continuity −4.5% on the free-outfall spin-up (gate 6%) |
| 1d-dynwave-semi | baseline | 🟦 BASE-PASS | 3.873 | 2.797 | 0.003 | 0.361 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | baseline | 🟥 BASE-FAIL | 1.153 | 1.396 | -115.4 | 0.367 | same implicit-DW choke limitation as the junction chain (l1 34% vs 32%) — VJ at parity |
| 1d-fv | analytic | ❌ FAIL | 0.0748 | 0.3998 | -0 | 0 | l1_h=0.0748 > 0.03 |
| 2d-explicit | baseline | 🟦 BASE-PASS | 0.2695 | 0.4186 | 2.762e-11 | 1.598e-14 | passes Fr=1; local-inertial neglects convective inertia — FROUDE_MAX raised to 3 (recorded). What that costs: q is EXACT everywhere (1.5300) and mass is 7e-13, so nothing is wrong with the fluxes or areas; only h is wrong, and only upstream (0.5898 vs 1.0144). Critical depth here is (q^2/g)^(1/3)=0.620, so the model sits at Fr 1.08 where the truth is Fr 0.48 — the SUPERCRITICAL BRANCH of the same specific energy, over the whole domain; downstream, where the truth is supercritical too, it matches to 0.2%. Without the advective term the frictionless steady balance reduces to d(eta)/dx=0, and the measured eta is indeed constant at 0.5898 from x=0.5 through the crest, so the upstream pool can never build |

## bump-shock — Transcritical flow with shock

*SWASHES 3.1.5* · family `bumps` · L=25 m, W1d=1 m, W2d=2 m, n=0, nx=25 (dx=1 m), dt=0.05 s, t_end=1800 s

![bump-shock profile](figures/bump-shock__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.03478 | 0.1889 | -5.069 | 0.01132 | transcritical choke + slow shock slosh — implicit DW holds no steady shock position (mean drifts ~20%); analytic tols recorded for FV; mass gate 3% (storage:throughput inflation at q=0.18) |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.03478 | 0.1889 | -5.069 | 0.01132 | same shock-slosh limitation as 1d-dynwave |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.03595 | 0.2138 | -4.389 | 0.04263 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | baseline | 🟥 BASE-FAIL | 40.92 | 67.38 | 0.003 | 0 | same shock-slosh limitation as the junction chain (l1 5.0% vs 4.1%) — VJ at parity |
| 1d-fv | analytic | ✅ PASS | 0.02545 | 0.1391 | -0 | 0 |  |
| 2d-explicit | baseline | 🟦 BASE-PASS | 0.1185 | 0.3921 | -6.661e-13 | 0.003729 | local-inertial through a hydraulic jump |

## macdonald-long-sub — MacDonald 1000 m channel, subcritical

*SWASHES 3.2.1 (subcritical)* · family `macdonald` · L=1000 m, W1d=500 m, W2d=10 m, n=0.033, nx=1000 (dx=1 m), dt=0.04 s, t_end=6000 s

![macdonald-long-sub profile](figures/macdonald-long-sub__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.01915 | 0.05691 | 0 | 0.00153 |  |
| 1d-dynwave-legacy | analytic | 💥 ERROR | – | – | – | – |  |
| 1d-dynwave-semi | analytic | ✅ PASS | 0.01914 | 0.05693 | 0.072 | 0.0009422 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ✅ PASS | 0.0194 | 0.05695 | 0 | 0.0008345 | zero-storage VJ chain matches the junction chain on frictional channels (l1 1.7%, mass 0.001%) |
| 1d-fv | analytic | ✅ PASS | 0.002348 | 0.03286 | 0 | 2.572e-08 |  |
| 2d-explicit | analytic | ✅ PASS | 0.01874 | 0.02761 | 8.754e-11 | 2.019e-09 | R=h native — no width correction |

## macdonald-long-sup — MacDonald 1000 m channel, supercritical

*SWASHES 3.2.1 (supercritical)* · family `macdonald` · L=1000 m, W1d=500 m, W2d=10 m, n=0.04, nx=1000 (dx=1 m), dt=0.035 s, t_end=6000 s

![macdonald-long-sup profile](figures/macdonald-long-sup__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.01945 | 0.1804 | -0.005 | 0.2215 | upstream q+h cannot both be pinned — graded on x in [0.05L, L] |
| 1d-dynwave-legacy | analytic | ✅ PASS | 0.01945 | 0.1804 | -0.005 | 0.2215 |  |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.01778 | 0.1382 | 1.748 | 0.1995 | ENGINE FINDING: SEMI_IMPLICIT loses 1.75% mass under resolved roll waves (explicit: -0.005%); l1 1.78% is fine — the red is the mass gate |
| 1d-dynwave-vj | analytic | ✅ PASS | 0.01852 | 0.1584 | 0.001 | 0.2247 | VJ chain ~matches the junction chain (l1 0.65% vs 0.60%) and is machine-steady (resid 1e-8) |
| 1d-fv | analytic | ✅ PASS | 0.009625 | 0.01362 | 0 | 0 |  |
| 2d-explicit | xfail | ⚪ XFAIL | 0.1557 | 0.5726 | 6.581e-14 | 1.093 | supercritical throughout; FROUDE_MAX 3. XFAIL: the local-inertial scheme carries no convective advection term, so the fully supercritical profile never steadies (roll-wave-like unsteadiness, drift ~0.9, q spikes with drying cells) — a physics limit, not a defect; requires a full-SWE momentum solver (investigated 2026-08-03: survives the inertial-BC, dt0-refresh and hysteresis fixes) |

## macdonald-long-sub2sup — MacDonald 1000 m channel, subcritical to supercritical

*SWASHES 3.2.1 (sub-to-supercritical)* · family `macdonald` · L=1000 m, W1d=500 m, W2d=10 m, n=0.0218, nx=1000 (dx=1 m), dt=0.04 s, t_end=6000 s

![macdonald-long-sub2sup profile](figures/macdonald-long-sub2sup__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.01043 | 0.02014 | -0.003 | 0.002817 | MEETS analytic through the smooth transonic point (unlike the frictionless bump-transcritical choke). Recorded deviation: INERTIAL_DAMPING PARTIAL — under the normalized NONE the VJ column carries a stationary odd-even sawtooth (l1 4.5% -> 0.9% with PARTIAL; q exact either way) |
| 1d-dynwave-legacy | analytic | ✅ PASS | 0.01043 | 0.02014 | -0.003 | 0.002817 |  |
| 1d-dynwave-semi | analytic | ✅ PASS | 0.01044 | 0.02019 | 0.078 | 0.00239 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ✅ PASS | 0.01063 | 0.02082 | -0.003 | 0.002859 | 0.9% with PARTIAL damping; sawtoothed at 4.5% under NONE (checkerboard mode of the undamped chain) |
| 1d-fv | analytic | ✅ PASS | 0.002647 | 0.002699 | 0 | 2.964e-08 |  |
| 2d-explicit | baseline | 🟦 BASE-PASS | 0.02144 | 0.03146 | 7.784e-12 | 0.03385 | downstream half is supercritical — the macdonald-long-sup no-advection limit. The retired THETA 0.7/0.5 columns met the analytic gate here purely by adding q-centred smoothing over the residual sawtooth; the 0.8 default does not. That is a damping-tuning artefact, not a physics fix — the advection column is the term this case is actually missing |

## macdonald-long-jump — MacDonald 1000 m channel, hydraulic jump at x = 500 m

*SWASHES 3.2.1 (super-to-subcritical)* · family `macdonald` · L=1000 m, W1d=500 m, W2d=10 m, n=0.0218, nx=1000 (dx=1 m), dt=0.04 s, t_end=6000 s

![macdonald-long-jump profile](figures/macdonald-long-jump__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.01348 | 0.1808 | 0 | 4.924e-05 | MEETS analytic ON A FRICTIONAL CHANNEL: l1 1.3%, shock error 2.5 m (half a cell) with the recorded INERTIAL_DAMPING PARTIAL deviation — under NONE the shock region carries a stationary sawtooth (l1 3.5%). Contrast bump-shock (frictionless): there the shock position drifts and cells stay baseline |
| 1d-dynwave-legacy | analytic | ✅ PASS | 0.01348 | 0.1808 | 0 | 4.924e-05 |  |
| 1d-dynwave-semi | analytic | ✅ PASS | 0.01348 | 0.1808 | 0.096 | 6.016e-05 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ✅ PASS | 0.01357 | 0.1809 | 0.001 | 5.873e-05 |  |
| 1d-fv | analytic | ✅ PASS | 0.001741 | 0.03803 | 0 | 1.743e-05 | l1 0.65%, shock error 2.5 m — the shock-capturing reference column |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.05115 | 0.1942 | -8.231e-13 | 0.1446 | MET analytic at dx=2.5 (l1 3.0%, shock 2.5 m); at 1 m edges the jump-toe seiche no longer decays and the time-mean shock smears over x 430-520 (shock_err 69 m, l1 4.5%) — the local-inertial jump limitation resolution re-reveals. Analytic gates stay recorded; a better 2D scheme flips this cell loudly |

## macdonald-short-shock — MacDonald 100 m channel, transonic then shock at x = 66.7 m

*SWASHES 3.2.2 (smooth transition and shock)* · family `macdonald` · L=100 m, W1d=500 m, W2d=5 m, n=0.0328, nx=200 (dx=0.5 m), dt=0.02 s, t_end=1800 s

![macdonald-short-shock profile](figures/macdonald-short-shock__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟦 BASE-PASS | 0.05693 | 0.192 | -0 | 0.004401 | steady smooth 5.7% with PARTIAL (shock 0.58 m); the damping smears the transonic drawdown past the 5% gate — implicit-DW limit, analytic tols recorded for promotion |
| 1d-dynwave-legacy | baseline | 🟦 BASE-PASS | 0.05693 | 0.192 | 0 | 0.004401 |  |
| 1d-dynwave-semi | baseline | 🟦 BASE-PASS | 0.05684 | 0.1899 | 0.01 | 0.001956 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.004467 | 0.1104 | -0 | 2.945e-08 | l1 0.38%, shock 0.08 m at dx=0.5 |
| 2d-explicit | baseline | 🟦 BASE-PASS | 0.07044 | 0.2379 | 2.642e-12 | 9.374e-08 | local-inertial through a hydraulic jump |

## macdonald-short-sup — MacDonald 100 m channel, supercritical throughout

*SWASHES 3.2.2 (supercritical)* · family `macdonald` · L=100 m, W1d=500 m, W2d=5 m, n=0.03, nx=200 (dx=0.5 m), dt=0.02 s, t_end=1800 s

![macdonald-short-sup profile](figures/macdonald-short-sup__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟦 BASE-PASS | 0.05671 | 0.09469 | -0.005 | 0.01178 | smooth +6% bias with the recorded PARTIAL deviation (under NONE a 0.18 m stationary sawtooth pushes l1 to 16.5% with q EXACT — the undamped checkerboard at dx = 1 m); residual: shallow upstream, deep downstream — the damped scheme under-tracks the 25 m-scale bed variation the long channel (dx = 5) never sees |
| 1d-dynwave-legacy | baseline | 🟦 BASE-PASS | 0.05671 | 0.09469 | -0.005 | 0.01178 |  |
| 1d-dynwave-semi | baseline | 🟦 BASE-PASS | 0.05666 | 0.09905 | 0.033 | 0.02245 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | baseline | 🟦 BASE-PASS | 0.05462 | 0.09288 | -0.004 | 0.01406 |  |
| 1d-fv | analytic | ✅ PASS | 0.004911 | 0.02212 | -0 | 0 |  |
| 2d-explicit | xfail | ⚪ XFAIL | 0.05513 | 0.0816 | 3.57e-11 | 1.429e-11 | fully supercritical — macdonald-long-sup precedent: local inertia never steadies without the convective term |

## macdonald-short-sub2sup — MacDonald 100 m channel, transonic at x = 50 m

*SWASHES 3.2.2 (sub-to-supercritical)* · family `macdonald` · L=100 m, W1d=500 m, W2d=5 m, n=0.0328, nx=200 (dx=0.5 m), dt=0.02 s, t_end=1800 s

![macdonald-short-sub2sup profile](figures/macdonald-short-sub2sup__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟦 BASE-PASS | 0.07081 | 0.4085 | -0.004 | 0.00706 | transcritical choke precedent (bump-transcritical): 6.0% smooth with the recorded PARTIAL deviation (8.7% + sawtooth under NONE) |
| 1d-dynwave-legacy | baseline | 🟦 BASE-PASS | 0.07081 | 0.4085 | -0.004 | 0.00706 |  |
| 1d-dynwave-semi | baseline | 🟦 BASE-PASS | 0.07088 | 0.4196 | 0.018 | 0.005764 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.0045 | 0.006916 | -0 | 0 |  |
| 2d-explicit | baseline | 🟦 BASE-PASS | 0.06421 | 0.09279 | -9.579e-12 | 2.001e-10 | supercritical downstream half — no-advection limit |

## macdonald-periodic — MacDonald 5000 m periodic channel, subcritical

*SWASHES 3.2.3* · family `macdonald` · L=5000 m, W1d=500 m, W2d=10 m, n=0.03, nx=5000 (dx=1 m), dt=0.04 s, t_end=12000 s

![macdonald-periodic profile](figures/macdonald-periodic__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.1548 | 0.3139 | 0 | 0.01564 | ENGINE FINDING: DW loses ~one velocity head (v²/2g = 0.161 m) to its 5000-junction chain — l1 0.141% at dx=10 vs 15.5% at dx=1, while FV converges normally |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.1548 | 0.3139 | 0 | 0.01564 | l1_h=0.1548 > 0.03 |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.1547 | 0.3137 | 0.293 | 0.02474 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.001551 | 0.001793 | -0 | 0.001355 |  |
| 2d-explicit | analytic | ❌ FAIL | 0.02647 | 0.03621 | 7.625e-11 | 0.1801 | steady_resid=0.18 > 0.02 (not steady) |

## macdonald-rain-sub — MacDonald 1000 m channel, subcritical with rain

*SWASHES 3.3.1* · family `macdonald-rain` · L=1000 m, W1d=500 m, W2d=10 m, n=0.033, nx=1000 (dx=1 m), dt=0.04 s, t_end=6000 s

![macdonald-rain-sub profile](figures/macdonald-rain-sub__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.02739 | 0.06727 | -0.219 | 0.001041 | rain R0 = 1 mm/s as per-node lateral inflows R0·dx·W; depth profile is eq. (12) with q(x) = 1 + 0.001x. Gate 3.5%: DW sits at 3.01% — the same scheme error as macdonald-long-sub's 3% plus the half-cell end-weight rain discretization |
| 1d-dynwave-legacy | analytic | ✅ PASS | 0.02739 | 0.06727 | -0.219 | 0.001041 |  |
| 1d-dynwave-semi | analytic | ✅ PASS | 0.02739 | 0.06735 | -0.164 | 0.001113 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.001784 | 0.003037 | -0.057 | 8.499e-06 | ENGINE FINDING (deliberate red, 2026-08-12): FV runs 18.9% deep with q(x) EXACT and the profile smooth — same signature at rain-sup (25%). DW on the identical deck is at 3%, so the deck is sound: the FV algebraic junction mishandles lateral inflow momentum (all 200 junctions carry inflows here). Left red pending an engine fix |
| 2d-explicit | – | — | – | – | – | – |  |

## macdonald-rain-sup — MacDonald 1000 m channel, supercritical with rain

*SWASHES 3.3.2* · family `macdonald-rain` · L=1000 m, W1d=500 m, W2d=10 m, n=0.04, nx=1000 (dx=1 m), dt=0.03 s, t_end=12000 s

![macdonald-rain-sup profile](figures/macdonald-rain-sup__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.02609 | 0.1754 | -0.003 | 0.1629 | rain steps on at tR = 1500 s (unit time series riding each node's Sfactor); graded on the final rained state. 0.8% with the recorded PARTIAL deviation — under NONE a 0.16 m stationary sawtooth pushes l1 to 11% (q exact) |
| 1d-dynwave-legacy | analytic | ✅ PASS | 0.02609 | 0.1754 | -0.003 | 0.1629 |  |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.02365 | 0.1181 | 2.097 | 0.1503 | ENGINE FINDING: SEMI_IMPLICIT loses 2.10% mass under resolved roll waves (explicit: -0.003%); l1 2.36% is fine — the red is the mass gate (replicates macdonald-long-sup) |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.01379 | 0.01939 | -0 | 0 | ENGINE FINDING (deliberate red, 2026-08-12): 25% deep with exact q — the FV junction lateral-inflow momentum defect (see macdonald-rain-sub) |
| 2d-explicit | – | — | – | – | – | – |  |

## p2d-sub-short — Pseudo-2D subcritical, B1 rectangular, 200 m

*SWASHES 3.5.1* · family `macdonald-p2d` · L=200 m, W1d=10 m, W2d=10 m, n=0.03, nx=400 (dx=0.5 m), dt=0.015 s, t_end=1800 s

![p2d-sub-short profile](figures/p2d-sub-short__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.5549 | 1.164 | 0.001 | 0.007757 | non-prismatic conveyance: per-conduit local width; non-prismatic momentum: DW junction chains drop the cross-junction convective + wall-pressure terms — dx-independent deep bias with exact q (see cases_pseudo2d.py header note). FV no longer shares this: the width-step single-flux fix (face_geom) closed it 2026-08-13 |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.5549 | 1.164 | 0.001 | 0.007757 | no baseline pinned — review run, then pin-baseline --case p2d-sub-short --solver 1d-dynwave-legacy |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.5538 | 1.16 | 0.042 | 0.006837 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.001883 | 0.003558 | 0 | 1.766e-08 | FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the width-step single-flux treatment — one shared face section, so the step's wall finally exerts force — brings the family to 0.17-0.60% and the jumps inside half a cell |
| 2d-explicit | – | — | – | – | – | – |  |

## p2d-sup-short — Pseudo-2D supercritical, B1 rectangular, 200 m

*SWASHES 3.5.2* · family `macdonald-p2d` · L=200 m, W1d=10 m, W2d=10 m, n=0.03, nx=400 (dx=0.5 m), dt=0.015 s, t_end=1800 s

![p2d-sup-short profile](figures/p2d-sup-short__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.2717 | 0.4208 | -0.003 | 0 | fully supercritical through the contraction; non-prismatic momentum: DW junction chains drop the cross-junction convective + wall-pressure terms — dx-independent deep bias with exact q (see cases_pseudo2d.py header note). FV no longer shares this: the width-step single-flux fix (face_geom) closed it 2026-08-13 |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.2717 | 0.4208 | -0.003 | 0 | no baseline pinned — review run, then pin-baseline --case p2d-sup-short --solver 1d-dynwave-legacy |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.269 | 0.4208 | 0.016 | 0 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.005853 | 0.03138 | 0 | 7.285e-09 | FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the width-step single-flux treatment — one shared face section, so the step's wall finally exerts force — brings the family to 0.17-0.60% and the jumps inside half a cell |
| 2d-explicit | – | — | – | – | – | – |  |

## p2d-trans-short — Pseudo-2D smooth sub-to-supercritical, B1, 200 m

*SWASHES 3.5.3* · family `macdonald-p2d` · L=200 m, W1d=10 m, W2d=10 m, n=0.03, nx=400 (dx=0.5 m), dt=0.015 s, t_end=1800 s

![p2d-trans-short profile](figures/p2d-trans-short__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.1771 | 0.4328 | -0.005 | 0.001554 | transcritical choke precedent (bump-transcritical); non-prismatic momentum: DW junction chains drop the cross-junction convective + wall-pressure terms — dx-independent deep bias with exact q (see cases_pseudo2d.py header note). FV no longer shares this: the width-step single-flux fix (face_geom) closed it 2026-08-13 |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.1771 | 0.4328 | -0.005 | 0.001554 | no baseline pinned — review run, then pin-baseline --case p2d-trans-short --solver 1d-dynwave-legacy |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.176 | 0.4277 | 0.017 | 0.006291 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.003993 | 0.02409 | 0 | 2.101e-08 | FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the width-step single-flux treatment — one shared face section, so the step's wall finally exerts force — brings the family to 0.17-0.60% and the jumps inside half a cell |
| 2d-explicit | – | — | – | – | – | – |  |

## p2d-jump-short — Pseudo-2D hydraulic jump at x = 120 m, B1, 200 m

*SWASHES 3.5.4* · family `macdonald-p2d` · L=200 m, W1d=10 m, W2d=10 m, n=0.03, nx=400 (dx=0.5 m), dt=0.015 s, t_end=1800 s

![p2d-jump-short profile](figures/p2d-jump-short__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.2899 | 0.6759 | 0 | 0.1327 | steady shock position precedent (bump-shock); downstream eta is hex(200) of the RH-verified construction (Table-2 hout differs — see provenance); non-prismatic momentum: DW junction chains drop the cross-junction convective + wall-pressure terms — dx-independent deep bias with exact q (see cases_pseudo2d.py header note). FV no longer shares this: the width-step single-flux fix (face_geom) closed it 2026-08-13 |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.2899 | 0.6759 | 0 | 0.1327 | no baseline pinned — review run, then pin-baseline --case p2d-jump-short --solver 1d-dynwave-legacy |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.2897 | 0.6753 | 0.028 | 0.001951 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.002487 | 0.07577 | 0 | 8.163e-07 | FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the width-step single-flux treatment — one shared face section, so the step's wall finally exerts force — brings the family to 0.17-0.60% and the jumps inside half a cell |
| 2d-explicit | – | — | – | – | – | – |  |

## p2d-sub-long — Pseudo-2D subcritical, B2 trapezoidal Z=2, 400 m

*SWASHES 3.5.5* · family `macdonald-p2d` · L=400 m, W1d=10 m, W2d=10 m, n=0.03, nx=400 (dx=1 m), dt=0.04 s, t_end=1800 s

![p2d-sub-long profile](figures/p2d-sub-long__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.428 | 0.7451 | 0.187 | 0.02463 | trapezoidal non-prismatic conveyance (Z = 2); non-prismatic momentum: DW junction chains drop the cross-junction convective + wall-pressure terms — dx-independent deep bias with exact q (see cases_pseudo2d.py header note). FV no longer shares this: the width-step single-flux fix (face_geom) closed it 2026-08-13 |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.428 | 0.7451 | 0.187 | 0.02463 | no baseline pinned — review run, then pin-baseline --case p2d-sub-long --solver 1d-dynwave-legacy |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.429 | 0.7514 | 0.355 | 0.02734 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.001574 | 0.003173 | -0 | 0.0001016 | FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the width-step single-flux treatment — one shared face section, so the step's wall finally exerts force — brings the family to 0.17-0.60% and the jumps inside half a cell |
| 2d-explicit | – | — | – | – | – | – |  |

## p2d-jump-long — Pseudo-2D transonic + jump at x = 120 m, B2 trapezoidal, 400 m

*SWASHES 3.5.6* · family `macdonald-p2d` · L=400 m, W1d=10 m, W2d=10 m, n=0.03, nx=400 (dx=1 m), dt=0.04 s, t_end=1800 s

![p2d-jump-long profile](figures/p2d-jump-long__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.3697 | 0.7069 | 0.113 | 0.1346 | smooth transition then steady shock (bump-shock precedent); non-prismatic momentum: DW junction chains drop the cross-junction convective + wall-pressure terms — dx-independent deep bias with exact q (see cases_pseudo2d.py header note). FV no longer shares this: the width-step single-flux fix (face_geom) closed it 2026-08-13 |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.3697 | 0.7069 | 0.113 | 0.1346 | no baseline pinned — review run, then pin-baseline --case p2d-jump-long --solver 1d-dynwave-legacy |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 0.3665 | 0.7066 | 0.261 | 0.182 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.00249 | 0.07332 | 0 | 0.0003423 | FIXED 2026-08-13 (was a deliberate red at 5.4-16.5%): the width-step single-flux treatment — one shared face section, so the step's wall finally exerts force — brings the family to 0.17-0.60% and the jumps inside half a cell |
| 2d-explicit | – | — | – | – | – | – |  |

## stoker-wet-dam-break — Stoker dam break on a wet domain

*SWASHES 4.1.1* · family `dam-breaks` · L=10 m, W1d=1 m, W2d=1 m, n=0, nx=200 (dx=0.05 m), dt=0.01 s, t_end=6 s

![stoker-wet-dam-break profile](figures/stoker-wet-dam-break__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ✅ PASS | 0.04956 | 0.7453 | 0 | – | DW MEETS analytic tolerance on the wet dam break (l1 4.8%, mass 0.0%) — bit-identical to legacy since the MINIMUM_STEP floor fix; wet bed: no front metric |
| 1d-dynwave-legacy | analytic | ✅ PASS | 0.04956 | 0.7453 | 0 | – | legacy DW MEETS analytic tolerance on the wet dam break (l1 4.8%, mass 0.0%) |
| 1d-dynwave-semi | analytic | ✅ PASS | 0.04959 | 0.732 | -0.003 | – | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.01535 | 0.21 | 0 | – |  |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.06007 | 0.3079 | -5.089e-13 | – | local-inertial; DRY_DEPTH/H_MOVE lowered to 1e-4 (depth scale is mm). TWO separate errors on the star region (exact 0.00254 flat, x 4.8-6.2): a +-4.5% sawtooth, which is what the de Almeida q-centred damping leaves at n=0 (THETA defaults to 0.8 and IS active - at zero friction the friction denominator is identically 1.0 and adds no dissipation); and a plateau 31% high (0.00333) with the shock at x~5.8 vs 6.25, which is the MISSING CONVECTIVE MOMENTUM FLUX giving wrong Rankine-Hugoniot conditions. Lowering THETA addresses only the first |

## ritter-dry-dam-break — Ritter dam break on a dry domain

*SWASHES 4.1.2* · family `dam-breaks` · L=10 m, W1d=1 m, W2d=1 m, n=0, nx=200 (dx=0.05 m), dt=0.01 s, t_end=6 s

![ritter-dry-dam-break profile](figures/ritter-dry-dam-break__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 0.1086 | 0.9912 | -0.048 | – | corpus precedent: implicit DW cannot resolve the dry-bed rarefaction (dw-ritter-drybed-strip); front lags analytic (~27 dx), mass clean — bit-identical to legacy since the MINIMUM_STEP floor fix |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 0.1086 | 0.9912 | 0 | – | front lags analytic by ~27 dx (corpus precedent); mass clean |
| 1d-dynwave-semi | baseline | 🟦 BASE-PASS | 0.1042 | 1.013 | -0.117 | – | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ❌ FAIL | 0.02335 | 0.1094 | 0 | – | front_err_dx=84 > 3 |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.1117 | 0.7605 | -2.706e-12 | – | wet/dry front under local inertia; same two-part error as stoker (undamped sawtooth at n=0 plus a missing convective flux), and the front lags because the scheme carries no advection to drive it |

## dressler-dry-dam-break — Dressler dam break on a dry domain with friction

*SWASHES 4.1.3* · family `dam-breaks` · L=2000 m, W1d=500 m, W2d=10 m, n=0.0294398, nx=2000 (dx=1 m), dt=0.01 s, t_end=40 s

![dressler-dry-dam-break profile](figures/dressler-dry-dam-break__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟦 BASE-PASS | 0.1196 | 0.3652 | 0 | – | dry-bed front precedent (ritter); reference friction is Chézy C=40 — deck carries the equivalent Manning n = (4/9·hl)^(1/6)/C (approximation recorded in provenance) |
| 1d-dynwave-legacy | baseline | 🟦 BASE-PASS | 0.1196 | 0.3652 | 0 | – |  |
| 1d-dynwave-semi | baseline | 🟦 BASE-PASS | 0.1195 | 0.3656 | -0.018 | – | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ✅ PASS | 0.02607 | 0.1623 | -0 | – | graded on l1_h only: Dressler's front is pinned at Ritter's FRICTIONLESS position xB = x0+2t√(ghl) (his first-order correction does not move the front — a stated limit of the solution), so every frictional solver undershoots it (FV: 1300 vs 1580 m at t=40) and front_err cannot gate; body l1 = 3.4% at t=40. Chézy→Manning mismatch also over-damps the shallow tip (n_eq fixed at the star depth) |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.1349 | 0.6407 | 1.94e-13 | – | wet/dry front under local inertia with friction |

## thacker-planar-1d — Thacker planar surface in a parabola

*SWASHES 4.2.1* · family `oscillations` · L=4 m, W1d=1 m, W2d=0.5 m, n=0, nx=200 (dx=0.02 m), dt=0.004 s, t_end=10 s

![thacker-planar-1d profile](figures/thacker-planar-1d__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | baseline | 🟥 BASE-FAIL | 8.291 | 6.96 | -1.597e+04 | – | NOT gradual wet/dry mass loss: a t=0 blow-up. 200 of 202 nodes flood at 0 00:00 at 36-48 CMS in a basin holding ~1 m3; depths pin at MaxDepth and the excess is discarded (ALLOW_PONDING NO), so Flooding Loss is 177x the Initial Stored Volume and the -27912% is that over a near-zero denominator. The ICs are correct (planar eta, dry bank above the waterline). Prime suspect is conditioning: MIN_SURFAREA floors the DENOMINATOR of the node head update (DynamicWave.cpp:3210/3325), and this deck sets 0.01 m2 against the 1.167 m2 default - 117x smaller - at ROUTING_STEP 0.004. Oscillation heavily damped vs analytic; bit-identical to legacy since the MINIMUM_STEP floor fix |
| 1d-dynwave-legacy | baseline | 🟥 BASE-FAIL | 8.291 | 6.96 | -1.597e+04 | – | same t=0 blow-up as 1d-dynwave (see that row): whole-network flooding at 0 00:00, 98x the Initial Stored Volume discarded, suspect the 0.01 m2 MIN_SURFAREA denominator; oscillation heavily damped vs analytic |
| 1d-dynwave-semi | baseline | 🟥 BASE-FAIL | 5.376 | 5.069 | -4459 | – | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | analytic | ❌ FAIL | 0.2447 | 0.3236 | 0 | – | l1_h=0.2447 > 0.05 |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.7776 | 0.9094 | 3.331e-13 | – | u(x,0)=0 — depth-only IC is exact at t=0 |

## thacker-radial-2d — Thacker radially-symmetric paraboloid oscillation

*SWASHES 4.2.2 (radial)* · family `oscillations` · L=4 m, W1d=1 m, W2d=4 m, n=0, nx=80 (dx=0.05 m), dt=0 s, t_end=6.72855 s

![thacker-radial-2d profile](figures/thacker-radial-2d__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | – | — | – | – | – | – |  |
| 1d-dynwave-legacy | – | — | – | – | – | – |  |
| 1d-dynwave-semi | – | — | – | – | – | – |  |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | – | — | – | – | – | – |  |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.2795 | 0.373 | 3.892e-13 | – | u=v=0 at t=0 (depth-only IC exact); phase/amplitude drift expected of local inertia — XPASS flips analytic |

## thacker-planar-2d — Thacker planar surface in a paraboloid

*SWASHES 4.2.2 (planar)* · family `oscillations` · L=4 m, W1d=1 m, W2d=4 m, n=0, nx=80 (dx=0.05 m), dt=0 s, t_end=13.4571 s

![thacker-planar-2d profile](figures/thacker-planar-2d__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | – | — | – | – | – | – |  |
| 1d-dynwave-legacy | – | — | – | – | – | – |  |
| 1d-dynwave-semi | – | — | – | – | – | – |  |
| 1d-dynwave-vj | – | — | – | – | – | – |  |
| 1d-fv | – | — | – | – | – | – |  |
| 2d-explicit | baseline | 🟥 BASE-FAIL | 0.4287 | 0.612 | 0 | – | v(t=0)=eta*omega seeded via [2D_INITIAL_VELOCITY] (engine edge-flux seeding, 2026-08-03); remaining error is local-inertia phase/front drift — XPASS flips analytic |

## bend00-gentle — Straight control, gentle flow (Fr 0.30)

*n/a — 2D cross-reference* · family `bends` · L=120 m, W1d=4 m, W2d=4 m, n=0.025, nx=240 (dx=0.5 m), dt=0.05 s, t_end=3600 s

![bend00-gentle profile](figures/bend00-gentle__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.1063 | 0.1613 | -47.33 | 0.008779 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); theta=0 control — generic 1D-vs-2D bias incl. sidewall friction |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.1063 | 0.1613 | -47.33 | 0.008779 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); theta=0 control — generic 1D-vs-2D bias incl. sidewall friction |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.1126 | 0.1624 | -16.17 | 0.004007 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 0.09907 | 0.1555 | -45.81 | 0.007115 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); theta=0 control — generic 1D-vs-2D bias incl. sidewall friction |
| 1d-fv | analytic | ✅ PASS | 0.02362 | 0.04414 | -0 | 2.384e-08 |  |
| 2d-explicit | – | — | – | – | – | – |  |

## bend00-swift — Straight control, swift flow (Fr 0.80)

*n/a — 2D cross-reference* · family `bends` · L=120 m, W1d=4 m, W2d=4 m, n=0.025, nx=240 (dx=0.5 m), dt=0.05 s, t_end=3600 s

![bend00-swift profile](figures/bend00-swift__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.07638 | 0.08161 | -36.38 | 0.0002438 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); theta=0 control for the swift regime |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.07638 | 0.08161 | -36.38 | 0.0002438 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); theta=0 control for the swift regime |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.07642 | 0.08162 | -16.12 | 0.0003759 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 0.07622 | 0.08157 | -52.57 | 0.0004946 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); theta=0 control for the swift regime |
| 1d-fv | analytic | ✅ PASS | 0.07597 | 0.08608 | -0 | 0 |  |
| 2d-explicit | – | — | – | – | – | – |  |

## bend90-gentle — 90-degree miter bend, gentle flow (Fr 0.30)

*n/a — 2D cross-reference* · family `bends` · L=120 m, W1d=4 m, W2d=4 m, n=0.025, nx=240 (dx=0.5 m), dt=0.05 s, t_end=3600 s

![bend90-gentle profile](figures/bend90-gentle__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.1086 | 0.1666 | -47.33 | 0.008773 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.1086 | 0.1666 | -47.33 | 0.008773 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.1149 | 0.1677 | -16.17 | 0.004004 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 0.1014 | 0.1608 | -45.81 | 0.00711 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-fv | analytic | ✅ PASS | 0.02574 | 0.04954 | -0 | 2.383e-08 |  |
| 2d-explicit | – | — | – | – | – | – |  |

## bend90-swift — 90-degree miter bend, swift flow (Fr 0.80)

*n/a — 2D cross-reference* · family `bends` · L=120 m, W1d=4 m, W2d=4 m, n=0.025, nx=240 (dx=0.5 m), dt=0.05 s, t_end=3600 s

![bend90-swift profile](figures/bend90-swift__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.08332 | 0.1333 | -36.38 | 0.0002415 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.08332 | 0.1333 | -36.38 | 0.0002415 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.08337 | 0.1333 | -16.12 | 0.0003724 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 0.08316 | 0.1333 | -52.57 | 0.00049 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-fv | analytic | ✅ PASS | 0.08291 | 0.1337 | -0 | 0 |  |
| 2d-explicit | – | — | – | – | – | – |  |

## bend45-swift — 45-degree miter bend, swift flow (Fr 0.80)

*n/a — 2D cross-reference* · family `bends` · L=120 m, W1d=4 m, W2d=4 m, n=0.025, nx=240 (dx=0.5 m), dt=0.05 s, t_end=3600 s

![bend45-swift profile](figures/bend45-swift__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.07723 | 0.08815 | -36.38 | 0.0002432 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.07723 | 0.08815 | -36.38 | 0.0002432 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.07728 | 0.08816 | -16.12 | 0.0003751 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 0.07707 | 0.08814 | -52.57 | 0.0004936 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss) |
| 1d-fv | analytic | ✅ PASS | 0.07683 | 0.0884 | -0 | 0 |  |
| 2d-explicit | – | — | – | – | – | – |  |

## bend90-swift-k — 90-degree bend, swift flow, literature miter K

*n/a — 2D cross-reference* · family `bends` · L=120 m, W1d=4 m, W2d=4 m, n=0.025, nx=240 (dx=0.5 m), dt=0.05 s, t_end=3600 s

![bend90-swift-k profile](figures/bend90-swift-k__profile.png)

| solver | mode | verdict | l1_h | linf_h | mass % | steady resid | notes |
|---|---|---|---|---|---|---|---|
| 1d-dynwave | analytic | ❌ FAIL | 0.1393 | 0.4066 | -23.31 | 0.0005642 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); 1D decks carry K_miter = 1.1(1-cos90) = 1.1 as Kentry on the corner conduit — the standard mitigation |
| 1d-dynwave-legacy | analytic | ❌ FAIL | 0.1393 | 0.4066 | -23.31 | 0.0005642 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); 1D decks carry K_miter = 1.1(1-cos90) = 1.1 as Kentry on the corner conduit — the standard mitigation |
| 1d-dynwave-semi | analytic | ❌ FAIL | 0.1393 | 0.4066 | -14.49 | 0.001054 | policy mirrored from 1d-dynwave |
| 1d-dynwave-vj | analytic | ❌ FAIL | 0.1389 | 0.4067 | -49.57 | 0.0001559 | graded against the pinned 2D bent-geometry reference (local-inertial — lower-bound bend loss); 1D decks carry K_miter = 1.1(1-cos90) = 1.1 as Kentry on the corner conduit — the standard mitigation |
| 1d-fv | analytic | ✅ PASS | 0.1329 | 0.3801 | 0 | 0 |  |
| 2d-explicit | – | — | – | – | – | – |  |

## Appendix

**Verdicts**: PASS/FAIL = analytic tolerances; BASE-PASS/FAIL = vs pinned baseline (`cases/<id>/baselines/`); XFAIL = documented impossibility; XPASS = expected-fail passed analytic tolerances — promote; ERROR = run/extraction failure; n/a = solver unavailable.

**Known engine limitations / findings recorded by this suite**: (1) RESOLVED 2026-08-03 — the apparent refactored-DW "short-conduit" instability was a fixed-step defect: the MINIMUM_STEP floor (0.5 s) was applied to fixed ROUTING_STEPs below 0.5 s, so decks silently marched at 0.5 s. With the TimestepController fix the refactored engine is bit-identical to legacy at every routing step on all Phase-A 1D decks (post-mortem in `runs/lake-at-rest-immersed/_debug/REPRO.md`). (2) RESOLVED 2026-08-04 — the "CFL 0.7 unstable on union-jack meshes" finding was a length-scale accounting error, not a scheme limit: cell_lchar (2A/ξ_max, the altitude) overstated the operator's stable dt by √3 on this triangulation (von Neumann: λ_checkerboard = 2·(g·h/A)·Σ ξ_f/dn_f ⇒ critical nominal CFL 0.577; measured 0.5 flat / 0.6 seiche). Two engine fixes landed: a tighten-only dt0 refresh between LTS rebuilds (dt was frozen up to 32 substeps), and L_char = √(2A/Σ ξ/dn) derived from the discrete operator — CFL_NUMBER is now a TRUE Courant fraction (raster recovers the classic 1/√2; the lake is machine-flat at nominal 0.7, stable through 0.95). The suite pins CFL 0.5 for ACCURACY (reproduces the truncation error its tolerances/baselines were calibrated at; macdonald-long-sub 2.0% vs 3.1% at 0.7); the engine default 0.7 is a genuine 30% stability margin. Sweep record: `runs/lake-at-rest-immersed/_debug_cfl07/FINDINGS_CFL_2026-08-03.md`. (3) Implicit Preissmann DW cannot resolve dry-bed rarefactions (Ritter; engine corpus precedent), cannot hold a transcritical choke or steady shock position, and needs PARTIAL inertial damping + dx >= 1 m on frictionless flumes. (4) 2D subcritical steady error RESOLVED 2026-08-03: the dominant 4.4% bump-subcritical error was a stage-BC offset (collapsed-Manning diffusive-wave conductance saturating the equilibrium clamp into a Dirichlet cell, plus a momentum-less SPECIFIED_FLOW inflow invisible to the Perot reconstruction) — both boundaries now integrate the interior inertial momentum law with a prognostic bc_q, and bump-subcritical passes the 3% analytic gate (l1 0.7%). The wet/dry hysteresis band now scales with H_MOVE (min(1 mm, H_MOVE/2)), un-freezing shallow shorelines (Thacker wet count oscillates instead of ratcheting), and [2D_INITIAL_VELOCITY] seeds face momentum so v(t=0) ≠ 0 solutions are representable (thacker-planar-2d de-XFAILed). What remains is the scheme's missing convective-inertia term: Bernoulli-dip residual ~0.7%, dam breaks / jumps / oscillation phase drift are baseline-mode, and macdonald-long-sup (fully supercritical) never steadies — formal XFAIL pending a full-SWE momentum solver. (5) Legacy requires an outlet node (ERROR 145) — closed basins carry a never-engaged sacrificial spillway. (6) Virtual-junction chains (`1d-dynwave-vj`, RESOLVED 2026-08-03): the shipped VJ coupling had three implementation errors (lossy one-slot chain mapping that left upwinding inert and applied the convective correction one-sided; no flow-direction handling; a destabilizing blanket σ_j override) — fixed in DynamicWave.cpp. The fixed BASIC chain (zero storage + direction-aware upwinding) matches the junction chain across all Phase-A regimes and stays stable at fine dx under small fairness-scaled dt where junction chains seiche (dx=0.2 m/dt=0.01 s: VJ l1 0.24% vs junctions 21%). FULL's dq4j flux term double-counts v²·∂A/∂x in EXTRAN's non-conservative form and remains opt-in/experimental. At the case dt=0.05 s BOTH chains refine cleanly (nx=125: l1 6.8e-4) — the frictionless-flume 'seiche' is a low-numerical-dissipation (small dt) phenomenon, not a dx cap. Full probe matrix: `runs/_resolution_probe/VJ_FINDINGS.md`. (7) Planform-blindness implications (bend family, 2026-08-04): the 1D solvers never see `[COORDINATES]` — junction chains transmit no momentum across nodes and carry no bend loss unless the user adds `[LOSSES]` K; VJ chains transmit full scalar momentum through any dogleg. Measured against the 2D solver on true L-shaped geometry: the dominant 1D-vs-2D bias is SIDEWALL FRICTION (θ=0 controls: l1 15.7%/8.1%, matching the RECT_OPEN R = Wh/(W+2h) normal depths exactly); bend-specific backwater is small (+17.6 mm / K_Δη ≈ 0.14 at 90°, Fr 0.8) because the local-inertial reference produces ~a tenth of the literature miter loss (lower bound); all three 1D discretizations are indistinguishable at steady state — the implication is the missing loss, not the momentum-transmission model; blindly adding literature K = 1.1 overshoots this reference. Full analysis: `runs/_bend_study/BEND_FINDINGS.md`. (8) The 2D axis is exactly two columns as of 2026-08-12: the local-acceleration marcher as shipped and the same marcher with `[2D_OPTIONS] ADVECTION YES`. The THETA sweep (`2d-explicit-th07/-th05`) was retired — θ is the q-centred de Almeida damping, the only dissipation the scheme has at n → 0, so it moves sawtooth amplitude on frictionless plateaus and cannot reach the plateau LEVEL or the shock position; those follow from the missing convective flux, which is what the advection column actually tests. (9) Advection quantifies the bend study's own blind spot (2026-08-12): running the ADVECTION column on the identical bent mesh that produced each pinned reference isolates the convective contribution exactly. It is precisely zero on the straight gentle control (the Stelling–Duinmeijer term vanishes in uniform flow — a free correctness check), and grows monotonically with turn angle: l1_h / linf_h = 0.00024/0.00067 (straight, swift), 0.00068/0.00860 (45°), 0.00560/0.01310 (90° gentle), 0.00506/0.03793 (90° swift). So the local-inertial reference under-reads bend loss by ~0.5% of depth in the mean and up to ~3.8% locally at the miter — that bounds the 'lower bound' caveat finding (7) carries. `bend90-swift-k` is bit-identical to `bend90-swift` in this column, as it must be (bend_k is a 1D `[LOSSES]` row the 2D deck never sees).

