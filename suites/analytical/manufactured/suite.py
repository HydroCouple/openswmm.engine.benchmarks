#!/usr/bin/env python3
"""analytical/manufactured — exact-by-construction reference datasets.

17 cases whose reference is exact by construction — a method-of-manufactured-
solutions problem, or an analytically integrated ODE — rather than measured or
simulated. `reference.class` is ``manufactured``: error norms are meaningful
and these cells feed the `verification` badge.

Unlike the other suites, most of these cases have no ``.inp``: they are
reference datasets for engine *components* (infiltration, groundwater
recession, ODE integrators, cross-section geometry), consumed by the engine's
own unit tests. What this suite contributes to the platform is the part that
can be checked anywhere: that each committed ``reference.csv`` is still
exactly reproducible from the formula its provenance documents.

    python run_regression.py --suite analytical/manufactured
    python -m suites.analytical.manufactured.suite --regen   # rewrite references

Cases that ship a generator script are verified here. Cases that do not are
reported SKIP with the reason, never silently counted as passing.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SUITE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SUITE_DIR.parents[2]
sys.path.insert(0, str(REPO_ROOT))

from harness import engines, scoring  # noqa: E402

SUITE = "analytical/manufactured"
REFERENCE_CLASS = "manufactured"
CASES = SUITE_DIR / "cases"
RESULTS = REPO_ROOT / "results" / "analytical_manufactured"


def cases() -> list[Path]:
    return sorted(d for d in CASES.iterdir()
                  if d.is_dir() and (d / "provenance.yaml").exists())


def claims_reproducible(case: Path) -> bool:
    """Does this case's provenance assert that its reference is reproducible?"""
    import yaml
    try:
        doc = yaml.safe_load((case / "provenance.yaml").read_text(encoding="utf-8")) or {}
    except Exception:
        return False
    return bool((doc.get("provenance") or {}).get("reproducible"))


def _generator(case: Path) -> Path | None:
    scripts = sorted((case / "scripts").glob("*.py")) if (case / "scripts").is_dir() else []
    return scripts[0] if scripts else None


def _check_case(case: Path, regen: bool = False) -> dict:
    """Re-run the case's generator and compare against the committed data."""
    cell = {"case": case.name, "solver": "closed-form",
            "reference_class": REFERENCE_CLASS}
    ref = case / "reference.csv"
    script = _generator(case)

    if not ref.exists():
        return {**cell, "verdict": "ERROR", "note": "reference.csv missing"}
    if script is None:
        # A case whose provenance asserts reproducible:true but ships no
        # generator makes a claim this repository cannot back. That is data
        # debt, not a regression, so it does not gate CI — but it is reported
        # as an unmet claim rather than a quiet skip.
        return {**cell, "verdict": "SKIP",
                "unverified_claim": claims_reproducible(case),
                "note": ("provenance asserts reproducible:true but ships no "
                         "generator script — claim unverifiable here"
                         if claims_reproducible(case) else
                         "no generator script; provenance documents the "
                         "formula but does not claim reproducibility")}

    before = ref.read_bytes()
    proc = subprocess.run([sys.executable, str(script)], cwd=str(case),
                          capture_output=True, text=True, timeout=300)
    after = ref.read_bytes() if ref.exists() else None

    if proc.returncode != 0:
        ref.write_bytes(before)
        tail = (proc.stderr.strip().splitlines() or ["nonzero exit"])[-1]
        return {**cell, "verdict": "ERROR", "note": tail[:200]}
    if after == before:
        return {**cell, "verdict": "PASS", "note": "reference reproduced exactly"}
    if regen:
        return {**cell, "verdict": "BASELINE-FAIL",
                "note": "reference REGENERATED — review the diff before committing"}
    ref.write_bytes(before)                      # leave committed data untouched
    return {**cell, "verdict": "FAIL",
            "note": "generator no longer reproduces the committed reference"}


def run(argv: list[str] | None = None) -> dict | None:
    ap = argparse.ArgumentParser(prog="manufactured")
    ap.add_argument("--regen", action="store_true",
                    help="keep regenerated references instead of restoring them")
    ap.add_argument("--only", help="comma-separated case names")
    args, _ = ap.parse_known_args(argv or [])

    RESULTS.mkdir(parents=True, exist_ok=True)
    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    scores = RESULTS / "scores.json"

    selected = cases()
    if args.only:
        wanted = set(args.only.split(","))
        selected = [c for c in selected if c.name in wanted]

    for case in selected:
        scoring.save_cell(scores, envelope, _check_case(case, regen=args.regen))

    unmet = [c["case"] for c in envelope["cells"] if c.get("unverified_claim")]
    if unmet:
        print(f"note: {len(unmet)} case(s) assert reproducible:true but ship no "
              f"generator, so the claim cannot be checked here: "
              f"{', '.join(unmet)}", file=sys.stderr)
    print(scoring.summary(envelope))
    return envelope


def report(argv: list[str] | None = None) -> list[Path]:
    """Regenerate the suite's markdown report — STUB (plan step 5)."""
    return []


if __name__ == "__main__":
    env = run(sys.argv[1:])
    sys.exit(scoring.exit_code(env) if env else 0)
