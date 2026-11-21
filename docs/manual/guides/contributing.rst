=====================
Contributing a model
=====================

Models that break engines, or that once exposed a difference between two
engines, are the most useful contributions. The rules for what a submission
needs are in :repo:`CONTRIBUTING.md`; this page walks through the commands.

Create the case
===============

.. code-block:: sh

   mkdir -p corpus/contributed
   cp -r corpus/_template corpus/contributed/my-case-id
   cp /path/to/model.inp corpus/contributed/my-case-id/model.inp

``corpus/contributed/`` does not exist until the first contribution, so the
``mkdir`` is needed. Then edit the two YAML files the template provides:

* ``metadata.yaml``: set ``id`` to the folder name, a one-line ``title``,
  every tag from :repo:`harness/schemas/tags.yaml` that applies, ``units``
  and ``routing``. Leave ``tiers: [nightly]``; the ``pr`` tier is by
  promotion. Declare the reference class honestly: a real network with no
  external reference is ``self_consistency``.
* ``provenance.yaml``: where the model came from, a license (an SPDX id,
  ``public-domain``, or ``unverified`` if you cannot confirm one) and who
  contributed it.

Put every file the model reads in the same folder and refer to it by bare
file name; absolute paths only work on the machine that wrote them.

Validate it
===========

.. code-block:: sh

   python -m harness.validate "$PWD/corpus/contributed/my-case-id"

Use the absolute path (see :doc:`../corpus`). The validator reports errors
(missing fields, unknown tags, files that do not exist) and advisory
warnings (an unverified license, absolute paths, coordinates that look like
real latitude and longitude).

Then run it through both engines:

.. code-block:: sh

   python run_regression.py --suite parity --tier nightly --only my-case-id --keep-out all

Anonymize it, if needed
=======================

:mod:`harness.anonymize` removes the identifying content it knows how to
find. It cannot know that an element name refers to a real street, or that
a network's shape is recognizable, so review its output yourself. Run it on
a copy outside ``corpus/``: ``--verify`` runs both models with the
``openswmm-v6`` engine and writes those runs to ``_anon_verify/`` next to the
input model.

.. code-block:: console

   $ mkdir -p /tmp/anon
   $ cp corpus/epa/diversion-weir-network/model.inp /tmp/anon/model.inp
   $ python -m harness.anonymize /tmp/anon/model.inp -o /tmp/anon/anon.inp --map /tmp/anon/ids.json --verify
   wrote /tmp/anon/anon.inp
     renamed 18 identifiers
     translated coordinates by (-5704965.2224, -2123212.4468)
     scrubbed 20 title/tag/comment/path item(s)
     id map -> /tmp/anon/ids.json  (keep this private; it reverses the rename)
     verify: results byte-identical — anonymization did not change physics

   No tool can guarantee anonymity. Review the output yourself before sharing it.

The default transforms are ``rename-ids`` (``JCT-10`` becomes ``N1``,
``CDT-11`` becomes ``L1``...), ``coords-offset`` (move the network's
lower-left corner to the origin, keeping shape and scale), ``scrub-text``
(clear the title, tags and comments, blank rain gage station ids, reduce
absolute paths to file names) and ``relocate-data`` (rewrite external file
references to bare file names). ``coords-strip`` removes
the map sections instead of offsetting them. Identifiers that read as numbers
(EXTRAN's ``80408``) are not renamed. Keep the id map private, and record the
transforms under ``anonymized`` in ``provenance.yaml``.

``--verify`` exits 1 if the results differ and 3 if it could not check
(no engine, or a model that did not run).

Submit it
=========

Open a pull request with the model-submission template, or, without git, a
`model submission issue <https://github.com/HydroCouple/openswmm.engine.benchmarks/issues/new?template=model-submission.yml>`__
with the file attached. On a pull request the Validate workflow runs the
harness tests on Linux, Windows and macOS and validates the cases the branch
changed. When the branch changed cases, it also builds the engines, runs the
first 40 changed cases through their owning suites (each bounded by
``--max-wall 300``) and comments the results on the pull request.
