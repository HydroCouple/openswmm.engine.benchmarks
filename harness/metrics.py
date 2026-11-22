#!/usr/bin/env python3
"""Statistics over scores envelopes, shared by the dashboard and the history.

Everything here reads cells as the suites write them and computes nothing a
cell does not support: a runtime is an engine run's ``wall`` (``wall_s`` in
the UK suites), a mass-balance figure is a ``.rpt`` continuity error, a
parity figure is a pair cell's ``max_rel``. Where a statistic leaves cells out
(by-design continuity cases, sub-second speed ratios), the functions return
what they left out so the page can say so.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter, defaultdict

from . import scoring

PASSING = {"PASS", "BASELINE-PASS"}
EXPECTED = {"XFAIL"}
NOT_RUN = {"SKIP", "UNAVAILABLE"}

#: Verdict groups, in the order every bar and legend shows them.
GROUPS = ("pass", "expected", "gating", "not_run")
GROUP_LABEL = {"pass": "passed", "expected": "expected failure",
               "gating": "gating", "not_run": "not run"}

#: The parity gate's pair: the legacy reference and the engine under test.
LEGACY, V6 = "swmm-5.3.0", "openswmm-v6"

#: Below this, a run's wall time is mostly process start-up, and a ratio of
#: two such times says nothing about the engines.
RATIO_FLOOR_S = 1.0


def group_of(verdict: str | None) -> str:
    if verdict in PASSING:
        return "pass"
    if verdict in EXPECTED:
        return "expected"
    if verdict in scoring.GATING:
        return "gating"
    return "not_run"


def cells_of(envelopes: list[dict]) -> list[dict]:
    """Every cell, tagged with where it came from (``_suite``, ``_platform``,
    ``_shard``, ``_env``)."""
    out = []
    for env in envelopes:
        for c in env.get("cells", []):
            out.append({**c, "_suite": env.get("suite", "?"),
                        "_platform": platform_of(env),
                        "_shard": env.get("shard"), "_env": env})
    return out


def platform_of(env: dict) -> str:
    run = env.get("_run") or {}
    return (run.get("platform_alias") or env.get("platform")
            or (run.get("host") or {}).get("os") or "unknown")


def wall(cell: dict) -> float | None:
    w = cell.get("wall")
    if w is None:
        w = cell.get("wall_s")
    return float(w) if isinstance(w, (int, float)) else None


def is_engine_run(cell: dict) -> bool:
    return bool(cell.get("solver")) and cell.get("solver") != "-" and "pair" not in cell


def counts(cells: list[dict]) -> Counter:
    return Counter(c.get("verdict", "?") for c in cells)


def group_counts(cells: list[dict]) -> dict[str, int]:
    g = Counter(group_of(c.get("verdict")) for c in cells)
    return {k: g.get(k, 0) for k in GROUPS}


def summary_stats(values: list[float]) -> dict:
    v = sorted(x for x in values if x is not None and math.isfinite(x))
    if not v:
        return {"n": 0, "total": 0.0, "median": None, "p90": None, "max": None}
    return {"n": len(v), "total": sum(v), "median": statistics.median(v),
            "p90": v[min(len(v) - 1, int(0.9 * len(v)))], "max": v[-1]}


# ── runtime ────────────────────────────────────────────────────────────────

def parity_runs(cells: list[dict]) -> list[dict]:
    """Engine runs of the parity suite that completed (PASS or XFAIL)."""
    return [c for c in cells if c["_suite"] == "parity" and is_engine_run(c)
            and wall(c) is not None and c.get("verdict") in PASSING | EXPECTED]


def speed_points(cells: list[dict], a: str = LEGACY, b: str = V6
                 ) -> dict[str, list[tuple[str, float, float]]]:
    """{platform: [(case, wall_a, wall_b)]} for cases where both ran."""
    by = defaultdict(dict)
    for c in parity_runs(cells):
        if c.get("solver") in (a, b) and not c.get("trimmed"):
            by[(c["_platform"], c["case"])][c["solver"]] = wall(c)
    out = defaultdict(list)
    for (plat, case), w in sorted(by.items()):
        if a in w and b in w:
            out[plat].append((case, w[a], w[b]))
    return dict(out)


def ratio_summary(points: list[tuple[str, float, float]],
                  floor: float = RATIO_FLOOR_S) -> dict:
    """b/a over the cases where either engine took at least `floor` seconds."""
    r = [wb / wa for _, wa, wb in points if max(wa, wb) >= floor and wa > 0 and wb > 0]
    if not r:
        return {"n": 0, "left_out": len(points)}
    return {"n": len(r), "left_out": len(points) - len(r),
            "median": statistics.median(r),
            "geomean": math.exp(sum(math.log(x) for x in r) / len(r)),
            "faster": sum(1 for x in r if x < 1.0)}


# ── mass balance ───────────────────────────────────────────────────────────

def continuity(cells: list[dict], key: str = "continuity_err") -> dict:
    """|continuity error| of engine runs; by-design cases separated out."""
    runs = [c for c in cells if is_engine_run(c)
            and isinstance(c.get(key), (int, float))]
    graded = [c for c in runs if not c.get("expected_high_continuity")]
    return {"graded": graded, "by_design": len(runs) - len(graded),
            "worst": sorted(graded, key=lambda c: -abs(c[key]))}


# ── stability ──────────────────────────────────────────────────────────────

STABLE_PCT = 1.0          # the stability badge's threshold (scoring.badges)


def stability(cells: list[dict]) -> dict:
    runs = [c for c in cells if is_engine_run(c)
            and isinstance(c.get("pct_not_converging"), (int, float))]
    stable = [c for c in runs if c["pct_not_converging"] <= STABLE_PCT]
    return {"runs": runs, "stable": len(stable),
            "worst": sorted(runs, key=lambda c: -c["pct_not_converging"])}


# ── parity ─────────────────────────────────────────────────────────────────

def pairs(cells: list[dict]) -> list[dict]:
    return [c for c in cells if "pair" in c and isinstance(c.get("max_rel"), (int, float))]


# ── failure mechanisms ─────────────────────────────────────────────────────

_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")
_NUMBER = re.compile(r"[-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?", re.I)
_LINE_REF = re.compile(r"\s*at line # of \[[A-Z_ ]+\] section:?", re.I)


def note_family(cell: dict) -> str:
    """The cell's note with names, numbers and line references taken out, so
    cells failing the same way share one family."""
    # A trimmed run's note starts with the trim; the failure comes after it.
    parts = [p.strip() for p in (cell.get("note") or "").split(";")
             if p.strip() and not p.strip().startswith("CI trim:")]
    note = parts[0] if parts else ""
    if not note:
        # Baseline suites grade by a measured change and leave the note empty.
        return f"{cell.get('verdict', '?')} in {cell.get('_suite', '?')} (no note)"
    note = _NUMBER.sub("#", _QUOTED.sub("'…'", note))
    note = _LINE_REF.sub("", note)
    # Names SWMM prints unquoted after "Node", "Link", "Curve", ...
    note = re.sub(r"\b(Node|Link|Subcatchment|Outfall|Curve|Pump|Conduit|name)\s+\S+",
                  r"\1 …", note)
    return re.sub(r"\s+", " ", note)[:140]


def mechanisms(cells: list[dict]) -> list[tuple[str, list[dict]]]:
    """Gating cells grouped by note family, largest group first."""
    fam = defaultdict(list)
    for c in cells:
        if c.get("verdict") in scoring.GATING:
            fam[note_family(c)].append(c)
    return sorted(fam.items(), key=lambda kv: (-len(kv[1]), kv[0]))


# ── platforms ──────────────────────────────────────────────────────────────

def agreement(cells: list[dict]) -> dict:
    """Same case and engine on two platforms: do they agree?

    Returns {"platforms": [p, q], "engines": {eid: {...}}, "differ": [...]}
    for the first two platforms seen; {} when fewer than two ran.
    """
    runs = [c for c in cells if c["_suite"] == "parity" and is_engine_run(c)]
    plats = sorted({c["_platform"] for c in runs})
    if len(plats) < 2:
        return {}
    p, q = plats[:2]
    by = defaultdict(dict)
    for c in runs:
        if c["_platform"] in (p, q):
            by[(c["solver"], c["case"])][c["_platform"]] = c
    eng: dict[str, dict] = defaultdict(lambda: {"both": 0, "verdict_agree": 0,
                                                "hashed": 0, "identical": 0,
                                                "ratios": []})
    differ = []
    for (eid, case), d in sorted(by.items()):
        if p not in d or q not in d:
            continue
        a, b = d[p], d[q]
        e = eng[eid]
        e["both"] += 1
        if a.get("verdict") == b.get("verdict"):
            e["verdict_agree"] += 1
        else:
            differ.append((eid, case, a, b))
        if a.get("out_sha16") and b.get("out_sha16"):
            e["hashed"] += 1
            e["identical"] += a["out_sha16"] == b["out_sha16"]
        wa, wb = wall(a), wall(b)
        done = PASSING | EXPECTED
        # A crash's time says nothing about the platform: only runs that
        # completed on both are compared.
        if (a.get("verdict") in done and b.get("verdict") in done
                and wa and wb and max(wa, wb) >= RATIO_FLOOR_S):
            e["ratios"].append(wb / wa)
    for e in eng.values():
        r = e.pop("ratios")
        e["wall_ratio_median"] = statistics.median(r) if r else None
        e["wall_ratio_n"] = len(r)
    return {"platforms": [p, q], "engines": dict(eng), "differ": differ}


# ── binning for the histograms ─────────────────────────────────────────────

def bin_counts(values: list[float], edges: list[float]) -> list[int]:
    """Counts in (-inf, e0), [e0, e1), ..., [e_last, inf)."""
    out = [0] * (len(edges) + 1)
    for v in values:
        i = 0
        while i < len(edges) and v >= edges[i]:
            i += 1
        out[i] += 1
    return out


def bin_labels(edges: list[float], unit: str = "", fmt=None) -> list[str]:
    f = fmt or (lambda x: f"{x:g}")
    labels = [f"< {f(edges[0])}"]
    labels += [f"{f(a)}–{f(b)}" for a, b in zip(edges, edges[1:])]
    labels.append(f"≥ {f(edges[-1])}")
    if unit:
        labels = [f"{x} {unit}" for x in labels]
    return labels
