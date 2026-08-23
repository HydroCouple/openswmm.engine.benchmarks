#!/usr/bin/env python3
"""Post-migration cleanup of the legacy directory layout.

Run after tools/migrate_corpus.py. Three actions, in this order:

1. **Preserve evidence.** Every legacy ``.rpt`` that sat beside a model now in
   the corpus is copied into that case's ``reference/legacy.rpt``. Those
   reports are where the `surcharge`, `flooding`, and `flow_instability` tags
   came from, so keeping them makes the tagging auditable instead of asserted.
   They are NOT a grading reference — the case's ``reference.class`` stays
   ``self_consistency`` — and provenance records what they are.

2. **Relocate source material.** XPSWMM projects, per-model markdown
   summaries, archives, and loose text move to ``legacy/`` preserving their
   relative paths; data files (``.dat``, ``.rff``, ``.hsf``) move to
   ``data/<collection>/``.

3. **Delete regenerable output.** ``.rpt`` (after step 1), ``.out``, ``.log``,
   ``.ini``, ``.bak``. These are engine output of unknown provenance and are
   reproducible by running the corpus.

Duplicate ``.inp`` files are deliberately left where they are.

    python tools/cleanup_legacy.py            # report what would happen
    python tools/cleanup_legacy.py --apply
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "corpus"
DATA = REPO_ROOT / "data"
LEGACY = REPO_ROOT / "legacy"

MANAGED_DIRS = {".git", ".github", "corpus", "harness", "suites", "tests",
                "tools", "plans", "docs", "site", "results", "data", "legacy",
                "__pycache__"}

DATA_EXT = {".dat", ".rff", ".hsf"}
SOURCE_EXT = {".xp", ".xpx", ".xpj", ".xpp", ".md", ".zip", ".txt", ".bat",
              ".json", ".inp"}
DELETE_EXT = {".rpt", ".out", ".log", ".ini", ".bak"}

#: .inp files stay put: they are byte-identical duplicates of migrated cases
#: and removing them was explicitly declined.
KEEP_IN_PLACE_EXT = {".inp"}


def legacy_dirs() -> list[Path]:
    return [p for p in sorted(REPO_ROOT.iterdir())
            if p.is_dir() and p.name not in MANAGED_DIRS]


def case_origins() -> dict[Path, Path]:
    """Original legacy path -> case directory, from each case's provenance."""
    import yaml
    out: dict[Path, Path] = {}
    for prov in CORPUS.rglob("provenance.yaml"):
        if prov.parent.name == "_template":
            continue
        try:
            doc = yaml.safe_load(prov.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError:
            continue
        m = re.search(r"originally (.+?)\)", str(doc.get("source", "")))
        if m:
            out[REPO_ROOT / m.group(1)] = prov.parent
    return out


def plan(apply: bool = False) -> dict:
    origins = case_origins()
    stats = Counter()
    dirs = legacy_dirs()

    # ── 1. preserve the reports that produced tags ─────────────────────────
    for origin, case_dir in origins.items():
        rpt = origin.with_suffix(".rpt")
        if not rpt.exists():
            continue
        stats["reports_preserved"] += 1
        if not apply:
            continue
        ref = case_dir / "reference"
        ref.mkdir(exist_ok=True)
        shutil.copy2(rpt, ref / "legacy.rpt")
        _note_evidence(case_dir, origin)

    # ── 2 & 3. relocate source material, delete output ─────────────────────
    for d in dirs:
        for f in sorted(d.rglob("*")):
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            rel = f.relative_to(REPO_ROOT)
            if ext in KEEP_IN_PLACE_EXT:
                stats["inp_left_in_place"] += 1
            elif ext in DATA_EXT:
                stats["data_moved"] += 1
                if apply:
                    dst = DATA / rel.parts[0].lower().replace(" ", "-") / f.name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        shutil.move(str(f), str(dst))
                    else:
                        f.unlink()          # same name, same collection
            elif ext in SOURCE_EXT:
                stats["source_moved"] += 1
                if apply:
                    dst = LEGACY / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        shutil.move(str(f), str(dst))
            elif ext in DELETE_EXT:
                stats["output_deleted"] += 1
                stats["bytes_deleted"] += f.stat().st_size
                if apply:
                    f.unlink()
            else:
                stats[f"untouched{ext or '/noext'}"] += 1

    if apply:
        for d in dirs:
            _prune_empty(d)
    return dict(stats)


def _note_evidence(case_dir: Path, origin: Path) -> None:
    """Record in provenance what reference/legacy.rpt is, and is not."""
    import yaml
    prov_path = case_dir / "provenance.yaml"
    doc = yaml.safe_load(prov_path.read_text(encoding="utf-8")) or {}
    doc["notes"] = (str(doc.get("notes", "")).rstrip() + " "
                    "reference/legacy.rpt is the report that shipped beside "
                    "this model in the pre-migration corpus, from an engine "
                    "and version that were not recorded. It is the evidence "
                    "behind this case's surcharge/flooding/flow_instability "
                    "tags. It is NOT a grading reference: the case is graded "
                    "as self_consistency.").strip()
    prov_path.write_text(yaml.safe_dump(doc, sort_keys=False,
                                        default_flow_style=False,
                                        allow_unicode=True), encoding="utf-8")


def _prune_empty(root: Path) -> None:
    for p in sorted(root.rglob("*"), key=lambda p: -len(p.parts)):
        if p.is_dir() and not any(p.iterdir()):
            p.rmdir()
    if root.is_dir() and not any(root.iterdir()):
        root.rmdir()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    stats = plan(apply=args.apply)
    mb = stats.pop("bytes_deleted", 0) / 1048576
    print("DRY RUN — nothing changed" if not args.apply else "APPLIED")
    for k, v in sorted(stats.items()):
        print(f"  {k:24s} {v}")
    print(f"  {'output size':24s} {mb:.0f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
