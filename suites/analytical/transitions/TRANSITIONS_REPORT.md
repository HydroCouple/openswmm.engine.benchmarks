# Open-channel ↔ pressurized transition suite

Engine SHA `29cbc361` · refactored `/Users/calebbuahin/Documents/Projects/cbuahin_github/openswmm.engine/build/darwin-parity/bin/Release/openswmm` · legacy `/Users/calebbuahin/Documents/Projects/cbuahin_github/openswmm.engine/build/darwin-parity/bin/Release/openswmm-legacy` · single-threaded, OPENSWMM_2D_BACKEND=cpu · swept 2026-08-22T11:55:03

Three purpose-built cases stress the open-channel ↔ pressurized transition: a filling bore with an analytic front speed, a surcharge/relief cycle with an analytic peak-hold HGL, and a permanently pressurized inverted siphon with an energy-balance HGL. Five solver columns run the identical generated decks (only FLOW_ROUTING and per-solver keys differ). Grading is analytic; expected-fails are documented characteristics, never hidden (see Findings).

## Verdict matrix

| case | FV (no LTS) | FV + LTS | DW (EXTRAN) | DW (SLOT) | Legacy DW (EXTRAN) |
|---|---|---|---|---|---|
| rapid-fill | ✅ 0.023 | ✅ 0.023 | ✅ 0.012 | ✅ 0.034 | ✅ 0.012 |
| surcharge-cycle | ❌ 0.123 | ❌ 0.101 | ⚠️ 0.001 | ⚠️ 10.840 | ⚠️ 0.001 |
| inverted-siphon | ⚠️ 29.475 | ⚠️ 21.479 | ✅ 0.000 | ✅ 0.000 | ✅ 0.000 |

Cell = verdict + key metric (rapid-fill: relative front-speed error; surcharge-cycle: hold-mean head error, m; inverted-siphon: steady head error, m).

![continuity](figures/continuity.png)

![walltime](figures/walltime.png)

## rapid-fill — Rapid filling bore, horizontal pipe (analytic front trajectory)

Ambient column at rest (outfall stage = initial depth); step inflow 2.0 m3/s pressurizes the pipe end-to-end in ~220 s (analytic bore speed 2.97 m/s after formation).

Chain: 1 pipe(s), 25 conduits, L = 500 m; outfall FIXED 0.2 m; routing step 0.5 s; report 5 s.

![figures/rapid-fill__hgl_t60s.png](figures/rapid-fill__hgl_t60s.png)

![figures/rapid-fill__hgl_t120s.png](figures/rapid-fill__hgl_t120s.png)

![figures/rapid-fill__hgl_t168s.png](figures/rapid-fill__hgl_t168s.png)

![figures/rapid-fill__front_trajectory.png](figures/rapid-fill__front_trajectory.png)

![figures/rapid-fill__ts.png](figures/rapid-fill__ts.png)

| solver | verdict | front_speed | front_speed_err | head_drop | head_drop_err | continuity % | wall s |
|---|---|---|---|---|---|---|---|
| FV (no LTS) | PASS | 3.038 | 0.023 | 1.559 | 0.088 | 0.0 | — |
| FV + LTS | PASS | 3.038 | 0.023 | 1.559 | 0.088 | 0.0 | — |
| DW (EXTRAN) | PASS | 2.934 | 0.012 | 1.646 | 0.001 | -0.697 | — |
| DW (SLOT) | PASS | 2.869 | 0.034 | 1.646 | 0.001 | -1.155 | — |
| Legacy DW (EXTRAN) | PASS | 2.934 | 0.012 | 1.646 | 0.001 | -0.697 | — |

## surcharge-cycle — Surcharge onset and relief, sloped chain (peak-hold HGL analytic)

Hydrograph 0.3 -> 2.0 -> 0.3 m3/s; capacity ~1.07 m3/s, so the chain pressurizes on the rise and relieves on the recession.

Chain: 3 pipe(s), 120 conduits, L = 600 m; outfall FIXED 1 m; routing step 1 s; report 15 s.

![figures/surcharge-cycle__hgl_t600s.png](figures/surcharge-cycle__hgl_t600s.png)

![figures/surcharge-cycle__hgl_t2400s.png](figures/surcharge-cycle__hgl_t2400s.png)

![figures/surcharge-cycle__hgl_t4500s.png](figures/surcharge-cycle__hgl_t4500s.png)

![figures/surcharge-cycle__ts.png](figures/surcharge-cycle__ts.png)

| solver | verdict | head_hold_err | head_hold_range | links_surcharged | relief_ok | continuity % | wall s |
|---|---|---|---|---|---|---|---|
| FV (no LTS) | FAIL | 0.123 | 1.131 | 120 | True | -0.0 | — |
| | ↳ hold-mean head off by 0.123 m (tol 0.1) | | | | | | 
| FV + LTS | FAIL | 0.101 | 1.125 | 120 | True | -0.001 | — |
| | ↳ hold-mean head off by 0.101 m (tol 0.1) | | | | | | 
| DW (EXTRAN) | XFAIL | 0.001 | 0.000 | 120 | True | -6.093 | — |
| | ↳ routing continuity -6.09% (gate 2.0%) | | | | | | 
| DW (SLOT) | XFAIL | 10.840 | 20.000 | 120 | False | -33310.754 | — |
| | ↳ hold-mean head off by 10.840 m (tol 0.1); heads still above crown at end — no relief; routing continuity -33310.75% (gate 2.0%) | | | | | | 
| Legacy DW (EXTRAN) | XFAIL | 0.001 | 0.000 | 120 | True | -6.094 | — |
| | ↳ routing continuity -6.09% (gate 2.0%) | | | | | | 

## inverted-siphon — Inverted siphon, steady pressurized HGL (energy-balance analytic)

Barrel sits 5.8 m below the hydraulic grade line; the whole system runs full once spun up.

Chain: 5 pipe(s), 24 conduits, L = 460 m; outfall FIXED 8.6 m; routing step 1 s; report 30 s.

![figures/inverted-siphon__hgl_final.png](figures/inverted-siphon__hgl_final.png)

![figures/inverted-siphon__ts.png](figures/inverted-siphon__ts.png)

| solver | verdict | head_steady_err | barrel_full | continuity % | wall s |
|---|---|---|---|---|---|
| FV (no LTS) | XFAIL | 29.475 | True | -0.0 | — |
| | ↳ steady head off by 29.475 m (tol 0.05) | | | | 
| FV + LTS | XFAIL | 21.479 | True | -0.185 | — |
| | ↳ steady head off by 21.479 m (tol 0.05) | | | | 
| DW (EXTRAN) | PASS | 0.000 | True | -0.071 | — |
| DW (SLOT) | PASS | 0.000 | True | -0.307 | — |
| Legacy DW (EXTRAN) | PASS | 0.000 | True | -0.071 | — |

## Findings (first calibration sweep, 2026-08-12)

Probe artifacts under `runs/_probe/`; every number below is reproducible from
the probe decks.

1. **EXTRAN's surcharge leak grows with mesh refinement.** On
   surcharge-cycle both engines produce bit-identical heads (hold-mean error
   0.001 m) but leak **−6.09 %** of routing volume through one
   pressurize/relieve cycle at 5 m conduits — and the leak was −3.13 % at
   20 m conduits (probe4). FV closes at −0.00 % on the same decks. The
   non-conservative surcharge iteration does not converge away; it gets
   worse as you resolve the network.
2. **The static-slot method (SURCHARGE_METHOD SLOT) is unstable at a fixed
   1 s step on BOTH engines** for surcharge-cycle: refactored −37 235 %,
   legacy −208 % (mixed mesh) / −356 % (probe4). Verdict column is
   expected-fail with this documentation; do not read it as a refactored
   regression.
3. **FV pressurized friction is biased low on coarse cells of sloped
   pipes.** Uniform 20 m cells reach a steady state at roughly HALF the
   Manning friction slope (N0 head 3.07 m vs 5.18 analytic); uniform 5 m
   cells converge (5.22 m, ring ±0.6 m); a mixed 5/20 m mesh is bistable and
   rings ±2.3 m (probe3). The horizontal rapid-fill case shows NO such bias
   at 20 m cells (head drop 1.680 vs 1.647 m analytic), pointing at a
   slope–slot interaction. Suite decks therefore use 5 m conduits for the
   sloped case.
4. **FV local timestepping has a tier-depth cliff on pressurization
   transients** (probe5/probe6, surcharge-cycle, uniform 5 m):
   FV_LTS_MAX_TIERS ≤ 4 is clean (hold-mean 5.22 m, continuity −0.001 %) and
   **2.4× faster** than FV_LTS NO at equal accuracy; 5 tiers rings to 21 m;
   6 tiers (the engine default) collapses with **−687 %** continuity. The
   suite's fv-lts column pins MAX_TIERS 4; the default-6 breakage is an open
   engine defect.
5. **FV fails the steep-legged inverted siphon outright** (19 % drop /
   18 % rise legs, 15 m conduits): spurious head transients spike the barrel
   to 20–60 m. FV_CELL_LENGTH 2 reduces the steady error to ~2.6 m at 33×
   the wall clock; FV_ORDER 2 / RK2 to ~1.9–3.3 m; FV_LTS on the 2 m cells
   breaks conservation (−3.8 %). Expected-fail, under investigation. DW
   (both engines) reproduces the energy-balance HGL to 0.000 m here.
6. **NODE_CONTINUITY SEMI_IMPLICIT distorts stiff pressurized cases on the
   refactored DW path**: rapid-fill front speed drops to 1.69 m/s (analytic
   2.97, EXPLICIT gives 2.93) and the siphon leaks +10.4 % continuity
   (EXPLICIT: −0.10 %). The suite's shared options block pins
   NODE_CONTINUITY EXPLICIT (the epa_qa parity config); legacy ignores the
   key either way.
7. **Benchmark-design note:** junction MaxDepth is set so the flood ceiling
   is unreachable — with ALLOW_PONDING NO, any transient overshoot that
   reaches invert+MaxDepth silently deletes water and masquerades as a
   continuity error (this was conflating solver ringing with mass loss in
   early calibration runs).

