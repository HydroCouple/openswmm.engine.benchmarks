#!/usr/bin/env python3
"""Deterministic subprocess execution of a SWMM CLI run, for any suite.

`run(exe, inp, rpt, out)` invokes ``<exe> <in.inp> <out.rpt> <out.out>`` with
the harness.engines environment and returns
{ok, launched, returncode, wall, peak_rss_mb, stdout, stderr}.
`inp_sha` provides the input-hash used for result caching by suite runners.

``peak_rss_mb`` is the engine process's own peak resident memory, from
``wait4``'s resource usage for that one child. ``getrusage(RUSAGE_CHILDREN)``
cannot give it: its ``ru_maxrss`` is the largest of every child waited for so
far, so a small run after a large one reads the large one's peak. Windows has
no ``wait4``, so the value is None there.

On Linux ``wait4`` alone is not enough either: when the child execs, the
kernel records the memory it inherited from the harness into its
``ru_maxrss``, so every engine smaller than the harness process read as the
harness's size (148.6 MB for a 1 MB engine on the Validate runner). There the
engine's own high-water mark is read from ``/proc/<pid>/status`` (``VmHWM``,
which belongs to the program after exec) every 20 ms while it runs, and
``ru_maxrss`` is used only when it clearly exceeds the harness's own peak.
The sampled value can miss growth in the last 20 ms of a run.

Report parsing lives in harness.rptparse — this module used to carry a second,
divergent copy of it whose surcharge and flooding patterns matched no real
report. One parser, one place.
"""
from __future__ import annotations

import hashlib
import locale
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

from . import engines


def inp_sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


_LINUX = sys.platform.startswith("linux")
#: How far ru_maxrss must exceed the harness's own peak before it is taken as
#: the engine's: the harness can grow a little between measuring itself and
#: the exec.
_INHERITED_MARGIN = 16 * 2**20


def _vm_hwm(pid: int) -> int | None:
    """The process's peak resident memory in bytes from /proc, or None once
    it has exited (a zombie's status has no VmHWM line)."""
    try:
        with open(f"/proc/{pid}/status", encoding="ascii", errors="replace") as fh:
            for line in fh:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _execute(cmd: list[str], env: dict, cwd: str | None,
             timeout: float | None) -> subprocess.CompletedProcess:
    """``subprocess.run(cmd, capture_output=True, text=True, ...)`` that also
    records the child's peak RSS as ``.peak_rss`` (bytes, or None).

    Raises subprocess.TimeoutExpired, with the output so far, as
    subprocess.run does.
    """
    if not hasattr(os, "wait4"):
        res = subprocess.run(cmd, capture_output=True, text=True, env=env,
                             cwd=cwd, timeout=timeout)
        res.peak_rss = None
        return res

    own_peak = 0
    if _LINUX:
        import resource
        own_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    # Popen returns once the child has exec'd (it waits on the exec error
    # pipe), so /proc from here on describes the engine, not a copy of us.
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         env=env, cwd=cwd)
    sampled = [0]
    stop_sampling = threading.Event()

    def sample():
        while not stop_sampling.is_set():
            hw = _vm_hwm(p.pid)
            if hw is None:
                return
            sampled[0] = max(sampled[0], hw)
            stop_sampling.wait(0.02)

    sampler = threading.Thread(target=sample, daemon=True) if _LINUX else None
    if sampler:
        sampler.start()
    captured = {"out": b"", "err": b""}

    def drain(stream, key):
        captured[key] = stream.read()

    readers = [threading.Thread(target=drain, args=(p.stdout, "out"), daemon=True),
               threading.Thread(target=drain, args=(p.stderr, "err"), daemon=True)]
    for t in readers:
        t.start()
    killed = threading.Event()

    def kill():
        killed.set()
        p.kill()            # Popen polls first, so this never signals a reaped pid

    timer = threading.Timer(timeout, kill) if timeout else None
    if timer:
        timer.start()
    peak = None
    try:
        _, status, usage = os.wait4(p.pid, 0)
        p.returncode = os.waitstatus_to_exitcode(status)
        # ru_maxrss is bytes on macOS and KiB on Linux.
        peak = usage.ru_maxrss * (1 if sys.platform == "darwin" else 1024)
    except ChildProcessError:
        p.wait()            # the timer's poll reaped it first
    finally:
        if timer:
            timer.cancel()
        stop_sampling.set()
    if sampler:
        sampler.join()
        if peak is None or peak <= own_peak + _INHERITED_MARGIN:
            # ru_maxrss may be our own memory, inherited at exec.
            peak = sampled[0] or None
    # After a timeout kill, a process the engine started can still hold the
    # pipes open; subprocess.run does not wait for them then, and neither
    # does this (the threads are daemons).
    for t in readers:
        t.join(timeout=1 if killed.is_set() else None)
    if not any(t.is_alive() for t in readers):
        p.stdout.close()
        p.stderr.close()

    enc = locale.getpreferredencoding(False)

    def text(b: bytes) -> str:
        return b.decode(enc, errors="replace").replace("\r\n", "\n")

    if killed.is_set() and p.returncode == -signal.SIGKILL:
        raise subprocess.TimeoutExpired(cmd, timeout, output=captured["out"],
                                        stderr=captured["err"])
    res = subprocess.CompletedProcess(cmd, p.returncode, text(captured["out"]),
                                      text(captured["err"]))
    res.peak_rss = peak
    return res


def run(exe: Path, inp: Path, rpt: Path, out: Path, reps: int = 1,
        cwd: Path | None = None, threads: int = 1,
        dylib_dirs: list[str] | None = None,
        extra_env: dict[str, str] | None = None,
        timeout: float | None = None) -> dict:
    """Run an engine CLI; return {ok, returncode, wall (best of reps), stderr}."""
    e = engines.env(threads, dylib_dirs)
    if extra_env:
        e.update(extra_env)
    best, rc, err, stdout = None, -1, "", ""
    peak = None
    launched = True
    for _ in range(max(1, reps)):
        stdout = ""
        for p in (rpt, out):
            if p and Path(p).exists():
                Path(p).unlink()
        t0 = time.perf_counter()
        try:
            res = _execute([str(exe), str(inp), str(rpt), str(out)], e,
                           str(cwd) if cwd else None, timeout)
            rc, err = res.returncode, res.stderr.strip()
            stdout = res.stdout
            rss = getattr(res, "peak_rss", None)
            if rss is not None:
                peak = max(peak or 0, rss)
        except subprocess.TimeoutExpired as exc:
            rc, err = -9, f"timeout after {timeout}s"
            partial = exc.stdout or ""
            stdout = partial.decode("utf-8", errors="replace") if isinstance(partial, bytes) else partial
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
            "stdout": stdout[-20000:],
            "wall": best,
            "peak_rss_mb": round(peak / 2**20, 1) if peak is not None else None,
            "stderr": err[:500]}
