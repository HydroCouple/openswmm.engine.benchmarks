#!/usr/bin/env python3
"""Verdict taxonomy, reference classes, scores envelope, badges, exit policy.

A suite's sweep produces one envelope:
    {"suite": str, "engine_sha": str, "timestamp": iso8601, "cells": [cell...]}
where each cell minimally carries {"case", "solver", "verdict", ...metrics}.
Envelopes are written incrementally (rewrite-after-each-cell) so interrupted
sweeps resume; `save_cell` implements that convention.

Verdicts (per matrix cell):
  PASS / FAIL                — graded against analytic tolerances
  BASELINE-PASS / BASELINE-FAIL — graded against a pinned baseline profile
  XFAIL                      — expected-fail ran and failed (documented reason)
  XPASS                      — expected-fail PASSED analytic tols: loud promotion candidate
  ERROR                      — nonzero exit / NaN / missing output
  SKIP                       — physics not applicable to this solver
  UNAVAILABLE                — solver/exe not present in this environment

CI gate: nonzero iff any {FAIL, BASELINE-FAIL, ERROR, XPASS}.
"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

VERDICTS = ("PASS", "FAIL", "BASELINE-PASS", "BASELINE-FAIL",
            "XFAIL", "XPASS", "ERROR", "SKIP", "UNAVAILABLE")
GATING = {"FAIL", "BASELINE-FAIL", "ERROR", "XPASS"}

# ── reference classes ──────────────────────────────────────────────────────
# What "truth" a case is graded against determines what may be computed from
# it and what a failure means. See the plan's "Reference classes" section.
#
#   analytic          closed-form exact solution      -> engine is wrong
#   manufactured      exact by construction (MMS)     -> engine is wrong
#   external_reference another tool's results         -> engines disagree
#   observed          field measurements              -> goodness of fit
#   blessed_baseline  pinned prior output @ SHA       -> behavior changed
#   self_consistency  none; invariants + parity only  -> engines differ
REFERENCE_CLASSES = ("analytic", "manufactured", "external_reference",
                     "observed", "blessed_baseline", "self_consistency")

#: Classes whose reference IS ground truth — the only ones for which error
#: norms and convergence order are meaningful, and the only ones that may be
#: reported as an accuracy (verification) claim.
TRUTH_CLASSES = {"analytic", "manufactured"}

#: Default gating policy per reference class (a case's metadata may override).
DEFAULT_GATE = {
    "analytic": "fail",
    "manufactured": "fail",
    "external_reference": "report",
    "observed": "report",
    "blessed_baseline": "fail",       # fail on drift from the pinned baseline
    "self_consistency": "parity",     # graded only by parity + invariants
}


def is_truth(reference_class: str) -> bool:
    """May accuracy metrics (L1/L2/Linf, observed order) be computed/reported?"""
    return reference_class in TRUTH_CLASSES


def check_accuracy_allowed(reference_class: str) -> None:
    """Guard: refuse to compute accuracy metrics against a non-truth reference.

    Reporting an error norm against a baseline or another engine would imply
    an accuracy claim the reference cannot support.
    """
    if not is_truth(reference_class):
        raise ValueError(
            f"accuracy metrics are not meaningful for reference class "
            f"{reference_class!r}; only {sorted(TRUTH_CLASSES)} are ground truth")


def new_envelope(suite: str, engine_sha: str) -> dict:
    return {"suite": suite, "engine_sha": engine_sha,
            "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
            "cells": []}


def load(path: Path) -> dict | None:
    path = Path(path)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def save_cell(path: Path, envelope: dict, cell: dict) -> None:
    """Replace any prior cell for the same (case, solver) and rewrite the file."""
    key = (cell.get("case"), cell.get("solver"))
    envelope["cells"] = [c for c in envelope["cells"]
                         if (c.get("case"), c.get("solver")) != key]
    envelope["cells"].append(cell)
    Path(path).write_text(json.dumps(envelope, indent=2, default=str))


def exit_code(envelope: dict) -> int:
    return 1 if any(c.get("verdict") in GATING for c in envelope["cells"]) else 0


def summary(envelope: dict) -> str:
    counts: dict[str, int] = {}
    for c in envelope["cells"]:
        v = c.get("verdict", "?")
        counts[v] = counts.get(v, 0) + 1
    parts = [f"{v}:{counts[v]}" for v in VERDICTS if v in counts]
    return f"[{envelope.get('suite', '?')}] " + " ".join(parts) if parts else "no cells"


# ── badges ─────────────────────────────────────────────────────────────────
# shields.io endpoint JSON: https://shields.io/badges/endpoint-badge
# Published with the Pages site; consumable by this repo, the engine repo, and
# any registered engine's README.

BADGE_GREEN, BADGE_YELLOW, BADGE_RED, BADGE_GREY = (
    "brightgreen", "yellow", "red", "lightgrey")


def badge(label: str, message: str, color: str) -> dict:
    return {"schemaVersion": 1, "label": label, "message": message,
            "color": color}


def _cells(envelopes: list[dict], predicate) -> list[dict]:
    return [c for env in envelopes for c in env.get("cells", []) if predicate(c)]


def badges(envelopes: list[dict], *, corpus_count: int | None = None) -> dict[str, dict]:
    """Build the badge set from one or more suite envelopes.

    `verification` counts ONLY truth-class cases (analytic + manufactured) —
    it is the sole accuracy claim. `regression` covers everything else, so a
    large corpus pass rate is never presented as an accuracy figure.
    """
    out: dict[str, dict] = {}

    ver = _cells(envelopes, lambda c: is_truth(c.get("reference_class", "")))
    if ver:
        # A skipped case is NOT a verified case. Counting SKIP toward the
        # numerator would report "17/17" for a suite that actually checked 6 —
        # the exact overclaim the verification/regression split exists to
        # prevent. Skips are excluded from the ratio and disclosed alongside it.
        unchecked = [c for c in ver
                     if c.get("verdict") in ("SKIP", "UNAVAILABLE")]
        checked = [c for c in ver if c not in unchecked]
        ok = sum(1 for c in checked
                 if c.get("verdict") in ("PASS", "BASELINE-PASS", "XFAIL"))
        msg = f"{ok}/{len(checked)} checked" if checked else "none checked"
        if unchecked:
            msg += f" · {len(unchecked)} unchecked"
        if not checked:
            color = BADGE_GREY
        elif ok < len(checked):
            color = BADGE_RED
        elif unchecked:
            color = BADGE_YELLOW      # all checks pass, but coverage is partial
        else:
            color = BADGE_GREEN
        out["verification"] = badge("verification", msg, color)

    reg = _cells(envelopes, lambda c: not is_truth(c.get("reference_class", "")))
    if reg:
        bad = sum(1 for c in reg if c.get("verdict") in GATING)
        out["regression"] = badge(
            "regression", "passing" if not bad else f"{bad} failing",
            BADGE_GREEN if not bad else BADGE_RED)

    par = [c for c in _cells(envelopes, lambda c: "max_rel" in c)]
    if par:
        worst = max(float(c.get("max_rel") or 0.0) for c in par)
        failed = any(c.get("verdict") in GATING for c in par)
        out["parity"] = badge(
            "parity", "fail" if failed else f"max rel {worst:.1e}",
            BADGE_RED if failed else BADGE_GREEN)

    mb = [c for c in _cells(envelopes, lambda c: "continuity_err" in c)]
    if mb:
        worst = max(abs(float(c.get("continuity_err") or 0.0)) for c in mb)
        out["mass-balance"] = badge(
            "mass balance", f"worst {worst:.2f}%",
            BADGE_GREEN if worst <= 1 else BADGE_YELLOW if worst <= 5 else BADGE_RED)

    st = [c for c in _cells(envelopes, lambda c: "pct_not_converging" in c)]
    if st:
        stable = sum(1 for c in st
                     if float(c.get("pct_not_converging") or 0.0) <= 1.0)
        pct = 100.0 * stable / len(st)
        out["stability"] = badge(
            "stability", f"{pct:.0f}% stable",
            BADGE_GREEN if pct >= 99 else BADGE_YELLOW if pct >= 90 else BADGE_RED)

    if corpus_count is not None:
        out["models"] = badge("models", f"{corpus_count:,}", "blue")

    return out


def write_badges(dest: Path, badge_map: dict[str, dict]) -> list[Path]:
    """Write one endpoint-JSON file per badge; returns the paths written."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    written = []
    for name, payload in badge_map.items():
        p = dest / f"{name}.json"
        p.write_text(json.dumps(payload))
        written.append(p)
    return written
