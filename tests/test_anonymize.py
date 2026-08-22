"""Anonymization must remove identity without touching physics.

The tool's whole value rests on one property: a submitter can hand over a
network they could not otherwise share, and the engine still sees the same
model. `--verify` proves that with an engine; these tests prove the
structural half of it without one — topology, numbers, and units survive
every transform, and identifiers are renamed consistently everywhere they
appear.
"""
from __future__ import annotations

import re

import pytest

from harness import anonymize as A

MODEL = """\
[TITLE]
City of Springfield trunk sewer, Elm St basin
Prepared by J. Rivera, Acme Engineering

[OPTIONS]
;;Option             Value
FLOW_UNITS           CFS
FLOW_ROUTING         DYNWAVE
START_DATE           01/01/2020

[FILES]
USE RAINFALL "D:\\Projects\\Springfield\\rain.dat"

[RAINGAGES]
;;Name  Format Interval SCF Source
ELM_GAGE INTENSITY 1:00 1.0 TIMESERIES TS_ELM

[SUBCATCHMENTS]
;;Name        RainGage  Outlet    Area  %Imperv Width Slope
ELM_N         ELM_GAGE  MH_ELM_1  12.5  45      500   0.5
ELM_S         ELM_GAGE  MH_ELM_2  8.25  60      400   0.5

[JUNCTIONS]
;;Name      Elev  MaxDepth
MH_ELM_1    120.5 8.0
MH_ELM_2    118.25 8.0

[OUTFALLS]
;;Name      Elev  Type
OUT_RIVER   110.0 FREE

[CONDUITS]
;;Name        From      To         Length Roughness
TRUNK_ELM_A   MH_ELM_1  MH_ELM_2   450.0  0.013
TRUNK_ELM_B   MH_ELM_2  OUT_RIVER  380.5  0.013

[XSECTIONS]
TRUNK_ELM_A   CIRCULAR 2.5 0 0 0
TRUNK_ELM_B   CIRCULAR 3.0 0 0 0

[TIMESERIES]
TS_ELM 0:00 0.5

[TAGS]
Node MH_ELM_1 ElmStreetBasin

[COORDINATES]
;;Node       X            Y
MH_ELM_1     2145678.500  845123.250
MH_ELM_2     2145900.750  845400.000
OUT_RIVER    2146200.000  845800.125
"""


def sections(text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    cur = ""
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^\[([A-Za-z_0-9]+)\]", line)
        if m:
            cur = m.group(1).upper()
            out.setdefault(cur, [])
            continue
        if cur:
            out.setdefault(cur, []).append(line)
    return out


def topology(text: str):
    s = sections(text)
    nodes = {l.split()[0] for k in ("JUNCTIONS", "OUTFALLS", "STORAGE", "DIVIDERS")
             for l in s.get(k, [])}
    links = {l.split()[0]: tuple(l.split()[1:3])
             for k in ("CONDUITS", "PUMPS", "ORIFICES", "WEIRS", "OUTLETS")
             for l in s.get(k, []) if len(l.split()) >= 3}
    return nodes, links


def numbers(text: str) -> list[float]:
    """Every number outside the coordinate sections."""
    vals, cur = [], ""
    for raw in text.splitlines():
        line = raw.split(";", 1)[0].strip()
        m = re.match(r"^\[([A-Za-z_0-9]+)\]", line)
        if m:
            cur = m.group(1).upper()
            continue
        if not line or cur in A._COORD_SECTIONS:
            continue
        for tok in line.split():
            try:
                vals.append(float(tok))
            except ValueError:
                pass
    return vals


# ── identity removal ───────────────────────────────────────────────────────

def test_identifiers_are_renamed():
    res = A.anonymize(MODEL)
    assert res.id_map, "nothing was renamed"
    for original in ("MH_ELM_1", "TRUNK_ELM_A", "ELM_GAGE", "OUT_RIVER"):
        assert original in res.id_map
        assert original not in res.text, f"{original} survives in the output"


def test_titles_tags_and_comments_are_removed():
    res = A.anonymize(MODEL)
    for leak in ("Springfield", "Elm St", "J. Rivera", "Acme Engineering",
                 "ElmStreetBasin", "Project Title"):
        assert leak not in res.text, f"{leak!r} survives in the output"


def test_absolute_paths_are_reduced_to_filenames():
    res = A.anonymize(MODEL)
    assert "D:\\Projects" not in res.text
    assert "Springfield" not in res.text
    assert "rain.dat" in res.text, "the reference itself must survive"


def test_coordinates_are_moved_to_the_origin():
    res = A.anonymize(MODEL)
    coords = [tuple(map(float, l.split()[1:3]))
              for l in sections(res.text).get("COORDINATES", [])]
    assert coords
    assert min(x for x, _ in coords) == pytest.approx(0.0)
    assert min(y for _, y in coords) == pytest.approx(0.0)
    assert "2145678" not in res.text, "original georeference survives"


# ── physics preservation ───────────────────────────────────────────────────

def test_topology_survives_renaming():
    """Every link must still connect the same two nodes, under the map."""
    res = A.anonymize(MODEL)
    n0, l0 = topology(MODEL)
    n1, l1 = topology(res.text)
    m = res.id_map
    assert len(n0) == len(n1) and len(l0) == len(l1)
    for lid, (a, b) in l0.items():
        new = m.get(lid, lid)
        assert new in l1, f"link {lid} lost"
        assert l1[new] == (m.get(a, a), m.get(b, b)), f"link {lid} rewired"
    for a, b in l1.values():
        assert a in n1 and b in n1, "dangling endpoint introduced"


def test_no_numeric_value_changes_outside_coordinates():
    """Elevations, lengths, roughness, areas — every number must be identical."""
    res = A.anonymize(MODEL)
    assert numbers(res.text) == numbers(MODEL)


def test_coordinate_offset_preserves_relative_geometry():
    """Shape and scale are what a model needs; absolute position is what
    identifies it. Distances between nodes must be unchanged."""
    res = A.anonymize(MODEL, ["coords-offset"])
    def pts(t):
        return [tuple(map(float, l.split()[1:3]))
                for l in sections(t).get("COORDINATES", [])]
    a, b = pts(MODEL), pts(res.text)
    assert len(a) == len(b)
    for i in range(len(a) - 1):
        d0 = ((a[i][0] - a[i + 1][0]) ** 2 + (a[i][1] - a[i + 1][1]) ** 2) ** 0.5
        d1 = ((b[i][0] - b[i + 1][0]) ** 2 + (b[i][1] - b[i + 1][1]) ** 2) ** 0.5
        assert d0 == pytest.approx(d1, rel=1e-9)


def test_cross_section_references_follow_the_rename():
    """A rename that misses [XSECTIONS] leaves conduits with no geometry —
    the model would still load and silently behave differently."""
    res = A.anonymize(MODEL)
    xs = {l.split()[0] for l in sections(res.text).get("XSECTIONS", [])}
    links = set(topology(res.text)[1])
    assert xs == links, "xsection ids diverged from conduit ids"


def test_options_and_units_are_untouched():
    res = A.anonymize(MODEL)
    opts = sections(res.text)["OPTIONS"]
    assert "FLOW_UNITS           CFS" in "\n".join(opts) or \
           any(o.split() == ["FLOW_UNITS", "CFS"] for o in opts)
    assert any(o.startswith("FLOW_ROUTING") and "DYNWAVE" in o for o in opts)


# ── transform selection and honesty ────────────────────────────────────────

def test_id_map_reverses_the_rename():
    """The submitter keeps the map; it must actually let them trace back."""
    res = A.anonymize(MODEL, ["rename-ids"])
    inverse = {v: k for k, v in res.id_map.items()}
    assert len(inverse) == len(res.id_map), "rename map is not injective"
    restored = A.rename_ids(res.text, inverse)
    assert topology(restored) == topology(MODEL)


def test_coords_strip_removes_geometry_entirely():
    res = A.anonymize(MODEL, ["coords-strip"])
    assert not sections(res.text).get("COORDINATES")
    assert topology(res.text) == topology(MODEL), "stripping geometry changed the network"


def test_transforms_are_independently_selectable():
    only_coords = A.anonymize(MODEL, ["coords-offset"])
    assert not only_coords.id_map
    assert "MH_ELM_1" in only_coords.text, "ids renamed when not requested"


def test_verify_reports_unchecked_when_no_engine(tmp_path, monkeypatch):
    """It must never report success it did not observe."""
    from harness import engines

    def no_engines(reg, only=None):
        for e in reg.engines.values():
            e.status, e.exe = "UNAVAILABLE", None
        return reg

    monkeypatch.setattr(engines, "resolve_all", no_engines)
    a, b = tmp_path / "a.inp", tmp_path / "b.inp"
    a.write_text(MODEL)
    b.write_text(MODEL)
    v = A.verify(a, b)
    assert v["checked"] is False
    assert v["identical"] is False
    assert "NOT verified" in v["note"]
