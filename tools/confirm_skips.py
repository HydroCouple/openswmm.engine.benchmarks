#!/usr/bin/env python3
"""Confirm — by running them — that every skip-listed case fails as stated.

`suites/parity/manifests/skip_list.yaml` was built by STATIC analysis of each
deck's file references. That is a claim about behaviour, and an unverified
claim in a skip list is how a runnable model quietly stops being tested. This
runs each listed case through the engine and checks that the observed failure
matches the stated reason.

Outcomes per case:
  CONFIRMED   the engine failed, for the reason the list gives
  MISMATCH    the engine failed, but for a different reason
  RUNS        the engine SUCCEEDED — the entry should be removed

    python tools/confirm_skips.py
    python tools/confirm_skips.py --limit 20 --engine openswmm-v6
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness import corpus, engines, runner  # noqa: E402

OUT = REPO_ROOT / "results" / "skip_list_confirmation.json"

#: The reasons the list uses, and what each predicts in the report.
REASON_PATTERNS = {
    "missing input file": re.compile(
        r"ERROR (30[0-9]|31[0-9]|32[0-9]):|cannot open|could not open", re.I),
    "no hydraulic or hydrologic elements": re.compile(
        r"ERROR (30[0-9]|20[0-9]):|no .*(nodes|links|objects)", re.I),
}


def classify_reason(reason: str) -> str:
    for key in REASON_PATTERNS:
        if key in reason:
            return key
    return "other"


def main(argv=None) -> int:
    import yaml
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--engine", default="openswmm-v6")
    ap.add_argument("--timeout", type=float, default=120.0)
    args = ap.parse_args(argv)

    doc = yaml.safe_load(
        (REPO_ROOT / "suites/parity/manifests/skip_list.yaml").read_text())
    entries = doc.get("skip") or []
    if args.limit:
        entries = entries[:args.limit]

    reg = engines.resolve_all(engines.load())
    engine = reg.engines[args.engine]
    if not engine.ok:
        print(f"{args.engine} did not resolve: {engine.note}", file=sys.stderr)
        return 2

    cases = {c.id: c for c in corpus.load()}
    work = REPO_ROOT / "results" / "skip_confirm"
    work.mkdir(parents=True, exist_ok=True)

    rows, counts = [], {}
    for e in entries:
        cid = e["case"] if isinstance(e, dict) else e
        reason = (e.get("reason", "") if isinstance(e, dict) else "")
        case = cases.get(cid)
        if case is None:
            outcome, detail = "MISSING-CASE", "not present in the corpus"
        else:
            rpt = work / f"{cid}.rpt"
            r = runner.run(engine.exe, case.inp, rpt, work / f"{cid}.out",
                           timeout=args.timeout)
            text = rpt.read_text(errors="replace") if rpt.exists() else ""
            errs = [ln.strip() for ln in text.splitlines() if "ERROR" in ln]
            detail = (errs[0] if errs else r.get("stderr") or
                      f"rc={r['returncode']}")[:160]
            if r["ok"]:
                outcome = "RUNS"
            else:
                pat = REASON_PATTERNS.get(classify_reason(reason))
                blob = "\n".join(errs) or detail
                outcome = ("CONFIRMED" if pat and pat.search(blob)
                           else "MISMATCH")
            # the .out is not needed once the outcome is known
            (work / f"{cid}.out").unlink(missing_ok=True)
        counts[outcome] = counts.get(outcome, 0) + 1
        rows.append({"case": cid, "outcome": outcome,
                     "stated_reason": reason, "observed": detail})
        print(f"{outcome:13s} {cid:46s} {detail[:80]}", flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"engine": args.engine, "engine_sha": engines.engine_sha(),
         "counts": counts, "cases": rows}, indent=2))
    print(f"\n{counts}\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
