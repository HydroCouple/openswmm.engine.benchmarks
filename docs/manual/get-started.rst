===========
Get started
===========

This page goes from a fresh checkout to a graded two-case sweep and a local
copy of the dashboard. Run every command from the repository root. The
example outputs are from the ``dev`` branch on macOS with an OpenSWMM engine
install tree; paths are shortened to ``/path/to/...``.

Install
=======

The harness needs Python 3.12 (the version CI uses) and the packages in
``requirements.txt``: numpy, PyYAML, matplotlib, h5py, pyshp, jsonschema and
pypdf. The ``.out`` and ``.rpt`` readers need only numpy.

.. code-block:: sh

   python -m venv .venv
   . .venv/bin/activate
   pip install -r requirements.txt pytest

Run the harness tests
=====================

The tests need no engine: ``.out`` fixtures are synthesized by
``tests/outfixture.py`` and report fixtures are inline text.

.. code-block:: sh

   python -m pytest

Tests that need a native engine are skipped unless you opt in (for example
``UK_2D_ENGINE_TEST=1`` for the UK 2D output-freshness tests).

Look around without an engine
=============================

List the suites the runner discovers:

.. code-block:: console

   $ python run_regression.py --list
   coupling
   epa_qa
   parity
   performance
   quality
   stability
   uk_2d
   uk_river
   analytical/hydraulic_jumps
   analytical/manufactured
   analytical/momentum2d
   analytical/swashes
   analytical/transitions
   quality/reactions

Count the corpus by tag (first lines and the total shown):

.. code-block:: console

   $ python -m harness.corpus --census
     1413  regression
     1338  hydraulics
     1295  dynamic_wave
     1263  evaporation
     1187  circular_xsect
   ...
     1419  TOTAL cases

Select cases by tag expression. Each line is the case id, its reference
class and its tags:

.. code-block:: console

   $ python -m harness.corpus "lid AND pollutants"
   greenville-all-swmm5-features            self_consistency     buildup_washoff,circular_xsect,controls,divider,dwf,dynamic_wave,evaporation,force_main,groundwater,hydraulics,hydrology,infiltration,irregular_xsect,lid,lid_pollutants,orifice,outlet,pollutants,pump,quality,rdii,real_world,regression,rtc,snowmelt,storage,weir
   ...

Two suites check their references without any engine. The manufactured suite
reruns each case's generator script and requires a byte-identical
``reference.csv``:

.. code-block:: console

   $ python run_regression.py --suite analytical/manufactured
   === suite: analytical/manufactured ===
   note: 7 case(s) assert reproducible:true but ship no generator, so the claim cannot be checked here: dynwave-gvf-backwater-m1, exfil-cylindrical-storage-greenampt, exfil-storage-constant-area, kinwave-normal-depth-rect-open, odesolve-exponential-decay, odesolve-sir-epidemic, quality-cstr-first-order-decay
   [analytical/manufactured] PASS:6 SKIP:11
   [analytical/manufactured] PASS:6 SKIP:11

The summary line appears twice: once from the suite and once from the
runner. The SWASHES suite can rebuild its closed-form references from the
Delestre et al. formulas:

.. code-block:: sh

   python -c "from suites.analytical.swashes import suite; suite.gen_refs(check=True)"

This rewrites ``reference.csv`` and ``provenance.yaml`` in place for the 27
closed-form cases (the six ``bend*`` cases have engine-generated 2D references
and are skipped). The ``self-check max dev`` it prints compares the reference
with one computed at twice the sampling density; it is not a comparison with
the committed file. Use ``git diff`` to see whether the rewritten files
differ.

.. _first-engine:

Point the harness at an engine
==============================

Engines are found through environment variables, so the same command works
locally and in CI. With nothing set, the harness looks for a build tree at
``../openswmm.engine/build/darwin-parity`` next to this repository, and every
engine is ``UNAVAILABLE`` if it is not there. To use an engine install tree:

.. code-block:: sh

   export OPENSWMM_ENGINE_DIR=/path/to/openswmm.engine
   export OPENSWMM_EXE=$OPENSWMM_ENGINE_DIR/install/Darwin/bin/openswmm
   export OPENSWMM_LEGACY_EXE=$OPENSWMM_ENGINE_DIR/install/Darwin/bin/openswmm-legacy

.. code-block:: console

   $ python -m harness.engines
   openswmm-v6          RESOLVED     dialect=swmm53   /path/to/openswmm.engine/install/Darwin/bin/openswmm
   swmm-5.3.0           RESOLVED     dialect=swmm53   /path/to/openswmm.engine/install/Darwin/bin/openswmm-legacy
   swmm-5.2.4           UNAVAILABLE  dialect=swmm52    not executable: None

   comparisons (both engines resolved):
     swmm-5.3.0 vs openswmm-v6  rtol=1e-09 atol=1e-12 gate=fail

``OPENSWMM_ENGINE_DIR`` is also where the harness reads the engine's git
commit, which is stamped on every result (see :ref:`engine-resolution`).

Run a two-case sweep
====================

Run the EXTRAN manual's first example and the first routing test through both
engines and compare them:

.. code-block:: console

   $ python run_regression.py --suite parity --tier nightly --only extran1,test1
   === suite: parity ===
   disk: reclaimed 0.00 GiB, retained 0.00 GiB
   [parity] PASS:6
   [parity] PASS:6

Six cells: one run cell per case and engine (four) and one comparison cell
per case (two). The scores envelope is ``results/parity/scores_nightly.json``.
Each case's run tree (seeded inputs, ``.rpt``, ``.out``) is deleted once its
cells are written unless something failed; ``--keep-out all`` keeps them (see
:doc:`guides/investigating`).

Build the dashboard
===================

Render the static site from every envelope under ``results/``, the same
command the Publish workflow runs:

.. code-block:: sh

   python -m harness.report results/ --site site/build

Open ``site/build/index.html``. With the two suites above it holds the
scoreboard, one page per run under ``runs/``, one page per tag under
``tags/`` and the badge endpoints under ``badges/``. ``results/``,
``badges/`` and ``site/build/`` are git-ignored.

Next steps
==========

* :doc:`concepts/architecture` for what happened in that sweep.
* :doc:`concepts/grading` for what the verdicts and badges mean.
* :doc:`guides/running` for tiers, engine selection, runtime limits and the
  other suites.
