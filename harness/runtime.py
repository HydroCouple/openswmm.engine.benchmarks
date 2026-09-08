#!/usr/bin/env python3
"""Measured wall-clock runtimes: the ledger, the CI gate, and the CI trim.

Long models are a local concern. Every workflow passes ``--max-wall 300``, and
a case MEASURED to cost more than that is skipped on GitHub Actions with a
warning — never silently, and never as a pass: the skip lands in the scores
envelope as a SKIP cell, so the dashboard shows a deliberate exclusion rather
than a missing result. Locally the flag is unset and everything runs.

Three rules keep the gate honest:

* **Measured, not estimated.** ``runtime_class`` in a case's metadata is an
  estimate from model size, and it is wrong often enough to be unusable as a
  gate: half the cases that actually exceed five minutes are classed
  ``medium``, while ``275000-h-h-elements`` is classed ``slow`` and runs in
  about a second. This gate keys on recorded wall time alone.
* **Unmeasured means run.** A case with no ledger entry is not presumed slow.
  It runs, bounded by the per-case ``timeout_s`` that already exists, and a
  local sweep records what it cost — so the ledger fills in over time from the
  runs that are allowed to take as long as they need.
* **A trim beats a skip.** A case carrying ``ci_runtime`` in its metadata runs
  a SHORTENED simulated period on CI instead of being dropped, so the model
  still exercises the engine there. The committed ``.inp`` is never modified;
  the trim is applied to the seeded copy in the run directory.

    python -m harness.runtime                       # what CI skips at 300 s
    python -m harness.runtime --max-wall 120        # ...at another threshold
    python -m harness.runtime --record results/parity/scores_nightly.json
"""
from __future__ import annotations

import argparse
import datetime as _dt
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LEDGER = Path(__file__).resolve().parent / "runtimes.yaml"

# The threshold CI runs at. Kept here so the workflows, the docs and the tests
# all quote one number.
DEFAULT_MAX_WALL_S = 300.0

# Cases faster than this are not written to the ledger. They cannot approach
# the threshold, and recording all ~1300 of them would bury the handful that
# matter in four thousand lines of noise. A case that gets slower is picked up
# the next time a local sweep measures it.
RECORD_FLOOR_S = 60.0


# ── the ledger ─────────────────────────────────────────────────────────────

def load(path: Path | None = None) -> dict:
    """Read the ledger; an absent or unreadable file means 'nothing measured'."""
    import yaml
    p = Path(path or LEDGER)
    if not p.exists():
        return {"suites": {}}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return {"suites": {}}
    data.setdefault("suites", {})
    return data


def measured(ledger: dict, suite: str, case: str) -> dict | None:
    """The recorded entry for one case, or None if it has never been timed.

    Falls back to the other suites' buckets: a suite names itself
    inconsistently in places (``swashes`` in its envelope, ``analytical/swashes``
    in the registry), and a case that is known to cost ten minutes should be
    gated on that fact whichever label it was recorded under.
    """
    suites = ledger.get("suites") or {}
    hit = suites.get(suite, {}).get(case)
    if hit:
        return hit
    for name, entries in suites.items():
        if name != suite and case in entries:
            return entries[case]
    return None


def record(envelope: dict, path: Path | None = None) -> int:
    """Merge the wall times from a completed sweep into the ledger.

    Keeps the SLOWEST engine's time for each case: the gate is about what the
    case costs a runner, and a case is only as cheap as its slowest engine.
    Returns the number of entries written or updated.
    """
    import yaml
    suite = envelope.get("suite") or "?"
    stamp = envelope.get("timestamp") or _dt.datetime.now().isoformat(
        timespec="seconds")

    worst: dict[str, dict] = {}
    for cell in envelope.get("cells") or []:
        wall, case = cell.get("wall"), cell.get("case")
        if wall is None or not case or wall < RECORD_FLOOR_S:
            continue
        if case not in worst or wall > worst[case]["wall_s"]:
            entry = {
                "wall_s": round(float(wall), 1),
                "engine": cell.get("solver") or "?",
                "sweep": stamp,
            }
            # A killed run reports the timeout as its wall, so the recorded
            # number is a FLOOR, not a measurement. Say so, or the ledger
            # quietly asserts that a case costs exactly 600s when nobody knows
            # what it costs.
            if "timeout" in str(cell.get("note", "")).lower():
                entry["timed_out"] = True
            worst[case] = entry

    p = Path(path or LEDGER)
    ledger = load(p)
    if worst:
        bucket = ledger.setdefault("suites", {}).setdefault(suite, {})
        bucket.update(worst)
        ledger["suites"][suite] = dict(sorted(bucket.items()))

    header = (
        "# Measured wall-clock seconds per case, worst engine, from local\n"
        "# sweeps. This is the ONLY input to the CI runtime gate — see\n"
        f"# harness/runtime.py. Cases under {RECORD_FLOOR_S:.0f}s are not recorded.\n"
        "#\n"
        "# Refresh after a local sweep:\n"
        "#   python -m harness.runtime --record results/parity/scores_nightly.json\n"
    )
    p.write_text(header + yaml.safe_dump(ledger, sort_keys=True,
                                         default_flow_style=False),
                 encoding="utf-8")
    return len(worst)


# ── the gate ───────────────────────────────────────────────────────────────

def in_actions() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def warn(message: str) -> None:
    """A warning that is visible in the Actions log AND in a local terminal."""
    prefix = "::warning::" if in_actions() else "warning: "
    print(f"{prefix}{message}", file=sys.stderr)


def trim_hours(meta: dict) -> float | None:
    """The CI-only simulated duration for this case, in hours, if it has one."""
    ci = meta.get("ci_runtime") or {}
    d = ci.get("duration_h")
    return float(d) if d else None


def skip_reason(ledger: dict, suite: str, case: str,
                max_wall: float | None, meta: dict | None = None) -> str | None:
    """Why this case must not run here, or None to run it.

    A case with a ``ci_runtime`` trim always runs: the trim is what brings it
    inside the budget, so skipping it as well would discard the coverage the
    trim was added to keep.
    """
    if not max_wall:
        return None
    if meta is not None and trim_hours(meta):
        return None
    entry = measured(ledger, suite, case)
    if not entry:
        return None
    wall = float(entry.get("wall_s", 0))
    if wall <= max_wall:
        return None
    how = "timed out at" if entry.get("timed_out") else "measured"
    return (f"{how} {wall:.0f}s > --max-wall {max_wall:.0f}s "
            f"(sweep {entry.get('sweep', '?')}); runs locally, not on CI")


# ── the trim ───────────────────────────────────────────────────────────────

_OPT = re.compile(r"^\s*(START_DATE|START_TIME|END_DATE|END_TIME)\s+(\S+)",
                  re.IGNORECASE)


def _parse_start(lines: list[str]) -> _dt.datetime | None:
    date = time = None
    for line in lines:
        m = _OPT.match(line)
        if not m:
            continue
        key, val = m.group(1).upper(), m.group(2)
        if key == "START_DATE":
            date = val
        elif key == "START_TIME":
            time = val
    if not date:
        return None
    h, mnt, s = (list(map(int, (time or "0:0:0").split(":"))) + [0, 0])[:3]
    try:
        d = _dt.datetime.strptime(date, "%m/%d/%Y")
    except ValueError:
        return None
    return d + _dt.timedelta(hours=h, minutes=mnt, seconds=s)


def apply_trim(inp: Path, duration_h: float) -> str:
    """Shorten a SEEDED model's simulated period in place.

    Only ever called on the copy inside a run directory — never on the file in
    ``corpus/``, which stays byte-identical to what was contributed. Returns a
    one-line description of what changed, for the run note.
    """
    lines = Path(inp).read_text(encoding="utf-8", errors="replace").splitlines(
        keepends=True)
    start = _parse_start(lines)
    if start is None:
        raise ValueError(f"{inp.name}: no parseable START_DATE to trim from")
    end = start + _dt.timedelta(hours=duration_h)
    want = {"END_DATE": end.strftime("%m/%d/%Y"),
            "END_TIME": end.strftime("%H:%M:%S")}

    seen = set()
    for i, line in enumerate(lines):
        m = _OPT.match(line)
        if not m:
            continue
        key = m.group(1).upper()
        if key in want:
            # Preserve the file's own indentation and separator style.
            head = line[:m.start(2)]
            lines[i] = f"{head}{want[key]}\n"
            seen.add(key)
    missing = [k for k in want if k not in seen]
    if missing:
        raise ValueError(f"{inp.name}: no {', '.join(missing)} line to trim")

    Path(inp).write_text("".join(lines), encoding="utf-8")
    return (f"CI trim: simulated period shortened to {duration_h:g} h "
            f"(ends {want['END_DATE']} {want['END_TIME']})")


# ── CLI ────────────────────────────────────────────────────────────────────

def _census(max_wall: float) -> int:
    from . import corpus
    ledger = load()
    cases = {c.id: c.meta for c in corpus.load()}
    rows, trims = [], []
    for suite, entries in sorted((ledger.get("suites") or {}).items()):
        for case, entry in sorted(entries.items()):
            meta = cases.get(case, {})
            if trim_hours(meta):
                if float(entry.get("wall_s", 0)) > max_wall:
                    trims.append((suite, case, entry, trim_hours(meta)))
                continue
            why = skip_reason(ledger, suite, case, max_wall, meta)
            if why:
                rows.append((suite, case, why))

    print(f"threshold: --max-wall {max_wall:.0f}s\n")
    print(f"trimmed for CI ({len(trims)}) — these RUN, on a shortened period:")
    for suite, case, entry, hours in trims:
        print(f"  {suite}/{case}: {entry['wall_s']:.0f}s at full period "
              f"-> {hours:g} h")
    print(f"\nskipped on CI ({len(rows)}):")
    for suite, case, why in rows:
        print(f"  {suite}/{case}: {why}")
    if not rows:
        print("  (none)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="harness.runtime", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-wall", type=float, default=DEFAULT_MAX_WALL_S,
                    help="threshold to report against (default %(default)s)")
    ap.add_argument("--record", type=Path, metavar="SCORES.JSON",
                    help="merge the wall times from a scores envelope "
                         "into the ledger")
    args = ap.parse_args(argv)

    if args.record:
        import json
        envelope = json.loads(args.record.read_text(encoding="utf-8"))
        n = record(envelope)
        print(f"recorded {n} case(s) over {RECORD_FLOOR_S:.0f}s into {LEDGER}")
        return 0
    return _census(args.max_wall)


if __name__ == "__main__":
    sys.exit(main())
