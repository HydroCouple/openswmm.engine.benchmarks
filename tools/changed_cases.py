#!/usr/bin/env python3
"""List the corpus case ids a branch touched, for the PR smoke run.

Reuses harness.validate.changed_paths so "changed" means the same thing to the
schema job and the run-the-model job. Prints a comma-separated list of case
IDS (not paths), because that is what `suites.parity.suite --only` takes.

    python tools/changed_cases.py                  # comma-separated ids
    python tools/changed_cases.py --github-output  # also write to $GITHUB_OUTPUT
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness import validate  # noqa: E402

#: A PR that touches the shared schema or a whole collection can sweep in
#: hundreds of cases; the smoke job is meant to be fast, so it runs a bounded
#: prefix and says so rather than silently truncating.
MAX_CASES = 40


def changed_case_ids() -> list[str]:
    import yaml
    ids = []
    for d in validate.changed_paths():
        try:
            meta = yaml.safe_load((d / "metadata.yaml").read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError):
            continue
        ids.append(meta.get("id", d.name))
    return sorted(set(ids))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--github-output", action="store_true",
                    help="append cases=<...> to $GITHUB_OUTPUT")
    ap.add_argument("--max", type=int, default=MAX_CASES)
    args = ap.parse_args(argv)

    ids = changed_case_ids()
    truncated = len(ids) > args.max
    if truncated:
        print(f"note: {len(ids)} cases changed; smoke-running the first "
              f"{args.max}. The nightly sweep covers the rest.", file=sys.stderr)
        ids = ids[:args.max]

    line = ",".join(ids)
    print(line)
    if args.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
            fh.write(f"cases={line}\n")
            fh.write(f"count={len(ids)}\n")
            fh.write(f"truncated={'true' if truncated else 'false'}\n")
    return 0


if __name__ == "__main__":
    from harness import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
