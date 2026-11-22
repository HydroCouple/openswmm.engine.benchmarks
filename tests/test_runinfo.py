"""The run manifest: every published result must say which run produced it.

A scores envelope records cells; without the manifest beside it the dashboard
cannot say which workflow run and job produced them, on what CPU, from which
engine commit, or where the job's artifacts are.
"""
from __future__ import annotations

import json

import pytest

from harness import report, runinfo


@pytest.fixture
def github_env(monkeypatch):
    for k, v in {"GITHUB_SERVER_URL": "https://github.com", "GITHUB_REPOSITORY": "o/r",
                 "GITHUB_RUN_ID": "4242", "GITHUB_RUN_ATTEMPT": "2",
                 "GITHUB_WORKFLOW": "Nightly", "GITHUB_EVENT_NAME": "schedule",
                 "BENCH_JOB_ID": "77", "BENCH_JOB_NAME": "Sweep (Linux-x64, parity-1of4)",
                 "BENCH_PART": "parity-1of4", "BENCH_PLATFORM_ALIAS": "Linux-x64",
                 "OPENSWMM_ENGINE_REF": "swmm6_rel"}.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("BENCH_RUN_DESCRIPTION", raising=False)


def test_a_ci_run_links_its_run_and_job(github_env):
    m = runinfo.collect(argv=["--suite", "parity"], tier="nightly", max_wall=300.0)
    assert m["id"] == "4242" and m["attempt"] == "2"
    assert m["url"] == "https://github.com/o/r/actions/runs/4242"
    assert m["job_url"] == "https://github.com/o/r/actions/runs/4242/job/77"
    assert m["engine"]["ref"] == "swmm6_rel"
    assert m["host"]["os"] and m["host"]["cpu_count"]
    assert m["finished"] is None, "a run that has not ended must not look finished"


def test_a_generated_description_names_trigger_engine_and_job(github_env, monkeypatch):
    # Validate runs without an engine checkout, so the engine is stubbed here.
    monkeypatch.setattr(runinfo, "engine", lambda: {"sha": "abc1234", "ref": "swmm6_rel"})
    d = runinfo.collect(argv=[])["description"]
    assert d == "Nightly (scheduled) · swmm6_rel@abc1234 · Linux-x64 · parity 1of4"


def test_without_an_engine_checkout_the_description_still_names_the_ref(github_env, monkeypatch):
    monkeypatch.setattr(runinfo, "engine", lambda: {"sha": "", "ref": "swmm6_rel"})
    assert runinfo.collect(argv=[])["description"] == \
        "Nightly (scheduled) · swmm6_rel · Linux-x64 · parity 1of4"


def test_a_given_description_wins(github_env, monkeypatch):
    monkeypatch.setenv("BENCH_RUN_DESCRIPTION", "from the dispatch form")
    assert runinfo.collect(argv=[])["description"] == "from the dispatch form"
    assert runinfo.collect(argv=[], description="from the flag")["description"] == "from the flag"


def test_finish_records_duration_exit_and_crashes(github_env):
    m = runinfo.collect(argv=[])
    m["started"] = "2026-11-22T07:00:00+00:00"
    runinfo.finish(m, exit_code=1, crashed=["analytical/swashes: ValueError: x"])
    assert m["exit_code"] == 1 and m["crashed"] and m["duration_s"] > 0


def test_an_artifact_url_is_recorded_even_without_a_manifest(tmp_path):
    """A sweep that died before writing its manifest still gets its link."""
    p = tmp_path / "run.json"
    assert runinfo.main(["--set-artifact", "evidence", "https://x/artifacts/9",
                         "--manifest", str(p)]) == 0
    assert json.loads(p.read_text(encoding="utf-8"))["artifacts"]["evidence"] == "https://x/artifacts/9"
    runinfo.main(["--set-artifact", "evidence", "", "--manifest", str(p)])
    assert json.loads(p.read_text(encoding="utf-8"))["artifacts"]["evidence"] == "https://x/artifacts/9"


def test_run_regression_writes_the_manifest_at_start_and_end(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import run_regression
    seen = {}

    def run(argv):
        seen["during"] = runinfo.load()
        return None

    monkeypatch.setattr(run_regression.suites, "list_suites", lambda: ["coupling"])
    monkeypatch.setattr(run_regression.suites, "discover",
                        lambda names: {"coupling": SimpleNamespace(run=run, report=lambda a: [])})
    assert run_regression.main(["--suite", "coupling", "--description", "a test run"]) == 0
    assert seen["during"]["description"] == "a test run" and seen["during"]["finished"] is None
    done = runinfo.load()
    assert done["finished"] and done["exit_code"] == 0
    assert str(runinfo.path()).startswith(str(tmp_path)), "tests never touch results/run.json"


def test_each_artifact_folder_pairs_envelopes_with_its_own_manifest(tmp_path):
    """Publish downloads every job's artifact into its own folder; the
    envelopes of one job must not borrow another job's manifest."""
    for job in ("scores-Linux-x64-parity-1of4", "scores-Windows-x64-parity-1of4"):
        res = tmp_path / job / "results"
        (res / "parity").mkdir(parents=True)
        (res / "run.json").write_text(json.dumps({"job": job}), encoding="utf-8")
        (res / "parity" / "scores_nightly.json").write_text(
            json.dumps({"suite": "parity", "cells": []}), encoding="utf-8")
    swashes = tmp_path / "scores-Linux-x64-parity-1of4" / "suites" / "analytical" / "swashes"
    swashes.mkdir(parents=True)
    (swashes / "swashes_scores.json").write_text(
        json.dumps({"suite": "analytical/swashes", "cells": []}), encoding="utf-8")
    envs = report.load_envelopes([tmp_path])
    jobs = sorted((e["suite"], e["_run"].get("job")) for e in envs)
    assert jobs == [("analytical/swashes", "scores-Linux-x64-parity-1of4"),
                    ("parity", "scores-Linux-x64-parity-1of4"),
                    ("parity", "scores-Windows-x64-parity-1of4")]
