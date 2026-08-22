#!/usr/bin/env python3
"""Repair unusable file references in migrated corpus models.

Three distinct problems hide behind "the model references a file that isn't
there", and they need different handling:

1. **Absolute SAVE paths** — the model writes an interface/hotstart file to
   ``C:\\TEMP\\HS.HSF``. Nothing is missing; the path simply does not exist off
   the authoring machine. Rewriting it to the bare filename makes the model
   run anywhere and removes a leaked path (several carry usernames and client
   project names). This is a **non-physical** edit: no parameter, element, or
   option that affects results is touched.

2. **Resolvable USE paths** — the input file exists somewhere in the repo
   (``data/``, ``legacy/``) under the same basename. Copy it beside the model.

3. **Genuinely missing inputs** — the data was never in the repository. These
   stay skip-listed; no amount of rewriting conjures a rainfall file.

Every edit is recorded in the case's ``provenance.yaml`` under
``modifications``, and the skip list is rebuilt so it names only what is
actually still broken.

    python tools/repair_references.py            # report
    python tools/repair_references.py --apply
"""
from __future__ import annotations

import argparse
import collections
import re
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "corpus"
sys.path.insert(0, str(REPO_ROOT))

import tools.migrate_corpus as M  # noqa: E402

USE_RE = re.compile(r"^(\s*USE\s+\w+\s+)(.+?)(\s*)$", re.I)
SAVE_RE = re.compile(r"^(\s*SAVE\s+\w+\s+)(.+?)(\s*)$", re.I)
FILE_RE = re.compile(r"(\bFILE\s+)(\"[^\"]+\"|\S+)", re.I)

SEARCH_ROOTS = ("data", "legacy")
DATA_EXT = {".dat", ".rff", ".txt", ".hsf", ".ts", ".csv", ".int", ".15m",
            ".ncd", ".rof", ".rin", ".mst"}


def basename(ref: str) -> str:
    return Path(ref.replace("\\", "/")).name.strip('"')


def build_index() -> dict[str, list[Path]]:
    """Every candidate data file we hold, keyed by lowercase basename."""
    index: dict[str, list[Path]] = collections.defaultdict(list)
    for root in SEARCH_ROOTS:
        r = REPO_ROOT / root
        if not r.exists():
            continue
        for p in r.rglob("*"):
            if p.is_file() and p.suffix.lower() in DATA_EXT:
                index[p.name.lower()].append(p)
    return index


def repair_case(case: Path, index: dict[str, list[Path]],
                apply: bool = False) -> dict:
    """Returns what this case needs, and performs it when apply=True."""
    inp = case / "model.inp"
    result = {"saves_rewritten": [], "inputs_copied": [], "missing": []}
    if not inp.exists():
        return result

    # latin-1 round-trips every byte, so untouched lines are preserved exactly
    raw = inp.read_bytes().decode("latin-1")
    lines = raw.splitlines(keepends=True)
    section = ""
    changed = False

    for i, line in enumerate(lines):
        stripped = line.split(";", 1)[0].strip()
        m = re.match(r"^\[([A-Za-z_0-9]+)\]", stripped)
        if m:
            section = m.group(1).upper()
            continue
        if not stripped:
            continue

        if section == "FILES":
            ms = SAVE_RE.match(line)
            if ms and M.is_absolute(ms.group(2).strip('"')):
                new = basename(ms.group(2))
                result["saves_rewritten"].append((ms.group(2).strip(), new))
                lines[i] = f'{ms.group(1)}"{new}"{ms.group(3)}'
                changed = True
                continue
            mu = USE_RE.match(line)
            if mu:
                _handle_input(case, mu.group(2), index, result, lines, i,
                              mu.group(1), mu.group(3), apply)
                changed = changed or bool(result["inputs_copied"])
                continue

        if section in ("TIMESERIES", "RAINGAGES"):
            mf = FILE_RE.search(line)
            if mf:
                ref = mf.group(2).strip('"')
                base = basename(ref)
                if (case / base).exists():
                    continue
                hit = index.get(base.lower())
                if hit:
                    result["inputs_copied"].append((ref, str(hit[0])))
                    if apply:
                        shutil.copy2(hit[0], case / base)
                    if ref != base:
                        lines[i] = line[:mf.start(2)] + f'"{base}"' + line[mf.end(2):]
                        changed = True
                else:
                    result["missing"].append(ref)

    if apply and changed:
        inp.write_bytes("".join(lines).encode("latin-1"))
        _record(case, result)
    return result


def _handle_input(case: Path, ref: str, index, result, lines, i,
                  prefix: str, suffix: str, apply: bool) -> None:
    ref = ref.strip('"')
    base = basename(ref)
    if (case / base).exists():
        if ref != base:
            lines[i] = f'{prefix}"{base}"{suffix}'
        return
    hit = index.get(base.lower())
    if hit:
        result["inputs_copied"].append((ref, str(hit[0])))
        if apply:
            shutil.copy2(hit[0], case / base)
        lines[i] = f'{prefix}"{base}"{suffix}'
    else:
        result["missing"].append(ref)


def _record(case: Path, result: dict) -> None:
    import yaml
    p = case / "provenance.yaml"
    doc = yaml.safe_load(p.read_text()) or {}
    notes = []
    if result["saves_rewritten"]:
        notes.append(
            f"{len(result['saves_rewritten'])} absolute SAVE path(s) in [FILES] "
            "rewritten to the bare filename so the model runs off its "
            "authoring machine (and to remove leaked directory names). "
            "Non-physical: no parameter, element, or option affecting results "
            "was changed.")
    if result["inputs_copied"]:
        notes.append(
            f"{len(result['inputs_copied'])} referenced input file(s) located "
            "elsewhere in the repository and copied beside the model; the "
            "reference was shortened to the bare filename.")
    if notes:
        prev = str(doc.get("modifications", "")).strip()
        doc["modifications"] = (prev + " " if prev else "") + " ".join(notes)
        p.write_text(yaml.safe_dump(doc, sort_keys=False,
                                    default_flow_style=False,
                                    allow_unicode=True))


def rebuild_skip_list(broken: dict[str, list[str]]) -> int:
    """Rewrite the parity skip list to name only what is still unrunnable."""
    import yaml
    path = REPO_ROOT / "suites" / "parity" / "manifests" / "skip_list.yaml"
    manual = []
    if path.exists():
        for e in (yaml.safe_load(path.read_text()) or {}).get("skip") or []:
            if "not a runnable model" in str(e.get("reason", "")):
                manual.append(e)                 # keep non-reference skips

    entries = manual + [
        {"case": case,
         "reason": f"missing input file(s) never present in the repository: "
                   f"{', '.join(sorted(set(refs))[:3])}",
         "revisit": "when the data files are recovered and committed under data/"}
        for case, refs in sorted(broken.items())]

    header = (
        "# Cases excluded from sweeps, with a reason each. A skip is a\n"
        "# decision, not a convenience: every entry states why and what would\n"
        "# let it come back.\n#\n"
        "# Rebuilt by tools/repair_references.py: only cases whose INPUT data\n"
        "# is genuinely absent remain. Models that merely wrote to an absolute\n"
        "# path were repaired, not skipped.\n")
    path.write_text(header + yaml.safe_dump({"skip": entries}, sort_keys=False,
                                            default_flow_style=False,
                                            allow_unicode=True, width=100))
    return len(entries)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    index = build_index()
    stats = collections.Counter()
    broken: dict[str, list[str]] = {}

    for meta in sorted(CORPUS.rglob("metadata.yaml")):
        if meta.parent.name == "_template":
            continue
        r = repair_case(meta.parent, index, apply=args.apply)
        stats["saves_rewritten"] += len(r["saves_rewritten"])
        stats["inputs_copied"] += len(r["inputs_copied"])
        if r["saves_rewritten"]:
            stats["cases_save_repaired"] += 1
        if r["inputs_copied"]:
            stats["cases_input_recovered"] += 1
        if r["missing"]:
            broken[meta.parent.name] = r["missing"]

    print("APPLIED" if args.apply else "DRY RUN — nothing changed")
    for k, v in sorted(stats.items()):
        print(f"  {k:24s} {v}")
    print(f"  {'cases still broken':24s} {len(broken)}")
    if args.apply:
        n = rebuild_skip_list(broken)
        print(f"  {'skip list entries':24s} {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
