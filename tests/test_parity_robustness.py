"""The three failure modes that killed the first real nightly sweep.

The 2026-08-23 nightly is the reference incident:

* **Windows** never ran at all — the build asked ninja for `openswmm-legacy`,
  which is the binary's OUTPUT_NAME, not the CMake target `openswmm_legacy`.
* **Linux** built and started, then died on case
  `greenville-small-snowmelt-model` with a `FileNotFoundError` raised deep
  inside `compare_full`, because the legacy engine exited 0 without writing a
  `.out`. Every case after it was lost, and the partial envelope that survived
  looked like a finished run.

The underlying model writes `SAVE RAINFALL "greenville.rff"` — a bare
filename, resolved against the process working directory, which was the repo
root rather than anywhere the model intended.

These tests pin all three fixes: seeded run directories, output verified
rather than assumed, and per-case exception isolation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from suites.parity import suite  # noqa: E402
from tests.outfixture import write_out  # noqa: E402


class FakeCase:
    """Minimal stand-in for harness.corpus.Case."""

    def __init__(self, d: Path, case_id="c1", tags=frozenset(), meta=None):
        self.dir = d
        self.id = case_id
        self.tags = set(tags)
        self.meta = meta or {}
        self.reference_class = "self_consistency"

    @property
    def inp(self):
        return self.dir / "model.inp"

    def tolerances(self, rtol, atol):
        return rtol, atol


@pytest.fixture
def case(tmp_path):
    d = tmp_path / "corpus" / "coll" / "c1"
    d.mkdir(parents=True)
    (d / "model.inp").write_text("[TITLE]\ntest\n", encoding="utf-8")
    (d / "rain.dat").write_text("0 0\n", encoding="utf-8")       # colocated data
    (d / "metadata.yaml").write_text("id: c1\n", encoding="utf-8")
    (d / "provenance.yaml").write_text("source: test\n", encoding="utf-8")
    ref = d / "reference"
    ref.mkdir()
    (ref / "legacy.rpt").write_text("evidence\n", encoding="utf-8")
    return FakeCase(d)


# ── seeded run directory ───────────────────────────────────────────────────

def test_run_dir_is_seeded_with_model_and_data(case, tmp_path):
    """Relative references only resolve if the data travels with the model."""
    run_dir = tmp_path / "run"
    model = suite._seed_run_dir(case, run_dir)
    assert model == run_dir / "model.inp" and model.exists()
    assert (run_dir / "rain.dat").exists(), "colocated data was not seeded"


def test_run_dir_excludes_metadata_and_reference(case, tmp_path):
    """Only model inputs belong in the run directory. `reference/` is evidence
    and can be large; metadata describes the case, it does not feed the engine."""
    run_dir = tmp_path / "run"
    suite._seed_run_dir(case, run_dir)
    assert not (run_dir / "metadata.yaml").exists()
    assert not (run_dir / "provenance.yaml").exists()
    assert not (run_dir / "reference").exists()


def test_seeding_never_writes_into_the_corpus(case, tmp_path):
    """A sweep must not mutate the library it is measuring."""
    before = sorted(p.name for p in case.dir.rglob("*"))
    suite._seed_run_dir(case, tmp_path / "run")
    assert sorted(p.name for p in case.dir.rglob("*")) == before


def test_seeding_is_idempotent(case, tmp_path):
    """Re-running a case must not fail on files already seeded."""
    run_dir = tmp_path / "run"
    suite._seed_run_dir(case, run_dir)
    suite._seed_run_dir(case, run_dir)          # must not raise
    assert (run_dir / "rain.dat").exists()


# ── output verification ────────────────────────────────────────────────────

def test_missing_output_is_not_usable(tmp_path):
    ok, why = suite._usable_output(tmp_path / "absent.out")
    assert ok is False
    assert "wrote no .out" in why


def test_truncated_output_is_not_usable(tmp_path):
    p = tmp_path / "t.out"
    p.write_bytes(b"\x00" * 8)
    ok, why = suite._usable_output(p)
    assert ok is False
    assert "truncated" in why


def test_corrupt_output_is_not_usable(tmp_path):
    """A file of the right size but the wrong content must be rejected here,
    not by an exception thrown from inside the comparison."""
    p = tmp_path / "bad.out"
    p.write_bytes(b"\x01" * 512)
    ok, why = suite._usable_output(p)
    assert ok is False
    assert "unreadable" in why


def test_valid_output_is_usable(tmp_path):
    p = write_out(tmp_path / "good.out")
    ok, why = suite._usable_output(p)
    assert ok is True and why == ""


def test_exit_zero_without_output_is_not_ok(case, tmp_path, monkeypatch):
    """The exact Linux failure: the engine reports success and delivers
    nothing. The run must be marked not-ok so the comparison is never
    attempted."""
    def fake_run(exe, inp, rpt, out, **kw):
        Path(rpt).write_text("ERROR 138: invalid elevation\n", encoding="utf-8")
        return {"ok": True, "launched": True, "returncode": 0,
                "wall": 0.1, "stderr": ""}

    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "swmm-5.3.0"})()
    info = suite._run_case(case, engine, tmp_path / "run", timeout=10)

    assert info["produced_output"] is False
    assert info["ok"] is False, "exit 0 with no output must not count as success"
    assert "ERROR 138" in info["stderr"], (
        "the engine's own explanation should be preferred over ours")


def test_engine_explanation_falls_back_when_report_is_silent(case, tmp_path,
                                                             monkeypatch):
    def fake_run(exe, inp, rpt, out, **kw):
        Path(rpt).write_text("nothing useful\n", encoding="utf-8")
        return {"ok": True, "launched": True, "returncode": 0,
                "wall": 0.1, "stderr": ""}

    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "e"})()
    info = suite._run_case(case, engine, tmp_path / "run", timeout=10)
    assert info["ok"] is False
    assert "wrote no .out" in info["stderr"]


def test_successful_run_reports_produced_output(case, tmp_path, monkeypatch):
    def fake_run(exe, inp, rpt, out, **kw):
        Path(rpt).write_text("  Flow Routing Continuity\n", encoding="utf-8")
        write_out(Path(out))
        return {"ok": True, "launched": True, "returncode": 0,
                "wall": 0.1, "stderr": ""}

    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "e"})()
    info = suite._run_case(case, engine, tmp_path / "run", timeout=10)
    assert info["ok"] is True and info["produced_output"] is True


def test_run_uses_the_seeded_model_and_run_dir_as_cwd(case, tmp_path,
                                                      monkeypatch):
    """The model handed to the engine must be the seeded copy, and cwd must be
    the run directory — otherwise bare-filename references miss."""
    seen = {}

    def fake_run(exe, inp, rpt, out, **kw):
        seen["inp"] = Path(inp)
        seen["cwd"] = kw.get("cwd")
        write_out(Path(out))
        Path(rpt).write_text("x\n", encoding="utf-8")
        return {"ok": True, "launched": True, "returncode": 0,
                "wall": 0.1, "stderr": ""}

    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "e"})()
    run_dir = tmp_path / "run"
    suite._run_case(case, engine, run_dir, timeout=10)

    assert seen["inp"] == run_dir / "model.inp"
    assert Path(seen["cwd"]) == run_dir
    assert seen["inp"] != case.inp, "the corpus copy must not be run in place"


# ── sweep isolation ────────────────────────────────────────────────────────

def test_one_exploding_case_does_not_end_the_sweep(tmp_path, monkeypatch):
    """The property the lost nightly was missing.

    `_sweep_case` raising must produce an ERROR cell and let the sweep carry
    on to every remaining case.
    """
    from harness import scoring

    envelope = scoring.new_envelope("parity", "sha")
    scores = tmp_path / "scores.json"
    seen = []

    def exploding(case, *a, **kw):
        seen.append(case.id)
        if case.id == "boom":
            raise FileNotFoundError("no such .out")
        return False

    cases = [FakeCase(tmp_path, "before"), FakeCase(tmp_path, "boom"),
             FakeCase(tmp_path, "after")]

    for case in cases:
        try:
            exploding(case)
        except Exception as exc:
            scoring.save_cell(scores, envelope, {
                "case": case.id, "solver": "-",
                "reference_class": case.reference_class, "verdict": "ERROR",
                "note": f"harness error, sweep continued: "
                        f"{type(exc).__name__}: {exc}"})

    assert seen == ["before", "boom", "after"], "the sweep stopped early"
    errors = [c for c in envelope["cells"] if c["verdict"] == "ERROR"]
    assert len(errors) == 1 and errors[0]["case"] == "boom"
    assert "sweep continued" in errors[0]["note"]


def test_sweep_isolation_is_wired_into_run():
    """Guard the wiring, not just the concept: run() must call _sweep_case
    inside a try/except that records a cell and keeps going."""
    src = (REPO_ROOT / "suites" / "parity" / "suite.py").read_text(encoding="utf-8")
    body = src.split("def run(")[1].split("\ndef ")[0]
    assert "_sweep_case(" in body
    assert "except Exception" in body
    assert "sweep continued" in body


# ── the Windows build target ───────────────────────────────────────────────

def test_build_action_uses_the_cmake_target_not_the_output_name():
    """`openswmm-legacy` is the binary's OUTPUT_NAME; `openswmm_legacy` is the
    CMake target. Ninja Multi-Config on Windows rejects the former outright,
    which is why the Windows leg never ran."""
    action = REPO_ROOT / ".github" / "actions" / "build-engine" / "action.yml"
    if not action.exists():
        pytest.skip("build-engine action not present")
    build = [ln for ln in action.read_text(encoding="utf-8").splitlines()
             if "cmake --build" in ln]
    assert build, "no cmake --build step found"
    line = build[0]
    assert "openswmm_legacy" in line
    assert "--target openswmm openswmm-legacy" not in line
