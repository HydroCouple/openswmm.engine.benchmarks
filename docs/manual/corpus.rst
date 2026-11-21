======
Corpus
======

The corpus is the model library every engine is run against: 1,419 cases on
the ``dev`` branch in November 2026, in 25 collections. Each case is a folder
with the model, a description of what it is (``metadata.yaml``) and where it
came from (``provenance.yaml``).

Layout
======

.. code-block:: text

   corpus/
     _template/                 starting point for a new case
     <collection>/
       <case-id>/
         model.inp              the model (another name if metadata says so)
         metadata.yaml          what the case is: tags, units, tiers, reference class
         provenance.yaml        where it came from, and its license
         reference/             optional evidence or reference data
         *.dat, *.rff, ...      files the model reads, beside it

Collections are the source folders the models came from in the
pre-migration repository (``owa-extran`` was ``OWA_EXTRAN/``, ``epa`` was
``EPA/``), kept for traceability. A collection carries no meaning: suites and
tiers select cases by tag, never by path.

Files a model reads must be in its case folder. The parity suite copies the
folder's files (not its subfolders) into a fresh run folder and runs there,
so relative paths in ``[FILES]``, ``[RAINFALL]`` and ``[TIMESERIES]`` resolve
and ``corpus/`` is never written. The ``data_files`` metadata field is not
read by any code; in the migrated cases it lists those colocated files.
``data/`` keeps the shared forcing files from the original collections.

Metadata
========

``metadata.yaml`` for the EXTRAN manual's first example, as committed:

.. literalinclude:: ../../corpus/owa-extran/extran1/metadata.yaml
   :language: yaml

.. list-table::
   :header-rows: 1
   :widths: 20 80

   * - Field
     - Meaning
   * - ``id``
     - Case id, lowercase, matching the folder name. Required.
   * - ``title``
     - One line. Required.
   * - ``model``
     - Model file in the folder (default ``model.inp``).
   * - ``tags``
     - Non-empty list from ``harness/schemas/tags.yaml``. Required.
   * - ``units``
     - ``US`` or ``SI``. Required.
   * - ``routing``
     - ``DYNWAVE``, ``KINWAVE``, ``STEADY`` or ``FV``. 2D surface routing is a
       tag (``finite_volume_2d``), not a routing value.
   * - ``size_class``, ``runtime_class``
     - Estimates from model size (``XS`` to ``XL``; ``fast``, ``medium``,
       ``slow``). The CI runtime gate does not use them.
   * - ``tiers``
     - CI tiers that include the case: ``pr``, ``nightly``, ``weekly``
       (default ``[nightly]``).
   * - ``timeout_s``
     - Per-run timeout override.
   * - ``ci_runtime``
     - ``duration_h`` and ``reason``: a shorter simulated period used only
       under ``--max-wall`` (see :ref:`runtime-gate`).
   * - ``reference``
     - ``class`` (see :doc:`concepts/grading`), plus ``source``, ``files``,
       and ``blessed_by`` (engine, commit, reviewer, date) for a
       ``blessed_baseline``. Required.
   * - ``tolerances``
     - Per-case ``rtol``, ``atol`` and ``gate`` overriding the comparison
       pair's.
   * - ``expected_failures``
     - Known failures (``engine``, ``reason``, optional ``issue`` and
       ``report_error``), graded ``XFAIL``.
   * - ``notes``
     - Free text.

The schemas in ``harness/schemas/`` document these fields.
:mod:`harness.validate` enforces them in code: required fields, enumerated
values, known tags, reference files that exist and are relative, a complete
``blessed_by``, ``ci_runtime`` with a reason of at least ten characters, and
a model file that exists. It does not load the schemas as JSON Schema, so
some schema rules are not checked, among them unknown fields and ``id``
matching the folder name.

Tags
====

Tags are flat and a case carries every one that applies; the vocabulary in
:repo:`harness/schemas/tags.yaml` groups them into domain (``hydrology``,
``hydraulics``, ``quality``, ``lid``, ``2d``...), purpose (``regression``,
``analytical``, ``stability``, ``performance``, ``calibration``, the two UK
suite tags), features (routing method, link and node types, cross sections,
pollutant processes, ``surcharge``, ``flooding``...) and provenance
(``real_world``, ``synthetic``, ``textbook``, ``contributed``, converted
models). An unknown tag fails validation; adding one is a one-line change to
the vocabulary.

The migration derived tags from what each model contains (a non-empty
section, an option value, a cross-section type). The ``surcharge``,
``flooding`` and ``flow_instability`` tags come from the report that sat
beside the model, kept as ``reference/legacy.rpt`` in 663 cases. That report
is evidence for the tags, written by an unrecorded engine version; it is not
a grading reference.

Tag expressions use ``AND``, ``OR``, ``NOT`` and parentheses; adjacent tags
mean ``AND``:

.. code-block:: sh

   python -m harness.corpus "lid AND pollutants"
   python -m harness.corpus "(hydraulics OR hydrology) AND NOT long_term" --tier nightly
   python -m harness.corpus --census

Reference classes in the corpus
===============================

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - Class
     - Cases
     - Where
   * - ``self_consistency``
     - 1,405
     - Everything else
   * - ``analytic``
     - 7
     - ``uk-ea-river`` (W5-105 analytical profiles)
   * - ``observed``
     - 7
     - ``rubinato-2017`` (5), ``uk-ea-river`` (2)

The analytical suites keep their own cases under ``suites/analytical/*/cases/``
and ``suites/quality/reactions/``, outside the corpus.

Provenance and licenses
=======================

``provenance.yaml`` requires ``source``, ``license`` and ``contributed_by``,
and may add a citation, DOI, URL, contact, date, the original units, any
``modifications`` made to the model, and an ``anonymized`` record.

.. list-table::
   :header-rows: 1
   :widths: 25 15 60

   * - License
     - Cases
     - Collections
   * - ``public-domain``
     - 1,307
     - 19 of the 22 collections migrated from the original benchmark
       repository (all but ``simon-epa``, ``greenville`` and ``special``)
   * - ``unverified``
     - 106
     - ``simon-epa`` (85), ``uk-ea-river`` (10), ``uk-ea-2d`` (7),
       ``greenville`` (3), ``special`` (1)
   * - ``CC-BY-4.0``
     - 6
     - ``rubinato-2017``

The 1,396 migrated cases carry the provenance the migration could record:
the original path and ``contributed_by: unknown (pre-migration corpus)``.
The ``uk-ea-2d``, ``uk-ea-river`` and ``rubinato-2017`` collections were
added later from their published sources. A case marked ``unverified`` gets
a validator warning and is excluded from redistribution claims. Where a model
was edited to run anywhere (an absolute ``SAVE`` path rewritten to a bare
file name, a missing input copied beside it), the edit is recorded under
``modifications`` (78 cases).

Validate a case
===============

.. code-block:: console

   $ python -m harness.validate "$PWD/corpus/owa-extran/extran1"
   ok   corpus/owa-extran/extran1

   1 case(s): 1 ok, 0 failed, 0 warning(s)

Errors fail the run; warnings are advisory: an unverified license, an
absolute path in the model, or coordinates that look like real latitude and
longitude. Pass the case folder as an absolute path (a relative path stops
with ``ValueError`` when the result is printed). With no path the whole
corpus is validated, which reads every case and takes about a minute.
