# stability — solver robustness under stress

Cases that exist to break solvers rather than to measure accuracy: surcharge
cycling, dry-bed starts, allow-ponding configurations, extreme timestep and
Courant ratios, isolated-node topologies, high-elevation and steep-slope
networks, and long continuous runs.

Graded on convergence behavior (% steps not converging, iterations per step),
timestep collapse (min Δt vs routing step), reported flow instabilities,
mass-balance drift over long runs, and crash/timeout outcomes. Nothing here
claims correctness — `reference.class` is typically `self_consistency`.

Seeded from the corpus's `z1000Years/` and `Special/` collections plus
contributed pathological models tagged `stability`.

**Scaffold stub** — plan step 3 populates it via tag query.
