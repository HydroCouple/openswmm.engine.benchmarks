# Hydraulic jumps and wall-reflected bores

Run through `run_regression.py --suite analytical/hydraulic_jumps`, or run
`python -m suites.analytical.hydraulic_jumps.suite --exe /path/to/openswmm`.
The suite is discovered automatically. A missing engine produces UNAVAILABLE
records. `--max-wall` bounds each native execution. `--build-provenance` accepts
a JSON record with `engine_sha` and the exact `binary_manifest()` mapping;
those hashes must match the executed CLI and library.

Sixteen CPU full-SWE cases exercise first- and second-order reconstruction at
0 and 64 degrees: a stationary jump, an upstream-moving jump, an oblique-flow
jump with continuous tangential velocity, and reflection of a supercritical
stream against a solid wall. Initial upstream depth is 0.03 m and normal speed
is 1.7 m/s; gravity is 9.80665 m/s². Conjugate states and reflected-bore speed
come from mass and momentum Rankine-Hugoniot relations and the compressive
root. No other hydraulic model supplies a reference.

Triangular cells use 0.025 m longitudinal and 0.05 m transverse spacing.
The domain has closed walls. At 0.5 s, artificial outer-wall disturbances
cannot reach the central assessment window; the reflection wall is part of
the exact wall-case solution. All runs continue to 1 s with ten required
0.1 s output frames. Missing or misaligned frames are rejected. The routing
and report intervals are both 0.1 s.

The frozen limits are 5% relative depth L1, 8% normal-velocity L1, 5%
transverse-velocity L1 scaled by the upstream speed, front-position error
below three longitudinal cells, 3% momentum jump residual, and closed volume
error below 1e-10 relative. Norms and jump states are assessed in the declared
causal window; global water balance is checked separately. Cs=0 retains the
accepted cell momentum output and global stepping used by the UK diagnostic
controls, with no SGS stress. Coriolis and wall skin friction are off.

This verifies controlled discontinuities and pressure reflection. It does
not validate the two-dimensional jump trajectory in UK Test 6, calibrate
roughness, establish mesh convergence, or change its canonical inputs or
reviewed regression anchors. Rotation cases are checked against the exact
solution; exact second-order rotational covariance is not assumed.
