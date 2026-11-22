====================
Dashboard and badges
====================

The dashboard is a static site rendered from scores envelopes and run
manifests by :mod:`harness.site`. GitHub Pages serves it at the root of the
project site, ``https://www.hydrocouple.org/openswmm.engine.benchmarks/``,
with this manual under ``/docs/``; the badges in the README read their JSON
from the same deployment.

It uses the HydroCouple documentation theme: the site build copies the
theme's color tokens, fonts and logo from the manual's vendored copy
(``docs/manual/_hydrocouple/static/hc``) into ``assets/hc/``, so the pages
load nothing from another host. The color-mode button stores its choice
under the same key as the manuals, so light, dark or automatic carries over
between the dashboard and ``/docs/``. Charts are inline SVG drawn by
:mod:`harness.charts`; every chart has a table view, so no value is reachable
only by hovering.

From results to the site
========================

.. mermaid::
   :caption: How a scheduled or dispatched sweep reaches GitHub Pages.
   :alt: Flowchart from the sweep workflows to the Pages deployment

   flowchart TD
     nightly["nightly.yml<br/>07:00 UTC daily or manual"] --> sweep
     push["on_engine_push.yml<br/>engine-push dispatch"] --> sweep
     sweep["Sweep jobs<br/>parity --shard K/4, or<br/>--suite all --exclude parity"] --> evidence["results-* artifact<br/>run trees, envelopes, run.json"]
     sweep --> scores["scores-* artifact<br/>run.json, envelopes, badges"]
     scores --> build["publish.yml build"]
     build --> history["benchmark-data branch<br/>runs/&lt;run id&gt;.json"]
     history --> build
     build --> pages["upload-pages-artifact<br/>site/build with the manual in docs/"]
     pages --> deploy["publish.yml deploy<br/>deploy-pages"]

Each sweep job uploads two artifacts. ``results-<platform>-<part>`` is the
evidence: every retained run tree as well as the envelopes and the manifest,
up to about a gigabyte, kept 30 days. ``scores-<platform>-<part>`` is what
the dashboard reads: ``results/run.json``, every ``*scores*.json`` (including
the SWASHES and transitions envelopes, which live in their suite folders) and
the badges, about a megabyte, kept 90 days. The job records the evidence
artifact's URL in its manifest before uploading the scores, so the dashboard
links every run to its evidence.

Publish is told which run to publish (``run_id``). Its build job downloads
that run's ``scores-*`` artifacts (``results-*`` for a run from before the
split), each into its own ``results/<artifact>/`` folder because every job
writes the same envelope paths. It then

1. appends the run to the ``benchmark-data`` branch with
   ``python -m harness.history results/ --out history/`` (a failure warns and
   publishing goes on),
2. builds the site with
   ``python -m harness.report results/ --site site/build --history history/``,
3. builds this manual into ``site/build/docs`` (a failure warns), and
4. uploads ``site/build`` for the deploy job.

:func:`harness.report.load_envelopes` reads every ``*scores*.json`` under the
paths it is given, skipping any file under a ``site`` or ``runs`` folder (the
site keeps copies of the envelopes, and reading them back would double every
count), and pairs each envelope with the nearest ``run.json`` above it, so
each job's envelopes carry that job's manifest. The publish job never fails
for lack of results: an empty set renders a page that says the run produced
no results, so a broken sweep cannot leave an older, healthy-looking
dashboard in place.

The run manifest
================

``run_regression.py`` writes ``results/run.json`` when a run starts and again
when it ends (:mod:`harness.runinfo`); a manifest without ``finished``
belongs to a run that never ended. It records:

* the workflow run and job: id, attempt, workflow, trigger, job name, and the
  URLs of the run and of the job's log;
* the description: ``--description``, else ``BENCH_RUN_DESCRIPTION`` (the
  Nightly dispatch form's *description*), else one generated from the trigger,
  engine and job, such as ``Nightly (scheduled) · swmm6_rel@de02d856 ·
  Linux-x64 · parity 1of4``;
* the engine: ref, short and full commit, whether the tree was modified, the
  commit's date and subject, each engine's ``--version`` line and executable
  path;
* the host: operating system and release, architecture, CPU model and count,
  memory, Python and numpy versions, runner name;
* the benchmarks commit, the arguments, the tier and ``--max-wall``;
* when it started and finished, its duration and exit status, and any suite
  that crashed;
* the artifacts' URLs.

What the pages show
===================

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Path
     - Contents
   * - ``index.html``
     - The latest run's description, engine commit, platforms and a link to
       its workflow run; tiles for verification, regression, parity,
       mass balance, stability, engine time, peak memory and the corpus; the
       note separating exact-solution cells from the rest and any coverage
       notes; verdicts per suite and platform; one expandable row per job and
       suite with its manifest and links (run page, workflow run, job log,
       evidence artifact, all artifacts, ``scores.json``); failures by
       mechanism; then the Performance, Mass balance, Stability, Parity,
       Platforms and Corpus by tag sections described below.
   * - ``runs/<stamp>_<suite>[_<platform>][_<K>-of-<N>]@<sha>/``
     - One page per envelope: its description and links, verdicts, manifest,
       failures by mechanism, the same sections for its cells, and every cell
       in a table that sorts by column and filters as you type, with the
       envelope itself as ``scores.json``.
   * - ``cases/<id>/``
     - One case: its title, reference class, expected failures and tags, and
       every engine run and compared pair of it on every platform.
   * - ``tags/<tag>/``
     - Every case carrying the tag, its reference class and its verdicts on
       each platform.
   * - ``trends/``
     - Per recorded run, from ``benchmark-data``: for parity on each platform,
       gating cells, engine time, median run time, worst continuity and the
       share of stable runs per engine; gating cells and engine time for the
       other suites.
   * - ``badges/<name>.json``
     - The shields.io endpoint files.
   * - ``docs/``
     - This manual.

The sections, and what each figure leaves out:

Failures by mechanism
   Gating cells grouped by their note with names, numbers and line
   references taken out, so one cause is one row however many cases it
   affects. A trimmed run's note is grouped by the failure after the trim
   notice; a cell with no note is grouped by verdict and suite.

Performance
   Wall time of each completed parity engine run (one process, one thread):
   per engine and platform, the total, median and 90th percentile, a
   distribution, and the slowest runs. *Engine against engine* plots each
   case's openswmm-v6 time against its swmm-5.3.0 time on log axes, with
   the median ratio over the cases where either engine took at least 1 s
   (below that, process start-up dominates). Cases trimmed for the CI budget
   are left out of that comparison. Peak memory is each engine process's own
   peak resident memory, measured on Linux and macOS (:mod:`harness.runner`);
   Windows has no per-process peak in the standard library.

Mass balance
   The flow routing continuity error from each engine's report, as a
   distribution for the parity engines, and the largest errors across suites
   with runoff, groundwater and worst quality continuity. Runs of models
   tagged ``expected_high_continuity`` are left out of the distribution and
   the worst figure, and their number is shown.

Stability
   The share of routing steps that did not converge, as a distribution, and
   the least converged runs with average iterations, minimum and average
   time step, unstable links, flooded nodes and surcharged nodes, all read
   from the engine's report.

Parity
   For each compared pair, the largest relative difference over every
   element, variable and period, binned from identical to at least 1e-3,
   and the largest differences with the worst variable, element, first
   diverging period and the number of values over tolerance.

Platforms
   The same case and engine on two operating systems: how many runs share
   a verdict, how many wrote a byte-identical ``.out`` (from the first 16 hex
   digits of each output's SHA-256; outputs over 256 MiB are not hashed), and
   the median time ratio over runs that completed on both and took at least
   1 s. The runners' CPUs can differ, so each run's manifest names its CPU.

Building from the two-case sweep in :doc:`../get-started` writes the index,
two run pages with their envelopes, two case pages, a page for each tag in
use, the Trends page, six badges, and the theme and dashboard assets.

Badges
======

The README shows shields.io endpoint badges that read
``badges/verification.json``, ``regression.json``, ``mass-balance.json``,
``stability.json`` and ``models.json`` from the Pages site. The rules for
each are in :ref:`badges <grading-badges>`. Badge files are written in two
places:

* ``run_regression.py --badges DIR`` writes them from the envelopes of that
  run, in memory. The Nightly sweep uploads these in its artifacts.
* ``harness.report --site`` writes them again from the envelopes it loaded,
  adding ``models`` (the corpus size). These are the ones published.

Not on the dashboard yet
========================

* The ``performance`` suite is a scaffold; runtimes come from the sweeps'
  own engine runs.
* Peak memory on Windows.
* Envelopes written before 2026-11-22 carry no platform, manifest, peak
  memory, report statistics or output fingerprints; the pages show those as
  missing rather than guessing.
