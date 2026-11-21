============
Architecture
============

The repository is data plus a small Python harness. Models and their metadata
live in ``corpus/``; each suite in ``suites/`` decides which models or test
problems to run and how to grade them; ``harness/`` holds everything the
suites share; ``run_regression.py`` runs one or more suites and collects
their results.

Repository layout
=================

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Path
     - Contents
   * - ``harness/``
     - The shared modules (table below), the engine registry
       ``engines.yaml``, the runtime ledger ``runtimes.yaml``, and
       ``schemas/`` (case metadata and provenance schemas, tag vocabulary).
   * - ``suites/``
     - One folder per suite with a ``suite.py``; one level of nesting
       (``suites/analytical/swashes/``). ``_suite_template.py`` is the
       protocol template.
   * - ``corpus/``
     - The model library: ``corpus/<collection>/<case>/``. See
       :doc:`../corpus`.
   * - ``data/``
     - Shared forcing files (rainfall, temperature and other time series).
   * - ``legacy/``
     - Pre-migration source material kept for traceability (XPSWMM
       projects, per-model summaries).
   * - ``tools/``
     - Maintenance scripts: sweep triage, changed-case detection for pull
       requests, skip-list confirmation, and the one-time corpus migration.
   * - ``tests/``
     - The harness tests (no engine needed) and dated verification records
       under ``tests/verification/``.
   * - ``results/``, ``badges/``, ``site/build/``
     - Generated output. Git-ignored; CI keeps it as workflow artifacts and
       in the Pages deployment.
   * - ``plans/``, ``docs/``
     - Design documents and working notes. This manual is ``docs/manual/``.

How a sweep flows
=================

The ``parity`` suite is the main path through the harness. Other suites reuse
the same pieces (engine resolution, the runner, the readers, the envelope)
with their own case lists and grading.

.. mermaid::
   :caption: A parity sweep, from case selection to the published dashboard.
   :alt: Flowchart of a parity sweep through the harness

   flowchart TD
     corpus["corpus case folders<br/>model.inp, metadata.yaml"] --> select["corpus.select<br/>tag query and tier"]
     manifests["parity manifests<br/>tier and skip list"] --> select
     select --> seed["seed a run folder<br/>per case and engine"]
     registry["harness/engines.yaml"] --> run
     seed --> run["runner.run<br/>exe model.inp .rpt .out"]
     run --> rpt["rptparse.parse<br/>continuity, convergence"]
     run --> cmp["compare.compare_full<br/>each comparison pair"]
     rpt --> runcells["run cells"]
     cmp --> paircells["pair cells"]
     runcells --> env["scores envelope<br/>results/parity/"]
     paircells --> env
     env --> summary["job summary and badges<br/>run_regression.py"]
     env --> site["dashboard<br/>harness.report --site"]

Step by step, for each case the tier selects:

1. **Select.** ``suites/parity/manifests/tier_<tier>.yaml`` holds a tag
   expression (``select``) and a default ``timeout_s``. A case runs when it
   matches the expression *and* lists the tier under ``tiers`` in its
   metadata. Cases tagged ``uk_ea_2d`` or ``uk_ea_river`` are always removed
   (their own suites grade them), then ``--only`` narrows the list.
2. **Skip or bound.** A case in ``manifests/skip_list.yaml`` gets a ``SKIP``
   cell with its reason. With ``--max-wall``, a case whose measured runtime in
   ``harness/runtimes.yaml`` exceeds the limit is skipped the same way (see
   :ref:`runtime-gate`). If the estimated ``.out`` size would leave less than
   3 GiB free, the case is recorded as ``UNAVAILABLE``.
3. **Seed.** The case's files (not its subfolders, ``metadata.yaml``,
   ``provenance.yaml`` or ``README.md``) are copied into
   ``results/parity/<case>/<engine>/``, so the model's relative file
   references resolve and ``corpus/`` is never written to.
4. **Run.** Each resolved engine runs ``exe model.inp <case>.rpt <case>.out``
   in that folder with the case's timeout. A run counts as successful only
   with exit status 0, a readable ``.out`` with at least one reporting period
   and no error code, and no ``ERROR`` line in the report.
5. **Grade.** The report is scraped for continuity and convergence figures,
   which ride on the run cell. Each comparison pair whose two engines both
   produced output is diffed with :func:`harness.compare.compare_full`.
6. **Record.** Every cell is written to the envelope as soon as it exists,
   then the case's run folder is deleted unless something failed
   (``--keep-out``).

A failure inside one case (an unreadable file, an unexpected exception)
becomes an ``ERROR`` cell for that case and the sweep continues.

Harness modules
===============

.. list-table::
   :header-rows: 1
   :widths: 22 78

   * - Module
     - Role
   * - :mod:`harness.engines`
     - Loads ``engines.yaml``, resolves each engine to an executable, builds
       the subprocess environment, reads the engine commit.
   * - :mod:`harness.runner`
     - Runs one engine on one model with a timeout; returns exit status,
       wall time, stdout and stderr.
   * - :mod:`harness.corpus`
     - Loads case metadata and provenance; evaluates tag expressions.
   * - :mod:`harness.validate`
     - Checks case metadata, provenance, tags and referenced files.
   * - :mod:`harness.readers`
     - Reads the SWMM binary ``.out`` (numpy only) and the engine's 2D HDF5
       output (h5py, imported on use).
   * - :mod:`harness.rptparse`
     - Scrapes the text ``.rpt``: continuity tables, convergence statistics,
       surcharge and flooding table sizes, LID performance, error lines.
   * - :mod:`harness.compare`
     - Element-by-element, period-by-period comparison of two ``.out`` files.
   * - :mod:`harness.scoring`
     - Verdicts, reference classes, the envelope, the exit code and the
       badges.
   * - :mod:`harness.runtime`
     - The measured-runtime ledger, the CI skip rule and the CI-only
       simulation trim.
   * - :mod:`harness.suites`
     - Suite discovery.
   * - :mod:`harness.report`, :mod:`harness.site`
     - The markdown job summary, badge files and the static dashboard.
   * - :mod:`harness.anonymize`
     - Best-effort anonymization of a model before it is contributed.

Suites
======

A suite is a folder ``suites/<name>/`` with a ``suite.py`` that defines two
functions:

``run(argv) -> dict | None``
   Runs the sweep and returns its scores envelope.

``report(argv) -> list[Path]``
   Regenerates the suite's report files and returns their paths.

:func:`harness.suites.list_suites` finds suites by globbing
``suites/*/suite.py`` and ``suites/*/*/suite.py``, without importing them; a
nested suite is named ``parent/child``. ``run_regression.py`` imports only
the suites it runs, calls ``run`` then ``report`` for each, and passes every
argument it does not recognize to both. It exits 1 if any envelope holds a
gating verdict, 0 otherwise, and 2 for an unknown suite name.

.. _engine-resolution:

Engines
=======

Engines are declared in ``harness/engines.yaml``; adding one is a stanza, not
code. Each entry has a ``source`` of one of three types:

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Type
     - Resolution
   * - ``in-tree``
     - The environment variable named by ``env`` if it is set; otherwise
       ``target`` under ``$OPENSWMM_BUILD_DIR/bin/Release``,
       ``$OPENSWMM_BUILD_DIR/bin`` or ``$OPENSWMM_BUILD_DIR`` (with ``.exe``
       on Windows).
   * - ``git-ref``
     - A cached executable at
       ``$OPENSWMM_BENCH_CACHE/<ref>-<os>/<target>``. Building from the ref
       is not implemented; without the cached file the engine is
       ``UNAVAILABLE``.
   * - ``external-binary``
     - The variable named by ``env``, else ``path``, else ``command`` looked
       up on ``PATH``.

An engine whose executable is missing or not executable is ``UNAVAILABLE``;
resolution never raises. The registry declares three engines and two
comparisons:

.. list-table::
   :header-rows: 1
   :widths: 18 30 52

   * - Engine
     - Source
     - Notes
   * - ``openswmm-v6``
     - in-tree ``openswmm``, ``OPENSWMM_EXE``
     - The engine under test. Output dialect ``swmm53``.
   * - ``swmm-5.3.0``
     - in-tree ``openswmm-legacy``, ``OPENSWMM_LEGACY_EXE``
     - The legacy EPA SWMM 5.3 engine built from the same tree.
   * - ``swmm-5.2.4``
     - git-ref ``build-v5.2.4``
     - Historical baseline; ``UNAVAILABLE`` until a cached build exists.
       Output dialect ``swmm52``.

.. list-table::
   :header-rows: 1
   :widths: 30 30 40

   * - Comparison
     - Tolerances
     - Gate
   * - ``swmm-5.3.0`` vs ``openswmm-v6``
     - rtol 1e-9, atol 1e-12
     - ``fail``: a difference fails the job.
   * - ``swmm-5.2.4`` vs ``swmm-5.3.0``
     - rtol 1e-4, atol 1e-6
     - ``report``: differences are recorded, not gated.

A comparison involving an ``external-binary`` engine is always downgraded to
``report``, and such an engine is treated as not ``comparable_build`` unless
its entry says otherwise.

Environment
-----------

.. list-table::
   :header-rows: 1
   :widths: 28 72

   * - Variable
     - Meaning (default)
   * - ``OPENSWMM_ENGINE_DIR``
     - Engine checkout; its git commit is stamped on results
       (``../openswmm.engine``).
   * - ``OPENSWMM_BUILD_DIR``
     - Engine build tree, searched for in-tree engines and prepended to the
       library path (``$OPENSWMM_ENGINE_DIR/build/darwin-parity``).
   * - ``OPENSWMM_EXE``, ``OPENSWMM_LEGACY_EXE``
     - Explicit paths to the two in-tree engines.
   * - ``OPENSWMM_BENCH_CACHE``
     - Cache for ``git-ref`` engines (``.engine-cache/`` in this
       repository).

Every engine run gets ``OMP_NUM_THREADS=1``, ``OPENSWMM_2D_BACKEND=cpu``
unless already set, and the build tree's library folders prepended to
``DYLD_LIBRARY_PATH`` and ``LD_LIBRARY_PATH``.

The engine identifier on every envelope is the short commit of
``OPENSWMM_ENGINE_DIR``, with ``-dirty`` appended when that checkout has
modified tracked files: results from an uncommitted build are not
attributed to a commit that cannot reproduce them.
