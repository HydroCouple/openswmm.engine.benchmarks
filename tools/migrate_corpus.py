#!/usr/bin/env python3
"""One-time corpus migration — flat model directories into corpus/ cases.

Scans every ``.inp`` in the legacy directory layout, derives draft metadata
from what the file actually contains, and (with --apply) moves each model into
``corpus/<collection>/<case-id>/`` alongside a generated ``metadata.yaml`` and
``provenance.yaml``.

    python tools/migrate_corpus.py                    # scan + report, no writes
    python tools/migrate_corpus.py --report out.md    # write the report
    python tools/migrate_corpus.py --apply            # perform the migration

**Collections are the source directory, not a judgment.** Directory placement
carries no semantic weight (harness/corpus.py selects by tag query), so keeping
the original folder name preserves traceability instead of inventing groupings.
All classification lives in tags.

**Tags are evidence-based only.** A tag is emitted when the model demonstrably
contains the thing — a non-empty section, an option value, a cross-section
type. Nothing is inferred from a filename or a folder name, because those lie.
The one exception, clearly marked, is `surcharge`, taken from a sibling report
file when one exists; it is advisory and provenance records where it came from.

Run once. After migration the corpus is maintained by hand and by
harness/validate.py.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS = REPO_ROOT / "corpus"
DATA = REPO_ROOT / "data"

#: Directories that are not model collections.
EXCLUDE_DIRS = {".git", "corpus", "harness", "suites", "tests", "tools",
                "plans", "docs", "site", "results", "data", ".github",
                "ICM Import Log Files"}

#: Collections whose models came from a colleague rather than a public source
#: (see the repository's original license note); provenance is marked
#: unverified so they are excluded from redistribution claims until confirmed.
UNVERIFIED_COLLECTIONS = {"greenville", "simon-epa", "special"}

REAL_WORLD_COLLECTIONS = {"semi-real-models", "greenville"}

SI_UNITS = {"CMS", "LPS", "MLD"}


# ── .inp parsing ───────────────────────────────────────────────────────────
def parse_sections(text: str) -> dict[str, list[str]]:
    """Section name (upper) -> its non-comment, non-blank data lines."""
    sections: dict[str, list[str]] = defaultdict(list)
    current = ""
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^\[([A-Za-z_0-9]+)\]", line)
        if m:
            current = m.group(1).upper()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    return dict(sections)


def options(sections: dict[str, list[str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in sections.get("OPTIONS", []):
        parts = line.split(None, 1)
        if len(parts) == 2:
            out[parts[0].upper()] = parts[1].strip()
    return out


def duration_days(opts: dict[str, str]) -> float | None:
    """Simulation span in days, from START_DATE/END_DATE."""
    from datetime import datetime
    fmt_candidates = ("%m/%d/%Y", "%m-%d-%Y", "%Y-%m-%d")

    def parse(key):
        v = opts.get(key)
        if not v:
            return None
        for fmt in fmt_candidates:
            try:
                return datetime.strptime(v.split()[0], fmt)
            except ValueError:
                continue
        return None

    a, b = parse("START_DATE"), parse("END_DATE")
    return (b - a).days if a and b and b >= a else None


FILE_REF_PATTERNS = (
    # [FILES]:  USE|SAVE  RAINFALL|RUNOFF|HOTSTART|RDII|INFLOWS|OUTFLOWS  path
    re.compile(r"^\s*(?:USE|SAVE)\s+\w+\s+(.+?)\s*$", re.I),
    # [TIMESERIES] / [RAINGAGES]:  <name> ... FILE  path
    re.compile(r"\bFILE\s+(\"[^\"]+\"|\S+)", re.I),
)


def file_references(sections: dict[str, list[str]]) -> list[str]:
    """External files the model needs, as written in the .inp."""
    refs: list[str] = []
    for name in ("FILES", "TIMESERIES", "RAINGAGES"):
        for line in sections.get(name, []):
            for pat in FILE_REF_PATTERNS:
                m = pat.search(line)
                if m:
                    refs.append(m.group(1).strip().strip('"'))
                    break
    seen: dict[str, None] = {}
    for r in refs:
        seen.setdefault(r, None)
    return list(seen)


def is_absolute(ref: str) -> bool:
    return bool(re.match(r"^(?:[A-Za-z]:[\\/]|[\\/])", ref))


# ── tag derivation ─────────────────────────────────────────────────────────
def derive_tags(sections: dict[str, list[str]], opts: dict[str, str],
                collection: str, rpt: dict | None) -> tuple[set[str], list[str]]:
    """Tags plus the evidence for each, so a reviewer can audit the mapping."""
    tags: set[str] = set()
    why: list[str] = []

    def add(tag: str, evidence: str):
        if tag not in tags:
            tags.add(tag)
            why.append(f"{tag}: {evidence}")

    def has(section: str) -> bool:
        return bool(sections.get(section))

    add("regression", "every migrated model guards against engine drift")

    routing = opts.get("FLOW_ROUTING", "").upper()
    if routing.startswith("DYN"):
        add("dynamic_wave", "OPTIONS FLOW_ROUTING DYNWAVE")
    elif routing.startswith("KIN"):
        add("kinematic_wave", "OPTIONS FLOW_ROUTING KINWAVE")
    elif routing.startswith("STEADY"):
        add("steady_flow", "OPTIONS FLOW_ROUTING STEADY")
    elif routing.startswith("FV"):
        add("finite_volume", "OPTIONS FLOW_ROUTING FV")

    if has("CONDUITS") or has("PUMPS") or has("WEIRS") or has("ORIFICES"):
        add("hydraulics", "conveyance elements present")
    if has("SUBCATCHMENTS"):
        add("hydrology", "[SUBCATCHMENTS] non-empty")
    if has("INFILTRATION"):
        add("infiltration", "[INFILTRATION] non-empty")
    if has("EVAPORATION"):
        add("evaporation", "[EVAPORATION] non-empty")

    if has("POLLUTANTS"):
        add("quality", "[POLLUTANTS] non-empty")
        add("pollutants", "[POLLUTANTS] non-empty")
    if has("BUILDUP") or has("WASHOFF"):
        add("buildup_washoff", "[BUILDUP]/[WASHOFF] non-empty")
    if has("TREATMENT"):
        add("treatment", "[TREATMENT] non-empty")
    if has("LID_CONTROLS") or has("LID_USAGE"):
        add("lid", "[LID_CONTROLS]/[LID_USAGE] non-empty")
    if {"lid", "pollutants"} <= tags:
        add("lid_pollutants", "LID controls and pollutants both present")

    if has("AQUIFERS") or has("GROUNDWATER") or has("GWF"):
        add("groundwater", "[AQUIFERS]/[GROUNDWATER] non-empty")
    if has("SNOWPACKS"):
        add("snowmelt", "[SNOWPACKS] non-empty")
    if has("CONTROLS"):
        add("controls", "[CONTROLS] non-empty")
        add("rtc", "[CONTROLS] non-empty")
    if has("RDII") or has("HYDROGRAPHS"):
        add("rdii", "[RDII]/[HYDROGRAPHS] non-empty")
    if has("DWF"):
        add("dwf", "[DWF] non-empty")

    for section, tag in (("PUMPS", "pump"), ("WEIRS", "weir"),
                         ("ORIFICES", "orifice"), ("OUTLETS", "outlet"),
                         ("STORAGE", "storage"), ("DIVIDERS", "divider"),
                         ("TRANSECTS", "irregular_xsect")):
        if has(section):
            add(tag, f"[{section}] non-empty")

    if has("STREETS") or has("INLETS") or has("INLET_USAGE"):
        add("street_inlet", "[STREETS]/[INLETS] non-empty")
        add("dual_drainage", "street/inlet coupling present")

    xsect = " ".join(sections.get("XSECTIONS", [])).upper()
    if "FORCE_MAIN" in xsect:
        add("force_main", "FORCE_MAIN cross-section in [XSECTIONS]")
    if "CIRCULAR" in xsect:
        add("circular_xsect", "CIRCULAR cross-section in [XSECTIONS]")

    outfalls = " ".join(sections.get("OUTFALLS", [])).upper()
    if "TIDAL" in outfalls or "TIMESERIES" in outfalls:
        add("outfall_bc", "non-trivial outfall boundary condition")

    # 2D surface routing is declared by its own sections, not by FLOW_ROUTING,
    # so a model can be 1D-FV, 2D, or coupled.
    if any(k.startswith("2D_") for k in sections):
        add("2d", "[2D_*] sections present")
        add("finite_volume_2d", "2D shallow-water finite-volume surface routing")
    if sections.get("VIRTUAL_JUNCTIONS"):
        add("virtual_junctions", "[VIRTUAL_JUNCTIONS] non-empty")

    if any(k.startswith("INNOVYZE") for k in sections):
        add("interop", "Innovyze supplementary sections present")
        add("converted_icm", "Innovyze supplementary sections present")
    if collection == "xpswmm":
        add("interop", "XPSWMM-derived collection")
        add("converted_xpswmm", "XPSWMM-derived collection")

    days = duration_days(opts)
    if days is not None and days > 365:
        add("long_term", f"simulation spans {days} days")

    if collection in REAL_WORLD_COLLECTIONS:
        add("real_world", f"collection {collection!r}")

    # Advisory: taken from a sibling report file, whose engine and version are
    # unknown. Provenance records the source; these three say what the model
    # *did* on some run, which no amount of .inp parsing can reveal.
    #
    # Note: `transition_pressurized` is deliberately NOT inferred here.
    # Surcharging proves a conduit pressurized, not that it transitioned back
    # and forth, and mis-tagging 600+ models would make the tag worthless for
    # the transition suite it exists to feed. It stays a curation decision.
    if rpt:
        if rpt.get("conduits_surcharged"):
            add("surcharge", f"sibling .rpt: "
                             f"{rpt['conduits_surcharged']} conduit(s) surcharged")
        if rpt.get("nodes_flooded"):
            add("flooding", f"sibling .rpt: "
                            f"{rpt['nodes_flooded']} node(s) flooded")
        if rpt.get("links_instability"):
            add("flow_instability", f"sibling .rpt: "
                                    f"{rpt['links_instability']} unstable link(s)")

    return tags, why


def size_class(n_elements: int) -> str:
    if n_elements < 10:
        return "XS"
    if n_elements < 100:
        return "S"
    if n_elements < 1000:
        return "M"
    if n_elements < 10000:
        return "L"
    return "XL"


def runtime_class(size: str, tags: set[str]) -> str:
    """Estimate only — plan step 7 replaces these with measured timings."""
    if "long_term" in tags or size == "XL":
        return "slow"
    if size in ("L",):
        return "medium"
    return "fast"


def slug(name: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
    return re.sub(r"-{2,}", "-", s) or "model"


# ── case model ─────────────────────────────────────────────────────────────
@dataclass
class ScannedCase:
    src: Path
    collection: str
    case_id: str
    tags: set[str] = field(default_factory=set)
    evidence: list[str] = field(default_factory=list)
    units: str = "US"
    routing: str = ""
    size_class: str = "S"
    runtime_class: str = "fast"
    counts: dict = field(default_factory=dict)
    n_pollut: int = 0
    duration_days: int | None = None
    refs_local: list[str] = field(default_factory=list)
    refs_absolute: list[str] = field(default_factory=list)
    refs_missing: list[str] = field(default_factory=list)
    sha: str = ""
    title: str = ""
    problems: list[str] = field(default_factory=list)

    @property
    def dest(self) -> Path:
        return CORPUS / self.collection / self.case_id


def scan_one(path: Path, collection: str) -> ScannedCase:
    text = path.read_text(encoding="utf-8", errors="replace")
    sections = parse_sections(text)
    opts = options(sections)

    counts = {k.lower(): len(sections.get(k, []))
              for k in ("SUBCATCHMENTS", "JUNCTIONS", "OUTFALLS", "STORAGE",
                        "DIVIDERS", "CONDUITS", "PUMPS", "ORIFICES", "WEIRS",
                        "OUTLETS")}
    n_elements = sum(counts.values())

    rpt_path = path.with_suffix(".rpt")
    rpt = None
    if rpt_path.exists():
        sys.path.insert(0, str(REPO_ROOT))
        from harness import rptparse
        rpt = rptparse.parse(rpt_path)

    tags, evidence = derive_tags(sections, opts, collection, rpt)
    size = size_class(n_elements)

    case = ScannedCase(
        src=path, collection=collection, case_id=slug(path.stem),
        tags=tags, evidence=evidence,
        units="SI" if opts.get("FLOW_UNITS", "CFS").upper() in SI_UNITS else "US",
        routing=(opts.get("FLOW_ROUTING", "") or "").upper()[:8],
        size_class=size, runtime_class=runtime_class(size, tags),
        counts=counts, n_pollut=len(sections.get("POLLUTANTS", [])),
        duration_days=duration_days(opts),
        sha=hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()[:16],
        title=(sections.get("TITLE") or [""])[0][:120],
    )

    for ref in file_references(sections):
        if is_absolute(ref):
            case.refs_absolute.append(ref)
        elif (path.parent / ref).exists():
            case.refs_local.append(ref)
        else:
            case.refs_missing.append(ref)

    if not n_elements:
        case.problems.append("no hydraulic or hydrologic elements found")
    if case.refs_absolute:
        case.problems.append(
            f"{len(case.refs_absolute)} absolute path(s) — will not resolve "
            "off the authoring machine")
    if case.refs_missing:
        case.problems.append(
            f"{len(case.refs_missing)} referenced file(s) not found")
    return case


def scan_all(root: Path = REPO_ROOT) -> tuple[list[ScannedCase], list[Path]]:
    """Returns (cases, empty_files). Zero-byte .inp files are not models and
    are excluded outright rather than becoming empty corpus cases."""
    cases: list[ScannedCase] = []
    empty: list[Path] = []
    # Case-INSENSITIVE: 57 models ship as .INP. A `rglob("*.inp")` silently
    # skipped every one of them on a case-sensitive filesystem, which is
    # invisible unless you reconcile the counts.
    for inp in sorted(p for p in root.rglob("*")
                      if p.is_file() and p.suffix.lower() == ".inp"):
        rel = inp.relative_to(root)
        top = rel.parts[0]
        if top in EXCLUDE_DIRS or inp.is_symlink():
            continue
        if inp.stat().st_size == 0:
            empty.append(inp)
            continue
        collection = slug(top) if len(rel.parts) > 1 else "root"
        cases.append(scan_one(inp, collection))
    _disambiguate(cases)
    return cases, empty


def _keeper_rank(c: ScannedCase) -> tuple:
    """Which copy of a duplicated model to keep.

    Prefer a name with no download-artifact suffix — `model.inp` over
    `model (1).inp` or `model(2).inp` — then the shallower path, then
    alphabetical, so the surviving case id is the clean one.
    """
    stem = c.src.stem
    has_suffix = bool(re.search(r"\s*\(\d+\)\s*$", stem))
    return (has_suffix, len(c.src.parts), str(c.src))


def _disambiguate(cases: list[ScannedCase]) -> None:
    """Make case ids unique within their collection, using the subdirectory."""
    by_key: dict[tuple[str, str], list[ScannedCase]] = defaultdict(list)
    for c in cases:
        by_key[(c.collection, c.case_id)].append(c)
    for (collection, cid), group in by_key.items():
        if len(group) == 1:
            continue
        for c in group:
            rel = c.src.relative_to(REPO_ROOT).parts[1:-1]   # inner dirs
            prefix = "-".join(slug(p) for p in rel)
            c.case_id = f"{prefix}-{cid}" if prefix else cid
    # any collision still standing gets a content-hash suffix
    seen: dict[tuple[str, str], int] = Counter()
    for c in cases:
        key = (c.collection, c.case_id)
        seen[key] += 1
        if seen[key] > 1:
            c.case_id = f"{c.case_id}-{c.sha[:6]}"


# ── reporting ──────────────────────────────────────────────────────────────
def duplicates(cases: list[ScannedCase]) -> dict[str, list[ScannedCase]]:
    by_sha: dict[str, list[ScannedCase]] = defaultdict(list)
    for c in cases:
        by_sha[c.sha].append(c)
    return {sha: group for sha, group in by_sha.items() if len(group) > 1}


def report(cases: list[ScannedCase], empty: list[Path] | None = None) -> str:
    tag_counts = Counter(t for c in cases for t in c.tags)
    coll_counts = Counter(c.collection for c in cases)
    dups = duplicates(cases)
    n_dup_files = sum(len(g) - 1 for g in dups.values())

    L: list[str] = ["# Corpus migration scan", ""]
    L += [f"- **{len(cases)}** models scanned across "
          f"**{len(coll_counts)}** collections",
          f"- **{len(dups)}** duplicate groups covering **{n_dup_files}** "
          "redundant copies",
          f"- **{sum(1 for c in cases if c.problems)}** models with problems",
          ""]

    L += ["## Collections", "", "| collection | models |", "|---|---|"]
    L += [f"| `{k}` | {v} |" for k, v in coll_counts.most_common()]

    L += ["", "## Tag census", "", "| tag | models |", "|---|---|"]
    L += [f"| `{k}` | {v} |" for k, v in tag_counts.most_common()]

    L += ["", "## Size and units", ""]
    for label, counter in (("size_class", Counter(c.size_class for c in cases)),
                           ("units", Counter(c.units for c in cases)),
                           ("routing", Counter(c.routing or "(unset)" for c in cases))):
        L.append(f"- **{label}**: " + ", ".join(
            f"{k}={v}" for k, v in counter.most_common()))

    if dups:
        L += ["", "## Duplicate groups (identical content)", ""]
        for sha, group in sorted(dups.items(),
                                 key=lambda kv: -len(kv[1]))[:40]:
            paths = ", ".join(str(c.src.relative_to(REPO_ROOT)) for c in group)
            L.append(f"- `{sha}` ×{len(group)}: {paths}")
        if len(dups) > 40:
            L.append(f"- … {len(dups) - 40} more groups")

    problems = [c for c in cases if c.problems]
    if problems:
        L += ["", "## Models with problems", "",
              "| model | problem |", "|---|---|"]
        for c in problems[:60]:
            L.append(f"| `{c.src.relative_to(REPO_ROOT)}` | "
                     f"{'; '.join(c.problems)} |")
        if len(problems) > 60:
            L.append(f"| … | {len(problems) - 60} more |")

    if empty:
        L += ["", "## Excluded: zero-byte files", "",
              "Not models. Excluded outright rather than becoming empty "
              "corpus cases.", ""]
        L += [f"- `{p.relative_to(REPO_ROOT)}`" for p in empty]

    L += ["", "## Sample of proposed cases", "",
          "| source | destination | tags |", "|---|---|---|"]
    for c in cases[:25]:
        L.append(f"| `{c.src.relative_to(REPO_ROOT)}` | "
                 f"`{c.dest.relative_to(REPO_ROOT)}` | "
                 f"{', '.join(sorted(c.tags))} |")
    return "\n".join(L) + "\n"


# ── apply ──────────────────────────────────────────────────────────────────
def metadata_doc(c: ScannedCase) -> str:
    import yaml
    doc = {
        "id": c.case_id,
        "title": c.title or c.src.stem,
        "model": "model.inp",
        "tags": sorted(c.tags),
        "units": c.units,
        "size_class": c.size_class,
        "runtime_class": c.runtime_class,
        "tiers": ["nightly"],
        "reference": {"class": "self_consistency"},
        "notes": (
            "Metadata generated by tools/migrate_corpus.py from the model's "
            "own sections; tags are evidence-based. runtime_class is an "
            "estimate from model size and is replaced by measured timings "
            "when the PR tier is curated."),
    }
    if c.routing in ("DYNWAVE", "KINWAVE", "STEADY"):
        doc["routing"] = c.routing
    if c.refs_local:
        doc["data_files"] = c.refs_local
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False,
                          allow_unicode=True)


def provenance_doc(c: ScannedCase) -> str:
    import yaml
    unverified = c.collection in UNVERIFIED_COLLECTIONS
    doc = {
        "source": f"Legacy benchmarks collection {c.collection!r} "
                  f"(originally {c.src.relative_to(REPO_ROOT).as_posix()})",
        "license": "unverified" if unverified else "public-domain",
        "contributed_by": "unknown (pre-migration corpus)",
        "date_added": "2026-08-22",
        "original_units": c.units,
        "notes": (
            "Provenance carried over mechanically during the corpus "
            "migration. Contributed collection — confirm the source and "
            "license before redistributing."
            if unverified else
            "Provenance carried over mechanically during the corpus "
            "migration; the repository's blanket public-domain dedication "
            "applies. Refine if the specific origin is known."),
    }
    return yaml.safe_dump(doc, sort_keys=False, default_flow_style=False,
                          allow_unicode=True)


def write_skip_list(cases: list[ScannedCase], migrated: set[Path]) -> Path:
    """Exclude models that cannot run anywhere, with the reason recorded.

    A model referencing `P:\\Active\\rain.dat` will fail on every machine that
    is not the one it was authored on. Left in a sweep it produces a permanent
    ERROR that trains everyone to ignore red. Skipping it with a stated reason
    and a route back is the honest handling — the model is still preserved,
    validated, and searchable.
    """
    import yaml
    entries = []
    for c in cases:
        if c.src not in migrated:
            continue
        if c.refs_absolute:
            entries.append({
                "case": c.case_id,
                "reason": f"references {len(c.refs_absolute)} absolute path(s) "
                          f"from the authoring machine, e.g. "
                          f"{c.refs_absolute[0][:60]}",
                "revisit": "when the referenced data is located and relocated "
                           "beside the model, or the reference is made relative",
            })
        elif c.refs_missing:
            entries.append({
                "case": c.case_id,
                "reason": f"referenced file(s) not found in the corpus: "
                          f"{', '.join(c.refs_missing[:3])}",
                "revisit": "when the missing data files are recovered",
            })
        elif "no hydraulic or hydrologic elements found" in " ".join(c.problems):
            entries.append({
                "case": c.case_id,
                "reason": "no hydraulic or hydrologic elements — not a runnable model",
                "revisit": "never, unless the file is a fragment that should be "
                           "removed from the corpus instead",
            })

    path = REPO_ROOT / "suites" / "parity" / "manifests" / "skip_list.yaml"
    header = (
        "# Cases excluded from sweeps, with a reason each. A skip is a\n"
        "# decision, not a convenience: every entry states why and what would\n"
        "# let it come back.\n"
        "#\n"
        "# Generated by tools/migrate_corpus.py during the corpus migration.\n"
        "# Entries added by hand afterwards are equally valid; the file is not\n"
        "# regenerated.\n")
    path.write_text(header + yaml.safe_dump({"skip": entries}, sort_keys=False,
                                            default_flow_style=False,
                                            allow_unicode=True, width=100), encoding="utf-8")
    return path


def git_mv(src: Path, dst: Path) -> None:
    """Move a model into place.

    A plain filesystem move, not `git mv`: 1,337 `git mv` calls each rewrite
    the index of a multi-gigabyte repository. Git detects these as renames at
    `git add -A` time anyway, because the content is byte-identical.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))


def apply(cases: list[ScannedCase], skip_duplicates: bool = True) -> dict:
    """Move models into corpus/ and write their metadata."""
    dup_groups = duplicates(cases)
    redundant: set[Path] = set()
    if skip_duplicates:
        for group in dup_groups.values():
            # keep the first by path order; the rest are recorded, not moved
            for c in sorted(group, key=_keeper_rank)[1:]:
                redundant.add(c.src)

    # Content already in the corpus — makes a re-run migrate only what is
    # genuinely new instead of duplicating everything a previous run moved.
    already = {hashlib.sha256(p.read_bytes()).hexdigest()[:16]
               for p in CORPUS.rglob("model.inp")} if CORPUS.exists() else set()

    stats = Counter()
    migrated: set[Path] = set()
    for c in cases:
        if c.src in redundant:
            stats["skipped_duplicate"] += 1
            continue
        if c.sha in already:
            stats["skipped_already_in_corpus"] += 1
            continue
        dest = c.dest
        dest.mkdir(parents=True, exist_ok=True)
        # Copy referenced data BEFORE moving the model — afterwards the source
        # directory context is gone and relative references cannot be resolved.
        for ref in c.refs_local:
            srcfile = c.src.parent / ref
            target = dest / Path(ref).name
            if srcfile.exists() and not target.exists():
                shutil.copy2(srcfile, target)
                stats["data_files_copied"] += 1
        git_mv(c.src, dest / "model.inp")
        (dest / "metadata.yaml").write_text(metadata_doc(c), encoding="utf-8")
        (dest / "provenance.yaml").write_text(provenance_doc(c), encoding="utf-8")
        migrated.add(c.src)
        stats["migrated"] += 1

    skip_path = write_skip_list(cases, migrated)
    import yaml
    stats["skip_list_entries"] = len(
        (yaml.safe_load(skip_path.read_text(encoding="utf-8")) or {}).get("skip") or [])
    return dict(stats)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true",
                    help="perform the migration (default is scan only)")
    ap.add_argument("--report", type=Path, help="write the scan report here")
    ap.add_argument("--keep-duplicates", action="store_true",
                    help="migrate byte-identical copies instead of skipping them")
    args = ap.parse_args(argv)

    cases, empty = scan_all()
    text = report(cases, empty)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text, encoding="utf-8")
        print(f"report written to {args.report}")
    else:
        print(text)

    if args.apply:
        stats = apply(cases, skip_duplicates=not args.keep_duplicates)
        print(f"\nmigration complete: {stats}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
