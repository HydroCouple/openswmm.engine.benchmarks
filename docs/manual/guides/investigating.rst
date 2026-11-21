===========================
Investigating a difference
===========================

A failing pair cell names the worst variable, the element and the first
period over tolerance. To look further, keep the run folders and compare the
two outputs directly.

Keep the outputs
================

.. code-block:: sh

   python run_regression.py --suite parity --tier nightly --only extran1 --keep-out all

``results/parity/extran1/swmm-5.3.0/`` and
``results/parity/extran1/openswmm-v6/`` then hold each engine's seeded
model, ``extran1.rpt`` and ``extran1.out``. Without ``--keep-out all`` only
the folders of failed cases are kept.

Compare two outputs
===================

.. code-block:: sh

   python -m harness.compare results/parity/extran1/swmm-5.3.0/extran1.out \
                             results/parity/extran1/openswmm-v6/extran1.out

prints the JSON result of :func:`harness.compare.compare`, the strict ladder:
``verdict`` is ``PARITY`` (link flow, link depth and node depth bit-identical
in float32, the other link and node variables within 1.5 float32 units in the
last place), ``vol-diff`` (only velocity or volume differ), ``near`` (largest
difference under 1e-3) or ``DIVERGE``. It also reports ``strict_identical``
(every compared value equal), ``bytes_results_identical`` (the raw results
section), ``first_div`` and ``worst`` (where and in which variable the files
first and most differ), and per-variable statistics under ``per_var``. For
``extran1`` the two engines give ``PARITY``, with all 2,112 compared values
identical over 32 reporting periods and identical result bytes.

This check covers link and node hydraulics only. The parity suite's
:func:`harness.compare.compare_full` also covers subcatchments, system
variables and pollutants, with tolerances.

Follow one element
==================

.. code-block:: console

   $ python -m harness.compare drill results/parity/extran1/swmm-5.3.0/extran1.out results/parity/extran1/openswmm-v6/extran1.out link FLOW 8040 5
   # link.FLOW eid=8040  (legacy vs refactored)
   period           legacy       refactored       abs_diff
        0       39.2038574       39.2038574   0.000000e+00
        1       45.0107346       45.0107346   0.000000e+00
        2       44.9999733       44.9999733   0.000000e+00
        3               45               45   0.000000e+00
        4               45               45   0.000000e+00

Leave out the element id to follow the one with the largest difference.
Differences above 1e-9 are marked ``<==``.

Compare the reports
===================

.. code-block:: console

   $ python -m tools.compare_continuity results/parity/extran1/swmm-5.3.0/extran1.rpt results/parity/extran1/openswmm-v6/extran1.rpt
   Continuity tables match at printed precision.

It compares the continuity tables row by row, keeping pollutant columns
apart and reporting NaN entries rather than hiding them.

Triage a whole sweep
====================

Group a sweep's non-passing cells by cause rather than by case:

.. code-block:: console

   $ python -m tools.triage_sweep results/parity/scores_nightly.json
   3 cells over 1 cases  (results/parity/scores_nightly.json)

   pass                              3 cells  (100.0%)
       extran1
       extran1
       extran1

It reads the envelope of the last ``nightly`` run, here the single-case run
above. ``--markdown`` prints the same as markdown tables. The causes found in the
first full sweep, and what was done about each, are recorded in
:repo:`docs/SWEEP_TRIAGE.md`. To check that every skip-listed case still
fails for the stated reason, run ``python -m tools.confirm_skips``.
