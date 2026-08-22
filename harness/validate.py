#!/usr/bin/env python3
"""Corpus validation — metadata, provenance, tag vocabulary, file resolution.

Run on every pull request (.github/workflows/validate.yml) and locally:

    python -m harness.validate                 # whole corpus
    python -m harness.validate corpus/epa/extran1
    python -m harness.validate --changed       # only paths git reports changed

Checks (schema-level; the CI workflow adds the run-the-model checks):
  * metadata.yaml and provenance.yaml exist and parse
  * required fields present, enums valid, tags all in schemas/tags.yaml
  * reference.class is a known class and its files resolve
  * blessed_baseline carries blessing engine + SHA + reviewer
  * model.inp exists; referenced data files resolve; no absolute paths
  * likely-identifying content flagged (advisory, not an error)
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "corpus"
SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

REQUIRED_METADATA = ("id", "title", "tags", "units", "reference")
REQUIRED_PROVENANCE = ("source", "license", "contributed_by")

VALID_UNITS = {"US", "SI"}
VALID_ROUTING = {"DYNWAVE", "KINWAVE", "STEADY"}
VALID_SIZE = {"XS", "S", "M", "L", "XL"}
VALID_RUNTIME = {"fast", "medium", "slow"}
VALID_TIERS = {"pr", "nightly", "weekly"}
VALID_REFERENCE_CLASSES = {
    "analytic", "manufactured", "external_reference", "observed",
    "blessed_baseline", "self_consistency"}

#: Advisory scan — coordinates that look like real-world lat/long, and IDs or
#: titles that look like place names. Findings are reported, never fatal.
_LATLON = re.compile(r"^\s*\S+\s+(-?\d{1,3}\.\d{4,})\s+(-?\d{1,3}\.\d{4,})\s*$")


@dataclass
class Result:
    case: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def load_tags() -> dict:
    import yaml
    doc = yaml.safe_load((SCHEMA_DIR / "tags.yaml").read_text()) or {}
    return doc.get("tags", {})


def validate_case(case_dir: Path, vocab: dict | None = None) -> Result:
    """Validate one corpus case directory."""
    import yaml
    vocab = load_tags() if vocab is None else vocab
    r = Result(case=case_dir)

    meta_path = case_dir / "metadata.yaml"
    prov_path = case_dir / "provenance.yaml"
    if not meta_path.exists():
        r.errors.append("metadata.yaml missing")
        return r
    if not prov_path.exists():
        r.errors.append("provenance.yaml missing")

    try:
        meta = yaml.safe_load(meta_path.read_text()) or {}
    except yaml.YAMLError as exc:
        r.errors.append(f"metadata.yaml does not parse: {exc}")
        return r

    for key in REQUIRED_METADATA:
        if key not in meta:
            r.errors.append(f"metadata.yaml: required field {key!r} missing")

    tags = meta.get("tags") or []
    if not isinstance(tags, list) or not tags:
        r.errors.append("metadata.yaml: 'tags' must be a non-empty list")
    else:
        for t in tags:
            if t not in vocab:
                r.errors.append(
                    f"unknown tag {t!r} — add it to harness/schemas/tags.yaml "
                    "in the same PR if it is genuinely new")

    if meta.get("units") and meta["units"] not in VALID_UNITS:
        r.errors.append(f"units must be one of {sorted(VALID_UNITS)}")
    for key, valid in (("routing", VALID_ROUTING), ("size_class", VALID_SIZE),
                       ("runtime_class", VALID_RUNTIME)):
        if meta.get(key) and meta[key] not in valid:
            r.errors.append(f"{key} must be one of {sorted(valid)}")
    for tier in meta.get("tiers") or []:
        if tier not in VALID_TIERS:
            r.errors.append(f"tier {tier!r} must be one of {sorted(VALID_TIERS)}")

    ref = meta.get("reference") or {}
    rclass = ref.get("class")
    if rclass not in VALID_REFERENCE_CLASSES:
        r.errors.append(
            f"reference.class must be one of {sorted(VALID_REFERENCE_CLASSES)}")
    for rel in ref.get("files") or []:
        if Path(rel).is_absolute():
            r.errors.append(f"reference file must be a relative path: {rel}")
        elif not (case_dir / rel).exists():
            r.errors.append(f"reference file not found: {rel}")
    if rclass == "blessed_baseline":
        blessed = ref.get("blessed_by") or {}
        for key in ("engine", "sha", "reviewer", "date"):
            if not blessed.get(key):
                r.errors.append(
                    f"reference.blessed_by.{key} is required for a "
                    "blessed_baseline (a baseline is only as good as its review)")

    inp = case_dir / meta.get("model", "model.inp")
    if not inp.exists():
        r.errors.append(f"model file not found: {inp.name}")
    else:
        r.warnings.extend(scan_inp(inp))

    if prov_path.exists():
        try:
            prov = yaml.safe_load(prov_path.read_text()) or {}
            for key in REQUIRED_PROVENANCE:
                if key not in prov:
                    r.errors.append(
                        f"provenance.yaml: required field {key!r} missing")
            if str(prov.get("license", "")).lower() in ("unverified", ""):
                r.warnings.append(
                    "license unverified — case is excluded from redistribution")
        except yaml.YAMLError as exc:
            r.errors.append(f"provenance.yaml does not parse: {exc}")

    return r


def scan_inp(path: Path) -> list[str]:
    """Advisory scan of a model for portability and identifying content."""
    warnings: list[str] = []
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        return [f"could not read {path.name}: {exc}"]

    # Not anchored to the line start: in [FILES] and [RAINFALL] the path
    # follows a keyword ("USE RAINFALL /Users/…"), so an anchored pattern
    # missed exactly the lines that carry paths.
    # The lookbehind keeps a URL scheme ("https://") from reading as a drive
    # letter: the 's' there is preceded by a word character, a real drive
    # letter is not.
    m = re.search(r"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|/(?:Users|home)/)"
                  r"[^\s\"']*", text)
    if m:
        warnings.append(f"absolute path in model: {m.group(0)[:80]}")

    n_latlon = 0
    in_coords = False
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("["):
            in_coords = s.upper().startswith("[COORDINATES")
            continue
        if in_coords and _LATLON.match(line):
            n_latlon += 1
    if n_latlon:
        warnings.append(
            f"{n_latlon} coordinates look like real-world lat/long — consider "
            "harness/anonymize.py (offset or strip) before publishing")
    return warnings


def find_cases(paths: list[Path] | None = None) -> list[Path]:
    roots = paths or [CORPUS]
    cases: list[Path] = []
    for root in roots:
        root = Path(root)
        if (root / "metadata.yaml").exists():
            cases.append(root)
            continue
        cases.extend(sorted(p.parent for p in root.rglob("metadata.yaml")
                            if p.parent.name != "_template"))
    return cases


def changed_paths() -> list[Path]:
    """Corpus directories touched relative to origin/dev (best effort)."""
    try:
        diff = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "diff", "--name-only",
             "origin/dev...HEAD"],
            capture_output=True, text=True, timeout=60).stdout.split()
    except Exception:
        return []
    dirs = {(REPO_ROOT / p).parent for p in diff if p.startswith("corpus/")}
    return sorted(d for d in dirs if (d / "metadata.yaml").exists())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", type=Path,
                    help="case dirs or roots to validate (default: whole corpus)")
    ap.add_argument("--changed", action="store_true",
                    help="validate only cases changed vs origin/dev")
    ap.add_argument("--quiet", action="store_true", help="only show problems")
    args = ap.parse_args(argv)

    if not CORPUS.exists():
        print(f"corpus/ not found at {CORPUS} — nothing to validate")
        return 0

    cases = changed_paths() if args.changed else find_cases(args.paths or None)
    if not cases:
        print("no cases to validate")
        return 0

    vocab = load_tags()
    n_bad = n_warn = 0
    for case in cases:
        r = validate_case(case, vocab)
        rel = case.relative_to(REPO_ROOT)
        if r.errors:
            n_bad += 1
            print(f"FAIL {rel}")
            for e in r.errors:
                print(f"       error: {e}")
        elif not args.quiet:
            print(f"ok   {rel}")
        for w in r.warnings:
            n_warn += 1
            print(f"       warn:  {w}")

    print(f"\n{len(cases)} case(s): {len(cases) - n_bad} ok, {n_bad} failed, "
          f"{n_warn} warning(s)")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
