#!/usr/bin/env python3
"""Report and dashboard generation.

Three output tiers, per the plan's "Reporting, artifacts & publishing":

  1. job summary   markdown for $GITHUB_STEP_SUMMARY (implemented here)
  2. site          static HTML dashboard published to GitHub Pages (STUB)
  3. badges        shields.io endpoint JSON (harness.scoring.badges)

Generated output is NEVER committed: it goes to results/ locally, to workflow
artifacts in CI, and to the Pages deployment for publication.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import scoring

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "results"
SITE_TEMPLATES = REPO_ROOT / "site" / "templates"


def job_summary(envelopes: list[dict]) -> str:
    """Markdown summary of one or more suite envelopes."""
    lines: list[str] = ["# Benchmark run", ""]
    for env in envelopes:
        cells = env.get("cells", [])
        lines += [f"## {env.get('suite', '?')}", "",
                  f"engine `{env.get('engine_sha', '?')}` · "
                  f"{env.get('timestamp', '')} · {len(cells)} cell(s)", "",
                  scoring.summary(env), ""]
        bad = [c for c in cells if c.get("verdict") in scoring.GATING]
        if bad:
            lines += ["<details><summary>Failures</summary>", "",
                      "| case | engine/pair | verdict | worst | note |",
                      "|---|---|---|---|---|"]
            for c in bad[:50]:
                worst = c.get("max_rel", c.get("continuity_err", ""))
                worst = f"{worst:.3e}" if isinstance(worst, float) else worst
                lines.append(
                    f"| {c.get('case','')} | {c.get('solver', c.get('pair',''))} "
                    f"| {c.get('verdict','')} | {worst} | {c.get('note','')} |")
            if len(bad) > 50:
                lines.append(f"| … | | {len(bad) - 50} more | | |")
            lines += ["", "</details>", ""]
    return "\n".join(lines)


def build_site(envelopes: list[dict], dest: Path) -> list[Path]:
    """Render the static dashboard — STUB (plan step 5).

    Target layout:
        /                          latest scoreboard + badges
        /runs/<date>_<engine>@<sha>/   immutable per-run reports
        /tags/<tag>/               per-tag facets + corpus census
        /dev/bench/                perf trends (github-action-benchmark)
    """
    raise NotImplementedError(
        "harness.report.build_site is a scaffold stub — see plan step 5.")


def load_envelopes(paths: list[Path]) -> list[dict]:
    out = []
    for p in paths:
        p = Path(p)
        for f in ([p] if p.is_file() else sorted(p.rglob("*scores*.json"))):
            try:
                out.append(json.loads(f.read_text()))
            except (OSError, json.JSONDecodeError):
                pass
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("envelopes", nargs="*", type=Path, default=[RESULTS],
                    help="scores JSON files or directories (default: results/)")
    ap.add_argument("--summary", action="store_true", help="write job summary")
    ap.add_argument("--badges", type=Path, help="directory for badge JSON")
    ap.add_argument("--site", type=Path, help="build the static site into DIR")
    args = ap.parse_args(argv)

    envs = load_envelopes(args.envelopes)
    if not envs:
        print("no scores envelopes found", file=sys.stderr)
        return 2

    if args.summary or not (args.badges or args.site):
        print(job_summary(envs))
    if args.badges:
        written = scoring.write_badges(args.badges, scoring.badges(envs))
        print(f"wrote {len(written)} badge(s) to {args.badges}", file=sys.stderr)
    if args.site:
        build_site(envs, args.site)
    return 0


if __name__ == "__main__":
    sys.exit(main())
