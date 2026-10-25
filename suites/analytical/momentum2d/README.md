# Coriolis, Smagorinsky and wall-friction verification

Run `python -m suites.analytical.momentum2d.suite --exe /absolute/path/to/openswmm`.
The suite is also discovered as `analytical/momentum2d` by `run_regression.py`.

Eighteen CLI cases cover both reconstruction orders: uniform inertial
oscillations with negative, zero and positive Coriolis parameters; a lake at
rest with Smagorinsky enabled; and closed-domain shear decay for Cs 0.05, 0.10
and 0.20. Four additional wall-friction channel cases test both flow signs
and reconstruction orders against u(t)=u0/(1+2*Cw*abs(u0)*t/B), with Cw=.02
and channel width B=1 m. These use one quad across the width and four along
the channel, constant stage open ends, and two selected tangential wall
boundaries. SI units, deterministic CPU execution.

Inertial velocities have an independent analytical reference. The Coriolis
parameter here is artificial for controlled verification. Lake checks are
analytical rest checks. Shear checks are conservation/energy properties, not
measured validation or an analytical turbulent-decay claim. No other hydraulic
model is used as a reference. Inputs, executed binary hashes, reports, fields,
checks and a Markdown report are retained under the selected output directory.

The engine additionally tests nonlinear stress convergence on triangular
meshes, linear strain on skew triangles and quads, rigid rotation, dry/blocked
faces, geostrophic convergence, and exact equality of omitted versus disabled
controls. The UK Test 6 benchmark and its measured reference remain separate;
this suite never changes a UK input or promotes its regression baseline.
