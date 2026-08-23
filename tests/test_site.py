"""The dashboard must not overstate what was measured.

A published scoreboard is the most persuasive artifact this project produces
and therefore the easiest place to mislead. These tests pin the properties
that keep it honest: skipped work is never counted as verified, accuracy and
agreement are reported separately, and failures are visible rather than
summarized away.
"""
from __future__ import annotations

import json
import re

import pytest

from harness import scoring, site


def envelope(suite, cells, sha="abc1234"):
    return {"suite": suite, "engine_sha": sha,
            "timestamp": "2026-08-22T12:00:00", "cells": cells}


def text_of(path):
    """Visible text of a page, tags and styles removed."""
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"<style.*?</style>", " ", s, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s))


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


def test_site_is_self_contained(built):
    """No external hosts: the page must render from a plain artifact deploy."""
    root, _ = built
    for page in root.rglob("*.html"):
        s = page.read_text(encoding="utf-8")
        assert "http://" not in s and "https://" not in s, f"{page} loads remote content"
        assert "<script" not in s.lower(), f"{page} carries script"


def test_scoreboard_separates_verification_from_regression(built):
    root, _ = built
    body = text_of(root / "index.html")
    assert "Verification is not regression" in body
    assert "exact-solution cases only" in body


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
