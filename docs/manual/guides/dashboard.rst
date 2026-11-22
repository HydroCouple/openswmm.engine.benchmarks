====================
Dashboard and badges
====================

The dashboard is a static site rendered from scores envelopes by
:mod:`harness.site`. It is self-contained (no external stylesheets, scripts
or fonts) and follows the browser's light or dark preference. GitHub Pages
serves it at the root of the project site,
``https://www.hydrocouple.org/openswmm.engine.benchmarks/``, once the Publish
workflow has deployed it; the badges in the README read their JSON from the
same deployment.

From results to the site
========================

.. mermaid::
   :caption: How a scheduled or dispatched sweep reaches GitHub Pages.
   :alt: Flowchart from the sweep workflows to the Pages deployment

   flowchart TD
     nightly["nightly.yml<br/>07:00 UTC daily or manual"] --> sweep
     push["on_engine_push.yml<br/>engine-push dispatch"] --> sweep
     sweep["Sweep jobs<br/>build engines<br/>parity --shard K/4, or<br/>--suite all --exclude parity"] --> artifact["one artifact per job, results-*<br/>results/ and badges/"]
     artifact --> build["publish.yml build<br/>harness.report results/<br/>--site site/build"]
     build --> pages["upload-pages-artifact<br/>site/build"]
     pages --> deploy["publish.yml deploy<br/>deploy-pages"]

The Publish workflow's build job downloads every ``results-*`` artifact from
the run (or, when dispatched by hand, from the last completed Nightly run),
each into its own ``results/<artifact>/`` folder because every job writes the
same envelope paths, prints how many envelopes it found, and runs

.. code-block:: sh

   python -m harness.report results/ --site site/build

:func:`harness.report.load_envelopes` reads every ``*scores*.json`` under the
paths it is given, skipping any file under a ``site`` or ``runs`` folder (the
site keeps copies of the envelopes, and reading them back would double every
count). The publish job never fails for lack of results: an empty set
renders a page that says the run produced no results, so a broken sweep
cannot leave an older, healthy-looking dashboard in place.

Site layout
===========

.. list-table::
   :header-rows: 1
   :widths: 34 66

   * - Path
     - Contents
   * - ``index.html``
     - Cards for the corpus size, the verification and regression badges and
       the number of failing cells; a note separating exact-solution cells
       from the rest; any UK coverage notes; verdict counts per suite; the
       first 40 failing cells; the corpus by tag; the engine commits in the
       run.
   * - ``runs/<stamp>_<suite>[_<platform>][_<K>-of-<N>]@<sha>/``
     - One page per envelope (verdict counts and up to 200 failing cells)
       with the envelope itself as ``scores.json``. Parity envelopes carry
       their platform and shard, so the eight Nightly parity jobs get eight
       pages.
   * - ``tags/<tag>/``
     - Every case carrying the tag, its reference class, its tags and its
       latest verdicts.
   * - ``badges/<name>.json``
     - The shields.io endpoint files.

Building from the two-case sweep in :doc:`../get-started` writes 61 files:
the index, two run pages with their envelopes, a page for each of the 50
tags in use, and six badges.

Badges
======

The README shows shields.io endpoint badges that read
``badges/verification.json``, ``regression.json``, ``mass-balance.json``,
``stability.json`` and ``models.json`` from the Pages site. The rules for
each are in :ref:`badges <grading-badges>`. Badge files are written in two
places:

* ``run_regression.py --badges DIR`` writes them from the envelopes of that
  run, in memory. The Nightly sweep uploads these in its artifact.
* ``harness.report --site`` writes them again from the envelopes it loaded,
  adding ``models`` (the corpus size). These are the ones published.

Not on the dashboard yet
========================

* The ``analytical/swashes`` and ``analytical/transitions`` suites write their
  envelopes inside their suite folders (``swashes_scores.json``,
  ``transitions_scores.json``), not under ``results/``. The sweep artifacts
  hold only ``results/`` and ``badges/``, so the published dashboard and
  badges do not include those cells.
* Performance trends: the ``performance`` suite is a scaffold.
* This manual. It is built by the Documentation workflow and kept as a
  workflow artifact; the Publish workflow does not include it.
