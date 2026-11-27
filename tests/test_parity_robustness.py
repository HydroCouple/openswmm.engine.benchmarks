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


@pytest.mark.parametrize("report, expected", [
    ("  ERROR 133: Node 11 has more than one outlet link.\n", "ERROR 133"),
    ("nothing useful\n", "exit code 5"),
])
def test_nonzero_exit_without_stderr_still_says_why(case, tmp_path,
                                                    monkeypatch, report,
                                                    expected):
    """openswmm-v6 rejects a model with exit 5 and a silent stderr; its
    reasons are only in the .rpt. 979 Windows and 56 Linux nightly ERROR cells
    carried an empty note this way."""
    def fake_run(exe, inp, rpt, out, **kw):
        Path(rpt).write_text(report, encoding="utf-8")
        return {"ok": False, "launched": True, "returncode": 5,
                "wall": 0.1, "stderr": ""}

    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "openswmm-v6"})()
    info = suite._run_case(case, engine, tmp_path / "run", timeout=10)
    assert info["ok"] is False
    assert expected in info["stderr"]


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


# ── sharding ───────────────────────────────────────────────────────────────

def test_shards_partition_the_selection(tmp_path, monkeypatch):
    """--shard K/N: the N nightly jobs together run every case exactly once."""
    from types import SimpleNamespace
    ids = [f"c{i:02d}" for i in range(10)]
    monkeypatch.setattr(suite, "RESULTS", tmp_path / "runs")
    monkeypatch.setattr(suite, "_manifest", lambda tier: {})
    monkeypatch.setattr(suite, "_skip_list", lambda: set())
    monkeypatch.setattr(suite.corpus, "load",
                        lambda: [FakeCase(tmp_path, i) for i in ids])
    monkeypatch.setattr(suite.corpus, "select", lambda cases, expr, tier: cases)
    monkeypatch.setattr(suite.engines, "load", lambda: None)
    monkeypatch.setattr(suite.engines, "resolve_all",
                        lambda *a, **k: SimpleNamespace(resolved=lambda: {}))
    monkeypatch.setattr(suite.engines, "engine_sha", lambda: "sha")
    monkeypatch.setattr(suite.runtime, "load", lambda: {"suites": {}})
    ran: list[str] = []
    monkeypatch.setattr(suite, "_sweep_case",
                        lambda case, *a, **k: ran.append(case.id))

    shards = []
    for k in (1, 2, 3):
        ran.clear()
        env = suite.run(["--tier", "nightly", "--shard", f"{k}/3"])
        assert env["shard"] == f"{k}/3"
        shards.append(list(ran))
    assert sorted(sum(shards, [])) == ids
    assert shards[0] == ["c00", "c03", "c06", "c09"], "shards must interleave"


@pytest.mark.parametrize("bad", ["0/4", "5/4", "2", "a/b"])
def test_a_malformed_shard_is_rejected(bad):
    with pytest.raises(SystemExit):
        suite.run(["--shard", bad])


def test_exclude_drops_a_suite_and_rejects_a_typo(monkeypatch):
    """The nightly 'rest' job runs --suite all --exclude parity; a misspelled
    exclusion must fail loudly, not quietly run the 5-hour suite again."""
    from types import SimpleNamespace
    import run_regression
    ran: list[str] = []
    monkeypatch.setattr(run_regression.suites, "list_suites",
                        lambda: ["coupling", "parity", "uk_2d"])
    monkeypatch.setattr(
        run_regression.suites, "discover",
        lambda names: {n: SimpleNamespace(run=lambda argv, n=n: ran.append(n),
                                          report=lambda argv: [])
                       for n in names})
    assert run_regression.main(["--suite", "all", "--exclude", "parity"]) == 0
    assert ran == ["coupling", "uk_2d"]
    assert run_regression.main(["--suite", "all", "--exclude", "partiy"]) == 2


@pytest.mark.parametrize("report_only", [False, True])
def test_nightly_ci_resolution_reaches_only_swashes(monkeypatch, report_only):
    from types import SimpleNamespace
    import run_regression
    from suites.uk_2d import suite as uk_2d
    from suites.uk_river import suite as uk_river

    calls = []

    def recorder(name, phase):
        def record(argv):
            if name in {"uk_2d", "uk_river"}:
                parser = uk_2d.options if name == "uk_2d" else uk_river.options
                assert parser(argv).max_wall == 300
            calls.append((name, phase, "--ci-resolution" in argv))
        return record

    names = ["uk_2d", "uk_river", "analytical/swashes"]
    mods = {n: SimpleNamespace(run=recorder(n, "run"), report=recorder(n, "report"))
            for n in names}
    monkeypatch.setattr(run_regression.suites, "list_suites", lambda: ["parity", *names])
    monkeypatch.setattr(run_regression.suites, "discover", lambda selected: mods)
    args = ["--suite", "all", "--exclude", "parity", "--ci-resolution", "--tier", "nightly",
            "--max-wall", "300"]
    if report_only:
        args.append("--report-only")
    assert run_regression.main(args) == 0
    phases = ["report"] if report_only else ["run", "report"]
    assert calls == [(n, phase, n == "analytical/swashes") for n in names for phase in phases]


@pytest.mark.parametrize("failure, phase", [(ValueError("no positive root"), "run"),
                                            (SystemExit(2), "run"), (SystemExit(2), "report")])
def test_a_crashing_suite_fails_the_run_but_not_the_suites_after_it(
        monkeypatch, tmp_path, failure, phase):
    """The 2026-11-22 Nightly's other-suites job died inside the SWASHES
    reference generator, and transitions and reactions never ran. A crash is a
    failed run, and the summary names the suite; it is not the end of the
    run."""
    from types import SimpleNamespace
    import run_regression
    ran: list[str] = []

    def boom(argv):
        raise failure

    mods = {
        "coupling": SimpleNamespace(run=lambda argv: ran.append("coupling"),
                                    report=lambda argv: []),
        "analytical/swashes": SimpleNamespace(run=boom if phase == "run" else lambda argv: None,
                                              report=boom if phase == "report" else lambda argv: []),
        "transitions": SimpleNamespace(run=lambda argv: ran.append("transitions"),
                                       report=lambda argv: []),
    }
    monkeypatch.setattr(run_regression.suites, "list_suites", lambda: list(mods))
    monkeypatch.setattr(run_regression.suites, "discover",
                        lambda names: {n: mods[n] for n in names})
    summary = tmp_path / "summary.md"
    assert run_regression.main(["--suite", "all", "--summary", str(summary)]) == 1
    assert ran == ["coupling", "transitions"]
    assert (f"analytical/swashes: {type(failure).__name__}: {failure}"
            in summary.read_text(encoding="utf-8"))


def test_every_suite_accepts_the_options_nightly_forwards():
    """run_regression.py hands its extra options to EVERY suite. One suite
    rejecting another's --tier (coupling did, with SystemExit 2) ends
    `--suite all` there, before any later suite runs."""
    import importlib
    from harness import suites as registry
    forwarded = ["--tier", "nightly", "--max-wall", "300.0"]
    rejecting = []
    for name in registry.list_suites():
        mod = importlib.import_module("suites." + name.replace("/", ".") + ".suite")
        if not hasattr(mod, "options"):
            continue                     # parses inside run(); not probed here
        try:
            mod.options(list(forwarded))
        except SystemExit:
            rejecting.append(name)
    assert not rejecting, f"suites that reject forwarded options: {rejecting}"


# ── CI wiring ──────────────────────────────────────────────────────────────

def _workflow(name):
    import yaml
    p = REPO_ROOT / ".github" / "workflows" / name
    if not p.exists():
        pytest.skip(f"{name} not present")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("wf", ["nightly.yml", "on_engine_push.yml"])
def test_the_gate_actually_gates(wf):
    """`continue-on-error` on the sweep exists so artifacts upload and the
    dashboard publishes on failure. Without a gate step afterwards the job then
    concludes SUCCESS, and the workflow badge is green while parity is failing.
    """
    steps = _workflow(wf)["jobs"]["sweep"]["steps"]
    sweep = [s for s in steps if s.get("id") == "sweep"]
    assert sweep, "the sweep step needs an id for the gate to reference"
    if not sweep[0].get("continue-on-error"):
        return                       # no masking, nothing to re-raise
    gate = [s for s in steps if "outcome == 'failure'" in str(s.get("if", ""))]
    assert gate, f"{wf}: sweep failure is masked and never re-raised"
    assert "exit 1" in gate[0]["run"]
    # the gate must come after the upload, or a failing sweep loses its evidence
    names = [s.get("name") or str(s.get("uses", "")) for s in steps]
    assert names.index(gate[0]["name"]) > \
        max(i for i, n in enumerate(names) if "upload-artifact" in n)


@pytest.mark.parametrize("wf", ["nightly.yml", "on_engine_push.yml"])
def test_publish_runs_even_when_the_sweep_fails(wf):
    """A skipped publish leaves the previous dashboard up, so a broken run is
    indistinguishable from a healthy one (F20)."""
    pub = _workflow(wf)["jobs"].get("publish")
    assert pub, f"{wf} has no publish job"
    assert "always()" in str(pub.get("if", "")), (
        f"{wf}: publish is skipped when the sweep fails")


@pytest.mark.parametrize("wf", ["nightly.yml", "on_engine_push.yml"])
def test_publish_is_told_which_run_holds_the_results(wf):
    """Inside a reusable workflow github.event_name is the CALLER's event, so
    publish cannot tell a Nightly call from a stand-alone dispatch by it: a
    Nightly started by hand published the PREVIOUS night's artifacts (run
    44981179237). The caller names its run instead."""
    pub = _workflow(wf)["jobs"]["publish"]
    assert pub.get("with", {}).get("run_id") == "${{ github.run_id }}", (
        f"{wf}: publish is not told which run to download")
    publish = _workflow("publish.yml")
    triggers = publish.get("on", publish.get(True))   # YAML 1.1 reads `on` as true
    assert triggers["workflow_call"]["inputs"]["run_id"]["required"] is True


def test_every_job_has_an_explicit_timeout():
    """The 6h default silently cancels a job, and a cancellation reads as
    infrastructure noise rather than a result."""
    missing = []
    for wf in ("nightly.yml", "on_engine_push.yml", "validate.yml", "publish.yml"):
        for jn, j in _workflow(wf)["jobs"].items():
            if "uses" in j:          # reusable-workflow call: the callee sets it
                continue
            if not j.get("timeout-minutes"):
                missing.append(f"{wf}:{jn}")
    assert not missing, f"jobs without an explicit timeout: {missing}"


# ── disk reclamation ───────────────────────────────────────────────────────

def _make_run_tree(root: Path, case_id: str, out_bytes: int = 4096) -> Path:
    """A per-case run tree as the sweep leaves it: seeded inputs + .rpt + .out."""
    d = root / case_id
    for engine in ("openswmm-v6", "swmm-5.3.0"):
        e = d / engine
        e.mkdir(parents=True)
        (e / "model.inp").write_text("[TITLE]\nx\n", encoding="utf-8")
        (e / "rain.dat").write_text("0 0\n", encoding="utf-8")
        (e / f"{case_id}.rpt").write_text("report\n", encoding="utf-8")
        (e / f"{case_id}.out").write_bytes(b"\0" * out_bytes)
    return d


def test_a_passing_case_leaves_nothing_behind(tmp_path):
    """The envelope already holds every metric; the tree is disposable."""
    d = _make_run_tree(tmp_path, "c1")
    r = suite._Reclaimer(keep="fail")
    r.finish_case(d, failed=False)
    assert not d.exists()
    assert r.reclaimed > 0 and r.retained == 0


def test_seeded_inputs_are_reclaimed_too(tmp_path):
    """The seeded model and its data are copies, one per engine. Left behind
    they accumulate to ~4 GiB over the corpus — on a ~14 GiB runner."""
    d = _make_run_tree(tmp_path, "c1")
    suite._Reclaimer(keep="fail").finish_case(d, failed=False)
    assert not (d / "openswmm-v6" / "model.inp").exists()
    assert not (d / "openswmm-v6" / "rain.dat").exists()


def test_a_failing_case_is_retained_for_triage(tmp_path):
    d = _make_run_tree(tmp_path, "c1")
    r = suite._Reclaimer(keep="fail")
    r.finish_case(d, failed=True)
    assert d.exists(), "the evidence a human drills into must survive"
    assert r.retained > 0 and r.reclaimed == 0


def test_keep_none_discards_even_failures(tmp_path):
    d = _make_run_tree(tmp_path, "c1")
    r = suite._Reclaimer(keep="none")
    r.finish_case(d, failed=True)
    assert not d.exists()


def test_keep_all_retains_even_passes(tmp_path):
    d = _make_run_tree(tmp_path, "c1")
    r = suite._Reclaimer(keep="all")
    r.finish_case(d, failed=False)
    assert d.exists()


def test_retention_is_bounded_by_the_budget(tmp_path):
    """Retention exists for triage, but a sweep with many failures must not be
    able to fill the volume it is running on."""
    r = suite._Reclaimer(keep="fail", budget=20_000)
    for i in range(20):
        r.finish_case(_make_run_tree(tmp_path, f"c{i}", out_bytes=8192),
                      failed=True)
    assert r.retained <= 20_000, "budget breached"
    assert r.over_budget is True
    assert r.reclaimed > 0, "later failures must be reclaimed, not hoarded"


@pytest.mark.skipif(sys.platform == "win32",
                    reason="Windows cannot create the file this test needs")
def test_retained_evidence_gets_names_an_artifact_upload_accepts(tmp_path):
    """The legacy engine writes whatever file a deck names, verbatim: on Linux
    `F:\\2016PC\\November, 2013 Models\\A1 Podium RainBarrel.txt` is one file
    name. GitHub's artifact upload refuses a colon anywhere in a path, so three
    of four Linux parity shards swept to the end on 2026-11-22 and then lost
    every result at the upload."""
    d = _make_run_tree(tmp_path, "c1")
    stray = d / "swmm-5.3.0" / "F:\\2016PC\\November, 2013 Models\\A1 Podium RainBarrel.txt"
    stray.write_text("rain\n", encoding="utf-8")
    suite._Reclaimer(keep="fail").finish_case(d, failed=True)
    names = [p.name for p in d.rglob("*") if p.is_file()]
    assert not any(set('":<>|*?\\') & set(n) for n in names), names
    assert "F__2016PC_November, 2013 Models_A1 Podium RainBarrel.txt" in names
    assert (d / "swmm-5.3.0" / "c1.rpt").exists(), "ordinary evidence is untouched"


def test_working_set_stays_flat_across_many_passing_cases(tmp_path):
    """The property the whole design exists for: disk does not grow with the
    number of cases swept."""
    r = suite._Reclaimer(keep="fail")
    for i in range(50):
        r.finish_case(_make_run_tree(tmp_path, f"c{i}"), failed=False)
    leftover = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert leftover == [], f"{len(leftover)} files survived a clean sweep"


def test_reclaimer_is_wired_into_the_sweep():
    """Guard the wiring: the concept passing while the call is absent is
    exactly how unbounded growth returns."""
    src = (REPO_ROOT / "suites" / "parity" / "suite.py").read_text(encoding="utf-8")
    assert "reclaimer.finish_case(" in src
    assert "_prune_outputs" not in src, "the .out-only pruner should be gone"


def test_disk_totals_are_recorded_on_the_envelope():
    """A sweep should be able to prove its own footprint."""
    src = (REPO_ROOT / "suites" / "parity" / "suite.py").read_text(encoding="utf-8")
    assert 'envelope["disk"]' in src
    assert "reclaimed_bytes" in src and "retained_bytes" in src


def test_a_case_with_no_evidence_is_reclaimed_even_when_failed(tmp_path):
    """UNAVAILABLE cases produce only the seeded inputs — a copy of something
    already in corpus/. Retaining them re-creates the ~4 GiB of duplicated
    models this reclaimer exists to prevent, and there is nothing to drill
    into anyway."""
    d = tmp_path / "c1" / "openswmm-v6"
    d.mkdir(parents=True)
    (d / "model.inp").write_text("[TITLE]\nx\n", encoding="utf-8")
    (d / "rain.dat").write_text("0 0\n", encoding="utf-8")

    r = suite._Reclaimer(keep="fail")
    r.finish_case(tmp_path / "c1", failed=True)
    assert not (tmp_path / "c1").exists()
    assert r.retained == 0


def test_a_failed_case_with_a_report_is_still_retained(tmp_path):
    """A .rpt alone IS evidence — it carries the continuity and stability
    numbers and the engine's own error text."""
    d = tmp_path / "c1" / "openswmm-v6"
    d.mkdir(parents=True)
    (d / "model.inp").write_text("[TITLE]\nx\n", encoding="utf-8")
    (d / "c1.rpt").write_text("ERROR 138\n", encoding="utf-8")

    r = suite._Reclaimer(keep="fail")
    r.finish_case(tmp_path / "c1", failed=True)
    assert (tmp_path / "c1").exists()
    assert r.retained > 0


def test_callers_grant_every_permission_the_reusable_workflow_requests():
    """A reusable workflow cannot request more than its caller grants.

    This is not a runtime error — GitHub rejects the entire workflow file:

        Error calling workflow '.../publish.yml'. The workflow is requesting
        'actions: read', but is only allowed 'actions: none'.

    So the nightly does not merely fail to publish; it does not run at all.
    Adding a permission to publish.yml therefore requires adding it to every
    caller in the same change.
    """
    import yaml
    rank = {"none": 0, "read": 1, "write": 2}
    callee_path = REPO_ROOT / ".github" / "workflows" / "publish.yml"
    if not callee_path.exists():
        pytest.skip("publish.yml not present")
    needs = yaml.safe_load(callee_path.read_text(encoding="utf-8"))["permissions"]

    problems = []
    for wf in ("nightly.yml", "on_engine_push.yml"):
        p = REPO_ROOT / ".github" / "workflows" / wf
        if not p.exists():
            continue
        for job_name, job in yaml.safe_load(p.read_text(encoding="utf-8"))["jobs"].items():
            if "publish.yml" not in str(job.get("uses", "")):
                continue
            granted = job.get("permissions") or {}
            for scope, need in needs.items():
                have = granted.get(scope, "none")
                if rank[have] < rank[need]:
                    problems.append(
                        f"{wf}:{job_name} grants {scope}={have!r}, "
                        f"publish.yml requests {need!r}")
    assert not problems, "; ".join(problems)


@pytest.mark.parametrize("mode,run_verdict,pair_verdict", [
    ("expected", "XFAIL", "XFAIL"),
    ("different", "ERROR", "UNAVAILABLE"),
    ("unavailable", "UNAVAILABLE", "UNAVAILABLE"),
    ("timeout", "ERROR", "UNAVAILABLE"),
    ("accepted", "XPASS", "PASS"),
])
def test_expected_input_rejection_requires_its_diagnostic(
        case, tmp_path, monkeypatch, mode, run_verdict, pair_verdict):
    from types import SimpleNamespace
    from harness import scoring

    case.meta["expected_failures"] = [{
        "engine": "legacy", "reason": "unsupported authored cross section",
        "report_error": "ERROR 205: invalid keyword SEMI_ELLIPTICAL",
    }]
    monkeypatch.setattr(suite, "RESULTS", tmp_path / "runs")
    pair = SimpleNamespace(a="legacy", b="v6", rtol=1e-9, atol=1e-12, gate="fail")
    reg = SimpleNamespace(active_comparisons=lambda: [pair])
    resolved = {eid: SimpleNamespace(id=eid) for eid in ("legacy", "v6")}

    def fake_run(case, engine, out_dir, *args):
        out_dir.mkdir(parents=True, exist_ok=True)
        accepted = engine.id == "v6" or mode == "accepted"
        out = out_dir / "model.out"
        if accepted:
            write_out(out)
        error = ("ERROR 205: invalid keyword SEMI_ELLIPTICAL at line 10"
                 if mode in ("expected", "timeout") else "ERROR 209: undefined object X")
        return {"ok": accepted, "launched": mode != "unavailable" or engine.id == "v6",
                "produced_output": accepted, "out": out,
                "returncode": -9 if mode == "timeout" and not accepted else 0,
                "report_errors": [] if accepted or mode == "unavailable"
                                 else [error], "stderr": ""}

    monkeypatch.setattr(suite, "_run_case", fake_run)
    envelope = scoring.new_envelope("parity", "sha")
    suite._sweep_case(case, resolved, reg, tmp_path / "scores.json", envelope,
                      10, suite._Reclaimer(keep="none"))
    assert [c["verdict"] for c in envelope["cells"]] == [run_verdict, "PASS", pair_verdict]
    assert scoring.exit_code(envelope) == (0 if mode in ("expected", "unavailable") else 1)


def test_a_rejection_documented_for_every_engine_xfails_both(case, tmp_path, monkeypatch):
    """The F25 decks: both engines reject the same invalid keyword. With the
    entry scoped to one engine, the other's identical rejection gated."""
    from types import SimpleNamespace
    from harness import scoring

    case.meta["expected_failures"] = [{
        "engine": "*", "reason": "invalid authored keyword",
        "report_error": "ERROR 205: invalid keyword SEMI_ELLIPTICAL",
    }]
    monkeypatch.setattr(suite, "RESULTS", tmp_path / "runs")
    pair = SimpleNamespace(a="legacy", b="v6", rtol=1e-9, atol=1e-12, gate="fail")
    reg = SimpleNamespace(active_comparisons=lambda: [pair])
    resolved = {eid: SimpleNamespace(id=eid) for eid in ("legacy", "v6")}

    def fake_run(case, engine, out_dir, *args):
        out_dir.mkdir(parents=True, exist_ok=True)
        return {"ok": False, "launched": True, "produced_output": False,
                "out": out_dir / "model.out", "returncode": 0, "stderr": "",
                "report_errors": ["ERROR 205: invalid keyword SEMI_ELLIPTICAL."]}

    monkeypatch.setattr(suite, "_run_case", fake_run)
    envelope = scoring.new_envelope("parity", "sha")
    suite._sweep_case(case, resolved, reg, tmp_path / "scores.json", envelope,
                      10, suite._Reclaimer(keep="none"))
    assert [c["verdict"] for c in envelope["cells"]] == ["XFAIL", "XFAIL", "XFAIL"]
    assert scoring.exit_code(envelope) == 0


def test_readable_output_with_fatal_footer_is_not_usable(tmp_path):
    import struct
    p = write_out(tmp_path / 'fatal.out')
    data = bytearray(p.read_bytes())
    struct.pack_into('<i', data, len(data) - 8, 209)
    p.write_bytes(data)
    ok, why = suite._usable_output(p)
    assert not ok
    assert 'fatal error code 209' in why


def test_output_without_periods_is_not_usable(tmp_path):
    p = write_out(tmp_path / 'empty.out', n_periods=0)
    ok, why = suite._usable_output(p)
    assert not ok
    assert 'no reporting periods' in why


@pytest.mark.parametrize("diagnostic,ok", [
    ("WARNING 04: minimum elevation drop", True),
    ("WARNING 04: minimum elevation drop\nERROR 209: invalid object", False),
])
def test_fatal_report_wins_over_readable_output(case, tmp_path, monkeypatch,
                                                diagnostic, ok):
    def fake_run(exe, inp, rpt, out, **kw):
        Path(rpt).write_text(diagnostic + "\n", encoding="utf-8")
        write_out(Path(out))
        return {"ok": True, "launched": True, "returncode": 0,
                "wall": 0.1, "stderr": ""}
    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "e"})()
    info = suite._run_case(case, engine, tmp_path / "run", timeout=10)
    assert info["ok"] is ok
    assert info["produced_output"] is ok
    if not ok:
        assert info["stderr"].startswith("ERROR 209")


def test_failed_exit_cannot_supply_a_passing_comparison(case, tmp_path, monkeypatch):
    def fake_run(exe, inp, rpt, out, **kw):
        Path(rpt).write_text("interrupted\n", encoding="utf-8")
        write_out(Path(out))
        return {"ok": False, "launched": True, "returncode": 1,
                "wall": 0.1, "stderr": "run failed"}
    monkeypatch.setattr(suite.runner, "run", fake_run)
    engine = type("E", (), {"exe": Path("engine"), "id": "e"})()
    info = suite._run_case(case, engine, tmp_path / "run", timeout=10)
    assert not info["ok"]
    assert not info["produced_output"]


def test_output_paths_on_another_machines_drive_are_written_locally(tmp_path):
    """Legacy on Windows cannot open D:\\ (ERROR 351/305) while Linux writes a
    file literally named after the path, so the same deck errored on one
    platform and passed on the other (Nightly 45045451271: 30 cells). Only
    output columns of the seeded copy change; inputs stay as written."""
    deck = tmp_path / "model.inp"
    deck.write_bytes(
        b"[FILES]\r\n"
        b';;SAVE OUTFLOWS "D:\\commented\\out.txt"\r\n'
        b'SAVE Outflows/Calibration "D:\\SWMM\\OWA_EXTRAN\\Extran3.txt"\r\n'
        b'USE RAINFALL "C:\\data\\rain.dat"\r\n'
        b"\r\n[LID_USAGE]\r\n"
        b'wBC BC 100 50 10 0 25 0 "C:\\Xing\\LID\\drain_out.txt" woBC 2\r\n'
        b"CA-1 RB 10 1000 4 0 22 1 D:\\x\\CA-1_RB.txt\r\n")
    note = suite._localize_outputs(deck)
    text = deck.read_bytes()
    assert b'SAVE Outflows/Calibration "Extran3.txt"\r\n' in text
    assert b'"drain_out.txt" woBC 2\r\n' in text
    assert b" 1 CA-1_RB.txt\r\n" in text
    assert b'USE RAINFALL "C:\\data\\rain.dat"\r\n' in text
    assert b';;SAVE OUTFLOWS "D:\\commented\\out.txt"\r\n' in text
    assert note.startswith("seeded copy: 3 output path(s)")
    assert suite._localize_outputs(deck) == ""          # idempotent on reuse
