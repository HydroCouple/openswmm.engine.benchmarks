#!/usr/bin/env python3
"""Reference generation: cases/<id>/{reference.csv, provenance.yaml}.

One shared command (`run_swashes.py gen-refs`) regenerates every case —
no per-case scripts. `--check` recomputes each reference at 2x density and
asserts < 1e-6 interpolated self-agreement (guards grid-dependence bugs in
the semi-analytic solvers; SWASHES paper Remark 1).
"""
from __future__ import annotations

import numpy as np

from . import config
from .cases_bends import BEND_CASES
from .cases_pseudo2d import PSEUDO2D_CASES, reference_profile_p2d
from .cases_steady import STEADY_CASES, reference_profile, shock_x
from .cases_transient import (ALL_TRANSIENT, TRANSIENT_CASES,
                              reference_profile_t, reference_strip_2donly)

REF_DENSITY = 20          # reference stations per model cell (>= 10x rule)


class MissingReferenceError(RuntimeError):
    """A ref_source='2d' case has no pinned reference_2d.csv yet."""


def all_cases():
    return STEADY_CASES + PSEUDO2D_CASES + ALL_TRANSIENT + BEND_CASES


def case_by_id(cid: str):
    for c in all_cases():
        if c.id == cid:
            return c
    raise KeyError(cid)


def _ref_grid(case, density: int = REF_DENSITY) -> np.ndarray:
    return np.linspace(0.0, case.L, density * case.nx + 1)


def reference_blocks(case, density: int = REF_DENSITY) -> dict:
    """{t: (x, h, q)} from analytic formulas — or, for ref_source='2d'
    cases (bend family), from the pinned 2D-engine centerline profile at
    cases/<id>/reference_2d.csv (`density` is ignored: the pinned grid is
    the reference grid)."""
    if getattr(case, "ref_source", "analytic") == "2d":
        from . import extract
        pin = config.CASES_DIR / case.id / "reference_2d.csv"
        if not pin.exists():
            raise MissingReferenceError(
                f"{case.id}: no 2D reference pinned — run "
                f"`python run_swashes.py gen-2d-ref --cases {case.id} --pin`")
        return {t: (p["x"], p["h"], p["q"])
                for t, p in extract.read_extracted_csv(pin).items()}
    x = _ref_grid(case, density)
    blocks: dict = {}
    steady_ids = {c.id for c in STEADY_CASES}
    pseudo_ids = {c.id for c in PSEUDO2D_CASES}
    transient_ids = {c.id for c in TRANSIENT_CASES}
    if case.id in steady_ids:
        h, q = reference_profile(case, x)
        blocks[case.compare_times[0]] = (x, h, q)
    elif case.id in pseudo_ids:
        h, q = reference_profile_p2d(case, x)
        blocks[case.compare_times[0]] = (x, h, q)
    elif case.id in transient_ids:
        for t in case.compare_times:
            h, q = reference_profile_t(case, x, t)
            blocks[t] = (x, h, q)
    else:                                       # 2D-only strip references
        for t in case.compare_times:
            h, q = reference_strip_2donly(case, x, t)
            blocks[t] = (x, h, q)
    return blocks


def write_reference(case) -> str:
    d = config.CASES_DIR / case.id
    d.mkdir(parents=True, exist_ok=True)
    rows = [f"# {case.id} — {case.title}",
            f"# {case.swashes_ref}; Delestre et al. 2013, doi 10.1002/fld.3741",
            "# Independent Python implementation (swasheslib/analytic.py); "
            "no SWASHES-tool output vendored.",
            f"# grid: {REF_DENSITY * case.nx + 1} stations "
            f"({REF_DENSITY}x model resolution nx={case.nx})",
            "t_s,x_m,h_m,q_m2_per_s"]
    for t, (x, h, q) in sorted(reference_blocks(case).items()):
        for xi, hi, qi in zip(x, h, q):
            rows.append(f"{t:.6g},{xi:.8g},{hi:.10g},{qi:.10g}")
    path = d / "reference.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return str(path)


def write_provenance(case, verification_class: str = "analytical",
                     extra: list[str] | None = None) -> str:
    d = config.CASES_DIR / case.id
    d.mkdir(parents=True, exist_ok=True)
    xs = shock_x(case) if (case in STEADY_CASES
                           or case in PSEUDO2D_CASES) else None
    if verification_class == "analytical":
        source_lines = [
            "source:",
            "  citation: \"Delestre et al. (2013), SWASHES: a compilation of "
            "shallow water analytic solutions..., IJNMF\"",
            "  doi: 10.1002/fld.3741",
            f"  section: \"{case.swashes_ref}\"",
            "reference:",
            "  file: reference.csv",
            "  columns: [t_s, x_m, h_m, q_m2_per_s]",
            "  generator: \"python run_swashes.py gen-refs --cases "
            f"{case.id}\"",
            "  independent_implementation: true   # no CeCILL-V2 SWASHES-tool "
            "output vendored",
        ]
    else:
        source_lines = [
            "reference:",
            "  file: reference_2d.csv",
            "  columns: [t_s, x_m, h_m, q_m2_per_s]   # x = centerline arc "
            "length s",
            "  generator: \"python run_swashes.py gen-2d-ref --cases "
            f"{case.id} --pin\"",
        ] + (extra or [])
    lines = [
        f"id: {case.id}",
        f"title: \"{case.title}\"",
        f"verification_class: {verification_class}",
        *source_lines,
        "parameters:",
        f"  L_m: {case.L}",
        f"  W1d_m: {case.W1d}",
        f"  W2d_m: {case.W2d}",
        f"  n_manning: {case.n_manning}",
        f"  nx: {case.nx}",
        f"  dt_routing_s: {case.dt_routing}",
        f"  report_step_s: {case.report_step}",
        f"  t_end_s: {case.t_end}",
        f"  compare_times_s: [{', '.join(str(t) for t in case.compare_times)}]",
        f"  upstream: {case.upstream.kind}"
        + (f" (q={case.upstream.q} m2/s)" if case.upstream.kind == "inflow_q"
           else (f" (eta={case.upstream.eta} m)"
                 if case.upstream.kind == "stage" else "")),
        f"  downstream: {case.downstream.kind}"
        + (f" (eta={case.downstream.eta} m)"
           if case.downstream.kind == "stage" else ""),
        f"  interior_mask: [{case.interior_mask[0]}, {case.interior_mask[1]}]",
    ]
    if xs is not None:
        lines.append(f"  x_shock_m: {xs:.6f}")
    if case.opts_1d:
        lines.append(f"  opts_1d: {case.opts_1d}")
    if case.opts_2d:
        lines.append(f"  opts_2d: {case.opts_2d}")
    lines.append("cells:")
    for sid, pol in case.cells.items():
        lines.append(f"  {sid}:")
        lines.append(f"    mode: {pol.mode}")
        lines.append(f"    tol: {pol.tol}")
        if pol.baseline_tol:
            lines.append(f"    baseline_tol: {pol.baseline_tol}")
        if pol.note:
            lines.append(f"    note: \"{pol.note}\"")
    path = d / "provenance.yaml"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def self_check(case, tol: float = 1e-6) -> float:
    """Max interpolated disagreement between the standard-density and
    2x-density references."""
    worst = 0.0
    b1 = reference_blocks(case, REF_DENSITY)
    b2 = reference_blocks(case, 2 * REF_DENSITY)
    for t in b1:
        x1, h1, _ = b1[t]
        x2, h2, _ = b2[t]
        worst = max(worst, float(np.max(np.abs(np.interp(x1, x2, h2) - h1))))
    if worst > tol:
        raise AssertionError(f"{case.id}: self-check {worst:.3g} > {tol:g}")
    return worst


def main(case_glob: str | None = None, check: bool = False) -> None:
    import fnmatch
    for case in all_cases():
        if case_glob and not fnmatch.fnmatch(case.id, case_glob):
            continue
        if getattr(case, "ref_source", "analytic") == "2d":
            print(f"{case.id}: 2d-reference case — skipped (use "
                  f"`gen-2d-ref --cases {case.id} --pin`)")
            continue
        ref = write_reference(case)
        prov = write_provenance(case)
        msg = f"{case.id}: {ref}"
        if check:
            worst = self_check(case)
            msg += f"  (self-check max dev {worst:.2e})"
        print(msg)
