#!/usr/bin/env python3
"""Corpus discovery and tag-query selection.

Cases are selected by boolean TAG EXPRESSION, never by directory path —
directory placement under corpus/<collection>/ is organizational only. This is
what lets manifests, suite scopes, and report facets all be defined as queries
rather than hand-maintained file lists.

    lid AND pollutants
    transient AND NOT performance
    (hydraulics OR hydrology) AND regression

    python -m harness.corpus "lid AND pollutants"      # list matching cases
    python -m harness.corpus --census                  # counts per tag
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "corpus"


@dataclass
class Case:
    dir: Path
    meta: dict = field(default_factory=dict)
    prov: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.meta.get("id", self.dir.name)

    @property
    def tags(self) -> set[str]:
        return set(self.meta.get("tags") or [])

    @property
    def inp(self) -> Path:
        return self.dir / self.meta.get("model", "model.inp")

    @property
    def reference_class(self) -> str:
        return (self.meta.get("reference") or {}).get("class", "self_consistency")

    @property
    def tiers(self) -> list[str]:
        return list(self.meta.get("tiers") or ["nightly"])

    def tolerances(self, default_rtol: float, default_atol: float) -> tuple[float, float]:
        t = self.meta.get("tolerances") or {}
        return float(t.get("rtol", default_rtol)), float(t.get("atol", default_atol))


def load(root: Path | None = None) -> list[Case]:
    """Every case under corpus/ (or a subtree), metadata parsed."""
    import yaml
    root = Path(root or CORPUS)
    cases: list[Case] = []
    if not root.exists():
        return cases
    for meta_path in sorted(root.rglob("metadata.yaml")):
        if meta_path.parent.name == "_template":
            continue
        try:
            meta = yaml.safe_load(meta_path.read_text()) or {}
        except yaml.YAMLError:
            continue
        prov_path = meta_path.parent / "provenance.yaml"
        try:
            prov = yaml.safe_load(prov_path.read_text()) or {} \
                if prov_path.exists() else {}
        except yaml.YAMLError:
            prov = {}
        cases.append(Case(dir=meta_path.parent, meta=meta, prov=prov))
    return cases


# ── tag expressions ────────────────────────────────────────────────────────
_TOKEN = re.compile(r"\s*(\(|\)|\bAND\b|\bOR\b|\bNOT\b|[A-Za-z0-9_.:-]+)",
                    re.IGNORECASE)


def _tokenize(expr: str) -> list[str]:
    pos, out = 0, []
    while pos < len(expr):
        m = _TOKEN.match(expr, pos)
        if not m:
            raise ValueError(f"bad tag expression near {expr[pos:pos + 20]!r}")
        tok = m.group(1)
        out.append(tok.upper() if tok.upper() in ("AND", "OR", "NOT") else tok)
        pos = m.end()
    return out


def matches(tags: set[str], expr: str) -> bool:
    """Evaluate a boolean tag expression against a case's tag set.

    Recursive-descent over  expr := term (OR term)* ;
                            term := factor (AND factor)* ;
                            factor := NOT factor | '(' expr ')' | TAG
    Adjacent tags without an operator are treated as AND.
    """
    toks = _tokenize(expr)
    i = 0

    def peek() -> str | None:
        return toks[i] if i < len(toks) else None

    def parse_expr() -> bool:
        nonlocal i
        val = parse_term()
        while peek() == "OR":
            i += 1
            val = parse_term() or val
        return val

    def parse_term() -> bool:
        nonlocal i
        val = parse_factor()
        while peek() not in (None, ")", "OR"):
            if peek() == "AND":
                i += 1
            val = parse_factor() and val
        return val

    def parse_factor() -> bool:
        nonlocal i
        tok = peek()
        if tok is None:
            raise ValueError("unexpected end of tag expression")
        if tok == "NOT":
            i += 1
            return not parse_factor()
        if tok == "(":
            i += 1
            val = parse_expr()
            if peek() != ")":
                raise ValueError("unbalanced parenthesis in tag expression")
            i += 1
            return val
        if tok in ("AND", "OR", ")"):
            # A binary operator or a close-paren where a tag was expected —
            # e.g. "AND lid" or "lid OR AND". Treating it as a tag name would
            # silently evaluate to False and select nothing.
            raise ValueError(
                f"unexpected {tok!r} in tag expression — a tag was expected")
        i += 1
        return tok in tags

    result = parse_expr()
    if i != len(toks):
        raise ValueError(f"trailing tokens in tag expression: {toks[i:]}")
    return result


def select(cases: list[Case], expr: str | None = None,
           tier: str | None = None) -> list[Case]:
    """Filter cases by tag expression and/or CI tier."""
    out = cases
    if expr:
        out = [c for c in out if matches(c.tags, expr)]
    if tier:
        out = [c for c in out if tier in c.tiers]
    return out


def census(cases: list[Case]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for c in cases:
        for t in c.tags:
            counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("expr", nargs="?", help="tag expression, e.g. 'lid AND pollutants'")
    ap.add_argument("--tier", help="restrict to a CI tier (pr|nightly|weekly)")
    ap.add_argument("--census", action="store_true", help="print counts per tag")
    args = ap.parse_args(argv)

    cases = load()
    if not cases:
        print(f"no cases found under {CORPUS} "
              "(corpus migration is plan step 3)", file=sys.stderr)
        return 0
    if args.census:
        for tag, n in census(cases).items():
            print(f"{n:6d}  {tag}")
        print(f"{len(cases):6d}  TOTAL cases")
        return 0
    for c in select(cases, args.expr, args.tier):
        print(f"{c.id:40s} {c.reference_class:20s} {','.join(sorted(c.tags))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
