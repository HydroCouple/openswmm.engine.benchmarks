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
    """Render the static dashboard (implemented in harness.site).

    Layout:
        /                              scoreboard + badges
        /runs/<stamp>_<suite>@<sha>/   immutable per-run reports + raw JSON
        /tags/<tag>/                   per-tag facets over the corpus
        /badges/*.json                 shields.io endpoints
    """
    from . import site
    return site.build_site(envelopes, dest)


def load_envelopes(paths: list[Path]) -> list[dict]:
    """Collect scores envelopes, skipping generated site output.

    The dashboard writes a copy of each envelope into its per-run page. If the
    site is built underneath the directory being scanned, those copies are
    read back as if they were additional runs and every count doubles.
    """
    out = []
    for p in paths:
        p = Path(p)
        files = [p] if p.is_file() else sorted(p.rglob("*scores*.json"))
        for f in files:
            if "site" in f.parts or "runs" in f.parts:
                continue                     # generated copies, not new runs
            try:
                out.append(json.loads(f.read_text(encoding="utf-8")))
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
    ap.add_argument("--site", type=Path, nargs="?", const=Path("site/build"),
                    help="build the static site into DIR (default site/build)")
    args = ap.parse_args(argv)

    envs = load_envelopes(args.envelopes)
    if not envs:
        # With --site the caller is publishing a dashboard, and refusing to
        # publish leaves the PREVIOUS run's page standing — so a broken
        # nightly silently looks like a healthy one. Publish the failure
        # instead; build_site renders an unmistakable "no results" state.
        if args.site:
            print("no scores envelopes found — publishing the empty state",
                  file=sys.stderr)
            for p in build_site([], args.site):
                print(f"  wrote {p}", file=sys.stderr)
            return 0
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
    from . import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
