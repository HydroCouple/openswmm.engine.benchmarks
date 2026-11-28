#!/usr/bin/env python3
"""Build the Rubinato et al. (2017) flume decks for corpus/rubinato-2017/.

The rig (8 m x 4 m flume, 0.24 m manhole, 75 mm pipe; rig_geometry.yaml) and
the steady measurements (Table 2) come from the article; the decks are
original work. This mirrors the engine's
tests/unit/engine/test_2d_exchange_rubinato_model.cpp so both repositories
rebuild the same flume:

  * Table 2 does not tabulate inflows, so each row's boundary conditions are
    reconstructed from the row: surface inflow Q1 = Fr_s * sqrt(g h_s) * h_s * W
    on the upstream edge (none in S4); sewer inflow Q3 = abs(Q_e / (surcharge_pct/100))
    for S2-S4, from Table 2's definition (no sewer inflow in S1); the measured sewer
    head h_p imposed at the manhole by a FIXED outfall stage behind a short,
    wide pipe (S1: the 75 mm pipe to a free outfall).
  * The manhole sits at the flume centre and the mesh is a uniform 0.2 m
    grid, not the paper's 0.0125 m grading: a junction exchanges through one
    cell, and cells far smaller than the 0.045 m2 opening concentrate the
    whole exchange in a sliver.
  * Pond: the manhole shaft (COUPLING_POND_MODE CHAMBER); head: the
    structure-area wet mean (COUPLING_HEAD STENCIL_WET_MEAN).
  * HEAD_TOLERANCE 0.00001 and the law's regularization head H_EPS=0.0033333
    (0.02/6 m, the rig scale), as the engine's test decks set them: the rig's
    heads are millimeters, narrower than the default head tolerance (1.5 mm)
    and than the field-scale regularization head (0.02 m).

usage:
  python corpus/rubinato-2017/_tools/make_decks.py --engine-ref \\
      ../openswmm.engine/tests/benchmarks/rubinato2017 [--check]

writes model.inp and the reference/ copies of every case; --check only
reports whether the committed files are what this script would write.
"""
from __future__ import annotations

import argparse
import csv
import math
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
COLLECTION = HERE.parent
NU, G = 1.0e-6, 9.81

STEADY = {"S1": "rubinato-2017-flume-steady-s1", "S2": "rubinato-2017-flume-steady-s2",
          "S3": "rubinato-2017-flume-steady-s3", "S4": "rubinato-2017-flume-steady-s4"}
LEGACY = "rubinato-2017-flume-steady-s1-legacy-orifice"
UNSTEADY = "rubinato-2017-flume-unsteady-synthetic"
STEADY_REFERENCE = ("table2_steady_exchange.csv", "table3_coefficients.csv", "rig_geometry.yaml")
UNSTEADY_REFERENCE = ("table1_unsteady_tests.csv", "rig_geometry.yaml")


def read_rig(path: Path) -> dict[str, float]:
    rig = {}
    for line in path.read_text().splitlines():
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        rig[key.strip()] = float(value.split("#")[0])
    return rig


def read_table2(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def case_from_row(row: dict[str, str], rig: dict[str, float]) -> dict:
    """Boundary conditions for one Table 2 row (SI: m, m3/s)."""
    scenario = row["scenario"]
    h_s = float(row["h_s_m"]) if row["h_s_m"] else 0.0
    h_p = float(row["h_p_m"]) if row["h_p_m"] else 0.0
    fr = float(row["fr_s"])
    q1 = fr * math.sqrt(G * h_s) * h_s * rig["flume_width_m"] if h_s > 0 else 0.0
    q3 = (0.0 if scenario == "S1" else
          abs(float(row["q_e_lps"]) / float(row["surcharge_pct"])) * 0.1)
    return {"scenario": scenario, "q_e_lps": float(row["q_e_lps"]),
            "xi_f_lps": float(row["xi_f_lps"]), "h_s": h_s, "h_p": h_p, "q1": q1, "q3": q3}


def axis(lo: float, hi: float, c: float, h0: float, hmax: float, g: float) -> list[float]:
    """Grid lines from lo to hi through c: spacing h0 at c growing by g to hmax."""
    def side(end: float, sign: float) -> list[float]:
        xs, x, h = [], c, h0
        while sign * (end - (x + sign * h)) > 0.5 * h:
            x += sign * h
            xs.append(x)
            h = min(hmax, h * g)
        xs.append(end)
        return xs
    return list(reversed(side(lo, -1.0))) + [c] + side(hi, 1.0)


def fmt(x: float) -> str:
    return f"{x:.10g}"


def flume(rig: dict[str, float], q1: float) -> tuple[str, str]:
    """[2D_VERTICES] ... [2D_BOUNDARY_CONDITIONS] of the flume, and the [2D_VERTEX_NODE_MAP]."""
    L, W = rig["flume_length_m"], rig["flume_width_m"]
    slope, n, zc = rig["flume_slope"], rig["flume_manning_n"], rig["z_crest_m"]
    xm, ym, h = 0.5 * L, 0.5 * W, rig["mesh_size_boundary_m"]
    xs, ys = axis(0.0, L, xm, h, h, 1.1), axis(0.0, W, ym, h, h, 1.1)
    nx = len(xs)
    vid = lambda i, j: j * nx + i  # noqa: E731
    centre = vid(xs.index(xm), ys.index(ym))
    out = ["[2D_VERTICES]", ";;X  Y  Z  (bed = crest at the manhole, slope "
           + fmt(slope) + ")"]
    out += [f"{fmt(x)} {fmt(y)} {fmt(zc + slope * (xm - x))}" for y in ys for x in xs]
    out += ["", "[2D_TRIANGLES]", ";;V1  V2  V3  MANNINGS_N"]
    bc, tri = [], 0
    for j in range(len(ys) - 1):
        for i in range(nx - 1):
            # A = (v00, v10, v11), B = (v00, v11, v01); edge k is opposite vertex k.
            out.append(f"{vid(i, j)} {vid(i + 1, j)} {vid(i + 1, j + 1)} {fmt(n)}")
            if i + 2 == nx:
                bc.append(f"{tri} 0 NORMAL_FLOW {fmt(slope)}")
            tri += 1
            out.append(f"{vid(i, j)} {vid(i + 1, j + 1)} {vid(i, j + 1)} {fmt(n)}")
            if i == 0 and q1 > 0:
                bc.append(f"{tri} 1 SPECIFIED_FLOW {fmt(-q1 / W)}")
            tri += 1
    out += ["", "[2D_BOUNDARY_CONDITIONS]", ";;TRI  EDGE  TYPE  PARAM_1"] + bc
    return "\n".join(out), f"[2D_VERTEX_NODE_MAP]\n;;VERTEX  NODE\n{centre}  MH"


def options_2d(law: str) -> str:
    return ("[2D_OPTIONS]\nMAX_TIMESTEP  1\nDRY_DEPTH  0.0002\nREPORT_2D  NO\n"
            f"COUPLING_LAW  {law}\nCOUPLING_HEAD  STENCIL_WET_MEAN\nCOUPLING_POND_MODE  CHAMBER\n\n"
            "[2D_NODE_COUPLING]\n;;Node  Type  KEY=VALUE\n"
            "MH  MANHOLE  D=0.24 COEFFS=RUBINATO2017 H_EPS=0.0033333\n")


def steady_deck(case: dict, rig: dict[str, float], law: str = "WEIR_ORIFICE", title: str = "") -> str:
    zc, d = rig["z_crest_m"], rig["pipe_diameter_m"]
    sewer = case["q3"] > 0
    lines = ["[TITLE]", title or f"Rubinato et al. (2017) flume, steady {case['scenario']}", "",
             "[OPTIONS]", "FLOW_UNITS  CMS", "FLOW_ROUTING  DYNWAVE",
             "START_DATE  01/01/2026", "START_TIME  00:00:00", "END_DATE  01/01/2026",
             "END_TIME  00:05:00", "REPORT_STEP  00:00:10", "ROUTING_STEP  0.5",
             "HEAD_TOLERANCE  0.00001", "",
             "[REPORT]", "NODES ALL", "LINKS ALL", "",
             "[JUNCTIONS]", ";;Name  Elev  MaxDepth  InitDepth  SurDepth  Aponded",
             f"MH  0  {fmt(zc)}  0  0  0", "", "[OUTFALLS]"]
    lines.append(f"OUT  0  FIXED  {fmt(case['h_p'])}  NO" if sewer else "OUT  0  FREE  NO")
    lines.append("")
    if sewer:
        # The inlet tank is a storage node so its volume is booked; a short
        # wide pipe lets the outfall's FIXED stage impose h_p at the manhole.
        lines += ["[STORAGE]", "IN  0  1.5  0  FUNCTIONAL  0  0  0.05  0  0", "",
                  "[CONDUITS]", "C1  IN  MH  2.0  0.010  0  0  0", "C2  MH  OUT  0.2  0.010  0  0  0", "",
                  "[XSECTIONS]", f"C1  CIRCULAR  {fmt(d)}  0  0  0  1", "C2  CIRCULAR  0.3  0  0  0  1", "",
                  "[INFLOWS]", f"IN  FLOW  \"\"  FLOW  1.0  1.0  {fmt(case['q3'])}", ""]
    else:
        lines += ["[CONDUITS]", "C2  MH  OUT  2.0  0.010  0  0  0", "",
                  "[XSECTIONS]", f"C2  CIRCULAR  {fmt(d)}  0  0  0  1", ""]
    mesh, nodemap = flume(rig, case["q1"])
    coordinates = "\n[COORDINATES]\nMH 4 2\nOUT 6 2\n" + ("IN 2 2\n" if sewer else "")
    return "\n".join(lines) + "\n" + options_2d(law) + "\n" + mesh + "\n\n" + nodemap + "\n" + coordinates


def unsteady_deck(rig: dict[str, float], ratio: float = 1.26, duration_s: float = 341.0) -> str:
    """Synthetic surcharge event (Table 1 T9's peak ratio and duration).

    Not a reproduction of a measured test: the article's imposed sewer head
    (Fig. 5) and measured series are not tabulated. Q1 = 8.15 l/s constant;
    sewer inflow 0.25 Q1, ramped over 30 s to ratio x Q1, held duration_s,
    ramped back; the pipe drains to a fixed 0.45 m stage, so the manhole drains
    the surface, surcharges and spills, then drains again.
    """
    zc, d = rig["z_crest_m"], rig["pipe_diameter_m"]
    q1 = rig["surface_inflow_unsteady_lps"] / 1000.0
    base, peak = 0.25 * q1, ratio * q1
    t0 = 60.0
    pts = [(0.0, base), (t0, base), (t0 + 30, peak), (t0 + 30 + duration_s, peak),
           (t0 + 60 + duration_s, base), (900.0, base)]
    # SWMM interprets two fields as hours:minutes, not minutes:seconds.
    ts = [f"Q3  {int(t) // 3600:02d}:{int(t) // 60 % 60:02d}:{int(t) % 60:02d}  {fmt(q)}" for t, q in pts]
    lines = ["[TITLE]", f"Rubinato et al. (2017) flume, synthetic surcharge event "
             f"(Q3max/Q1 {ratio:g}, {duration_s:g} s)", "",
             "[OPTIONS]", "FLOW_UNITS  CMS", "FLOW_ROUTING  DYNWAVE",
             "START_DATE  01/01/2026", "START_TIME  00:00:00", "END_DATE  01/01/2026",
             "END_TIME  00:10:00", "REPORT_STEP  00:00:10", "ROUTING_STEP  0.5", "HEAD_TOLERANCE  0.00001",
             f"MIN_SURFAREA  {fmt(math.pi*rig['manhole_diameter_m']**2/4)}", "",
             "[REPORT]", "NODES ALL", "LINKS ALL", "",
             "[STORAGE]", f"MH  0  {fmt(zc)}  0  FUNCTIONAL  0  0  {fmt(math.pi*rig['manhole_diameter_m']**2/4)}  0  0",
             "", "[OUTFALLS]", "OUT  0  FIXED  0.45  NO", "",
             "[STORAGE]", "IN  0  1.5  0  FUNCTIONAL  0  0  0.05  0  0", "",
             "[CONDUITS]", "C1  IN  MH  2.0  0.010  0  0  0", "C2  MH  OUT  2.0  0.010  0  0  0", "",
             "[XSECTIONS]", f"C1  CIRCULAR  {fmt(d)}  0  0  0  1", f"C2  CIRCULAR  {fmt(d)}  0  0  0  1", "",
             "[TIMESERIES]", ";;Name  Time  Value (m3/s)"] + ts + ["",
             "[INFLOWS]", "IN  FLOW  Q3  FLOW  1.0  1.0", ""]
    mesh, nodemap = flume(rig, q1)
    return ("\n".join(lines) + "\n" + options_2d("WEIR_ORIFICE") + "\n" + mesh + "\n\n" + nodemap
            + "\n\n[COORDINATES]\nMH 4 2\nIN 2 2\nOUT 6 2\n")


def planned(engine_ref: Path) -> dict[Path, bytes]:
    """Every file this script owns, with its content."""
    rig = read_rig(engine_ref / "rig_geometry.yaml")
    rows = read_table2(engine_ref / "table2_steady_exchange.csv")
    files: dict[Path, bytes] = {}
    first = {}
    for row in rows:
        first.setdefault(row["scenario"], row)
    for scenario, case_id in STEADY.items():
        case = case_from_row(first[scenario], rig)
        files[COLLECTION / case_id / "model.inp"] = steady_deck(
            case, rig, title=f"Rubinato et al. (2017) flume, steady {scenario}, Table 2 row 1").encode()
        for name in STEADY_REFERENCE:
            files[COLLECTION / case_id / "reference" / name] = (engine_ref / name).read_bytes()
    case = case_from_row(first["S1"], rig)
    files[COLLECTION / LEGACY / "model.inp"] = steady_deck(
        case, rig, law="ORIFICE",
        title="Rubinato et al. (2017) flume, steady S1, Table 2 row 1, legacy ORIFICE law").encode()
    files[COLLECTION / UNSTEADY / "model.inp"] = unsteady_deck(rig).encode()
    for name in UNSTEADY_REFERENCE:
        files[COLLECTION / UNSTEADY / "reference" / name] = (engine_ref / name).read_bytes()
    return files


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--engine-ref", type=Path, required=True,
                    help="openswmm.engine/tests/benchmarks/rubinato2017")
    ap.add_argument("--check", action="store_true", help="report drift; write nothing")
    args = ap.parse_args(argv)
    drift = 0
    for path, content in planned(args.engine_ref.resolve()).items():
        if path.exists() and path.read_bytes() == content:
            continue
        drift += 1
        if args.check:
            print(f"differs: {path.relative_to(COLLECTION)}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        print(f"wrote {path.relative_to(COLLECTION)}")
    return 1 if (args.check and drift) else 0


if __name__ == "__main__":
    sys.exit(main())
