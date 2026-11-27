"""The dashboard must not overstate what was measured.

A published scoreboard is the most persuasive artifact this project produces
and therefore the easiest place to mislead. These tests pin the properties
that keep it honest: skipped work is never counted as verified, accuracy and
agreement are reported separately, and failures are visible rather than
summarized away.
"""
from __future__ import annotations

import html
import json
import re

import pytest

from harness import scoring, site


def envelope(suite, cells, sha="abc1234"):
    return {"suite": suite, "engine_sha": sha,
            "timestamp": "2026-08-22T12:00:00", "cells": cells}


def text_of(path):
    """Visible text of a page, tags, styles and scripts removed."""
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"<(style|script)\b.*?</\1>", " ", s, flags=re.S)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)))


# ── the property that matters most ─────────────────────────────────────────

def test_skipped_cases_are_not_counted_as_verified():
    """A suite that checked 6 of 17 must never report 17/17.

    This is the failure the split exists to prevent: SKIP means the claim was
    not tested, and folding it into the numerator turns partial coverage into
    a green badge.
    """
    cells = ([{"case": f"p{i}", "reference_class": "manufactured",
               "verdict": "PASS"} for i in range(6)]
             + [{"case": f"s{i}", "reference_class": "manufactured",
                 "verdict": "SKIP"} for i in range(11)])
    b = scoring.badges([envelope("analytical/manufactured", cells)])
    assert b["verification"]["message"] == "6/6 checked · 11 unchecked"
    assert b["verification"]["color"] == scoring.BADGE_YELLOW, (
        "partial coverage must not be green")


def test_full_coverage_with_no_skips_is_green():
    cells = [{"case": f"p{i}", "reference_class": "analytic", "verdict": "PASS"}
             for i in range(4)]
    b = scoring.badges([envelope("analytical/swashes", cells)])
    assert b["verification"]["message"] == "4/4 checked"
    assert b["verification"]["color"] == scoring.BADGE_GREEN


def test_any_verification_failure_is_red():
    cells = [{"case": "a", "reference_class": "analytic", "verdict": "PASS"},
             {"case": "b", "reference_class": "analytic", "verdict": "FAIL"}]
    b = scoring.badges([envelope("analytical/swashes", cells)])
    assert b["verification"]["color"] == scoring.BADGE_RED


def test_nothing_checked_is_not_green():
    cells = [{"case": "a", "reference_class": "analytic", "verdict": "SKIP"}]
    b = scoring.badges([envelope("analytical/swashes", cells)])
    assert b["verification"]["color"] == scoring.BADGE_GREY


def test_regression_cases_never_enter_the_verification_count():
    """1,396 corpus models passing is not an accuracy result."""
    cells = ([{"case": f"c{i}", "reference_class": "self_consistency",
               "verdict": "PASS"} for i in range(1396)]
             + [{"case": "a", "reference_class": "analytic", "verdict": "PASS"}])
    b = scoring.badges([envelope("parity", cells)])
    assert b["verification"]["message"].startswith("1/1")
    assert b["regression"]["message"] == "passing"


# ── site rendering ─────────────────────────────────────────────────────────

@pytest.fixture
def built(tmp_path):
    envs = [
        envelope("analytical/manufactured",
                 [{"case": "horton", "reference_class": "manufactured",
                   "verdict": "PASS"},
                  {"case": "gvf", "reference_class": "manufactured",
                   "verdict": "SKIP", "note": "no generator script"}]),
        envelope("parity",
                 [{"case": "extran2", "pair": "a vs b",
                   "reference_class": "self_consistency", "verdict": "FAIL",
                   "max_rel": 3.2e-4, "continuity_err": -4.05,
                   "pct_not_converging": 3.68, "note": "47 cells over tolerance"}]),
    ]
    files = site.build_site(envs, tmp_path)
    return tmp_path, files


#: Anything a browser fetches on its own: stylesheets, scripts, images,
#: frames, and CSS url()/@import. Links a reader clicks (<a href>) are not
#: loads, so the GitHub and hydrocouple.org links are allowed.
_REMOTE_LOAD = re.compile(
    r"<(?:link|script|img|iframe|source)\b[^>]*\b(?:href|src)\s*=\s*['\"]?(?:https?:)?//"
    r"|url\(\s*['\"]?(?:https?:)?//|@import\s+['\"]?(?:url\()?\s*['\"]?(?:https?:)?//",
    re.I)


def test_site_is_self_contained(built):
    """No external hosts: the page must render from a plain artifact deploy,
    and keep rendering when a CDN does not. Every stylesheet, script, font
    and image the pages load is a file in the deployment."""
    root, _ = built
    for page in list(root.rglob("*.html")) + list(root.rglob("*.css")):
        s = page.read_text(encoding="utf-8")
        assert not _REMOTE_LOAD.search(s), f"{page} loads remote content"
    index = (root / "index.html").read_text(encoding="utf-8")
    for ref in re.findall(r"<(?:link|script)\b[^>]*\b(?:href|src)='([^']+)'", index):
        assert (root / ref).exists(), f"index.html loads {ref}, which was not written"
    assert (root / "assets" / "hc" / "fonts").is_dir()


def test_remote_load_check_catches_what_it_should():
    assert _REMOTE_LOAD.search("<script src='https://cdn.example/x.js'></script>")
    assert _REMOTE_LOAD.search("<link rel=stylesheet href=//fonts.example/css>")
    assert _REMOTE_LOAD.search("body{background:url(https://x/y.png)}")
    assert not _REMOTE_LOAD.search("<a href='https://github.com/HydroCouple'>GitHub</a>")
    assert not _REMOTE_LOAD.search("<script src='assets/dashboard.js' defer></script>")


def test_scoreboard_separates_verification_from_regression(built):
    root, _ = built
    body = text_of(root / "index.html")
    assert "Exact-solution checks 1 of 1 passed 0 gate failures · 1 skipped or unavailable" in body
    assert "Regression checks 0 of 1 passed 1 gate failure" in body


def test_failures_are_shown_not_summarized_away(built):
    root, _ = built
    body = text_of(root / "index.html")
    assert "extran2" in body
    assert "47 cells over tolerance" in body
    assert "FAIL" in body


def test_badges_and_run_pages_are_written(built):
    root, _ = built
    for name in ("verification", "regression", "models"):
        p = root / "badges" / f"{name}.json"
        if p.exists():
            assert json.loads(p.read_text(encoding="utf-8"))["schemaVersion"] == 1
    runs = list((root / "runs").iterdir())
    assert len(runs) == 2, "each envelope needs its own immutable run page"
    for r in runs:
        assert (r / "index.html").exists() and (r / "scores.json").exists()


def test_run_pages_are_keyed_by_engine_sha(built):
    """A result is meaningless without knowing which engine produced it."""
    root, _ = built
    assert all("@abc1234" in r.name for r in (root / "runs").iterdir())


def test_sharded_envelopes_get_one_run_page_each(tmp_path):
    """Nightly runs parity as 4 shards on 2 OSes: same suite, same SHA, often
    the same second. Keyed on those alone the pages overwrite each other."""
    cell = {"case": "c", "reference_class": "self_consistency",
            "verdict": "PASS"}
    envs = [{**envelope("parity", [cell]), "platform": os_, "shard": f"{k}/4"}
            for os_ in ("Linux", "Windows") for k in (1, 2, 3, 4)]
    site.build_site(envs, tmp_path)
    runs = sorted(r.name for r in (tmp_path / "runs").iterdir())
    assert len(runs) == 8
    assert "20260822T120000_parity_Windows_3-of-4@abc1234" in runs


def test_html_is_escaped(tmp_path):
    """Case ids and notes come from files on disk; they must not inject markup."""
    envs = [envelope("parity", [{"case": "<img src=x onerror=alert(1)>",
                                 "reference_class": "self_consistency",
                                 "verdict": "FAIL",
                                 "note": "<b>bold</b> & 'quoted'"}])]
    site.build_site(envs, tmp_path)
    s = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "<img src=x" not in s
    assert "&lt;img" in s


# ── the empty run ──────────────────────────────────────────────────────────

def test_a_run_with_no_results_does_not_render_as_a_clean_run(tmp_path):
    """The most dangerous page this project could publish.

    With zero cells the ordinary layout reads "Failing cells 0" and "No
    failing cells in this run" — a clean bill of health for work that never
    happened. The first failed publish (2026-08-23) was only saved from this
    by crashing before it could deploy.
    """
    site.build_site([], tmp_path)
    body = text_of(tmp_path / "index.html")
    assert "This run produced no results" in body
    assert "not a passing run" in body
    assert "No failing cells in this run" not in body
    assert "Failing cells 0" not in body


def test_empty_run_emits_a_red_status_badge():
    """Otherwise the only badge left is a cheerful corpus count."""
    b = scoring.badges([], corpus_count=1396)
    assert b["status"]["message"] == "no results"
    assert b["status"]["color"] == scoring.BADGE_RED
    assert "verification" not in b, "nothing was verified"
    assert "regression" not in b


def test_status_badge_absent_when_there_are_results():
    b = scoring.badges([envelope("parity", [
        {"case": "a", "reference_class": "self_consistency", "verdict": "PASS"}])])
    assert "status" not in b


def test_publishing_an_empty_run_succeeds_rather_than_leaving_a_stale_page(tmp_path):
    """Refusing to publish leaves the PREVIOUS dashboard up, so a broken
    nightly looks healthy. Publish the failure instead."""
    from harness import report
    rc = report.main([str(tmp_path / "absent"), "--site", str(tmp_path / "site")])
    assert rc == 0
    assert (tmp_path / "site" / "index.html").exists()
    assert "no results" in text_of(tmp_path / "site" / "index.html").lower()


def test_report_without_site_still_signals_empty(tmp_path, capsys):
    """A human running the CLI wants a nonzero exit, not a silent no-op."""
    from harness import report
    assert report.main([str(tmp_path / "absent")]) == 2


# ── the run behind every result ────────────────────────────────────────────

def _manifest(**over):
    m = {"schema": 1, "id": "4242", "url": "https://github.com/o/r/actions/runs/4242",
         "job_url": "https://github.com/o/r/actions/runs/4242/job/77",
         "workflow": "Nightly", "event": "schedule", "job": "Sweep (Linux-x64, parity-1of4)",
         "started": "2026-11-22T07:00:00+00:00", "finished": "2026-11-22T09:00:00+00:00",
         "duration_s": 7200.0, "exit_code": 1, "crashed": [],
         "description": "Nightly (scheduled) · swmm6_rel@de02d856",
         "platform_alias": "Linux-x64", "part": "parity-1of4",
         "host": {"os": "Linux", "machine": "x86_64", "cpu": "AMD EPYC 7763", "cpu_count": 4},
         "engine": {"sha": "de02d856", "sha_full": "de02d856" + "0" * 32, "ref": "swmm6_rel",
                    "subject": "Book the surcharge water", "versions": {}},
         "artifacts": {"evidence": "https://github.com/o/r/actions/runs/4242/artifacts/9"}}
    m.update(over)
    return m


def _engine_cell(case, solver, verdict="PASS", wall=2.0, **kw):
    return {"case": case, "solver": solver, "reference_class": "self_consistency",
            "verdict": verdict, "wall": wall, "continuity_err": 0.1,
            "pct_not_converging": 0.0, **kw}


@pytest.fixture
def with_run(tmp_path):
    cells = [_engine_cell("c1", "swmm-5.3.0", wall=2.0, out_sha16="aa"),
             _engine_cell("c1", "openswmm-v6", wall=3.0, peak_rss_mb=40.0, out_sha16="bb"),
             {"case": "c1", "pair": "swmm-5.3.0 vs openswmm-v6",
              "reference_class": "self_consistency", "verdict": "PASS", "max_rel": 0.0},
             _engine_cell("c2", "openswmm-v6", "ERROR", wall=0.01,
                          note="ERROR 14: the routing solution diverged at node 'J1' (head 3e15)")]
    env = {**envelope("parity", cells, sha="de02d856"), "platform": "Linux", "shard": "1/4",
           "_run": _manifest()}
    site.build_site([env], tmp_path)
    return tmp_path


def test_each_run_links_its_workflow_job_and_artifact(with_run):
    s = (with_run / "index.html").read_text(encoding="utf-8")
    for url in ("actions/runs/4242'", "actions/runs/4242/job/77", "actions/runs/4242/artifacts/9"):
        assert url in s, url
    run_page = next((with_run / "runs").iterdir()) / "index.html"
    assert "actions/runs/4242/artifacts/9" in run_page.read_text(encoding="utf-8")


def test_the_run_description_and_host_are_shown(with_run):
    body = text_of(with_run / "index.html")
    assert "Nightly (scheduled) · swmm6_rel@de02d856" in body
    assert "AMD EPYC 7763" in body, "the CPU qualifies every runtime"


def test_a_missing_link_is_shown_as_missing_not_dropped(tmp_path):
    env = {**envelope("parity", [_engine_cell("c1", "openswmm-v6")]),
           "_run": _manifest(job_url=None, artifacts={})}
    site.build_site([env], tmp_path)
    s = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "aria-disabled=true title='not recorded for this run'>Job log" in s


def test_failures_are_grouped_by_mechanism_with_their_cases(with_run):
    body = text_of(with_run / "index.html")
    assert "the routing solution diverged at node '…'" in body
    assert "head 3e15" in body, "the full note stays in the expanded rows"


def test_case_pages_hold_every_engine_and_platform(with_run):
    page = with_run / "cases" / "c1" / "index.html"
    body = text_of(page)
    assert "openswmm-v6" in body and "swmm-5.3.0" in body and "swmm-5.3.0 vs openswmm-v6" in body
    assert "40" in body, "peak memory"


def test_trends_say_when_there_is_too_little_history(tmp_path):
    site.build_site([envelope("parity", [_engine_cell("c1", "openswmm-v6")])], tmp_path,
                    history=[])
    assert "at least two recorded" in text_of(tmp_path / "trends" / "index.html")


def test_trends_plot_recorded_runs(tmp_path):
    from harness import history
    runs = []
    for i, (rid, w) in enumerate((("1", 2.0), ("2", 3.0))):
        env = {**envelope("parity", [_engine_cell("c1", "openswmm-v6", wall=w)]),
               "platform": "Linux",
               "_run": _manifest(id=rid, started=f"2026-11-2{i}T07:00:00+00:00")}
        runs += history.summarize([env])
    site.build_site([envelope("parity", [_engine_cell("c1", "openswmm-v6")])], tmp_path,
                    history=runs)
    s = (tmp_path / "trends" / "index.html").read_text(encoding="utf-8")
    assert "<polyline class='line s1'" in s
    assert "parity · Linux" in text_of(tmp_path / "trends" / "index.html")


def test_engine_against_engine_reports_the_ratio_it_plots(with_run):
    body = text_of(with_run / "index.html")
    assert "median openswmm-v6 ÷ swmm-5.3.0 time is 1.50" in body


def test_every_chart_has_a_table_view(with_run):
    s = (with_run / "index.html").read_text(encoding="utf-8")
    assert s.count("<svg class=chart__svg") + s.count("<svg class='chart__svg") > 0
    charts_with_bins = s.count("<div class=chart>") - s.count("chart__svg--square")
    assert s.count("<details class=tableview>") >= charts_with_bins


def test_overview_uses_archived_grading_modes(tmp_path):
    from harness import report
    archived = envelope("swashes", [
        {"case": "a", "mode": "analytic", "verdict": "PASS"},
        {"case": "b", "mode": "xfail", "verdict": "XFAIL"},
        {"case": "c", "mode": "baseline", "verdict": "XPASS"},
        {"case": "d", "mode": "ci-baseline", "analytic_verdict": "FAIL", "verdict": "BASELINE-PASS"},
        {"case": "e", "verdict": "SKIP"},
    ])
    source = tmp_path / "swashes_scores.json"
    source.write_text(json.dumps(archived))
    assert report.main([str(source), "--site", str(tmp_path / "public")]) == 0
    body = text_of(tmp_path / "public/index.html")
    assert "Exact-solution checks 1 of 2 passed 0 gate failures · 1 expected failure · 1 skipped" in body
    assert "Regression checks 1 of 2 passed 1 gate failure" in body
    badge = json.loads((tmp_path / "public/badges/verification.json").read_text())
    assert badge["message"] == "1/2 checked · 1 unchecked"


def test_overview_explains_absent_and_unchecked_exact_results():
    assert "This run reported no analytical or manufactured checks." in site._tiles(
        [_engine_cell("a", "v6", _suite="parity")], 1)
    tile = site._outcome_tile("Exact-solution checks", [{"verdict": "UNAVAILABLE"}], "")
    assert "None checked" in tile and "1 skipped or unavailable" in tile


def test_mass_balance_tile_uses_absolute_measured_engine_errors_only():
    cells = [_engine_cell(str(i), "v6", continuity_err=error)
             for i, error in enumerate([-1, -0.04, 80, None, float("nan")])]
    cells += [_engine_cell("excluded", "v6", continuity_err=99, expected_high_continuity=True),
              {"pair": "a vs b", "continuity_err": 100}]
    tile = site._mass_balance_tile(cells)
    assert "1% median" in tile
    assert "2 of 3 measured runs at or below 1%" in tile
    assert "1 excluded" in tile
    assert "href='#mass-balance'" in tile
    assert "No graded runs" in site._mass_balance_tile(cells[-2:])
