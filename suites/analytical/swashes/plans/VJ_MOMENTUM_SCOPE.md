# Virtual-junction axial momentum: scope (2026-08-14)

Requested after the VJ probe found that DW + virtual junctions does **not**
recover the accuracy DW loses on a subdivided chain, contrary to the design
intent ("axial momentum is conserved across a virtual junction").

Scoping measurement: `runs/_fv_vj_probe/vj_periodic_scaling.py`
(raw: `vj_periodic_scaling.json`, `classify_out.txt`).

> **STATUS 2026-08-14 — Phases 1-3 EXECUTED. See "OUTCOMES" at the end.**
> Phase 4 (design a junction momentum coupling) is **CANCELLED**: junction
> count is not what drives the error. Phase 3 confirmed the FULL-mode sign
> inversion and showed no term-level correction salvages the option.

---

## 0. The measurement that reframes the problem

`macdonald-periodic` (prismatic 500 m rectangle, sinusoidal bed, so VJ is legal
— no ERROR 611) at three resolutions, Courant held at 0.20 throughout:

| dx | config | l1 | bias | bias / (v²/2g) | mass | wall |
|---:|---|---:|---:|---:|---:|---:|
| 20 m | dw | 0.165 % | +0.0013 m | +0.008 | 0.000 % | 2.3 s |
| 20 m | vj_basic | 0.234 % | +0.0007 m | +0.005 | 0.000 % | 2.9 s |
| 20 m | vj_full | 4.171 % | **−0.0179 m** | **−0.111** | −0.000 % | 3.1 s |
| 20 m | fv | 0.748 % | +0.0004 m | +0.002 | 0.000 % | 3.2 s |
| 10 m | dw | 0.141 % | +0.0016 m | +0.010 | 0.000 % | 8.4 s |
| 10 m | vj_basic | 0.163 % | +0.0013 m | +0.008 | 0.000 % | 10.7 s |
| 10 m | vj_full | 9.003 % | +0.1013 m | +0.629 | **−224.2 %** | 70.5 s |
| 10 m | fv | 0.357 % | +0.0013 m | +0.008 | −0.000 % | 11.0 s |
| 5 m | dw | **11.266 %** | +0.1267 m | **+0.787** | 0.000 % | 125.5 s |
| 5 m | vj_basic | 9.363 % | +0.1053 m | +0.654 | **−351.8 %** | 263.0 s |
| 5 m | vj_full | 14.124 % | +0.1589 m | +0.986 | **−307.6 %** | 312.4 s |
| 5 m | fv | **0.179 %** | +0.0016 m | +0.010 | −0.000 % | 47.7 s |

`bias` is the mean **signed** depth error; v²/2g = 0.1611 m.

### 0.1 The "junction chain loses a velocity head" premise does not survive

DW is **accurate at dx = 20 and dx = 10** — l1 0.165 % / 0.141 %, bias ~0.01
velocity heads — with 250 and 500 interior junctions already in the chain. A
chain that lost momentum *per junction* would have failed at dx = 20 too. The
failure is a **threshold between dx = 10 and dx = 5**, after which the bias
saturates near one velocity head (0.79 → 1.09 / 0.93 at dx = 2.5 / 1, from
`runs/_periodic_probe/`). Saturation at one velocity head is a real and
reproducible signature, but it is the *endpoint* of the failure, not its cause.

**Consequence for this work: a junction-momentum fix cannot be designed yet,
because it is not established that missing junction momentum is the defect.**

Already eliminated as the cause:

- **Inertial damping.** The decks run `INERTIAL_DAMPING NONE`, which forces
  σ = 1, so the convective term is at full strength at every resolution.
- **Timestep / Courant.** Courant = 0.20 at all three resolutions here, and
  the earlier probe moved l1 by 0.012 pts for a 10× smaller dt.
- **Case, deck and reference.** FV solves the *identical* decks and converges
  at order ≈ 1 (0.748 → 0.357 → 0.179 %) with bias ≤ 0.01 velocity heads.

Weak remaining lead: the **normal-flow limiter** first activates at dx = 5
(`NormLtd` 0.000 → 0.007, 442 of 1000 links) and is absent at dx = 20/10. But
it never exceeds 5 % of the run on any single link, so it reads as a startup
artifact rather than a persistent kinematic throttle. Worth one experiment,
not a working hypothesis.

### 0.2 New defect — VJ BASIC (the default) destroys mass at dx = 5

`vj_basic` continuity error: 0.000 % at dx = 20, 0.000 % at dx = 10,
**−351.8 %** at dx = 5 — on a case where plain DW holds 0.000 % at the same
resolution. This is a correctness bug in the default VJ mode, independent of
the momentum question, and it is the reason the dx = 5 VJ numbers cannot be
read as accuracy results at all.

### 0.3 VJ FULL is sign-inverted, not merely double-counted

At dx = 20 — the only resolution where every configuration is stable — FULL
puts the bias on the **wrong side** (−0.111 velocity heads vs DW's +0.008)
and takes l1 from 0.165 % to 4.171 %. The algebra predicts exactly this. For
constant discharge, `Δ(v²A) = Q²Δ(1/A) = −v²ΔA`, so

```
link  (DynamicWave.cpp:2539)  dq4  = dt·σ·v²·(A₂ − A₁)/L          ∝ +v²ΔA
VJ    (DynamicWave.cpp:892)   dq4j = dt·σⱼ·[(v²A)_dn − (v²A)_up]/Λ ∝ −v²ΔA
```

`dq4` is the **correct** non-conservative EXTRAN form (from
`d(v²A)/dx = −v²dA/dx` at constant Q, which is what makes
`gA·dH/dx = v²dA/dx − gA·S_f` reproduce the steady momentum equation exactly at
σ = 1). `dq4j` therefore carries the opposite sign, and
`DynamicWave.cpp:2485,2490` adds it to **both** adjacent links, so an interior
link can receive ≈ −2·dq4 on top of its own +dq4 — net ≈ −dq4, a flipped
convective term. Earlier framing of this as a "double count" was imprecise;
the sign inversion is the sharper and more testable statement.

### 0.4 The engine's own VJ residual cannot gate this work as written

`vjAccumulateResiduals` (`DynamicWave.cpp:908`) reports mean 232 / max 1.07e6
at dx = 20, where DW is essentially exact (bias 0.008 velocity heads). It
accumulates over the whole run including the startup transient, and its max is
plainly transient-dominated (1.07e6 in *both* VJ modes at dx = 20). It must be
restricted to a steady window before it can serve as an acceptance metric.

### 0.5 FV already delivers what VJ was meant to

At dx = 5: l1 **0.179 %** vs DW 11.266 %, mass 0.000 %, and **2.6× faster**
than both DW (125.5 s) and VJ BASIC (263.0 s). FV converges; DW does not.

---

## Phase 0 — decide whether to do this at all (½ day, no code)

FV is 63× more accurate and 2.6× faster than VJ BASIC on the exact problem VJ
exists to solve. Two honest options:

- **(a) Fix it** — Phases 1-5 below. Justified if DW+VJ must serve models that
  cannot move to FV (parity obligations, unsupported FV features).
- **(b) Contain it** — fix the BASIC mass bug (Phase 2, non-optional either
  way), gate `VIRTUAL_JUNCTION_MOMENTUM FULL` off or remove it (Phase 3), and
  document VJ BASIC as a zero-storage node with *no* momentum transmission,
  pointing accuracy-driven users at FV.

Phase 2 is required under both options. Everything after it is contingent.

## Phase 1 — root-cause the dx = 10 → 5 cliff (1-2 days) — BLOCKING

No design work starts until this lands. Each experiment has a stated
discriminator; run them on `macdonald-periodic`, plain DW (no VJ).

1. **E1 — bisect.** dx = 8, 6.7, 6, 5. Threshold or rapid transition?
   A sharp step implicates a switch (limiter, flow classification, a clamp);
   a smooth ramp implicates a resolution-dependent truncation term.
2. **E2 — separate junction count from bed resolution.** *The key experiment.*
   Hold dx = 5 and halve the domain (L = 2500 m, same bed wavelength) so the
   junction count halves at fixed cells-per-wavelength; then hold the junction
   count at 1000 and double the bed wavelength so cells-per-wavelength doubles
   at fixed junction count. Whichever knob moves the error names the mechanism.
   If it tracks cells-per-wavelength, this is **not** a junction problem at all
   and Phases 4-5 are moot.
3. **E3 — `NORMAL_FLOW_LIMITED NONE` at dx = 5.** Eliminates or confirms §0.1's
   weak lead in one run.
4. **E4 — is the fine solution the no-convective solution?** Compare DW at
   dx = 5 against DW at dx = 5 with the convective term deleted
   (`INERTIAL_DAMPING FULL`, σ = 0). If they coincide, the convective term is
   being lost somewhere despite σ = 1, which is a very different bug from a
   junction closure.
5. **E5 — steadiness.** The earlier probe verified steadiness at dx = 1, not at
   dx = 5. Run to t = 30000 and confirm the t = 12000 profile is converged.
   `Dry = 0.112` in the dx = 5 classification summary needs explaining before
   any of the above is trusted.

**Exit criterion:** a named mechanism that predicts both the dx = 20/10 success
and the dx ≤ 5 failure, verified by a controlled experiment.

## Phase 2 — VJ BASIC mass conservation (1-2 days) — NOT CONTINGENT

−351.8 % continuity is unambiguous and lives in the default mode.

1. Bisect resolution to find where it starts; confirm it is resolution and not
   junction count (reuse E2's decks).
2. Instrument the node volume balance at one failing VJ: a zero-storage node
   must satisfy Σ Q = 0 exactly each iteration. Establish whether the loss is
   in the node solve, in the surface-area accounting for a storage-less node,
   or in the reporting path.
3. **Acceptance:** mass = 0.000 % at dx = 20/10/5/2.5/1, both continuity modes.

## Phase 3 — VJ FULL: test the sign, then keep or retire (1 day)

Two one-line experiments settle it:

1. Negate `dq4j` (`DynamicWave.cpp:892`). Predicted by §0.3 to move the dx = 20
   bias from −0.111 back toward +0.008 velocity heads.
2. Attribute each interface's term to **one** link, not both
   (`DynamicWave.cpp:2485,2490`).

If neither restores stability at dx = 10 (currently −224 % mass), retire FULL:
delete the option, keep the parser accepting-and-warning for one release.
A momentum term that destroys 224 % of the volume is not a tuning problem.

## Phase 4 — design the coupling (contingent on Phase 1, 3-5 days)

Only if Phase 1 shows junction momentum is genuinely the deficit.

**The FV fix does not transfer.** FV had a single face flux that could be made
well-posed by sharing one geometry. EXTRAN marches momentum per link in
non-conservative form and `dq4 ∝ v²ΔA` is already the correct form for that
framework — there is no flux object to share, and adding a term on top is what
FULL does and why it fails. The coupling must instead make the two links'
momentum equations **mutually consistent at the shared node** — the candidate
being a momentum-consistent end state (area/head) at a VJ face rather than an
additive correction, so the pair reduces to the single-link discretization when
the two conduits are identical. Design work, not a patch.

## Phase 5 — acceptance and guards

1. **Fix the residual diagnostic first** (§0.4) — restrict to a steady window.
   It is the gate; it cannot gate anything in its current form.
2. **`macdonald-periodic` at dx = 20/10/5/2.5/1:** monotone convergence, no
   cliff. This is the discriminator — `macdonald-long-sub/-jump` are nearly
   uniform in v and cannot separate the hypotheses (VJ moved them by +1.3 %).
3. **Mass = 0.000 %** at every resolution, both VJ modes, both continuity modes.
4. **No regression:** `macdonald-long-sub` l1 ≤ 1.915 %, `-long-jump` ≤ 1.348 %.
5. **Bit-identity:** every non-VJ deck byte-identical. VJ is opt-in so this is
   structurally guaranteed — assert it anyway, as `pin_variants.py` does.
6. **Cost gate:** VJ BASIC is 2.1× slower than DW at dx = 5 (263.0 vs 125.5 s)
   while FV is 2.6× faster *and* 63× more accurate. A fix that keeps the VJ
   cost penalty needs an explicit reason to exist.

## Non-goals

- **Unequal cross sections** (`ERROR 611`) — the p2d family stays FV-only.
- **VJ under FV** — 2.3-2.6× worse (VJ displaces FV's own splice);
  recommendation stands that it become a warned no-op.
- **The dx = 20 FV bias** (0.748 %, larger than DW's 0.165 % at that
  resolution) — FV is simply coarse there; it converges away.

---

# OUTCOMES (2026-08-14)

Detail: `runs/_periodic_cliff/FINDINGS.md`,
`runs/_fv_vj_probe/vj_full_sign_test.py`, `runs/_dw_parity_probe/`.

## Precondition verified — legacy ≡ refactored DW without virtual junctions

31 SWASHES cases, `1d-dynwave` vs `1d-dynwave-legacy`, `.out` compared region
by region (`runs/_dw_parity_probe/bitidentity.py`; decks confirmed VJ-free).
**Every solved state variable is bit-identical at every reporting period** —
node depth/head/volume/lateral inflow/overflow, link flow/depth/velocity/
volume/capacity — and `extracted.csv` is byte-identical 31/31.

Three reported quantities differ, none of them solver state
(`locate_diffs.py`): `sys.air_temp` (refactored emits the SWMM default 70 °F,
legacy 0.0; no climate block in these decks); `sys.storage_volume` (a
system-wide SUM at rel 1.7e-7..1.5e-4 — every individual volume is
bit-identical, so this is summation order, within the N·ε bound); and
`node.total_inflow` at **exactly one node per case, always the downstream
outfall**. The two `.inp` files differ only in two comment lines.

## Phase 1 — CANCELS Phase 4

`macdonald-periodic`, at **fixed 499 junctions**, dx alone flips l1 from
0.141 % (dx=10, L=5000) to 11.221 % (dx=5, L=2500); halving the junction count
at fixed dx changes nothing. Domain truncation is exact here (reference
reproduced to `max|Δh| = 0.000e+00`). **There is no per-junction momentum
deficit, so no junction-momentum treatment can repair this**, and any
object-count threshold is excluded too (both runs have nx=500).

Also eliminated: dt/Courant, the normal-flow limiter, non-steadiness (t=30000
identical), inertial damping (NONE 10.975 / PARTIAL 11.693 / FULL 13.058 % —
all bad), bed precision (6 decimals), and the initial condition (exact
analytic h0 gives 11.388 % vs 10.975 %). Two of those — damping and the IC —
were the leading hypotheses and both are disproved.

**Left open, and now its own problem:** EXTRAN's discrete steady state on this
deck bifurcates between dx = 6.67 m and dx = 5.71 m — steady in time,
mass-exact, error phase-locked to the bed (0.000 m at the trough, +0.32 m at
the crest) with q developing a steady spatial oscillation (1.93-2.05 against a
uniform 2.0). FV converges normally on the identical decks (0.748 → 0.357 →
0.179 %). Next instrument: the built-in term trace (`SWMM_TRACE_LINK`,
`DynamicWave.cpp:2577`) at matched physical stations either side of the
threshold.

Separately worth fixing on its own merits: the case's `h0` is a FLAT surface at
the outlet stage, which on this 5000 m channel leaves it nearly dry
(`InitDepth` mean 0.0282 m against an analytic 0.875-1.375 m). Not the cause,
but it makes every run a dry-bed filling problem.

## Phase 2 — VJ BASIC's mass break is damping-coupled

−351.8 % continuity at dx=5 with `INERTIAL_DAMPING NONE`, bisected to the same
dx threshold (clean at 6.67 m, −250.7 % at 5.71 m). With `PARTIAL` it is
**0.000 % at both**. Still a defect — no damping setting should let a
zero-storage node destroy 350 % of the volume — but narrower than first
recorded and inert for any deck running PARTIAL. With PARTIAL, VJ BASIC and
plain DW agree to three digits (9.833 vs 9.856 %, 11.661 vs 11.693 %), the
expected signature of a mode that computes no cross-junction term at all.

## Phase 3 — sign inversion CONFIRMED; FULL is not salvageable

Two env-gated switches were added, measured, and removed again (the engine now
carries comments only; a no-VJ deck was byte-identical to its pre-change run
before and after, and all variants re-collapse to the baseline).

| dx | variant | l1 | bias (v-heads) | mass |
|---:|---|---:|---:|---:|
| 20 | baseline | 4.171 % | −0.111 | −0.000 % |
| 20 | negated `dq4j` | 5.050 % | +0.136 | 0.000 % |
| 20 | one-side attribution | 86.421 % | +6.036 | 0.002 % |
| 20 | both | 2.306 % | +0.062 | **−321.5 %** |
| 10 | baseline | 9.003 % | +0.629 | **−224.2 %** |
| 10 | negated `dq4j` | 5.244 % | +0.135 | **0.000 %** |
| 10 | one-side attribution | 103.188 % | +7.206 | 0.001 % |
| 10 | both | 2.442 % | +0.069 | **−325.2 %** |

Negating `dq4j` **restores mass conservation outright** at dx=10 (−224.2 % →
0.000 %) and halves the bias — the sign analysis is confirmed. But even
sign-corrected, FULL is l1 5.24 % against BASIC's 0.163 % and plain DW's
0.141 % on the same deck, because `dq4j` is also added to BOTH adjacent links
on top of each link's own full-length `dq4`, so the convective term is applied
~3×. One-side attribution is far worse, and the combination destroys mass.
**No term-level correction makes FULL useful.**

## Recommendation

1. **Retire `VIRTUAL_JUNCTION_MOMENTUM FULL`** — parse-and-warn for one
   release, then remove. It is off by default, unused by the matrix, and in its
   shipped form destroys 224-325 % of the volume. (If it must stay, negate
   `dq4j`: that alone converts mass destruction into mere inaccuracy.)
2. **Document VJ BASIC** as a zero-storage node with cross-junction upwinding
   and *no* momentum transmission — which is what it is — and fix its
   `INERTIAL_DAMPING NONE` mass break.
3. **Point accuracy-driven users at FV**, which on this deck is 63× more
   accurate and 2.6× faster and converges where DW does not.
4. **Open the dx-bifurcation as its own investigation.** It is an EXTRAN
   issue, not a virtual-junction one, and it is the only finding here that
   affects ordinary DW models.
