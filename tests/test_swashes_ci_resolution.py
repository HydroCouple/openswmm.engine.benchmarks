"""SWASHES at the nightly CI resolution (owner 2026-11-22: coarse nightly,
full resolution weekly).

The McDonald cases cost 5-70 min per solver at 1 m. With --ci-resolution the
cases that carry a ``ci_nx`` run at it, graded as a regression check against
a CI-resolution pin -- their verdicts move with resolution, so a coarse run is
never presented as the analytic verdict.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from suites.analytical.swashes.swasheslib import config, extract, runcase  # noqa: E402
from suites.analytical.swashes.swasheslib.genrefs import all_cases  # noqa: E402

SLOW = {"macdonald-long-sub", "macdonald-long-sup", "macdonald-long-sub2sup",
        "macdonald-long-jump", "macdonald-periodic", "macdonald-rain-sub",
        "macdonald-rain-sup"}


def _case(cid):
    return next(c for c in all_cases() if c.id == cid)


def _profile(h):
    x = np.linspace(0.5, 9.5, len(h))
    return {"times": {100.0: {"x_h": x, "h": np.asarray(h, float),
                              "x_q": x, "q": np.ones(len(h))}}}


def test_only_the_slow_cases_run_coarse_on_ci():
    coarse = {c.id: c for c in all_cases() if c.ci_nx}
    assert set(coarse) == SLOW
    for c in coarse.values():
        assert c.ci_nx < c.nx and c.ci_nx in c.refine_nx, c.id


def test_a_ci_run_is_graded_against_its_ci_pin(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CASES_DIR", tmp_path)
    case = dataclasses.replace(_case("macdonald-long-sub"), id="c")
    policy = case.cells["1d-dynwave"]
    pin = tmp_path / "c" / "baselines" / "ci"
    pin.mkdir(parents=True)
    extract.write_extracted_csv(pin / "1d-dynwave.csv", _profile([1.0, 2.0, 3.0]))
    # a full-resolution pin beside it must not be the one used
    extract.write_extracted_csv(pin.parent / "1d-dynwave.csv", _profile([9.0, 9.0, 9.0]))

    same = runcase.ci_regression(case, "1d-dynwave", _profile([1.0, 2.0, 3.0]),
                                 policy, 0.0, 0.5)
    moved = runcase.ci_regression(case, "1d-dynwave", _profile([1.0, 2.5, 3.0]),
                                  policy, 0.0, 0.5)
    assert same[0] == "BASELINE-PASS"
    assert moved[0] == "BASELINE-FAIL"


def test_a_ci_run_without_a_pin_says_how_to_pin(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CASES_DIR", tmp_path)
    case = _case("macdonald-long-sub")
    verdict, reasons, _ = runcase.ci_regression(
        case, "1d-fv", _profile([1.0]), case.cells["1d-fv"], 0.0, 0.5)
    assert verdict == "BASELINE-FAIL"
    assert "pin-baseline --ci --case macdonald-long-sub --solver 1d-fv" in reasons[0]


def test_pinning_a_ci_run_reads_its_own_run_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CASES_DIR", tmp_path / "cases")
    monkeypatch.setattr(config, "RUNS_DIR", tmp_path / "runs")
    full = runcase._cell_dir("macdonald-long-sub", "1d-fv")
    coarse = runcase._cell_dir("macdonald-long-sub", "1d-fv", 200)
    (full / "extracted.csv").write_text("full\n", encoding="utf-8")
    (coarse / "extracted.csv").write_text("coarse\n", encoding="utf-8")
    runcase.pin_baseline("macdonald-long-sub", "1d-fv", ci=True)
    pinned = tmp_path / "cases" / "macdonald-long-sub" / "baselines" / "ci" / "1d-fv.csv"
    assert pinned.read_text(encoding="utf-8") == "coarse\n"


def test_shards_split_the_cells_exactly_and_spread_a_case(tmp_path, monkeypatch):
    """The weekly full-resolution sweep: every cell in exactly one shard, and
    one case's solvers in different shards (macdonald-periodic's six solvers
    are what make it hours long)."""
    monkeypatch.setattr(config, "SCORES_FILE", tmp_path / "full.json")
    ran = {}

    def fake_cell(case, solver, *, force=False, nx=None, ci=False):
        return {"case": case.id, "solver": solver.id, "verdict": "PASS"}

    monkeypatch.setattr(runcase, "run_cell", fake_cell)
    for k in (1, 2, 3, 4):
        monkeypatch.setattr(config, "SCORES_FILE", tmp_path / f"s{k}.json")
        env = runcase.run_matrix(case_glob="macdonald-*", shard=(k, 4))
        assert env["shard"] == f"{k}/4"
        ran[k] = {(c["case"], c["solver"]) for c in env["cells"]}
    every = set().union(*ran.values())
    assert sum(len(v) for v in ran.values()) == len(every)
    periodic = {k for k, cells in ran.items() if any(c == "macdonald-periodic" for c, _ in cells)}
    assert len(periodic) > 1


def test_the_ci_matrix_keeps_its_own_envelope(tmp_path, monkeypatch):
    """A local --ci-resolution run must not overwrite the full-resolution
    results, and every cell must be asked for its CI run."""
    monkeypatch.setattr(config, "SCORES_FILE", tmp_path / "full.json")
    monkeypatch.setattr(config, "CI_SCORES_FILE", tmp_path / "ci.json")
    monkeypatch.setattr(runcase, "all_cases", lambda: [_case("macdonald-long-sub")])
    asked = []

    def fake_cell(case, solver, *, force=False, nx=None, ci=False):
        asked.append(ci)
        return {"case": case.id, "solver": solver.id, "verdict": "PASS"}

    monkeypatch.setattr(runcase, "run_cell", fake_cell)
    runcase.run_matrix(solver_ids=["1d-fv"], ci_resolution=True)
    assert asked == [True]
    assert (tmp_path / "ci.json").exists() and not (tmp_path / "full.json").exists()
