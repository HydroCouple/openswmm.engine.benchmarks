#!/usr/bin/env python3
"""Deterministic subprocess execution of a SWMM CLI run, for any suite.

`run(exe, inp, rpt, out)` invokes ``<exe> <in.inp> <out.rpt> <out.out>`` with
the harness.engines environment and returns
{ok, launched, returncode, wall, stderr}.
`inp_sha` provides the input-hash used for result caching by suite runners.

Report parsing lives in harness.rptparse — this module used to carry a second,
divergent copy of it whose surcharge and flooding patterns matched no real
report. One parser, one place.
"""
from __future__ import annotations

import hashlib
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
    launched = True
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
        except OSError as exc:
            # The executable exists but cannot be launched here — wrong
            # architecture, missing loader, permissions. A sweep must degrade
            # to an UNAVAILABLE cell, never crash: one unusable engine in the
            # registry cannot be allowed to take down every other engine's
            # results for the whole corpus.
            #
            # `launched` separates "this environment cannot run the engine"
            # from "the engine ran and failed on this model". Only the second
            # is a result; the first must not gate CI, or every machine
            # without every registered engine would report failures.
            rc, err, launched = -1, f"cannot execute {exe}: {exc}", False
            break
        dt = time.perf_counter() - t0
        if best is None or dt < best:
            best = dt
        if rc != 0:
            break
    return {"ok": rc == 0, "launched": launched, "returncode": rc,
            "wall": best, "stderr": err[:500]}
