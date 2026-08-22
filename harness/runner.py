#!/usr/bin/env python3
"""Deterministic subprocess execution of a SWMM CLI run, for any suite.

`run(exe, inp, rpt, out)` invokes ``<exe> <in.inp> <out.rpt> <out.out>`` with
the core.engines environment, returns {ok, returncode, wall, stderr}.
`parse_rpt` scrapes the global continuity / stability metrics from a .rpt.
`inp_sha` provides the input-hash used for result caching by suite runners.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import time
from pathlib import Path

from . import engines


def inp_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def run(exe: Path, inp: Path, rpt: Path, out: Path, reps: int = 1,
        cwd: Path | None = None, threads: int = 1,
        dylib_dirs: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
        timeout: float | None = None) -> dict:
    """Run an engine CLI; return {ok, returncode, wall (best of reps), stderr}."""
    e = engines.env(threads, dylib_dirs)
    if extra_env:
        e.update(extra_env)
    best, rc, err = None, -1, ""
    for _ in range(max(1, reps)):
        for p in (rpt, out):
            if p and Path(p).exists():
                Path(p).unlink()
        t0 = time.perf_counter()
        try:
            res = subprocess.run([str(exe), str(inp), str(rpt), str(out)],
                                 capture_output=True, text=True, env=e,
                                 cwd=str(cwd) if cwd else None, timeout=timeout)
            rc, err = res.returncode, res.stderr.strip()
        except subprocess.TimeoutExpired:
            rc, err = -9, f"timeout after {timeout}s"
        dt = time.perf_counter() - t0
        if best is None or dt < best:
            best = dt
        if rc != 0:
            break
    return {"ok": rc == 0, "returncode": rc, "wall": best, "stderr": err[:500]}


def parse_rpt(path: Path) -> dict:
    """Global continuity / stability metrics from a SWMM .rpt (either engine)."""
    out: dict = {}
    path = Path(path)
    if not path.exists():
        return out
    text = path.read_text(errors="replace")

    def f1(pat, key, cast=float):
        m = re.search(pat, text, re.S)
        if m:
            try:
                out[key] = cast(m.group(1))
            except ValueError:
                pass

    for label, key in (("Runoff Quantity Continuity", "runoff_err"),
                       ("Flow Routing Continuity", "routing_err")):
        f1(re.escape(label) + r".*?Continuity Error \(%\)\s*\.+\s*([-\d.]+)", key)
    f1(r"Average Iterations per Step\s*[:.]*\s*([\d.]+)", "avg_iter")
    f1(r"(?:Percent\s+)?Not Converging\s*[:.]*\s*([\d.]+)", "pct_not_converging")
    f1(r"Average Time Step\s*[:.]*\s*([\d.]+)", "avg_dt")
    f1(r"Minimum Time Step\s*[:.]*\s*([\d.]+)", "min_dt")
    f1(r"Maximum Time Step\s*[:.]*\s*([\d.]+)", "max_dt")
    for label, pat in (("nodes_flooded", r"(\d+)\s+nodes? (?:were |was )?flooded"),
                       ("links_surcharged", r"(\d+)\s+links? (?:were |was )?surcharged"),
                       ("links_instability", r"(\d+)\s+links? .*?flow instability")):
        m = re.search(pat, text, re.I)
        if m:
            out[label] = int(m.group(1))
    out["had_error"] = bool(re.search(r"\bERROR\b", text))
    return out
