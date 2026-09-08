#!/usr/bin/env python3
"""The runtime gate: long models run locally, never on a shared CI runner.

Engine-free like the rest of tests/ — the ledger is data and the trim is a
text rewrite, so both are testable without building anything.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from harness import runtime  # noqa: E402

LEDGER = {"suites": {"parity": {
    "slowcase": {"wall_s": 601.0, "engine": "openswmm-v6", "sweep": "s"},
    "timeoutcase": {"wall_s": 600.0, "engine": "openswmm-v6", "sweep": "s",
                    "timed_out": True},
    "fastcase": {"wall_s": 61.0, "engine": "openswmm-v6", "sweep": "s"},
}}}


# ── the gate ───────────────────────────────────────────────────────────────

def test_no_threshold_skips_nothing():
    """A local sweep passes no --max-wall, and long models are its whole point."""
    assert runtime.skip_reason(LEDGER, "parity", "slowcase", None) is None


def test_over_threshold_is_skipped_with_the_number_in_the_reason():
    why = runtime.skip_reason(LEDGER, "parity", "slowcase", 300)
    assert why and "601" in why and "300" in why


def test_under_threshold_runs():
    assert runtime.skip_reason(LEDGER, "parity", "fastcase", 300) is None


def test_unmeasured_runs():
    """An unmeasured case is not presumed slow: it runs, bounded by timeout_s,
    and the sweep records what it cost. Presuming would silently drop a third
    of the corpus off CI."""
    assert runtime.skip_reason(LEDGER, "parity", "never-timed", 300) is None


def test_a_timeout_is_reported_as_a_floor_not_a_measurement():
    """A killed run's wall is the timeout, not the model's cost. Saying
    'measured 600s' would assert a number nobody has ever observed."""
    why = runtime.skip_reason(LEDGER, "parity", "timeoutcase", 300)
    assert "timed out at" in why


def test_a_trimmed_case_runs_instead_of_being_skipped():
    """The trim is what brings the case inside the budget; skipping it as well
    would throw away the coverage the trim exists to keep."""
    meta = {"ci_runtime": {"duration_h": 6, "reason": "x" * 20}}
    assert runtime.skip_reason(LEDGER, "parity", "slowcase", 300, meta) is None


def test_a_case_recorded_under_another_suite_label_is_still_gated():
    """The swashes suite names itself two different ways; a ten-minute case is
    ten minutes under either label."""
    assert runtime.skip_reason(LEDGER, "swashes", "slowcase", 300)


# ── the ledger ─────────────────────────────────────────────────────────────

def test_record_keeps_the_slowest_engine(tmp_path):
    """A case is only as cheap as its slowest engine."""
    p = tmp_path / "runtimes.yaml"
    runtime.record({"suite": "parity", "timestamp": "t", "cells": [
        {"case": "c", "solver": "fast-engine", "wall": 100.0},
        {"case": "c", "solver": "slow-engine", "wall": 400.0},
    ]}, p)
    assert yaml.safe_load(p.read_text())["suites"]["parity"]["c"] == {
        "wall_s": 400.0, "engine": "slow-engine", "sweep": "t"}


def test_record_ignores_cases_below_the_floor(tmp_path):
    p = tmp_path / "runtimes.yaml"
    n = runtime.record({"suite": "parity", "timestamp": "t", "cells": [
        {"case": "quick", "solver": "e", "wall": 1.0}]}, p)
    assert n == 0
    assert not yaml.safe_load(p.read_text())["suites"]


def test_record_flags_a_timeout(tmp_path):
    p = tmp_path / "runtimes.yaml"
    runtime.record({"suite": "parity", "timestamp": "t", "cells": [
        {"case": "c", "solver": "e", "wall": 600.0,
         "note": "timeout after 600s"}]}, p)
    assert yaml.safe_load(p.read_text())["suites"]["parity"]["c"]["timed_out"]


def test_a_missing_ledger_means_nothing_measured(tmp_path):
    """The gate must never be the reason a sweep cannot start."""
    assert runtime.load(tmp_path / "absent.yaml") == {"suites": {}}


def test_the_committed_ledger_parses_and_is_shaped_right():
    led = runtime.load()
    assert led["suites"], "the committed ledger has no measurements"
    for suite, entries in led["suites"].items():
        for case, entry in entries.items():
            assert isinstance(entry.get("wall_s"), (int, float)), (suite, case)
            assert entry.get("sweep"), f"{case} has no sweep provenance"


# ── the trim ───────────────────────────────────────────────────────────────

INP = """[TITLE]
example

[OPTIONS]
FLOW_ROUTING\tDYNWAVE
START_DATE\t01/20/2013
START_TIME\t00:00
END_DATE\t05/05/2013
END_TIME\t00:00
ROUTING_STEP\t30

[JUNCTIONS]
"""


def test_trim_rewrites_only_the_end_of_the_period(tmp_path):
    p = tmp_path / "model.inp"
    p.write_text(INP)
    note = runtime.apply_trim(p, 48)
    out = p.read_text()
    assert "END_DATE\t01/22/2013" in out
    assert "END_TIME\t00:00:00" in out
    assert "START_DATE\t01/20/2013" in out      # untouched
    assert "ROUTING_STEP\t30" in out            # untouched
    assert out.count("\n") == INP.count("\n")   # no lines added or lost
    assert "48" in note


def test_trim_handles_a_start_time_of_day(tmp_path):
    p = tmp_path / "model.inp"
    p.write_text(INP.replace("START_TIME\t00:00", "START_TIME\t06:30:00"))
    runtime.apply_trim(p, 2)
    assert "END_TIME\t08:30:00" in p.read_text()


def test_trim_refuses_a_model_it_cannot_parse(tmp_path):
    """Silently not trimming would hand CI the full-length run it was told to
    avoid, and the timeout would be blamed instead."""
    p = tmp_path / "model.inp"
    p.write_text("[OPTIONS]\nFLOW_ROUTING DYNWAVE\n")
    with pytest.raises(ValueError):
        runtime.apply_trim(p, 6)


# ── the corpus and the workflows ───────────────────────────────────────────

def test_every_ci_runtime_override_is_explained_and_positive():
    from harness import corpus
    for case in corpus.load():
        ci = case.meta.get("ci_runtime")
        if not ci:
            continue
        assert float(ci["duration_h"]) > 0, case.id
        assert len(str(ci.get("reason", "")).strip()) >= 10, (
            f"{case.id}: an unexplained trim is indistinguishable from a "
            "mistake six months later")


def test_trimmed_cases_actually_shorten_what_was_measured():
    """A trim on a case that was never slow is dead weight; one that does not
    shorten the run does not help."""
    from harness import corpus
    led = runtime.load()
    for case in corpus.load():
        if not case.meta.get("ci_runtime"):
            continue
        entry = runtime.measured(led, "parity", case.id)
        assert entry, (f"{case.id} carries a ci_runtime trim but has no "
                       "measurement justifying it")
        assert entry["wall_s"] > runtime.DEFAULT_MAX_WALL_S, (
            f"{case.id} is trimmed but measured only {entry['wall_s']}s")


@pytest.mark.parametrize("wf,job", [("nightly.yml", "sweep"),
                                    ("on_engine_push.yml", "sweep"),
                                    ("validate.yml", "smoke")])
def test_every_workflow_passes_the_runtime_gate(wf, job):
    """The gate is explicit in the YAML, not inferred from an env var: a local
    run reproduces CI by passing the same flag."""
    p = REPO_ROOT / ".github" / "workflows" / wf
    spec = yaml.safe_load(p.read_text(encoding="utf-8"))
    runs = " ".join(s.get("run", "") for s in spec["jobs"][job]["steps"])
    assert f"--max-wall {int(runtime.DEFAULT_MAX_WALL_S)}" in runs, (
        f"{wf}:{job} does not bound its runtime")
