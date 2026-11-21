=======
Grading
=======

Every result is a *cell*: a JSON object with at least ``case``, ``solver``
(or ``pair`` for a comparison), ``verdict`` and ``reference_class``. A suite
returns its cells in a *scores envelope*. Two of the six cells from the sweep
in :doc:`../get-started`, a run cell and a pair cell:

.. code-block:: json

   {
     "suite": "parity",
     "engine_sha": "ce190b08-dirty",
     "timestamp": "2026-11-21T12:33:38",
     "cells": [
       {
         "case": "extran1",
         "solver": "openswmm-v6",
         "reference_class": "self_consistency",
         "verdict": "PASS",
         "wall": 0.08439458399880095,
         "continuity_err": 0.011,
         "runoff_err": null,
         "quality_err": null,
         "pct_not_converging": 3.68,
         "expected_high_continuity": false,
         "trimmed": false,
         "note": ""
       },
       {
         "case": "extran1",
         "pair": "swmm-5.3.0 vs openswmm-v6",
         "reference_class": "self_consistency",
         "verdict": "PASS",
         "gate": "fail",
         "max_rel": 0.0,
         "worst_var": null,
         "worst_element": null,
         "first_div_period": null,
         "total_cells": 3840,
         "total_over_tol": 0,
         "dialects": {
           "a": "swmm53",
           "b": "swmm53"
         },
         "note": ""
       }
     ]
   }

``total_cells`` counts compared values (element, variable and period), not
envelope cells. :func:`harness.scoring.save_cell` rewrites the envelope file after every
cell, replacing any earlier cell with the same ``(case, solver)``, so an
interrupted sweep leaves a usable partial envelope.

Verification is not regression
==============================

What a verdict means depends on what the case is graded against. Each case
declares a *reference class*, and the class decides what may be computed
from it and which badge its cells feed.

.. list-table::
   :header-rows: 1
   :widths: 20 30 30 20

   * - Reference class
     - Graded against
     - A failure means
     - Counts toward
   * - ``analytic``
     - A closed-form exact solution
     - The engine is wrong
     - verification
   * - ``manufactured``
     - A solution exact by construction
     - The engine is wrong
     - verification
   * - ``external_reference``
     - Another tool's results
     - The engines disagree
     - regression
   * - ``observed``
     - Laboratory or field measurements
     - The fit is poor
     - regression
   * - ``blessed_baseline``
     - A reviewed, pinned earlier output
     - The behavior changed
     - regression
   * - ``self_consistency``
     - Nothing external: invariants and engine-to-engine parity
     - The engines differ
     - regression

Only ``analytic`` and ``manufactured`` are ground truth. Error norms and
convergence order are meaningful for those alone
(:func:`harness.scoring.check_accuracy_allowed` refuses the rest), and only
their cells count toward the ``verification`` badge. Most of the corpus is
``self_consistency``, so a corpus-wide pass is a regression result, not an
accuracy claim.

Verdicts
========

.. list-table::
   :header-rows: 1
   :widths: 22 60 18

   * - Verdict
     - Meaning
     - Gates CI
   * - ``PASS`` / ``FAIL``
     - Within, or outside, the tolerance for the reference.
     - ``FAIL``
   * - ``BASELINE-PASS`` / ``BASELINE-FAIL``
     - Graded against a pinned baseline; the parity suite also uses
       ``BASELINE-PASS`` for a difference under a ``report`` gate.
     - ``BASELINE-FAIL``
   * - ``XFAIL``
     - A documented expected failure that still fails.
     - no
   * - ``XPASS``
     - A documented expected failure that now passes: someone has to look.
     - yes
   * - ``ERROR``
     - Nonzero exit, missing or unreadable output, an inconsistent
       comparison, or a harness error.
     - yes
   * - ``SKIP``
     - Not run on purpose (skip list, runtime limit, not applicable).
     - no
   * - ``UNAVAILABLE``
     - The engine or input is not present in this environment.
     - no

:func:`harness.scoring.exit_code` returns 1 when any cell has a gating
verdict (``FAIL``, ``BASELINE-FAIL``, ``ERROR``, ``XPASS``). ``UNAVAILABLE``
never gates, so a machine without every registered engine does not fail.

``harness.scoring.DEFAULT_GATE`` records the intended gate per reference
class. No suite reads it today: the parity suite takes its gate from the
comparison pair in ``engines.yaml``, or from ``tolerances.gate`` in the
case's metadata.

How the parity suite grades
===========================

Run cells
---------

One per case and engine. ``PASS`` when the run succeeded (exit status 0, a
readable ``.out``, no ``ERROR`` line in the report), ``ERROR`` when it ran
and failed, ``UNAVAILABLE`` when the executable could not be launched. An
``expected_failures`` entry with a ``report_error`` text turns a matching
input rejection into ``XFAIL``, and a run that succeeds despite that entry
into ``XPASS``.

The report figures ride on the run cell but do not change its verdict:
``continuity_err`` (routing continuity, percent), ``runoff_err``,
``quality_err`` (worst pollutant), ``pct_not_converging`` and ``wall``. The
``continuity_warn_pct`` and ``continuity_fail_pct`` fields in the metadata
schema are not read by any code; mass balance and stability are graded only
by the badges below.

Pair cells
----------

One per case and active comparison, from
:func:`harness.compare.compare_full`. Every subcatchment, node, link and
system variable that both files carry, pollutants included, is compared at
every reporting period, matched by name. A value passes when
``|a - b| <= atol + rtol * |a|``, with the pair's tolerances or the case's
``tolerances`` override. Two NaNs,
or two equal infinities, agree; any other non-finite pair fails. The verdict
is ``PASS`` when every value passes, ``FAIL`` otherwise, and ``ERROR`` when
the files are inconsistent: different element ids, different period counts,
a binary error code, no reporting periods, or different output dialects.

Then the gate applies: a ``FAIL`` under a ``report`` gate becomes
``BASELINE-PASS``, and an ``expected_failures`` entry without
``report_error`` turns the result into ``XFAIL``, or ``XPASS`` if it passed.
The cell records the worst offender (variable, element, first period over
tolerance, largest relative difference) and the cell counts.

.. note::

   Two behaviors to know before a second comparison resolves:

   * A dialect difference (``swmm52`` against ``swmm53``) is recorded as a
     fault, so that comparison grades ``ERROR`` even though the shared
     variables are still compared. The declared ``swmm-5.2.4`` against
     ``swmm-5.3.0`` pair is such a comparison.
   * Pair cells have no ``solver``, so they share the key ``(case, None)``
     in :func:`~harness.scoring.save_cell`. With two active comparisons, the
     second pair cell replaces the first for each case. Today only one
     comparison resolves, so this does not arise yet.

:func:`harness.compare.compare` is a stricter, separate check used from the
command line: link flow, link depth and node depth must be bit-identical in
float32, the other variables within 1.5 float32 units in the last place, and
it also reports raw byte equality of the results section.

.. _grading-badges:

Badges
======

:func:`harness.scoring.badges` turns envelopes into shields.io endpoint
files (``{"schemaVersion": 1, "label", "message", "color"}``), one per badge:

.. list-table::
   :header-rows: 1
   :widths: 16 34 50

   * - Badge
     - Cells counted
     - Message and color
   * - ``verification``
     - Reference class ``analytic`` or ``manufactured``
     - ``passed/checked checked``; ``SKIP`` and ``UNAVAILABLE`` cells are left
       out of the ratio and disclosed as ``· n unchecked``. Red if any
       checked cell failed, yellow if all passed but some are unchecked,
       green otherwise, gray if none was checked.
   * - ``regression``
     - Every other cell
     - ``passing`` (green) or ``n failing`` (red), counting gating verdicts.
   * - ``parity``
     - Cells with ``max_rel`` (pair cells)
     - ``max rel`` of the worst cell (green), or ``fail`` (red) if any is
       gating.
   * - ``mass-balance``
     - Cells with ``continuity_err`` (run cells)
     - ``worst x.xx%`` by absolute value: green up to 1 %, yellow up to 5 %,
       red above. Cases tagged ``expected_high_continuity`` are left out and
       disclosed as ``· n by design``.
   * - ``stability``
     - Cells with ``pct_not_converging`` (run cells)
     - Share of cells at or below 1.0 % of steps not converging: green from
       99 %, yellow from 90 %, red below.
   * - ``models``
     - None; the corpus size
     - Written only by the dashboard build.
   * - ``uk-2d-coverage``, ``uk-river-coverage``
     - The suites' ``coverage`` block
     - ``executed/requested requested · validation pending``; yellow when
       anything executed, gray otherwise.
   * - ``status``
     - Written when there are no cells at all
     - ``no results`` (red).

For example, the two-case sweep in :doc:`../get-started`, with the
manufactured suite, gives:

.. code-block:: text

   parity         max rel 0.0e+00              brightgreen
   regression     passing                      brightgreen
   mass balance   worst 0.01%                  brightgreen
   stability      0% stable                    red
   verification   6/6 checked · 11 unchecked   yellow
   models         1,419                        blue

The stability badge is red because EXTRAN example 1 reports 3.68 % of
routing steps not converging and ``test1`` 2.5 %, on both engines, above the
1.0 % line. Both models pass parity and conserve mass; the badge measures
convergence only.
