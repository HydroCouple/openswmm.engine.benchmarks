======================
Command-line reference
======================

Every command runs from the repository root. The help text below is produced
by running the command with ``--help`` while the manual is built.

Runner
======

``run_regression.py``
---------------------

The single entry point CI and local sweeps use. Options it does not recognize
are forwarded to every selected suite, which is how ``--tier``, ``--only`` and
``--engines`` reach the parity suite.

.. cli-help:: run_regression.py

Harness modules
===============

``python -m harness.engines``
-----------------------------

Takes no options. It resolves every engine in ``harness/engines.yaml``, prints
one line per engine (``RESOLVED`` or ``UNAVAILABLE``, with the executable path
or the reason), then lists the comparisons whose two engines both resolved.
See :ref:`engine-resolution`.

``python -m harness.corpus``
----------------------------

.. cli-help:: -m harness.corpus

``python -m harness.validate``
------------------------------

.. cli-help:: -m harness.validate

.. note::

   Pass case directories as absolute paths, for example
   ``"$PWD/corpus/owa-extran/extran1"``. With a relative path the checks run,
   but printing the result stops with ``ValueError`` (``relative_to`` the
   repository root). Running with no paths, or with ``--changed``, is not
   affected.

``python -m harness.runtime``
-----------------------------

.. cli-help:: -m harness.runtime

``python -m harness.report``
----------------------------

.. cli-help:: -m harness.report

``python -m harness.anonymize``
-------------------------------

.. cli-help:: -m harness.anonymize

``python -m harness.compare``
-----------------------------

Takes positional arguments only (no ``--help``):

* ``python -m harness.compare <a.out> <b.out>`` prints the JSON result of
  :func:`harness.compare.compare`, the float32 bit-parity ladder.
* ``python -m harness.compare drill <a.out> <b.out> <link|node> <VAR> [id] [limit]``
  prints one element's series from both files side by side. Without an id it
  picks the element with the largest difference; ``limit`` needs an id before
  it. ``VAR`` is ``FLOW``, ``DEPTH``, ``VELOCITY`` or ``VOLUME`` for links and
  ``DEPTH``, ``HEAD`` or ``VOLUME`` for nodes.

Suites
======

Suites with their own command line. The other suites document their options
in their READMEs (see :doc:`../suites`).

``python -m suites.parity.suite``
---------------------------------

.. cli-help:: -m suites.parity.suite

``python -m suites.analytical.manufactured.suite``
--------------------------------------------------

.. cli-help:: -m suites.analytical.manufactured.suite

Tools
=====

Run these as modules (``python -m tools.<name>``). Started as
``python tools/<name>.py``, the scripts that import ``harness`` without first
adding the repository root to ``sys.path`` (``triage_sweep`` and
``compare_continuity``) stop with ``ModuleNotFoundError: No module named 'harness'``.

``python -m tools.triage_sweep``
--------------------------------

.. cli-help:: -m tools.triage_sweep

``python -m tools.compare_continuity``
--------------------------------------

.. cli-help:: -m tools.compare_continuity

``python -m tools.changed_cases``
---------------------------------

.. cli-help:: -m tools.changed_cases

``python -m tools.smoke_cases``
-------------------------------

.. cli-help:: -m tools.smoke_cases

``python -m tools.confirm_skips``
---------------------------------

.. cli-help:: -m tools.confirm_skips

Corpus migration tools
----------------------

One-time tools that built the corpus from the pre-migration layout. Without
``--apply`` they only report.

.. cli-help:: -m tools.migrate_corpus

.. cli-help:: -m tools.cleanup_legacy

.. cli-help:: -m tools.repair_references
