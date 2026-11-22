#!/usr/bin/env python3
"""The run manifest: what ran, where, on which engine, and why.

`run_regression.py` writes ``results/run.json`` when a run starts and again
when it ends. An envelope records a suite's cells; the manifest records the
run around them, so the dashboard can say which workflow run and job produced
a result, on what hardware, from which engine commit, and link back to the
run, its job log and its artifacts. A manifest with no ``finished`` belongs to
a run that never ended: canceled, timed out, or still going.

    python -m harness.runinfo --set-artifact evidence URL   # CI, after upload

Schema 1:

    id, url, job_url, attempt, repository, workflow, job, event, ref,
    benchmarks_sha, started, finished, duration_s, exit_code, crashed,
    description, args, tier, max_wall, part, platform_alias,
    host {os, release, machine, cpu, cpu_count, memory_gb, python, numpy, runner},
    engine {sha, sha_full, ref, dirty, commit_date, subject, versions {id: line},
            executables {id: path}},
    artifacts {name: url}

``BENCH_RUN_MANIFEST`` overrides the path (the tests point it at a temporary
folder so they never overwrite a real run's manifest).
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from . import engines

SCHEMA = 1
REPO_ROOT = Path(__file__).resolve().parent.parent


def path() -> Path:
    return Path(os.environ.get("BENCH_RUN_MANIFEST")
                or REPO_ROOT / "results" / "run.json")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


def _git(repo: Path, *args: str) -> str:
    try:
        return subprocess.run(["git", "-C", str(repo), *args],
                              capture_output=True, text=True, timeout=30,
                              encoding="utf-8", errors="replace").stdout.strip()
    except Exception:
        return ""


def _cpu() -> str:
    """CPU model: runner hardware varies, and runtimes are only comparable on
    the same model."""
    try:
        if sys.platform.startswith("linux"):
            for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
                if line.startswith("model name"):
                    return line.split(":", 1)[1].strip()
        if sys.platform == "darwin":
            return _sysctl("machdep.cpu.brand_string")
    except OSError:
        pass
    return platform.processor()


def _sysctl(key: str) -> str:
    try:
        return subprocess.run(["sysctl", "-n", key], capture_output=True,
                              text=True, timeout=10).stdout.strip()
    except Exception:
        return ""


def _memory_gb() -> float | None:
    try:
        if sys.platform == "darwin":
            return round(int(_sysctl("hw.memsize")) / 2**30, 1)
        return round(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30, 1)
    except (ValueError, OSError, AttributeError):
        return None


def host() -> dict:
    try:
        import numpy
        np_version = numpy.__version__
    except ImportError:
        np_version = None
    return {"os": platform.system(), "release": platform.release(),
            "machine": platform.machine(), "cpu": _cpu(),
            "cpu_count": os.cpu_count(), "memory_gb": _memory_gb(),
            "python": platform.python_version(), "numpy": np_version,
            "runner": os.environ.get("RUNNER_NAME")}


def _version_line(exe: Path) -> str | None:
    try:
        r = subprocess.run([str(exe), "--version"], capture_output=True,
                           text=True, timeout=20, env=engines.env(),
                           errors="replace")
    except Exception:
        return None
    lines = (r.stdout or r.stderr).strip().splitlines()
    return lines[0][:200] if r.returncode == 0 and lines else None


def engine() -> dict:
    d = engines.ENGINE_DIR
    full = _git(d, "rev-parse", "HEAD")
    sha = engines.engine_sha()
    date_subject = _git(d, "log", "-1", "--format=%cI%n%s").splitlines()
    versions, executables = {}, {}
    try:
        reg = engines.resolve_all(engines.load())
        for eid, e in reg.resolved().items():
            executables[eid] = str(e.exe)
            if (e.spec.get("source") or {}).get("type", "in-tree") == "in-tree":
                versions[eid] = _version_line(e.exe)
    except Exception:
        pass
    ref = os.environ.get("OPENSWMM_ENGINE_REF") or _git(d, "rev-parse", "--abbrev-ref", "HEAD")
    return {"sha": sha, "sha_full": full or None, "ref": None if ref == "HEAD" else ref or None,
            "dirty": sha.endswith("-dirty"),
            "commit_date": date_subject[0] if date_subject else None,
            "subject": date_subject[1] if len(date_subject) > 1 else None,
            # The executables say whether the commit above built them: an
            # OPENSWMM_EXE override can point outside the engine checkout.
            "versions": versions, "executables": executables}


def _event_label(event: str | None, workflow: str | None) -> str:
    if not event:
        return "Local run"
    how = {"schedule": "scheduled", "workflow_dispatch": "started by hand",
           "repository_dispatch": "engine push", "push": "push",
           "pull_request": "pull request"}.get(event, event)
    return f"{workflow or 'Workflow'} ({how})"


def describe(m: dict) -> str:
    """A one-line description for a run that was given none."""
    eng = m.get("engine") or {}
    where = m.get("platform_alias") or "-".join(
        x for x in ((m.get("host") or {}).get("os"), (m.get("host") or {}).get("machine")) if x)
    parts = [_event_label(m.get("event"), m.get("workflow")),
             "@".join(x for x in (eng.get("ref"), eng.get("sha")) if x),
             where, (m.get("part") or "").replace("-", " ")]
    return " · ".join(p for p in parts if p)


def collect(*, argv: list[str], description: str | None = None,
            tier: str | None = None, max_wall: float | None = None) -> dict:
    env = os.environ
    server = env.get("GITHUB_SERVER_URL", "https://github.com")
    repo = env.get("GITHUB_REPOSITORY")
    run_id = env.get("GITHUB_RUN_ID")
    url = f"{server}/{repo}/actions/runs/{run_id}" if repo and run_id else None
    job_id = env.get("BENCH_JOB_ID")
    started = _now()
    m = {
        "schema": SCHEMA,
        "id": run_id or "local-" + started.replace(":", "").replace("-", "")[:15],
        "url": url,
        "job_url": f"{url}/job/{job_id}" if url and job_id else None,
        "attempt": env.get("GITHUB_RUN_ATTEMPT"),
        "repository": repo,
        "workflow": env.get("GITHUB_WORKFLOW"),
        "job": env.get("BENCH_JOB_NAME") or env.get("GITHUB_JOB"),
        "event": env.get("GITHUB_EVENT_NAME"),
        "ref": env.get("GITHUB_REF_NAME"),
        "benchmarks_sha": engines.git_sha(REPO_ROOT),
        "started": started, "finished": None, "duration_s": None,
        "exit_code": None, "crashed": [],
        "args": list(argv), "tier": tier, "max_wall": max_wall,
        "part": env.get("BENCH_PART"),
        "platform_alias": env.get("BENCH_PLATFORM_ALIAS"),
        "host": host(), "engine": engine(), "artifacts": {},
    }
    m["description"] = (description or env.get("BENCH_RUN_DESCRIPTION") or "").strip() \
        or describe(m)
    return m


def finish(m: dict, *, exit_code: int, crashed: list[str]) -> dict:
    m["finished"] = _now()
    t0 = datetime.datetime.fromisoformat(m["started"])
    t1 = datetime.datetime.fromisoformat(m["finished"])
    m["duration_s"] = round((t1 - t0).total_seconds(), 1)
    m["exit_code"] = exit_code
    m["crashed"] = list(crashed)
    return m


def write(m: dict, where: Path | None = None) -> Path:
    p = Path(where or path())
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(m, indent=2), encoding="utf-8")
    return p


def load(where: Path | None = None) -> dict | None:
    p = Path(where or path())
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set-artifact", nargs=2, metavar=("NAME", "URL"),
                    help="record an uploaded artifact's URL in the manifest")
    ap.add_argument("--manifest", type=Path, help="manifest path (default results/run.json)")
    args = ap.parse_args(argv)
    if not args.set_artifact:
        ap.error("nothing to do")
    name, url = args.set_artifact
    # A sweep that died before writing its manifest still gets one, so the
    # artifact link is not lost with it.
    m = load(args.manifest) or {"schema": SCHEMA, "artifacts": {}}
    if url:
        m.setdefault("artifacts", {})[name] = url
    print(f"manifest {write(m, args.manifest)}: artifact {name} = {url or '(none)'}")
    return 0


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
