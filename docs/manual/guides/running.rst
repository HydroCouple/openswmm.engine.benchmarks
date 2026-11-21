==============
Running sweeps
==============

``run_regression.py`` runs one suite or all of them, prints each suite's
verdict counts, and can write a markdown summary and badge files. Point it at
engines first (:ref:`first-engine`).

.. code-block:: sh

   python run_regression.py --suite parity --tier nightly --only extran1,test1 \
       --summary summary.md --badges badges/

``--summary`` appends the markdown job summary to the file (CI passes
``$GITHUB_STEP_SUMMARY``); ``--badges`` writes one shields.io endpoint file
per badge. ``--report-only`` skips the sweeps and calls each suite's
``report()``. The exit status is 1 when any cell has a gating verdict, 2 for
an unknown suite name.

Arguments go to every suite
===========================

Every option ``run_regression.py`` does not define is passed to each
selected suite's ``run()`` and ``report()``, and ``--max-wall`` is passed on
as well. Most suites ignore options they do not know, but ``coupling``,
``uk_2d`` and ``uk_river`` reject them. ``coupling`` has no ``--tier``, and it
is the first suite in the list, so:

.. code-block:: console

   $ python run_regression.py --suite all --tier nightly --max-wall 300
   === suite: coupling ===
   usage: run_regression.py [-h] [--native-bin NATIVE_BIN] [--library LIBRARY]
                            [--output-dir OUTPUT_DIR] [--skip-unsteady]
                            [--max-wall MAX_WALL]
   run_regression.py: error: unrecognized arguments: --tier nightly

and no other suite runs. Run suites one at a time, with the options each one
takes.

The parity sweep
================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Option
     - Effect
   * - ``--tier pr|nightly``
     - Manifest to use (default ``pr``, which selects no cases yet).
   * - ``--only id1,id2``
     - Run only these case ids from the tier.
   * - ``--engines id1,id2``
     - Resolve only these registry engines; the rest are ``UNAVAILABLE``.
   * - ``--keep-out fail|all|none``
     - Keep a case's run folder (seeded inputs, ``.rpt``, ``.out``) only when
       something failed (default), always, or never.
   * - ``--retain-budget-gib N``
     - Stop keeping run folders past N GiB (default 2) and say so once.
   * - ``--no-skip-list``
     - Run the cases in ``manifests/skip_list.yaml`` too.
   * - ``--max-wall SECONDS``
     - Apply the CI runtime gate (below).

The envelope is ``results/parity/scores_<tier>.json`` and run folders are
``results/parity/<case>/<engine>/``. Each run starts a new envelope, so it
replaces the file left by the previous run of the same tier; a run with
``--only`` leaves only those cases in it. Each case is summarized into its
cells before its folder is deleted, so ``--keep-out none`` loses detail for
inspection, never a verdict.

The SWASHES and transitions suites work differently: they add to their
existing envelope, and when a cell's generated deck is unchanged and its
``model.out`` is still in the suite's ``runs/`` folder they grade that
output again without running the engine. Pass ``--force`` after changing the
engine, or the cells are graded on the previous engine's output.

Other suites
============

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Suite
     - Options
   * - ``analytical/swashes``, ``analytical/transitions``
     - ``--cases <glob>``, ``--solvers a,b``, ``--force``; SWASHES also
       ``--max-wall``. Engines come from the registry.
   * - ``analytical/manufactured``
     - ``--only a,b``, ``--regen``. No engine.
   * - ``analytical/hydraulic_jumps``
     - ``--exe``, ``--output-dir``, ``--max-wall``, ``--build-provenance``.
   * - ``analytical/momentum2d``
     - ``--exe``, ``--output-dir``.
   * - ``quality/reactions``
     - ``--exe``.
   * - ``coupling``
     - ``--native-bin``, ``--library``, ``--output-dir``, ``--skip-unsteady``,
       ``--max-wall``.
   * - ``uk_2d``
     - ``--tier``, ``--only``, ``--exe``, ``--output-dir``, ``--max-wall``,
       ``--require-complete``, ``--require-regression``,
       ``--require-observed``, ``--retain-h5``, ``--build-provenance``.
   * - ``uk_river``
     - ``--tier``, ``--only``, ``--exe``, ``--output-dir``, ``--max-wall``,
       ``--require-complete``, ``--require-regression``,
       ``--build-provenance``.

Where ``--exe`` is offered it defaults to the ``openswmm-v6`` executable
from the registry. A single SWASHES cell, for example:

.. code-block:: console

   $ python -m suites.analytical.swashes.suite --cases 'bump-subcritical' --solvers 1d-dynwave,1d-fv
   bump-subcritical         1d-dynwave         FAIL           l1_h=2.051 > 0.02
   bump-subcritical         1d-fv              PASS
   [swashes] PASS:1 FAIL:1

The ``1d-dynwave`` result matches the committed
:repo:`suites/analytical/swashes/SWASHES_REPORT.md`, where that case fails for
every implicit dynamic-wave configuration and passes for ``1d-fv`` and
``2d-explicit``. The command exits 1 because a ``FAIL`` gates.

.. _runtime-gate:

The CI runtime gate
===================

Long models are a local concern. Every workflow that sweeps passes
``--max-wall 300``; locally it is unset and everything runs. With it set:

* A case whose recorded wall time in :repo:`harness/runtimes.yaml` exceeds the
  limit gets a ``SKIP`` cell and a warning (``::warning::`` in Actions). The
  ledger holds measured times only (the slowest engine, from local sweeps);
  a case with no entry runs, bounded by its timeout.
* A case with ``ci_runtime`` in its metadata runs instead on a shortened
  simulated period (``duration_h`` hours from the start), applied to the
  seeded copy only. The cell is marked ``trimmed`` and its note says so.

``python -m harness.runtime`` lists what CI trims and skips at a threshold:

.. code-block:: console

   $ python -m harness.runtime
   threshold: --max-wall 300s

   trimmed for CI (8) — these RUN, on a shortened period:
     parity/1218-nodes: 600s at full period -> 24 h
     parity/14600-nodes: 600s at full period -> 48 h
     parity/1465-nodes: 324s at full period -> 32 h
     parity/3000-nodemodel: 516s at full period -> 72 h
     parity/4190-nodes: 328s at full period -> 6 h
     parity/5120-nodes: 452s at full period -> 12 h
     parity/5500-nodes: 311s at full period -> 9 h
     parity/5920-nodes: 460s at full period -> 6 h
   ...

After a long local sweep, merge its wall times into the ledger (cases under
60 s are not recorded, and this rewrites the tracked ``harness/runtimes.yaml``):

.. code-block:: sh

   python -m harness.runtime --record results/parity/scores_nightly.json
