#!/usr/bin/env python3
"""Classify a parity sweep's non-PASS cells by cause.

A sweep over 1,396 models produces thousands of cells; triage is only useful
if failures are grouped by MECHANISM rather than listed by case. This reads a
scores envelope and buckets every non-PASS cell into a named cause, so
`results/SWEEP_TRIAGE.md` states a cause per bucket instead of per case.

    python tools/triage_sweep.py results/parity/scores_nightly.json
    python tools/triage_sweep.py results/parity/scores_nightly.json --markdown
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

#: float32 is the .out storage type; its epsilon is ~1.19e-7, so a relative
#: difference at or below a few ULP cannot be distinguished from storage
#: rounding of a double-precision value. A pair tolerance of rtol=1e-9 is
#: BELOW that floor by two orders of magnitude, so such cells are reported as
#: their own bucket rather than lumped in with real divergence.
F32_ULP_REL = 2.4e-7        # ~2 ULP of float32


def classify(cell: dict) -> tuple[str, str]:
    """Return (bucket, detail) for one non-PASS cell."""
    v = cell.get("verdict")
    if v in ("PASS", "SKIP"):
        return v.lower(), ""
    if "pair" not in cell:
        # engine-run cell
        note = (cell.get("note") or "").strip()
        if v == "UNAVAILABLE":
            if "insufficient disk" in note:
                return "env-disk", note
            return "env-launch", note
        if v == "ERROR":
            return "engine-error", note or "nonzero exit / no output"
        return v.lower(), note

    if v == "UNAVAILABLE":
        return "pair-no-output", cell.get("note", "")

    worst = cell.get("worst_var") or "?"
    over = cell.get("total_over_tol") or 0
    rel = cell.get("max_rel") or 0.0

    if worst == "sys.TEMPERATURE":
        # Known engine-side default divergence; if it is the ONLY offender the
        # case is otherwise at parity.
        return "sys-temperature-default", f"{over} cell(s) over tol"
    if rel <= F32_ULP_REL:
        return "f32-rounding", f"max_rel={rel:.2e} (<= ~2 float32 ULP)"
    if rel >= 0.5:
        return "gross-divergence", f"{worst} max_rel={rel:.2e} over={over}"
    return "numeric-divergence", f"{worst} max_rel={rel:.2e} over={over}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scores", type=Path)
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--limit", type=int, default=12,
                    help="example cases listed per bucket")
    args = ap.parse_args(argv)

    env = json.loads(args.scores.read_text())
    cells = env.get("cells", [])
    buckets: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for c in cells:
        b, detail = classify(c)
        buckets[b].append((c.get("case", "?"), detail))

    order = sorted(buckets, key=lambda k: -len(buckets[k]))
    total = len(cells)
    cases = {c.get("case") for c in cells}

    if args.markdown:
        print(f"| bucket | cells | share | example cases |")
        print(f"|---|---:|---:|---|")
        for b in order:
            ex = ", ".join(f"`{c}`" for c, _ in buckets[b][:4])
            print(f"| {b} | {len(buckets[b])} | "
                  f"{100*len(buckets[b])/total:.1f}% | {ex} |")
        return 0

    print(f"{total} cells over {len(cases)} cases  ({args.scores})")
    for b in order:
        rows = buckets[b]
        print(f"\n{b:28s} {len(rows):6d} cells  ({100*len(rows)/total:.1f}%)")
        for case, detail in rows[:args.limit]:
            print(f"    {case:44s} {detail}")
        if len(rows) > args.limit:
            print(f"    ... and {len(rows)-args.limit} more")
    return 0


if __name__ == "__main__":
    sys.exit(main())
