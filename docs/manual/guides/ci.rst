======================
Continuous integration
======================

The workflows in ``.github/workflows/``, what starts them and what they run.
:repo:`docs/CI_TRIGGERS.md` describes how a push to ``openswmm.engine``
reaches this repository and what that path does not do (it does not gate an
engine merge).

.. list-table::
   :header-rows: 1
   :widths: 20 25 55

   * - Workflow
     - Trigger
     - What it does
   * - ``validate.yml``
     - Pull request or push to ``dev`` or ``main``; manual
     - Harness tests on Linux, Windows and macOS (Python 3.12, no engine);
       ``harness.validate --changed`` and a harness self-check; for branches
       that changed cases, builds the engines, runs the first 40 changed
       cases with ``--max-wall 300`` and comments the results on the pull
       request.
   * - ``nightly.yml``
     - 07:00 UTC daily; manual (``tier``, ``engine_ref``)
     - Five jobs on each of Linux and Windows, each building the engines from
       ``engine_ref`` (default ``swmm6_rel``): four run
       ``run_regression.py --suite parity --shard K/4`` and one runs
       ``--suite all --exclude parity``, all with ``--tier nightly
       --max-wall 300 --summary --badges``. Each uploads ``results/`` and
       ``badges/`` as ``results-<os>-<part>``, fails if its sweep failed, and
       the run then calls ``publish.yml``.
   * - ``on_engine_push.yml``
     - ``repository_dispatch`` of type ``engine-push`` from the engine
       repository
     - Refuses a payload without a commit SHA, builds that commit, runs the
       sweep at ``client_payload.tier`` (default ``nightly``), uploads
       ``results-engine-<sha>``, gates, then calls ``publish.yml``.
   * - ``publish.yml``
     - Called by the two workflows above; manual
     - Renders the dashboard from the run's artifacts and deploys it to
       GitHub Pages (:doc:`dashboard`).
   * - ``uk_2d.yml``
     - Pull requests touching the UK 2D suite or cases; Sundays 08:30 UTC;
       manual
     - The UK 2D tests, the ``pr`` pilot with ``--require-complete
       --require-regression``, the analytical supplement, and on schedule a
       ``nightly``-tier evidence sweep.
   * - ``uk_river.yml``
     - Pull requests touching the UK river suite or cases; Sundays 09:15 UTC;
       manual
     - The UK river tests, the ``pr`` pilot, and outside pull requests the
       full available-evidence sweep.
   * - ``documentation.yml``
     - Push or pull request to ``dev`` or ``main`` touching the manual or the
       Python sources it documents; manual
     - Builds this manual with warnings as errors and uploads it as the
       ``manual`` artifact. It does not deploy.

Engines in CI
=============

The composite action :repo:`.github/actions/build-engine/action.yml` checks
out the engine at the requested ref (default ``swmm6_rel``, the branch the
engine is developed on), builds only the ``openswmm`` and
``openswmm_legacy`` targets (tests, GPU plugin and HYPRE off; GeoPackage, 2D
and 2D HDF5 output on), and exports ``OPENSWMM_ENGINE_DIR`` and
``OPENSWMM_BUILD_DIR`` for the steps that follow.

Runtime budget
==============

Every sweeping workflow passes ``--max-wall``: 300 s in Validate, Nightly,
Engine push and the UK 2D pilot; 600 s for the UK river runs and the
scheduled UK 2D sweep; 3600 s for the manual UK 2D weekly qualification. A
case measured to cost more is skipped there with a warning, and cases with a
``ci_runtime`` trim run on a shorter simulated period. See
:ref:`runtime-gate`. Each Nightly sweep job is limited to 330 minutes; one
job for the whole parity corpus did not fit (it reached 889 of 1,402 cases),
which is why parity runs as four ``--shard`` jobs. A shard takes every fourth
case of the selection, so the large networks, which sort together, spread
across all four.

Things to know
==============

* ``run_regression.py`` forwards every option it does not recognize to every
  suite it runs, so a suite must ignore options meant for another; one that
  rejects them ends the run there.
* ``on_engine_push.yml`` still runs the whole sweep in one job, so it does not
  fit the time limit either.
* The ``engines`` input of a manual Nightly run is declared but not passed to
  the sweep.
* The sweep steps use ``continue-on-error`` so the artifacts upload and the
  dashboard publishes when a sweep fails; a later step fails the job, so the
  workflow status still reflects the sweep.
