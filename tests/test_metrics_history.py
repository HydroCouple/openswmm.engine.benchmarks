"""Dashboard statistics and the per-run history records behind Trends."""
from __future__ import annotations

import json

import pytest

from harness import history, metrics


def env(cells, platform="Linux", suite="parity", run_id="1", started="2026-11-22T07:00:00+00:00"):
    return {"suite": suite, "engine_sha": "abc", "timestamp": "2026-11-22T07:00:00",
            "platform": platform, "cells": cells,
            "_run": {"id": run_id, "started": started, "engine": {"sha": "abc"}}}


def run(case, solver, verdict="PASS", wall=1.0, **kw):
    return {"case": case, "solver": solver, "verdict": verdict, "wall": wall,
            "reference_class": "self_consistency", **kw}


@pytest.mark.parametrize("note, family", [
    ("ERROR 211: invalid number 3.5x at line 12 of [XSECTIONS] section:",
     "ERROR #: invalid number #x"),
    ("ERROR 209: undefined object 'J1'.; ERROR 209: undefined object 'J2'.",
     "ERROR #: undefined object '…'."),
    ("CI trim: simulated period shortened to 48 h (ends 01/03/2020 00:00:00); timeout after 600s",
     "timeout after #s"),
])
def test_one_cause_is_one_family(note, family):
    assert metrics.note_family({"verdict": "ERROR", "note": note}) == family


def test_a_baseline_cell_without_a_note_is_grouped_by_suite():
    c = {"verdict": "BASELINE-FAIL", "_suite": "uk_river"}
    assert metrics.note_family(c) == "BASELINE-FAIL in uk_river (no note)"


def test_speed_ratio_ignores_runs_dominated_by_start_up():
    cells = metrics.cells_of([env([
        run("tiny", "swmm-5.3.0", wall=0.01), run("tiny", "openswmm-v6", wall=0.05),
        run("big", "swmm-5.3.0", wall=10.0), run("big", "openswmm-v6", wall=5.0)])])
    pts = metrics.speed_points(cells)["Linux"]
    assert len(pts) == 2
    rs = metrics.ratio_summary(pts)
    assert rs["n"] == 1 and rs["left_out"] == 1
    assert rs["median"] == pytest.approx(0.5) and rs["faster"] == 1


def test_trimmed_runs_stay_out_of_the_engine_comparison():
    cells = metrics.cells_of([env([run("c", "swmm-5.3.0", wall=4.0, trimmed=True),
                                   run("c", "openswmm-v6", wall=5.0, trimmed=True)])])
    assert metrics.speed_points(cells) == {}


def test_continuity_discloses_the_by_design_cases():
    cells = metrics.cells_of([env([
        run("a", "openswmm-v6", continuity_err=-3.0),
        run("b", "openswmm-v6", continuity_err=40.0, expected_high_continuity=True)])])
    c = metrics.continuity(cells)
    assert c["by_design"] == 1 and abs(c["worst"][0]["continuity_err"]) == 3.0


def test_platform_agreement_counts_identical_outputs():
    lin = env([run("c1", "openswmm-v6", out_sha16="aa", wall=2.0),
               run("c2", "openswmm-v6", out_sha16="bb", wall=2.0)])
    win = env([run("c1", "openswmm-v6", out_sha16="aa", wall=4.0),
               run("c2", "openswmm-v6", "ERROR", out_sha16=None, wall=0.01)], platform="Windows")
    ag = metrics.agreement(metrics.cells_of([lin, win]))
    e = ag["engines"]["openswmm-v6"]
    assert ag["platforms"] == ["Linux", "Windows"]
    assert e["both"] == 2 and e["verdict_agree"] == 1
    assert e["hashed"] == 1 and e["identical"] == 1
    assert e["wall_ratio_median"] == pytest.approx(2.0)
    assert [d[1] for d in ag["differ"]] == ["c2"]


def test_bins_cover_every_value():
    assert metrics.bin_counts([0.05, 0.1, 5, 400], [0.1, 1, 300]) == [1, 1, 1, 1]
    assert metrics.bin_labels([0.1, 1]) == ["< 0.1", "0.1–1", "≥ 1"]


def test_a_history_record_aggregates_across_shards():
    shards = [env([run("a", "openswmm-v6", wall=1.0, pct_not_converging=0.0)]),
              env([run("b", "openswmm-v6", wall=3.0, pct_not_converging=5.0),
                   run("c", "openswmm-v6", "ERROR", wall=0.01)])]
    for i, e in enumerate(shards):
        e["shard"] = f"{i + 1}/2"
    (rec,) = history.summarize(shards)
    (g,) = rec["groups"]
    assert (g["suite"], g["platform"], g["cells"], g["gating"]) == ("parity", "Linux", 3, 1)
    s = g["engines"]["openswmm-v6"]
    assert s["runs"] == 3 and s["passed"] == 2
    assert s["wall_total"] == pytest.approx(4.0) and s["wall_median"] == pytest.approx(2.0)
    assert s["stable_pct"] == pytest.approx(50.0)


def test_history_keeps_workflow_runs_only_and_rewrites_in_place(tmp_path):
    recs = history.summarize([env([run("a", "openswmm-v6")], run_id="77"),
                              env([run("a", "openswmm-v6")], run_id="local-20261122T070000")])
    written = history.write(recs, tmp_path)
    assert [p.name for p in written] == ["77.json"]
    history.write(recs, tmp_path)
    assert len(list((tmp_path / "runs").glob("*.json"))) == 1, "republishing must not duplicate"
    loaded = history.load(tmp_path)
    assert [r["id"] for r in loaded] == ["77"]
    assert json.loads((tmp_path / "runs" / "77.json").read_text(encoding="utf-8"))["schema"] == 1
