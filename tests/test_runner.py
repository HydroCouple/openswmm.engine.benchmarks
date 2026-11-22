"""Runner robustness: a broken engine must never take down a sweep.

The platform runs an open registry of engines, several of which may be
unavailable, mis-built, or built for another platform on any given machine.
The plan's invariant is that these degrade to UNAVAILABLE cells rather than
aborting the run — one unusable engine cannot be allowed to destroy every
other engine's results for the whole corpus.
"""
from __future__ import annotations

import sys
import subprocess

from harness import runner


def _fake_engine(tmp_path, *, posix: str, windows: str, name: str = "engine"):
    """A stand-in engine the current OS can actually launch.

    runner.run execs `[exe, inp, rpt, out]` directly, so the fixture has to be
    something the platform will start on its own. A `#!/bin/sh` script is not
    that on Windows, and skipping there would drop coverage of the single most
    important behavior — "the engine ran and failed" being reported with its
    exit code — on a platform where the whole sweep runs.
    """
    if sys.platform == "win32":
        exe = tmp_path / f"{name}.bat"
        exe.write_text("@echo off\r\n" + windows, encoding="utf-8")
    else:
        exe = tmp_path / f"{name}.sh"
        exe.write_text("#!/bin/sh\n" + posix, encoding="utf-8")
        exe.chmod(0o755)
    return exe


def test_missing_executable_returns_not_ok(tmp_path):
    res = runner.run(tmp_path / "no-such-engine", tmp_path / "m.inp",
                     tmp_path / "m.rpt", tmp_path / "m.out")
    assert res["ok"] is False
    assert "cannot execute" in res["stderr"]


def test_wrong_architecture_binary_returns_not_ok(tmp_path):
    """A Mach-O binary on Linux (or vice versa) raises OSError from exec.
    This is the exact case that crashed a sweep before it was handled."""
    fake = tmp_path / "engine"
    fake.write_bytes(b"\xcf\xfa\xed\xfe" + b"\x00" * 64)   # Mach-O magic
    fake.chmod(0o755)
    res = runner.run(fake, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    assert res["ok"] is False
    assert res["returncode"] != 0


def test_nonzero_exit_is_reported(tmp_path):
    """An engine that RAN and failed is a result: its exit code must survive."""
    script = tmp_path / "engine.py"
    script.write_text("import sys; sys.stderr.write('boom'); sys.exit(3)\n", encoding="utf-8")
    exe = _fake_engine(
        tmp_path,
        posix=f'"{sys.executable}" "{script}" "$@"\n',
        windows=f'"{sys.executable}" "{script}" %*\r\nexit /b %errorlevel%\r\n')
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    assert res["ok"] is False
    assert res["launched"] is True, "the engine started; this is a result, not an environment problem"
    assert res["returncode"] == 3
    assert "boom" in res["stderr"]


def test_successful_run_reports_wall_time(tmp_path):
    exe = _fake_engine(tmp_path, posix="exit 0\n", windows="exit /b 0\r\n")
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    assert res["ok"] is True
    assert res["wall"] is not None and res["wall"] >= 0


def test_timeout_is_reported_not_raised(tmp_path):
    """A hung engine must be a cell, not an exception that ends the sweep."""
    sleeper = f'"{sys.executable}" -c "import time; time.sleep(5)"'
    exe = _fake_engine(tmp_path, posix=sleeper + "\n",
                       windows=sleeper + "\r\n")
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out", timeout=0.2)
    assert res["ok"] is False
    assert "timeout" in res["stderr"]


def test_inp_sha_is_content_addressed(tmp_path):
    a, b, c = tmp_path / "a.inp", tmp_path / "b.inp", tmp_path / "c.inp"
    a.write_text("[TITLE]\nx\n", encoding="utf-8")
    b.write_text("[TITLE]\nx\n", encoding="utf-8")
    c.write_text("[TITLE]\ny\n", encoding="utf-8")
    assert runner.inp_sha(a) == runner.inp_sha(b)
    assert runner.inp_sha(a) != runner.inp_sha(c)


def test_timeout_keeps_current_progress_instead_of_previous_repeat(tmp_path,monkeypatch):
    attempts=iter([subprocess.CompletedProcess(['engine'],0,stdout='first successful attempt',stderr=''),
                   subprocess.TimeoutExpired(['engine'],1,output=b'current timeout progress')])
    def execute(*args,**kwargs):
        result=next(attempts)
        if isinstance(result,Exception):raise result
        return result
    monkeypatch.setattr(runner,'_execute',execute)
    result=runner.run(tmp_path/'engine',tmp_path/'m.inp',tmp_path/'m.rpt',tmp_path/'m.out',reps=2,timeout=1)
    assert not result['ok'] and result['stdout']=='current timeout progress'


def test_peak_memory_is_the_engine_process_own(tmp_path):
    """wait4 reports one child's peak. getrusage(RUSAGE_CHILDREN) would report
    the largest child so far, so the small run after the large one is the
    check that tells them apart."""
    def engine(megabytes, name):
        script = tmp_path / f"{name}.py"
        script.write_text(
            f"b = bytearray({megabytes} * 2**20)\n"
            f"for i in range(0, len(b), 4096): b[i] = 1\n", encoding="utf-8")
        return _fake_engine(
            tmp_path, name=name,
            posix=f'exec "{sys.executable}" "{script}"\n',
            windows=f'"{sys.executable}" "{script}"\r\n')

    big = runner.run(engine(200, "big"), tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    small = runner.run(engine(1, "small"), tmp_path / "m.inp", tmp_path / "m.rpt",
                       tmp_path / "m.out")
    assert big["ok"] and small["ok"]
    if sys.platform == "win32":
        assert big["peak_rss_mb"] is None
        return
    assert big["peak_rss_mb"] >= 190, big
    assert small["peak_rss_mb"] < 100, small


def test_output_and_exit_code_survive_the_memory_measurement(tmp_path):
    script = tmp_path / "engine.py"
    script.write_text("import sys\nprint('x' * 300000)\n"
                      "sys.stderr.write('y' * 300000)\nsys.exit(4)\n",
                      encoding="utf-8")
    exe = _fake_engine(
        tmp_path,
        posix=f'exec "{sys.executable}" "{script}"\n',
        windows=f'"{sys.executable}" "{script}"\r\nexit /b %errorlevel%\r\n')
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    assert res["returncode"] == 4
    assert res["stdout"].endswith("x" * 1000 + "\n")
    assert res["stderr"].startswith("y" * 500)
