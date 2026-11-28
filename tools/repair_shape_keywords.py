#!/usr/bin/env python3
"""Correct cross-section shape keywords that no SWMM engine accepts.

Thirty-one decks of the legacy `owa-user` and `owa-routing` collections spell two
closed shapes with an underscore, `SEMI_ELLIPTICAL` and `SEMI_CIRCULAR`. SWMM's
keywords are `SEMIELLIPTICAL` and `SEMICIRCULAR` (keywords.c), and the match is by
leading part, so the underscored forms are ERROR 205 in EPA SWMM 5.2.4 and in both
OpenSWMM engines: those decks have never run. The shape the author meant is the
one named; the edit changes the spelling of a keyword, nothing else, and is
recorded in the case's ``provenance.yaml`` under ``modifications``.

    python tools/repair_shape_keywords.py            # report
    python tools/repair_shape_keywords.py --apply
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "corpus"

FIXES = {"SEMI_ELLIPTICAL": "SEMIELLIPTICAL", "SEMI_CIRCULAR": "SEMICIRCULAR"}
ROW_RE = re.compile(r"^(\s*\S+\s+)(SEMI_ELLIPTICAL|SEMI_CIRCULAR)(\b)", re.I)


def repair_case(case: Path, apply: bool) -> dict[str, int]:
    inp = case / "model.inp"
    if not inp.exists():
        return {}
    lines = inp.read_bytes().decode("latin-1").splitlines(keepends=True)
    section = None
    counts: dict[str, int] = {}
    for i, line in enumerate(lines):
        stripped = line.split(";", 1)[0].strip()
        m = re.match(r"^\[([A-Za-z_0-9]+)\]", stripped)
        if m:
            section = m.group(1).upper()
            continue
        if section != "XSECTIONS" or not stripped:
            continue
        mr = ROW_RE.match(line)
        if not mr:
            continue
        bad = mr.group(2).upper()
        counts[bad] = counts.get(bad, 0) + 1
        # Keep the column layout: the replacement is one character shorter, so pad.
        lines[i] = line[:mr.start(2)] + FIXES[bad] + " " + line[mr.end(2):]
    if counts and apply:
        inp.write_bytes("".join(lines).encode("latin-1"))
        _record(case, counts)
    return counts


def _record(case: Path, counts: dict[str, int]) -> None:
    p = case / "provenance.yaml"
    doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    parts = ", ".join(f"{n} {bad} -> {FIXES[bad]}" for bad, n in sorted(counts.items()))
    note = (f"[XSECTIONS] shape keyword(s) corrected to SWMM's spelling ({parts}); the "
            "underscored forms are ERROR 205 in EPA SWMM 5.2.4 and in OpenSWMM, so the "
            "model had never run. Only the keyword's spelling changed.")
    prev = str(doc.get("modifications", "")).strip()
    doc["modifications"] = (prev + " " if prev else "") + note
    p.write_text(yaml.safe_dump(doc, sort_keys=False, default_flow_style=False,
                                allow_unicode=True), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    cases = rows = 0
    for meta in sorted(CORPUS.rglob("metadata.yaml")):
        if meta.parent.name == "_template":
            continue
        counts = repair_case(meta.parent, args.apply)
        if counts:
            cases += 1
            rows += sum(counts.values())
            print(f"  {meta.parent.relative_to(CORPUS)}: "
                  + ", ".join(f"{k} x{v}" for k, v in sorted(counts.items())))
    print("APPLIED" if args.apply else "DRY RUN — nothing changed")
    print(f"  cases {cases}, rows {rows}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
