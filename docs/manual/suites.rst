======
Suites
======

``python run_regression.py --list`` names fourteen suites. Ten produce
cells; four are scaffolds that produce none. Each suite owns its case list,
its grading and its output folder; :doc:`concepts/grading` explains the
verdicts and reference classes used below.

.. list-table::
   :header-rows: 1
   :widths: 24 30 18 28

   * - Suite
     - Measures
     - Needs
     - Scores envelope
   * - ``parity``
     - Engine-to-engine parity, mass balance, convergence
     - Two engines
     - ``results/parity/scores_<tier>.json``
   * - ``analytical/swashes``
     - 1D and 2D shallow-water profiles against closed-form solutions
     - Engine
     - ``suites/analytical/swashes/swashes_scores.json``
   * - ``analytical/transitions``
     - Open-channel to pressurized transitions against closed-form references
     - Engine
     - ``suites/analytical/transitions/transitions_scores.json``
   * - ``analytical/manufactured``
     - Reproducibility of exact-by-construction reference datasets
     - Nothing
     - ``results/analytical_manufactured/scores.json``
   * - ``analytical/hydraulic_jumps``
     - 2D jumps and wall-reflected bores against Rankine-Hugoniot states
     - Engine with 2D HDF5 output, h5py
     - ``results/analytical_hydraulic_jumps/``
   * - ``analytical/momentum2d``
     - 2D Coriolis, Smagorinsky and wall-friction terms
     - Engine with 2D HDF5 output, h5py
     - ``results/analytical_momentum2d/``
   * - ``quality/reactions``
     - Multispecies reaction kinetics and conservation
     - Engine
     - ``results/quality_reactions/scores.json``
   * - ``coupling``
     - Rubinato et al. (2017) 1D-2D exchange
     - Native engine test binaries
     - ``results/coupling/``
   * - ``uk_2d``
     - UK Environment Agency 2D benchmark scenarios
     - Engine with 2D HDF5 output
     - ``results/uk_2d/``
   * - ``uk_river``
     - UK W5-105 river benchmarks
     - Engine with 2D HDF5 output
     - ``results/uk_river/``
   * - ``epa_qa``, ``stability``, ``performance``, ``quality``
     - Nothing yet (scaffolds)
     - Nothing
     - An empty envelope, not written to disk

Regression: ``parity``
======================

The central sweep. Every case in the selected tier runs through every
resolved engine, and every comparison declared in ``harness/engines.yaml`` is
evaluated across all subcatchment, node, link and system variables at every
reporting period (:doc:`concepts/architecture` walks through one case).
Today that is ``swmm-5.3.0`` (the vendored legacy engine) against
``openswmm-v6`` at ``rtol`` 1e-9 and ``atol`` 1e-12, gated: OpenSWMM 6 must
reproduce the legacy engine on the whole corpus, model by model.

Most cases are ``self_consistency``: no external truth exists for them, so
agreement between engines plus the mass-balance and convergence figures are
the whole result. Cases tagged ``uk_ea_2d`` or ``uk_ea_river`` are never run
here, even with ``--only``. Tiers are tag queries in
``suites/parity/manifests/``:

.. list-table::
   :header-rows: 1
   :widths: 14 58 14 14

   * - Tier
     - ``select``
     - ``timeout_s``
     - Cases listing it
   * - ``pr``
     - ``(hydraulics OR hydrology OR quality OR lid) AND NOT performance AND NOT long_term``
     - 120
     - 0
   * - ``nightly``
     - every case (``null``)
     - 600
     - 1,419
   * - ``weekly``
     - no manifest (``tier_weekly.yaml`` does not exist)
     - n/a
     - 17

A case runs only when it matches the query *and* lists the tier under
``tiers`` in its metadata. No case lists ``pr`` yet, so the ``pr`` tier
selects nothing and records an ``ERROR`` cell (``tier 'pr' selected no
cases``) rather than a pass over zero models. The seventeen cases that list
``weekly`` are the UK cases, which the parity suite never runs; it has no
``tier_weekly.yaml``, and ``--tier weekly`` stops with ``no manifest for
tier 'weekly'``.
``manifests/skip_list.yaml`` excludes 90 cases, each with a reason (most
reference input files that were never in the repository).

Mass balance
============

There is no separate mass-balance suite. Each parity run cell carries the
report's routing continuity error (``continuity_err``, percent), runoff
continuity error and worst pollutant continuity error, scraped by
:func:`harness.rptparse.parse`. These figures do not change the cell's
verdict; they feed the ``mass-balance`` badge, which reports the worst
absolute routing continuity error and is green up to 1 %, yellow up to 5 %.
Thirty-eight cases are tagged ``expected_high_continuity`` because the report
committed beside the model, written by an earlier engine, already shows more
than 10 % error; they are still run and still gated on parity, but left out
of the badge and counted on it.

Stability
=========

The ``stability`` suite is a scaffold. Convergence is graded from the parity
sweep: each run cell carries the report's ``% of Steps Not Converging``
(``pct_not_converging``), average iterations per step and minimum time step,
and a crash or timeout makes the run cell ``ERROR``. The ``stability`` badge
counts a run as stable at or below 1.0 % of steps not converging.

Verification
============

Cells graded against an exact or manufactured solution. These are the only
cells that count toward the ``verification`` badge.

``analytical/swashes``
   Shallow-water solutions from Delestre et al. (2013), *SWASHES: a
   compilation of shallow water analytic solutions for hydraulic and
   environmental studies* (doi:10.1002/fld.3741): steady flow over a bump,
   MacDonald channels, dam breaks (Ritter, Stoker, Dressler), Thacker
   oscillations, lakes at rest and 2D paraboloid cases, 33 cases in all, each
   run on a matrix of six solver configurations: ``1d-dynwave``,
   ``1d-dynwave-legacy``, ``1d-dynwave-semi``, ``1d-dynwave-vj``, ``1d-fv``
   and ``2d-explicit``. Six ``bend*`` cases use engine-generated 2D
   references. Runs and the envelope
   stay inside the suite folder. The committed
   :repo:`suites/analytical/swashes/SWASHES_REPORT.md` holds the last full
   matrix. Options: ``--cases <glob>``, ``--solvers a,b``, ``--force``,
   ``--shard K/N`` (every Nth case-solver cell) and ``--ci-resolution``.

   Since the cases were refined to 1 m (2026-08-13) the seven long McDonald
   cases cost 5–70 min per solver, more than a Nightly job can hold. Each
   carries a ``ci_nx`` (dx 5 m, 20 m for ``macdonald-periodic``); with
   ``--ci-resolution`` they run at it and are graded only against a pin made
   at that resolution in ``cases/<id>/baselines/ci/``, written to
   ``swashes_ci_scores.json``. A coarse run is not their analytic verdict:
   measured on 2026-11-22, DW improves when coarse (``macdonald-periodic``
   FAILs at 1 m and passes at 20 m) and FV worsens. The Nightly passes
   ``--ci-resolution``; ``swashes_weekly.yml`` grades every case at full
   resolution. Pin a reviewed coarse run with
   ``python run_swashes.py pin-baseline --ci --case ID --solver ID``.

``analytical/transitions``
   Three cases for the moment a pipe goes from open-channel flow to
   pressurized flow: a filling bore in a horizontal pipe (front speed), a
   surcharge cycle (pressurized peak hydraulic grade line), and an inverted
   siphon (steady energy balance). See
   :repo:`suites/analytical/transitions/README.md`.

``analytical/manufactured``
   Seventeen reference datasets that are exact by construction (infiltration,
   groundwater recession, ODE integrators, cross-section geometry and
   others). Most have no ``.inp``: they feed the engine's own unit tests. The
   suite reruns each case's generator script in the case folder and requires
   a byte-identical ``reference.csv``; a mismatch is restored and graded
   ``FAIL`` (``--regen`` keeps the new file instead). Six cases ship a
   generator and pass; eleven are ``SKIP``, seven of which claim
   ``reproducible: true`` in their provenance without a generator, which the
   suite reports. No engine is needed.

``analytical/hydraulic_jumps``
   Sixteen 2D full shallow-water cases: stationary, moving and oblique
   hydraulic jumps and a bore reflected from a wall, at two reconstruction
   orders and two orientations, against conjugate states from the mass and
   momentum jump conditions. See
   :repo:`suites/analytical/hydraulic_jumps/README.md`.

``analytical/momentum2d``
   Uniform inertial oscillations under Coriolis forcing, a lake at rest with
   Smagorinsky viscosity, closed-domain shear decay, and wall-friction
   channels with an exact decay law. The shear-decay cells are
   ``self_consistency`` (conservation and energy properties); the others are
   ``analytic``. See :repo:`suites/analytical/momentum2d/README.md`.

``quality/reactions``
   Parent and product species decaying with closed-form concentrations across
   the three network quality solvers, four rate units and per-element
   parameter overrides, plus conservation checks for wet pools, WALL
   geometry, dry buildup, bioretention and SETPOINT profiles. The
   conservation-only cells are ``self_consistency``. See
   :repo:`suites/quality/reactions/README.md`.

Measured references
===================

Suites that compare with laboratory or field data. The fit is reported, not
gated, and a ``PASS`` means the numerical checks passed (completion, finite
and nonnegative fields, continuity), not that the model matches the
measurements.

``coupling``
   The Rubinato et al. (2017) flume: observed steady exchange rows, legacy
   orifice anchors, physical-shaft sensitivities, an anti-choking check and
   synthetic events. It runs two native engine test programs
   (``test_engine_2d_exchange_rubinato_*``) from ``--native-bin`` and loads
   the engine library given by ``--library``. See
   :repo:`suites/coupling/README.md`.

``uk_2d``
   The UK Environment Agency 2D benchmark: ten historical scenarios kept
   visible in coverage, seven with decks rebuilt from the source archive,
   compared only with measured or analytical references and the suite's own
   reviewed baselines. Tiers ``pr``, ``nightly`` and ``weekly``, and flags
   ``--require-complete``, ``--require-regression`` and
   ``--require-observed`` that turn missing coverage into a failure. See
   :repo:`suites/uk_2d/README.md`.

``uk_river``
   The W5-105 river benchmarks: analytical water levels, tabulated
   laboratory histories and measured bridge afflux, with the bridge case and
   one analytical comparison still unavailable. See
   :repo:`suites/uk_river/README.md`.

Both UK suites publish a coverage badge that always reads ``validation
pending``.

Scaffolds
=========

``epa_qa``
   Meant to repeat the Rossman (2006) EPA SWMM 5 quality assurance comparison
   on its 21 models (``extran1`` to ``extran10`` with ``extran8a`` and
   ``extran8b``, ``test1`` to ``test5``, ``user1`` to ``user5``) against the
   original SWMM 4 reference series. The 21 models are in the corpus and run
   in the parity sweep; the QA sweep itself is not written.
``stability``
   Meant to run stress cases selected by tag. Convergence is graded by the
   parity sweep instead.
``performance``
   Meant to time synthetic scale models and real networks per engine for a
   trend dashboard. Nothing is timed today beyond the ``wall`` time on parity
   run cells.
``quality``
   Meant to select water-quality and LID-pollutant cases by tag. Those cases
   are run by the parity sweep; the separate ``quality/reactions`` suite is
   implemented.

Each prints ``scaffold stub — not yet migrated; no cells produced`` and
returns an empty envelope.

Adding a suite
==============

Copy :repo:`suites/_suite_template.py` to ``suites/<name>/suite.py`` and
implement ``run`` and ``report``. Put ``case``, ``solver`` or ``pair``,
``verdict`` and ``reference_class`` on every cell, write cells with
:func:`harness.scoring.save_cell`, return ``UNAVAILABLE`` cells when an
engine is missing, and write under ``results/<name>/``. The runner finds the
suite on its next run; there is no registration step.
