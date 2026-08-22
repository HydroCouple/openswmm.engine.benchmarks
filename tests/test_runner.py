"""Runner robustness: a broken engine must never take down a sweep.

The platform runs an open registry of engines, several of which may be
unavailable, mis-built, or built for another platform on any given machine.
The plan's invariant is that these degrade to UNAVAILABLE cells rather than
aborting the run — one unusable engine cannot be allowed to destroy every
other engine's results for the whole corpus.
"""
from __future__ import annotations

import sys

import pytest

from harness import runner


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
    script = tmp_path / "engine.py"
    script.write_text("import sys; sys.stderr.write('boom'); sys.exit(3)\n")
    exe = tmp_path / "engine.sh"
    exe.write_text(f"#!/bin/sh\n{sys.executable} {script} \"$@\"\n")
    exe.chmod(0o755)
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    assert res["ok"] is False
    assert res["returncode"] == 3
    assert "boom" in res["stderr"]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell fixture")
def test_successful_run_reports_wall_time(tmp_path):
    exe = tmp_path / "engine.sh"
    exe.write_text("#!/bin/sh\nexit 0\n")
    exe.chmod(0o755)
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out")
    assert res["ok"] is True
    assert res["wall"] is not None and res["wall"] >= 0


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX shell fixture")
def test_timeout_is_reported_not_raised(tmp_path):
    exe = tmp_path / "engine.sh"
    exe.write_text("#!/bin/sh\nsleep 5\n")
    exe.chmod(0o755)
    res = runner.run(exe, tmp_path / "m.inp", tmp_path / "m.rpt",
                     tmp_path / "m.out", timeout=0.2)
    assert res["ok"] is False
    assert "timeout" in res["stderr"]


def test_inp_sha_is_content_addressed(tmp_path):
    a, b, c = tmp_path / "a.inp", tmp_path / "b.inp", tmp_path / "c.inp"
    a.write_text("[TITLE]\nx\n")
    b.write_text("[TITLE]\nx\n")
    c.write_text("[TITLE]\ny\n")
    assert runner.inp_sha(a) == runner.inp_sha(b)
    assert runner.inp_sha(a) != runner.inp_sha(c)
