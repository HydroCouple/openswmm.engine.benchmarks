===================
OpenSWMM Benchmarks
===================

OpenSWMM Benchmarks is a benchmarking and regression platform for
SWMM-compatible engines. It holds a corpus of about 1,400 tagged SWMM models
(``python -m harness.corpus --census`` prints the current count), suites of
analytical test problems with exact or manufactured solutions, and the Python
harness that runs them through the engines declared in
``harness/engines.yaml``. The harness grades every run, writes a scores
envelope per suite, and renders a static dashboard and shields.io badges from
those envelopes.

The harness does not compile engines. It drives executables that follow the
SWMM command-line convention ``exe input.inp report.rpt output.out`` and reads
the text report and binary output they write; CI builds the engines first with
the repository's ``build-engine`` action, and locally you point the harness at
an existing build.

What it measures
================

.. list-table::
   :header-rows: 1
   :widths: 22 48 30

   * - Dimension
     - Question it answers
     - Where it is graded
   * - Result parity
     - Do two engines produce the same value for every subcatchment, node,
       link and system variable, pollutants included, at every reported
       period?
     - ``parity`` suite, from the ``.out`` files
   * - Mass balance
     - What runoff, routing and quality continuity error does each run
       report?
     - ``parity`` suite, from the ``.rpt`` files
   * - Stability
     - What share of routing steps fails to converge? Does the run crash or
       time out?
     - ``parity`` suite, from the ``.rpt`` files and the exit status
   * - Analytical accuracy
     - How far is the result from an exact or manufactured solution?
     - ``analytical/*`` and ``quality/reactions`` suites
   * - Agreement with measurements
     - How does the model compare with laboratory or field observations?
     - ``coupling``, ``uk_2d`` and ``uk_river`` suites (reported, not used
       to claim validation)

Only the cases graded against an exact or manufactured solution support an
accuracy claim. Everything else is change control or agreement between
engines, and the dashboard reports the two separately. :doc:`concepts/grading`
explains why.

What is not built yet
=====================

* The ``epa_qa``, ``stability``, ``performance`` and ``quality`` suites are
  scaffolds: they run, print ``scaffold stub — not yet migrated; no cells
  produced`` and grade nothing. Stability and mass balance are graded today
  by the ``parity`` suite.
* The ``swmm-5.2.4`` engine is declared but always resolves to
  ``UNAVAILABLE``: its git-ref build is a stub that only looks for a cached
  executable.
* The ``pr`` tier selects no cases: no case lists ``pr`` under ``tiers`` in
  its metadata yet, so ``--tier pr`` on the ``parity`` suite records an
  ``ERROR`` cell instead of passing over zero models.
* The suites' ``report()`` step is a stub for ``parity`` and
  ``analytical/manufactured``; they return no report files.

.. toctree::
   :maxdepth: 2
   :hidden:

   get-started
   concepts/index
   suites
   corpus
   guides/index
   reference/index

Contents
========

* :doc:`get-started`: install, run the tests, point the harness at an
  engine, run a two-case sweep and build the dashboard.
* :doc:`concepts/index`: how a sweep flows through the harness, and how
  results are graded.
* :doc:`suites`: what each suite measures, what it needs and where it writes.
* :doc:`corpus`: the model library, its metadata, tags, tiers and provenance.
* :doc:`guides/index`: running sweeps, investigating a difference,
  contributing a model, the dashboard and badges, and continuous integration.
* :doc:`reference/index`: the command lines and the Python modules,
  generated from the code.

The repository also keeps working notes in its ``docs/`` folder:
`what runs when <https://github.com/HydroCouple/openswmm.engine.benchmarks/blob/dev/docs/CI_TRIGGERS.md>`__,
the `parity sweep triage <https://github.com/HydroCouple/openswmm.engine.benchmarks/blob/dev/docs/SWEEP_TRIAGE.md>`__
and the `pre-migration repository layout <https://github.com/HydroCouple/openswmm.engine.benchmarks/blob/dev/docs/LEGACY_REPO_OVERVIEW.md>`__.
