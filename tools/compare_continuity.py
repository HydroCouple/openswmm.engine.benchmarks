"""Compare two reports without conflating pollutant columns or hiding NaNs.

Usage: python -m tools.compare_continuity legacy.rpt v6.rpt
This diagnoses reports only; binary-output parity is a separate comparison.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path

from harness.rptparse import continuity_rows


def differences(a: dict, b: dict, *, atol: float = 0.0015, rtol: float = 0.001):
    """Yield significant printed-row differences and all non-finite values.

    Include matching NaNs: an undefined ledger is not evidence of conservation.
    The tolerances accommodate reports rounded to three decimal places.
    """
    for key in sorted(a.keys() | b.keys()):
        x, y = a.get(key), b.get(key)
        if x is None or y is None:
            yield key, x, y, "missing row"
        elif not math.isfinite(x) or not math.isfinite(y):
            yield key, x, y, "non-finite ledger"
        elif abs(x - y) > max(atol, rtol * max(abs(x), abs(y))):
            yield key, x, y, "difference"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("legacy", type=Path)
    ap.add_argument("v6", type=Path)
    args = ap.parse_args()
    a = continuity_rows(args.legacy.read_text(encoding="utf-8", errors="replace"))
    b = continuity_rows(args.v6.read_text(encoding="utf-8", errors="replace"))
    if not a or not b:
        ap.error("both reports must contain continuity tables")
    rows = list(differences(a, b))
    for (table, label, column), x, y, why in rows:
        print(f"{table} | {label} | {column}: legacy={x} v6={y} ({why})")
    if not rows:
        print("Continuity tables match at printed precision.")
    return int(bool(rows))


if __name__ == "__main__":
    raise SystemExit(main())
