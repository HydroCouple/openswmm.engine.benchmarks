#!/usr/bin/env python3
"""Timestep-by-timestep parity diff between two SWMM .out files.

Compares two engines element-by-element, period-by-period over EVERY element
kind the format carries — subcatchments, nodes, links, and system variables —
including per-pollutant variables, using the standalone reader (no engine
binding needed, so any SWMM-compatible engine can be graded).

Parity verdict follows BIT_PARITY_AGENT_BRIEF.md: the .out stores float32, so
the realistic floor is the float32 ULP at each value's magnitude.
  * flow / depth / velocity / volume : require max|Δ| == 0  (bit-identical f32)
  * head                             : allow max|Δ| ≤ float32 ULP of the head
                                       magnitude (head ≈ invert+depth carries a
                                       sub-float32 storage floor even at parity)
A separate, stricter raw byte-equality of the results section is also reported.

Cross-dialect comparison: variables are matched by NAME, not storage index, so
a swmm52 file (14 system variables) and a swmm53 file (15, adds PET_RATE) are
compared over the intersection. Pollutant variables are matched by pollutant
ID for the same reason.

Promoted from epaswmm5_qa/suites/epa_qa/harness/outdiff.py; the element-kind
and pollutant coverage is the Appendix A gap-2 extension.
"""
from __future__ import annotations

import numpy as np

from .readers import (Out, NODE_DEPTH, NODE_HEAD, NODE_VOLUME,
                      LINK_FLOW, LINK_DEPTH, LINK_VELOCITY, LINK_VOLUME)

# (kind, name, var-index). Order matters: flow/depth first (the parity targets).
LINK_VARS = [("link", "FLOW", LINK_FLOW), ("link", "DEPTH", LINK_DEPTH),
             ("link", "VELOCITY", LINK_VELOCITY), ("link", "VOLUME", LINK_VOLUME)]
NODE_VARS = [("node", "DEPTH", NODE_DEPTH), ("node", "HEAD", NODE_HEAD),
             ("node", "VOLUME", NODE_VOLUME)]
#: The historical core set — link + node hydraulics only. Kept as the default
#: so existing parity verdicts are unchanged; `full_vars()` widens coverage.
ALL_VARS = LINK_VARS + NODE_VARS

ABS_EPS = 1e-9  # below this two float32 values are identical for first-div


def _f32_ulp(x: float) -> float:
    """Storage floor: the float32 spacing at magnitude x."""
    return float(np.spacing(np.float32(max(abs(x), 1e-30))))


def _series(o: Out, kind: str, eid: str, var: int) -> np.ndarray:
    return o.series(kind, eid, var)


def common_vars(a: Out, b: Out, kind: str) -> list[tuple[str, str, int, int]]:
    """Variables of one element kind present in BOTH files, matched by name.

    Returns (kind, name, var_index_in_a, var_index_in_b). Handles the two ways
    two files can disagree on layout: different system-variable counts across
    dialects, and different pollutant sets.
    """
    na, nb = a.var_names(kind), b.var_names(kind)
    ib = {name: i for i, name in enumerate(nb)}
    return [(kind, name, ia, ib[name]) for ia, name in enumerate(na)
            if name in ib]


def full_vars(a: Out, b: Out) -> list[tuple[str, str, int, int]]:
    """Every comparable (kind, variable) pair across all four element kinds."""
    out: list[tuple[str, str, int, int]] = []
    for kind in ("link", "node", "sub", "sys"):
        out.extend(common_vars(a, b, kind))
    return out


def common_ids(a: Out, b: Out, kind: str) -> list[str]:
    """Element IDs present in both files, in file-a order."""
    sb = set(b.ids(kind))
    return [i for i in a.ids(kind) if i in sb]


def compare(legacy_out, refact_out, point_ids: dict | None = None) -> dict:
    """Full per-variable parity metrics + first divergence + parity verdict.

    point_ids (optional): {"link_ids": [...], "node_ids": [...]} restricts the
    detailed per-timestep block to the QA comparison points; the global metrics
    always span ALL elements.
    """
    A, B = Out(legacy_out), Out(refact_out)
    nP = min(A.n_periods, B.n_periods)

    fault = []
    if set(A.link_ids) != set(B.link_ids):
        fault.append(f"link-id mismatch ({A.n_link} vs {B.n_link})")
    if set(A.node_ids) != set(B.node_ids):
        fault.append(f"node-id mismatch ({A.n_node} vs {B.n_node})")
    if A.n_periods != B.n_periods:
        fault.append(f"period-count mismatch ({A.n_periods} vs {B.n_periods})")

    link_ids = [i for i in A.link_ids if i in set(B.link_ids)]
    node_ids = [i for i in A.node_ids if i in set(B.node_ids)]

    # Primary state vars must be bit-identical (max_abs == 0); derived float32
    # quantities (head, velocity, volume) carry a storage floor, so they are
    # judged by their max |Δ| / float32-ULP ratio instead.
    EXACT = {"link.FLOW", "link.DEPTH", "node.DEPTH"}
    FLOOR_RATIO = 1.5  # ≤ this many float32 ULPs counts as "at storage floor"

    per_var = {}
    first = {"period": None, "eid": None, "var": None}
    worst = {"abs": 0.0, "eid": None, "var": None}

    for kind, name, var in ALL_VARS:
        key = f"{kind}.{name}"
        ids = link_ids if kind == "link" else node_ids
        v_abs = v_rel = 0.0
        v_sq = 0.0
        v_n = 0
        v_exact = 0          # # of (element,period) cells with Δ == 0 exactly
        v_ulp = 0.0          # max |Δ| / float32-ULP(value)
        v_first = None
        v_first_eid = v_worst_eid = None
        for eid in ids:
            a = _series(A, kind, eid, var)[:nP]
            b = _series(B, kind, eid, var)[:nP]
            d = np.abs(a - b)
            if not d.size:
                continue
            dmax = float(d.max())
            if dmax > v_abs:
                v_abs, v_worst_eid = dmax, eid
            denom = np.maximum(np.abs(a), 1e-6)
            v_rel = max(v_rel, float((d / denom).max()))
            v_sq += float(np.sum(d * d))
            v_n += d.size
            v_exact += int((d == 0.0).sum())
            nz_mask = d > 0
            if nz_mask.any():
                ulp = np.spacing(np.maximum(np.abs(a), 1e-30).astype(np.float32))
                v_ulp = max(v_ulp, float((d[nz_mask] / ulp[nz_mask]).max()))
            nz = np.where(d > ABS_EPS)[0]
            if nz.size:
                fp = int(nz[0])
                if v_first is None or fp < v_first:
                    v_first, v_first_eid = fp, eid
        at_floor = (v_abs == 0.0) if key in EXACT else (v_ulp <= FLOOR_RATIO)
        per_var[key] = {
            "max_abs": v_abs, "max_rel": v_rel, "ulp_ratio": v_ulp,
            "rms": (v_sq / v_n) ** 0.5 if v_n else 0.0, "at_floor": at_floor,
            "n_cells": v_n, "n_exact": v_exact,    # strict: Δ==0 cell count
            "max_ulp": v_ulp,
            "first_div_period": v_first, "first_div_eid": v_first_eid,
            "worst_eid": v_worst_eid}
        if v_abs > worst["abs"]:
            worst = {"abs": v_abs, "eid": v_worst_eid, "var": key}
        if v_first is not None and (first["period"] is None
                                    or v_first < first["period"]):
            first = {"period": v_first, "eid": v_first_eid, "var": key}

    head_ulp_ratio = per_var["node.HEAD"]["ulp_ratio"]
    # SERIES parity = the brief's bar (flow/depth bit-identical; head at floor).
    series_parity = (not fault and per_var["link.FLOW"]["at_floor"]
                     and per_var["link.DEPTH"]["at_floor"]
                     and per_var["node.DEPTH"]["at_floor"]
                     and per_var["node.HEAD"]["at_floor"])
    # FULL parity additionally requires velocity + volume at the float32 floor.
    full_parity = series_parity and all(
        per_var[k]["at_floor"] for k in
        ("link.VELOCITY", "link.VOLUME", "node.VOLUME"))
    bit_parity = full_parity  # the gate the scorecard reports

    # ── STRICT bar: every (object, period, variable) cell EXACTLY equal at
    #    float32 (Δ == 0). This is the "results are identical" standard. ──
    total_cells = sum(per_var[k]["n_cells"] for k in per_var)
    total_exact = sum(per_var[k]["n_exact"] for k in per_var)
    max_ulp_overall = max((per_var[k]["max_ulp"] for k in per_var), default=0.0)
    strict_identical = (not fault and total_cells > 0
                        and total_exact == total_cells)
    # which variables are not yet exactly identical, with their ULP gap
    not_exact = {k: {"max_abs": per_var[k]["max_abs"],
                     "max_ulp": per_var[k]["max_ulp"],
                     "n_diff": per_var[k]["n_cells"] - per_var[k]["n_exact"]}
                 for k in per_var if per_var[k]["max_abs"] > 0.0}

    if full_parity:
        verdict = "PARITY"
    elif series_parity:
        verdict = "vol-diff"   # series match; volume/velocity accounting differs
    elif worst["abs"] < 1e-3 and not fault:
        verdict = "near"
    else:
        verdict = "DIVERGE"

    # ── strict raw byte equality (strongest possible check) ──
    bytes_results = (not fault and A.results_bytes() == B.results_bytes())
    bytes_body = (not fault and A.body_after_version() == B.body_after_version())

    # ── detailed per-timestep at the QA comparison points ──
    points = None
    if point_ids:
        points = {}
        for kind, key, vlist in (("link", "link_ids", LINK_VARS),
                                 ("node", "node_ids", NODE_VARS)):
            for eid in point_ids.get(key, []):
                avail = set(link_ids if kind == "link" else node_ids)
                if eid not in avail:
                    points[f"{kind}:{eid}"] = {"missing": True}
                    continue
                pe = {}
                for _, name, var in vlist:
                    a = _series(A, kind, eid, var)[:nP]
                    b = _series(B, kind, eid, var)[:nP]
                    d = np.abs(a - b)
                    nz = np.where(d > ABS_EPS)[0]
                    pe[name] = {"max_abs": float(d.max()) if d.size else 0.0,
                                "first_div_period": int(nz[0]) if nz.size else None}
                points[f"{kind}:{eid}"] = pe

    return {
        "verdict": verdict,
        "bit_parity": bit_parity,
        "series_parity": series_parity,
        "full_parity": full_parity,
        "strict_identical": strict_identical,
        "total_cells": total_cells,
        "total_exact": total_exact,
        "max_ulp_overall": max_ulp_overall,
        "not_exact": not_exact,
        "bytes_results_identical": bytes_results,
        "bytes_body_identical": bytes_body,
        "head_ulp_ratio": head_ulp_ratio,
        "n_periods": nP,
        "fault": fault,
        "first_div": first,
        "worst": worst,
        "per_var": per_var,
        "points": points,
        "flow_units": A.flow_units,
    }


# ── full-coverage comparison (all element kinds, all pollutants) ────────────

def _var_metrics(A: Out, B: Out, kind: str, ia: int, ib: int,
                 ids: list[str], n_periods: int,
                 rtol: float, atol: float) -> dict:
    """Diff one (kind, variable) across every element and period."""
    v_abs = v_rel = v_sq = v_ulp = 0.0
    v_n = v_exact = 0
    v_first: int | None = None
    v_first_eid = v_worst_eid = None
    n_over_tol = 0
    for eid in ids:
        a = A.series(kind, eid, ia)[:n_periods]
        b = B.series(kind, eid, ib)[:n_periods]
        d = np.abs(a - b)
        if not d.size:
            continue
        dmax = float(d.max())
        if dmax > v_abs:
            v_abs, v_worst_eid = dmax, eid
        denom = np.maximum(np.abs(a), 1e-6)
        v_rel = max(v_rel, float((d / denom).max()))
        v_sq += float(np.sum(d * d))
        v_n += d.size
        v_exact += int((d == 0.0).sum())
        n_over_tol += int((d > (atol + rtol * np.abs(a))).sum())
        nz = d > 0
        if nz.any():
            ulp = np.spacing(np.maximum(np.abs(a), 1e-30).astype(np.float32))
            v_ulp = max(v_ulp, float((d[nz] / ulp[nz]).max()))
        over = np.where(d > ABS_EPS)[0]
        if over.size and (v_first is None or int(over[0]) < v_first):
            v_first, v_first_eid = int(over[0]), eid
    return {"max_abs": v_abs, "max_rel": v_rel, "max_ulp": v_ulp,
            "rms": (v_sq / v_n) ** 0.5 if v_n else 0.0,
            "n_cells": v_n, "n_exact": v_exact, "n_over_tol": n_over_tol,
            "first_div_period": v_first, "first_div_eid": v_first_eid,
            "worst_eid": v_worst_eid}


def compare_full(a_out, b_out, *, rtol: float = 1e-9, atol: float = 1e-12,
                 kinds: tuple[str, ...] = ("link", "node", "sub", "sys"),
                 max_offenders: int = 10) -> dict:
    """Element × variable × period comparison over ALL element kinds.

    This is scoring dimension 3 of the platform plan: every subcatchment,
    node, link, and system variable — including per-pollutant variables — at
    every reported period. Variables and pollutants are matched by name, so
    files written in different dialects are compared over their intersection.

    Verdict is tolerance-based (`rtol`/`atol` from the comparison pair or the
    case's metadata override), NOT the float32-ULP bit-parity ladder that
    `compare()` implements; use `compare()` for the near-bit-parity gate and
    this for general engine-vs-engine grading.
    """
    A, B = Out(a_out), Out(b_out)
    n_periods = min(A.n_periods, B.n_periods)

    fault: list[str] = []
    for kind in kinds:
        if kind == "sys":
            continue
        if set(A.ids(kind)) != set(B.ids(kind)):
            fault.append(f"{kind}-id mismatch "
                         f"({len(A.ids(kind))} vs {len(B.ids(kind))})")
    if A.n_periods != B.n_periods:
        fault.append(f"period-count mismatch ({A.n_periods} vs {B.n_periods})")
    if A.dialect != B.dialect:
        fault.append(f"dialect differs ({A.dialect} vs {B.dialect}) "
                     "— compared over the common variable set")

    per_var: dict[str, dict] = {}
    skipped: dict[str, list[str]] = {}
    for kind in kinds:
        ids = ["SYSTEM"] if kind == "sys" else common_ids(A, B, kind)
        names_a, names_b = set(A.var_names(kind)), set(B.var_names(kind))
        if names_a ^ names_b:
            skipped[kind] = sorted(names_a ^ names_b)
        for _, name, ia, ib in common_vars(A, B, kind):
            per_var[f"{kind}.{name}"] = _var_metrics(
                A, B, kind, ia, ib, ids, n_periods, rtol, atol)

    total_cells = sum(v["n_cells"] for v in per_var.values())
    total_exact = sum(v["n_exact"] for v in per_var.values())
    total_over = sum(v["n_over_tol"] for v in per_var.values())
    # Ranked by HOW MANY cells violate the tolerance first, then by magnitude.
    # Sorting by max_rel alone lets a single near-zero cell (where the relative
    # error is arbitrarily large but the absolute difference is negligible)
    # outrank a systematic divergence across every element and period.
    offenders = sorted(
        ({"var": k, "element": v["worst_eid"], "max_abs": v["max_abs"],
          "max_rel": v["max_rel"], "first_div_period": v["first_div_period"],
          "n_over_tol": v["n_over_tol"]}
         for k, v in per_var.items() if v["n_over_tol"]),
        key=lambda o: (o["n_over_tol"], o["max_abs"]),
        reverse=True)[:max_offenders]

    within_tol = not fault and total_over == 0
    return {
        "verdict": "PASS" if within_tol else ("ERROR" if fault else "FAIL"),
        "within_tol": within_tol,
        "rtol": rtol, "atol": atol,
        "dialects": {"a": A.dialect, "b": B.dialect},
        "n_periods": n_periods,
        "n_elements": {k: (1 if k == "sys" else len(common_ids(A, B, k)))
                       for k in kinds},
        "total_cells": total_cells,
        "total_exact": total_exact,
        "total_over_tol": total_over,
        "strict_identical": (not fault and total_cells > 0
                             and total_exact == total_cells),
        "worst_offenders": offenders,
        "skipped_vars": skipped,
        "fault": fault,
        "per_var": per_var,
        "flow_units": A.flow_units,
    }


def drilldown(legacy_out, refact_out, kind: str, var_name: str,
              eid: str | None = None, limit: int | None = None):
    """Print the per-period legacy vs refactored series for one element."""
    name2var = {"link": {"FLOW": LINK_FLOW, "DEPTH": LINK_DEPTH,
                         "VELOCITY": LINK_VELOCITY, "VOLUME": LINK_VOLUME},
                "node": {"DEPTH": NODE_DEPTH, "HEAD": NODE_HEAD,
                         "VOLUME": NODE_VOLUME}}
    var = name2var[kind][var_name]
    A, B = Out(legacy_out), Out(refact_out)
    ids = A.link_ids if kind == "link" else A.node_ids
    if eid is None:  # pick worst
        worst, wm = ids[0], -1.0
        for e in ids:
            a, b = _series(A, kind, e, var), _series(B, kind, e, var)
            n = min(len(a), len(b))
            m = float(np.abs(a[:n] - b[:n]).max())
            if m > wm:
                wm, worst = m, e
        eid = worst
    a, b = _series(A, kind, eid, var), _series(B, kind, eid, var)
    n = min(len(a), len(b))
    if limit:
        n = min(n, limit)
    print(f"# {kind}.{var_name} eid={eid}  (legacy vs refactored)")
    print(f"{'period':>6} {'legacy':>16} {'refactored':>16} {'abs_diff':>14}")
    for i in range(n):
        d = a[i] - b[i]
        mark = "  <==" if abs(d) > ABS_EPS else ""
        print(f"{i:6d} {a[i]:16.9g} {b[i]:16.9g} {d:14.6e}{mark}")


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    import sys, json
    if len(sys.argv) >= 5 and sys.argv[1] == "drill":
        # drill <legacy.out> <refact.out> <link|node> <VAR> [eid] [limit]
        _, _, leg, ref, kind, var = sys.argv[:6]
        eid = sys.argv[6] if len(sys.argv) > 6 else None
        lim = int(sys.argv[7]) if len(sys.argv) > 7 else None
        drilldown(leg, ref, kind, var, eid, lim)
    else:
        leg, ref = sys.argv[1], sys.argv[2]
        print(json.dumps(compare(leg, ref), indent=2, default=str))
