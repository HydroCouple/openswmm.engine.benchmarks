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
     - 07:00 UTC daily; manual (``tier``, ``engine_ref``, ``description``)
     - Five jobs on each of Linux and Windows, each building the engines from
       ``engine_ref`` (default ``swmm6_rel``): four run
       ``run_regression.py --suite parity --shard K/4`` and one runs
       ``--suite all --exclude parity``, all with ``--tier nightly
       --max-wall 300 --summary --badges``. Each uploads its evidence
       (``results/`` and ``badges/``) as ``results-<os>-<part>``, records
       that artifact's URL in the run manifest, uploads the manifest, the
       envelopes and the badges as ``scores-<os>-<part>``, and fails if its
       sweep failed. The run then calls ``publish.yml`` with its run id.
   * - ``on_engine_push.yml``
     - ``repository_dispatch`` of type ``engine-push`` from the engine
       repository
     - Refuses a payload without a commit SHA, builds that commit, runs the
       sweep at ``client_payload.tier`` (default ``nightly``), uploads
       ``results-engine-<sha>``, gates, then calls ``publish.yml``.
   * - ``publish.yml``
     - Called by the two workflows above with their run id; manual (``run_id``,
       default the last completed Nightly)
     - Downloads that run's ``scores-*`` artifacts, appends the run to the
       ``benchmark-data`` branch, renders the dashboard, builds this manual
       into its ``docs/`` folder, and deploys both to GitHub Pages
       (:doc:`dashboard`).
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
and 2D HDF5 output on), and exports ``OPENSWMM_ENGINE_DIR``,
``OPENSWMM_BUILD_DIR`` and ``OPENSWMM_ENGINE_REF`` for the steps that follow.
On Windows it copies the vcpkg runtime DLLs beside the executables. Its last
step resolves both engines and runs each with ``--version``, so an engine
that cannot start fails the build step instead of every case.

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
* The sweep step sets ``BENCH_JOB_NAME``, ``BENCH_JOB_ID`` (the job's check
  run, which makes the job-log link), ``BENCH_PART``, ``BENCH_PLATFORM_ALIAS``
  and ``BENCH_RUN_DESCRIPTION`` for the run manifest.
* Publish's build job has ``contents: write``, and the workflows that call
  it grant it, so it can push the run's record to ``benchmark-data``. That
  branch holds only ``runs/<run id>.json``; nothing else writes to it.
* Inside a reusable workflow ``github.event_name`` is the caller's event,
  which is why publish takes the run id as an input rather than guessing it.
* The publish job runs under ``always()`` so that a run whose sweeps failed
  or hit their time limit still refreshes the dashboard. A plain cancel runs
  ``always()`` jobs too, so a canceled Nightly deploys whatever its jobs had
  uploaded. To stop a run without publishing, force-cancel it:
  ``gh api -X POST repos/HydroCouple/openswmm.engine.benchmarks/actions/runs/<id>/force-cancel``.
