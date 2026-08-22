#!/usr/bin/env python3
"""Synthetic SWMM ``.out`` writer — test fixture, not production code.

Writes a byte-valid binary output file with a configurable number of
subcatchments, nodes, links, and pollutants, and a configurable system-variable
count so both output dialects (swmm52 = 14, swmm53 = 15) can be exercised.

Why this exists: the harness must grade engines it cannot run, and CI must
verify the readers without building any engine. A synthetic writer lets the
reader/compare layer be tested for pollutant, subcatchment, and system-variable
coverage on machines with no SWMM binary at all — which is exactly the
coverage that was missing (plan Appendix A, gap 2).

Values are a deterministic function of (kind, element, variable, period) so a
round-trip assertion is exact:

    value = KIND_BASE[kind] + 100*element + 10*variable + 0.5*period

stored as float32, which is what the format holds.
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

MAGIC = 516114522

KIND_BASE = {"sub": 1000.0, "node": 2000.0, "link": 3000.0, "sys": 4000.0}


def expected(kind: str, element_index: int, var: int, period: int) -> float:
    """The value the writer stores — as a float, after float32 rounding."""
    v = KIND_BASE[kind] + 100.0 * element_index + 10.0 * var + 0.5 * period
    return float(np.float32(v))


def write_out(path: str | Path, *, n_sub: int = 2, n_node: int = 3,
              n_link: int = 2, pollutants: list[str] | None = None,
              n_periods: int = 4, sys_vars: int = 15,
              version: int = 60000, flow_units: int = 0,
              perturb: dict | None = None) -> Path:
    """Write a synthetic .out file.

    perturb: optional {(kind, element_index, var, period): value} overriding
    individual cells, used to plant a known difference between two files.
    """
    path = Path(path)
    pollutants = list(pollutants or [])
    n_pollut = len(pollutants)
    perturb = perturb or {}

    sub_vars = 8 + n_pollut
    node_vars = 6 + n_pollut
    link_vars = 5 + n_pollut

    sub_ids = [f"S{i + 1}" for i in range(n_sub)]
    node_ids = [f"N{i + 1}" for i in range(n_node)]
    link_ids = [f"L{i + 1}" for i in range(n_link)]

    buf = bytearray()

    def i4(*vals):
        for v in vals:
            buf.extend(struct.pack("<i", int(v)))

    def f4(*vals):
        for v in vals:
            buf.extend(struct.pack("<f", float(v)))

    def r8(v):
        buf.extend(struct.pack("<d", float(v)))

    def ids(names):
        for name in names:
            raw = name.encode("ascii")
            i4(len(raw))
            buf.extend(raw)

    # ── opening records ────────────────────────────────────────────────
    i4(MAGIC, version, flow_units, n_sub, n_node, n_link, n_pollut)

    # ── object IDs ─────────────────────────────────────────────────────
    id_pos = len(buf)
    ids(sub_ids)
    ids(node_ids)
    ids(link_ids)
    ids(pollutants)
    i4(*([0] * n_pollut))                       # pollutant concentration units

    # ── object properties ──────────────────────────────────────────────
    prop_pos = len(buf)
    i4(1, 1)                                     # subcatchment: 1 property (area)
    f4(*[1.0 + i for i in range(n_sub)])
    i4(3, 0, 1, 2)                               # node: type, invert, max depth
    for i in range(n_node):
        f4(0.0, float(i), 10.0)
    i4(5, 0, 4, 4, 3, 5)                         # link: type, offsets, length, ...
    for i in range(n_link):
        f4(1.0, 0.0, 0.0, 100.0, 1.0)

    # variable-code tables (counts + codes), report start, report step
    i4(sub_vars, *range(sub_vars))
    i4(node_vars, *range(node_vars))
    i4(link_vars, *range(link_vars))
    i4(sys_vars, *range(sys_vars))
    r8(45000.0)                                  # report start (SWMM datetime)
    i4(3600)                                     # report step, seconds

    # ── computed results ───────────────────────────────────────────────
    result_pos = len(buf)
    for p in range(n_periods):
        r8(45000.0 + p / 24.0)
        for kind, count, nvars in (("sub", n_sub, sub_vars),
                                   ("node", n_node, node_vars),
                                   ("link", n_link, link_vars)):
            for e in range(count):
                for v in range(nvars):
                    key = (kind, e, v, p)
                    f4(perturb.get(key, expected(kind, e, v, p)))
        for v in range(sys_vars):
            key = ("sys", 0, v, p)
            f4(perturb.get(key, expected("sys", 0, v, p)))

    # ── closing records ────────────────────────────────────────────────
    i4(id_pos, prop_pos, result_pos, n_periods, 0, MAGIC)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(bytes(buf))
    return path
