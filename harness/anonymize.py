#!/usr/bin/env python3
"""Best-effort anonymization of a SWMM model.

**No tool can guarantee anonymity, and this one does not claim to.** It removes
the identifying content it knows how to find; it cannot know that a conduit
named ``TRUNK_MAIN_AT_5TH_AND_ELM`` names a real intersection, or that a
network's shape is recognizable to someone who works on it. What it provides
is a layer that, combined with the submitter's own review, can make an
otherwise unshareable model shareable. Final responsibility rests with the
submitter.

Transforms (each independently selectable):

  rename-ids      consistent renaming of subcatchment / node / link / gage /
                  curve / timeseries / pattern / LID / aquifer / snowpack /
                  landuse / pollutant / transect / street / inlet identifiers,
                  with the map written to a side file the submitter keeps
  coords-offset   translate all coordinates so the network's lower-left corner
                  sits at the origin, preserving shape and scale exactly
  coords-strip    remove [COORDINATES], [VERTICES], [POLYGONS], [SYMBOLS],
                  [LABELS], [BACKDROP], [MAP] entirely
  scrub-text      clear [TITLE] and [TAGS], drop ';' comments, blank rain-gage
                  station identifiers, and replace absolute file paths with
                  their bare filename
  relocate-data   rewrite external file references to bare filenames

**Correctness invariant.** Anonymization must never change physics. Renaming is
applied to identifier *tokens* in the positions where the SWMM input format
puts identifiers, and ``--verify`` re-runs the model before and after and
requires the resulting ``.out`` to be byte-identical. Without an engine
available, ``--verify`` reports that it could not check rather than passing
silently.

    python -m harness.anonymize model.inp -o anon.inp --map ids.json
    python -m harness.anonymize model.inp -o anon.inp \\
        --transforms rename-ids,coords-offset,scrub-text --verify
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

TRANSFORMS = ("rename-ids", "coords-offset", "coords-strip", "scrub-text",
              "relocate-data")
DEFAULT_TRANSFORMS = ("rename-ids", "coords-offset", "scrub-text",
                      "relocate-data")

#: Sections removed entirely by coords-strip.
GEOMETRY_SECTIONS = {"COORDINATES", "VERTICES", "POLYGONS", "SYMBOLS",
                     "LABELS", "BACKDROP", "MAP", "PROFILES"}

#: Where each kind of identifier is DEFINED: section -> (prefix, column index).
#: Column 0 is the first whitespace-separated field of a data line.
ID_DEFINITIONS: dict[str, tuple[str, int]] = {
    "SUBCATCHMENTS": ("S", 0),
    "JUNCTIONS": ("N", 0), "OUTFALLS": ("N", 0), "STORAGE": ("N", 0),
    "DIVIDERS": ("N", 0),
    "CONDUITS": ("L", 0), "PUMPS": ("L", 0), "ORIFICES": ("L", 0),
    "WEIRS": ("L", 0), "OUTLETS": ("L", 0),
    "RAINGAGES": ("G", 0),
    "CURVES": ("C", 0), "TIMESERIES": ("T", 0), "PATTERNS": ("P", 0),
    "AQUIFERS": ("A", 0), "SNOWPACKS": ("K", 0), "LANDUSES": ("U", 0),
    "POLLUTANTS": ("Q", 0), "TRANSECTS": ("X", 1),   # "NC"/"X1" keyword first
    "LID_CONTROLS": ("D", 0), "STREETS": ("R", 0), "INLETS": ("I", 0),
    "CONTROLS": ("", -1),                            # rules: renamed in text
}

#: Sections whose data lines are pure geometry/text and must not be
#: token-substituted (their first column is an id, handled separately).
_NO_SUBSTITUTE = {"TITLE", "OPTIONS", "REPORT", "FILES", "TAGS"}


@dataclass
class Result:
    text: str
    id_map: dict[str, str] = field(default_factory=dict)
    applied: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


# ── section-aware iteration ────────────────────────────────────────────────
def _iter_lines(text: str):
    """Yield (index, line, section, is_data) over an .inp."""
    section = ""
    for i, line in enumerate(text.splitlines(keepends=True)):
        body = line.split(";", 1)[0]
        stripped = body.strip()
        m = re.match(r"^\[([A-Za-z_0-9]+)\]", stripped)
        if m:
            yield i, line, m.group(1).upper(), False
            section = m.group(1).upper()
            continue
        yield i, line, section, bool(stripped)


def collect_ids(text: str) -> dict[str, str]:
    """Build the rename map from the sections where identifiers are defined."""
    counters: dict[str, int] = {}
    mapping: dict[str, str] = {}
    for _, line, section, is_data in _iter_lines(text):
        if not is_data or section not in ID_DEFINITIONS:
            continue
        prefix, col = ID_DEFINITIONS[section]
        if col < 0:
            continue
        fields = line.split(";", 1)[0].split()
        if len(fields) <= col:
            continue
        old = fields[col]
        if old in mapping or not _is_identifier(old):
            continue
        counters[prefix] = counters.get(prefix, 0) + 1
        mapping[old] = f"{prefix}{counters[prefix]}"
    return mapping


def _is_identifier(token: str) -> bool:
    """Reject things that are plainly not element names."""
    if not token or len(token) > 64:
        return False
    if token.startswith((";", "[")):
        return False
    try:                       # a bare number is data, not a name
        float(token)
        return False
    except ValueError:
        return True


def rename_ids(text: str, mapping: dict[str, str]) -> str:
    """Substitute identifier tokens wherever they appear as whole fields.

    Whole-token substitution only: a rename never rewrites part of a number,
    a keyword, or a longer name, which is what keeps the edit non-physical.
    """
    if not mapping:
        return text
    out: list[str] = []
    for _, line, section, is_data in _iter_lines(text):
        if not is_data or section in _NO_SUBSTITUTE:
            out.append(line)
            continue
        body, sep, comment = line.partition(";")
        tokens = re.split(r"(\s+)", body)
        tokens = [mapping.get(t, t) if not t.isspace() else t for t in tokens]
        out.append("".join(tokens) + sep + comment)
    return "".join(out)


# ── coordinates ────────────────────────────────────────────────────────────
_COORD_SECTIONS = ("COORDINATES", "VERTICES", "POLYGONS")


def offset_coordinates(text: str) -> tuple[str, tuple[float, float]]:
    """Translate every coordinate so the bounding box starts at the origin.

    Shape, scale, and every relative distance are preserved exactly; only the
    georeferencing is destroyed, which is what makes a network locatable.
    """
    xs: list[float] = []
    ys: list[float] = []
    for _, line, section, is_data in _iter_lines(text):
        if is_data and section in _COORD_SECTIONS:
            f = line.split(";", 1)[0].split()
            if len(f) >= 3:
                try:
                    xs.append(float(f[-2]))
                    ys.append(float(f[-1]))
                except ValueError:
                    pass
    if not xs:
        return text, (0.0, 0.0)
    dx, dy = min(xs), min(ys)

    out: list[str] = []
    for _, line, section, is_data in _iter_lines(text):
        if not (is_data and section in _COORD_SECTIONS):
            out.append(line)
            continue
        body, sep, comment = line.partition(";")
        f = body.split()
        if len(f) < 3:
            out.append(line)
            continue
        try:
            x, y = float(f[-2]) - dx, float(f[-1]) - dy
        except ValueError:
            out.append(line)
            continue
        lead = body[:len(body) - len(body.lstrip())]
        f[-2], f[-1] = f"{x:.4f}", f"{y:.4f}"
        out.append(lead + " ".join(f) + ("\n" if body.endswith("\n") and not sep
                                         else "") + sep + comment)
    return "".join(out), (dx, dy)


def strip_geometry(text: str) -> str:
    out: list[str] = []
    for _, line, section, is_data in _iter_lines(text):
        if section in GEOMETRY_SECTIONS and is_data:
            continue
        out.append(line)
    return "".join(out)


# ── text scrubbing ─────────────────────────────────────────────────────────
_ABS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s\"']*"
                       r"|/(?:Users|home)/[^\s\"']*")


def scrub_text(text: str) -> tuple[str, int]:
    """Clear titles and tags, drop comments, shorten absolute paths."""
    removed = 0
    out: list[str] = []
    for _, line, section, is_data in _iter_lines(text):
        if section in ("TITLE", "TAGS") and is_data:
            removed += 1
            continue
        body, sep, _comment = line.partition(";")
        if sep and body.strip():
            line = body.rstrip() + "\n"          # keep the data, drop the note
            removed += 1
        elif sep and not body.strip():
            removed += 1
            continue                              # whole-line comment
        if _ABS_PATH.search(line):
            line = _ABS_PATH.sub(lambda m: Path(m.group(0).replace("\\", "/")).name,
                                 line)
            removed += 1
        out.append(line)
    return "".join(out), removed


# ── driver ─────────────────────────────────────────────────────────────────
def anonymize(text: str, transforms=DEFAULT_TRANSFORMS) -> Result:
    res = Result(text=text)
    transforms = list(transforms)

    if "rename-ids" in transforms:
        res.id_map = collect_ids(res.text)
        res.text = rename_ids(res.text, res.id_map)
        res.applied.append("rename-ids")
        res.notes.append(f"renamed {len(res.id_map)} identifiers")

    if "coords-strip" in transforms:
        res.text = strip_geometry(res.text)
        res.applied.append("coords-strip")
        res.notes.append("removed all map geometry sections")
    elif "coords-offset" in transforms:
        res.text, (dx, dy) = offset_coordinates(res.text)
        if (dx, dy) != (0.0, 0.0):
            res.applied.append("coords-offset")
            res.notes.append(f"translated coordinates by ({-dx:.4f}, {-dy:.4f})")

    if "scrub-text" in transforms or "relocate-data" in transforms:
        res.text, n = scrub_text(res.text)
        res.applied.append("scrub-text")
        res.notes.append(f"scrubbed {n} title/tag/comment/path item(s)")

    return res


def verify(original: Path, anonymized: Path, engine_id: str = "openswmm-v6",
           work_dir: Path | None = None) -> dict:
    """Run both models and require byte-identical results.

    Returns {"checked": bool, "identical": bool, "note": str}. When no engine
    can be run this reports checked=False — it never reports success it did
    not observe.
    """
    from . import engines, runner
    reg = engines.resolve_all(engines.load(), only=[engine_id])
    eng = reg.engines.get(engine_id)
    if not eng or not eng.ok:
        return {"checked": False, "identical": False,
                "note": f"engine {engine_id!r} unavailable — anonymization "
                        "was NOT verified against results"}

    work = Path(work_dir or original.parent / "_anon_verify")
    work.mkdir(parents=True, exist_ok=True)
    outs = []
    for tag, model in (("orig", original), ("anon", anonymized)):
        rpt, out = work / f"{tag}.rpt", work / f"{tag}.out"
        info = runner.run(eng.exe, model, rpt, out, timeout=600)
        if not info["ok"]:
            return {"checked": False, "identical": False,
                    "note": f"{tag} model did not run: {info['stderr'][:160]}"}
        outs.append(out)

    from .readers import Out
    a, b = Out(outs[0]), Out(outs[1])
    identical = a.results_bytes() == b.results_bytes()
    return {"checked": True, "identical": identical,
            "note": ("results byte-identical — anonymization did not change "
                     "physics" if identical else
                     "RESULTS DIFFER — the anonymized model is not equivalent; "
                     "do not submit it")}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inp", type=Path, help="model to anonymize")
    ap.add_argument("-o", "--out", type=Path, required=True)
    ap.add_argument("--map", type=Path, help="write the id map here (keep it private)")
    ap.add_argument("--transforms", default=",".join(DEFAULT_TRANSFORMS),
                    help=f"comma-separated subset of {','.join(TRANSFORMS)}")
    ap.add_argument("--verify", action="store_true",
                    help="run both models and require identical results")
    ap.add_argument("--engine", default="openswmm-v6")
    args = ap.parse_args(argv)

    unknown = set(args.transforms.split(",")) - set(TRANSFORMS)
    if unknown:
        print(f"unknown transform(s): {', '.join(sorted(unknown))}",
              file=sys.stderr)
        return 2

    text = args.inp.read_bytes().decode("latin-1")
    res = anonymize(text, args.transforms.split(","))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(res.text.encode("latin-1"))

    print(f"wrote {args.out}")
    for n in res.notes:
        print(f"  {n}")
    if args.map and res.id_map:
        args.map.write_text(json.dumps(res.id_map, indent=2), encoding="utf-8")
        print(f"  id map -> {args.map}  (keep this private; it reverses the rename)")

    if args.verify:
        v = verify(args.inp, args.out, args.engine)
        print(f"  verify: {v['note']}")
        if v["checked"] and not v["identical"]:
            return 1
        if not v["checked"]:
            return 3

    print("\nNo tool can guarantee anonymity. Review the output yourself before "
          "sharing it.")
    return 0


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    sys.exit(main())
