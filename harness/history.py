#!/usr/bin/env python3
"""Per-run history records: what the dashboard's Trends page plots.

A Pages deployment holds one run; trends need the runs before it. The
Publish workflow appends one small JSON record per workflow run to the
``benchmark-data`` branch (``runs/<run id>.json``) and passes that folder to
the site build. A record keeps only aggregates, grouped by suite and
platform, so the branch grows by a few kilobytes a night:

    {schema, id, url, started, description, event, benchmarks_sha,
     engine {sha, sha_full, ref, commit_date, subject},
     groups [{suite, platform, cells, verdicts {V: n}, gating,
              engines {id: {runs, passed, wall_total, wall_median, wall_p90,
                            peak_rss_max, continuity_worst, stable_pct}}}]}

Writing a record twice for the same run replaces it, so republishing a run
never duplicates a point.

    python -m harness.history results/ --out history/
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

from . import metrics, scoring

SCHEMA = 1


def _engine_stats(cells: list[dict]) -> dict:
    by = defaultdict(list)
    for c in cells:
        if metrics.is_engine_run(c):
            by[c["solver"]].append(c)
    out = {}
    for eid, cs in sorted(by.items()):
        walls = [metrics.wall(c) for c in cs if c.get("verdict") in metrics.PASSING
                 and metrics.wall(c) is not None]
        w = metrics.summary_stats(walls)
        rss = [c["peak_rss_mb"] for c in cs if isinstance(c.get("peak_rss_mb"), (int, float))]
        cont = metrics.continuity(cs)
        stab = metrics.stability(cs)
        out[eid] = {
            "runs": len(cs),
            "passed": sum(1 for c in cs if c.get("verdict") in metrics.PASSING),
            "wall_total": round(w["total"], 3), "wall_median": w["median"],
            "wall_p90": w["p90"],
            "peak_rss_max": max(rss) if rss else None,
            "continuity_worst": (abs(cont["worst"][0]["continuity_err"])
                                 if cont["worst"] else None),
            "stable_pct": (round(100 * stab["stable"] / len(stab["runs"]), 2)
                           if stab["runs"] else None),
        }
    return out


def summarize(envelopes: list[dict]) -> list[dict]:
    """One record per workflow run id among the envelopes."""
    by_run = defaultdict(list)
    for env in envelopes:
        by_run[(env.get("_run") or {}).get("id") or "unknown"].append(env)
    records = []
    for run_id, envs in sorted(by_run.items()):
        runs = [e.get("_run") or {} for e in envs]
        m = min((r for r in runs if r.get("started")), key=lambda r: r["started"],
                default={})
        cells = metrics.cells_of(envs)
        groups = defaultdict(list)
        for c in cells:
            groups[(c["_suite"], c["_platform"])].append(c)
        eng = m.get("engine") or {}
        records.append({
            "schema": SCHEMA, "id": run_id, "url": m.get("url"),
            "started": m.get("started") or min((e.get("timestamp", "") for e in envs), default=""),
            "description": _run_description(runs),
            "event": m.get("event"), "benchmarks_sha": m.get("benchmarks_sha"),
            "engine": {k: eng.get(k) for k in ("sha", "sha_full", "ref", "commit_date", "subject")}
            if eng else {"sha": envs[0].get("engine_sha")},
            "groups": [{
                "suite": suite, "platform": plat, "cells": len(cs),
                "verdicts": dict(metrics.counts(cs)),
                "gating": sum(1 for c in cs if c.get("verdict") in scoring.GATING),
                "engines": _engine_stats(cs),
            } for (suite, plat), cs in sorted(groups.items())],
        })
    return records


def _run_description(manifests: list[dict]) -> str:
    """The run's own description: the one every job shares, else the
    generated one without a job's platform and part."""
    from . import runinfo
    ds = {m.get("description") for m in manifests if m.get("description")}
    if len(ds) == 1:
        return ds.pop()
    m = next((m for m in manifests if m), {})
    return runinfo.describe({**m, "platform_alias": None, "part": None, "host": {}}) if m else ""


def write(records: list[dict], out: Path) -> list[Path]:
    d = Path(out) / "runs"
    d.mkdir(parents=True, exist_ok=True)
    written = []
    for r in records:
        if r["id"] == "unknown" or str(r["id"]).startswith("local-"):
            continue                 # only workflow runs belong to the history
        p = d / f"{r['id']}.json"
        p.write_text(json.dumps(r, indent=1, sort_keys=True), encoding="utf-8")
        written.append(p)
    return written


def load(folder: Path | None) -> list[dict]:
    """Every record in `folder` (a history checkout or its runs/), oldest first."""
    if not folder:
        return []
    folder = Path(folder)
    if (folder / "runs").is_dir():
        folder = folder / "runs"
    out = []
    for p in sorted(folder.glob("*.json")) if folder.is_dir() else []:
        try:
            r = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(r, dict) and r.get("schema") == SCHEMA:
            out.append(r)
    return sorted(out, key=lambda r: r.get("started") or "")


def main(argv: list[str] | None = None) -> int:
    from . import report
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("results", type=Path, help="folder holding the run's envelopes")
    ap.add_argument("--out", type=Path, required=True, help="history checkout")
    args = ap.parse_args(argv)
    envs = report.load_envelopes([args.results])
    written = write(summarize(envs), args.out)
    for p in written:
        print(f"history: wrote {p}")
    if not written:
        print("history: no workflow run among the envelopes; nothing recorded")
    return 0


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
