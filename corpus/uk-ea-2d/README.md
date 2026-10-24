# UK EA 2013 source-derived scenarios

Executable decks for Tests 1–5, 6A and 6B, owned by `suites/uk_2d`. The original sources and their SHA-256 identities are listed in `suites/uk_2d/specifications/source-inventory.json`. Model generation, run commands, reference semantics and limitations are documented in `suites/uk_2d/README.md`.

Test 6A/6B now use the GUI's constrained Delaunay mesh with exact drawing boundaries, building exclusion, open dam gap and side-bank slopes. The user selected the written specification's 20-fold vertical scaling for 6B; the supplied raster's conflicting elevations are recorded in `uk-ea-2013-t6b/source-scale-audit.json`. The previous Cartesian anchors remain explicitly archived. The other tests still require their domain, boundary and breakline meshing corrections.

All cases are currently `self_consistency`: the original Test 6A measurements have not been acquired. Test 1 equilibrium constraints are scoped checks, not an exact transient reference. Test 6B is not validated by scaling Test 6A observations. Terrain/wall/source representation and permissions remain explicitly documented in each case.

Tests 7/8A/8B are retained in the suite's coverage manifest rather than represented by invalid or fabricated corpus decks. No competitor results are included.
