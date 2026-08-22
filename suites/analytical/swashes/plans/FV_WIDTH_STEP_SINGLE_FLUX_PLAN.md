# FV width-step junction: single-flux fix (design, 2026-08-13)

Fixes the pseudo-2D family (`runs/_p2d_probe/FINDINGS.md`): FV runs too deep
in contractions and too shallow in expansions (antisymmetric in dB/dx), exact
at the throat and BCs, dx-independent — the fingerprint of the missing
width-gradient momentum source `(q²/gA³)·h·B'(x)`. Benchmark validated
independently (RK4 re-integration reproduces the reference to l1 0.000%).

## Why the previous attempts failed (already on record in-source)

`ExplicitFvSolver.cpp` documents that ADDITIVE per-face closures make it
worse (splice-only l1 0.186 → convective ½Q̂²Δ(1/A) 0.313 → wall-pressure
½gΔI1 0.286). The reason is now clear, and it is not that the terms are
wrong: **the flux they were added to is ill-posed.** `faceSide()` reconstructs
each side in ITS OWN geometry —

```cpp
g = &mesh_->geom[mesh_->cell_geom[uc]];      // per-SIDE geometry
...
out.a  = k::areaOfDepth(*g, h_star);
out.i1 = k::i1OfDepth(*g, h_star, out.a);
```

— so at a width step `riemannFlux(L, R)` is handed two states living in
*different* cross-sections. That is not a Riemann problem; bolting a source
term onto its output double-counts, exactly as measured.

## The fix: give the FACE one geometry (this IS the "explicit wall term")

The scheme already solves the analogous problem for the BED by hydrostatic
reconstruction: `z* = max(z_L, z_R)`, states rebuilt at `h* = eta − z*`, and
the balance restored by the per-side correction

```cpp
f_corr_l_[uf] = k::kGravity * (i1l - L.i1);   // I1(cell, own h) − I1(reconstructed)
f_corr_r_[uf] = k::kGravity * (i1r - R.i1);
```

Do the same in the width dimension. Reconstruct **both sides in a single
shared FACE geometry** `g_f`, leaving `i1_raw` in each cell's own geometry.
The existing correction then automatically becomes the discrete wall-pressure
(I2) source: for a cell between faces of width B⁻ and B⁺ at rest it evaluates
to `g[I1(h,B⁻) − I1(h,B⁺)]`, which is exactly `g·I2 = g·(∂B/∂x)·h²/2`
discretized consistently with the fluxes that must balance it.

Two properties make this the right construction rather than another patch:

1. **Well-balanced by construction.** Flux and source use the SAME `g_f`, so
   lake-at-rest across a width step is preserved to machine precision. Every
   additive closure broke precisely this.
2. **Provably inert on prismatic chains.** When `B_L == B_R`, `g_f` is the
   cells' own geometry and every expression reduces to today's code —
   bit-identical, so the 40+ passing prismatic cells cannot regress.

## Implementation (4 edits, all additive)

1. **`NetworkMeshData.hpp` / mesh build** — add `std::vector<int> face_geom`
   alongside `cell_geom`. For each face: if both adjacent cells share a
   geometry index, reuse it (the prismatic no-op path). Otherwise look up or
   append a geometry whose parameters are the face-centred averages
   (`B_f = ½(B_L+B_R)`, likewise side slope Z; the face sits on the conduit
   boundary, so the mean is the second-order-accurate width there).
   De-duplicate through a map so a 400-conduit p2d chain adds ~400 entries,
   not one per face.
2. **`faceSide()`** — take the face geometry for the RECONSTRUCTED state
   (`out.a`, `out.c`, `out.i1`); keep `i1_raw` in the cell's own geometry. One
   extra parameter or a lookup of `mesh_->face_geom[uf]`.
3. **Pass-through splice** (the degree-2 junction path, where the far-cell
   ghost state is built) — evaluate the ghost side in `g_f` as well, and
   DELETE the reverted additive-closure comment block, replacing it with a
   pointer to this design.
4. **Node ghost / algebraic-node path** — the `cell < 0` branch of `faceSide`
   picks `geom` from the surviving neighbour; it must use `face_geom` too so a
   junction face at a width change is consistent with the interior faces.

Scope note: the SWASHES p2d cases are degree-2 chains, so implement and
validate on the pass-through path first. Degree ≥ 3 junctions with unequal
widths need the same face geometry per incident face, which this design
extends to naturally (each incident face gets its own `g_f`).

## Acceptance tests (in order — do not proceed past a failure)

1. **C-property unit test (new):** lake at rest over a width step
   (`u = 0`, flat surface, `B_L ≠ B_R`) must stay at rest to machine
   precision. This is the test every previous attempt would have failed.
2. **Prismatic bit-identity:** every constant-width SWASHES deck must produce
   a byte-identical `.out`. Non-negotiable regression gate.
3. **p2d acceptance (the new signature test):** on `p2d-sub-short`, the
   contraction error (+0.135/+0.225 m at x = 10/50 m) and the expansion error
   (−0.266/−0.122 m at x = 150/180 m) must fall toward zero TOGETHER. A fix
   that improves l1 while leaving the antisymmetry is moving the bias, not
   removing it.
4. **Two resolutions:** repeat at nx = 400 and nx = 1600. The defect is
   dx-independent, so a single-resolution improvement proves nothing.
5. **Jump position:** `p2d-jump-long` shock error 7.5 m → ≤ 1 cell, and
   `p2d-jump-short` stays ≤ 1.5 cells.
6. **Full matrix:** no new reds; `runs/_hires_sweep/merge_scores.py` +
   `run_swashes.py report`.

## What this does NOT fix

- **Dynamic wave.** EXTRAN marches momentum per link in non-conservative form,
  so there is no single flux to make well-balanced; and its virtual junctions
  reject unequal cross-sections outright (`ERROR 611`). DW width transitions
  stay a documented limitation (currently 37% on p2d-sub-long vs FV's 7%).
- **The smooth-flow uniform bias** (~2.5 mm on prismatic channels, §2 of
  `runs/_fv_vj_probe/FINDINGS.md`) — that is a cell-averaged bed/friction
  closure issue, unrelated to width steps.
