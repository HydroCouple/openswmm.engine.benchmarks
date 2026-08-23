#!/usr/bin/env python3
"""Result-file readers shared by all benchmark suites.

`Out` — standalone reader for the EPA SWMM5 binary output (.out) file.
`Surface2DOutput` — thin reader for the engine's 2D UGRID HDF5 output
(requires h5py; imported lazily).

Promoted from epaswmm5_qa/core/readers.py, extended here with subcatchment,
system, and pollutant series accessors plus the output-dialect adapter
(see plans/BENCHMARK_PLATFORM_PLAN_2026-08-22.md, Appendix A gaps 1–3).

Self-contained — depends only on the Python stdlib + numpy, NOT on the
(fragile, churn-prone) openswmm.engine binding. Both the legacy EPA SWMM 5.3
engine and the refactored openswmm 6.0 engine write this identical, version-
stable format; the only header difference is the version integer (legacy
53000 vs refactored 60000), so parity is judged on the RESULTS section, never
the raw bytes.

Layout (all little-endian; INT4='<i', REAL4='<f', REAL8='<d'):
  opening : magic, version, flow_units, n_sub, n_node, n_link, n_pollut  (7 INT4)
  IDs     : for sub, node, link, pollut -> INT4 len + len chars   (starts @ byte 28)
  ...     : pollutant units, object properties, variable lists, start date, step
  results : per period -> REAL8 datetime + REAL4 values
  closing : id_pos, prop_pos, result_pos, n_periods, err_code, magic  (6 INT4)

The standard saved-variable blocks (the first indices are all we compare):
  node vars : 0 DEPTH, 1 HEAD, 2 VOLUME, 3 LATFLOW, 4 INFLOW, 5 FLOODING, +pollut
  link vars : 0 FLOW, 1 DEPTH, 2 VELOCITY, 3 VOLUME, 4 CAPACITY, +pollut
  sub vars  : 8 standard + pollut ; sys vars : 15 (derived, not assumed)
"""
from __future__ import annotations

import struct
from pathlib import Path

import numpy as np

MAGIC = 516114522

# node result variable indices
NODE_DEPTH, NODE_HEAD, NODE_VOLUME, NODE_LATFLOW, NODE_INFLOW, NODE_FLOODING = range(6)
# link result variable indices
LINK_FLOW, LINK_DEPTH, LINK_VELOCITY, LINK_VOLUME, LINK_CAPACITY = range(5)

FLOW_UNITS = {0: "CFS", 1: "GPM", 2: "MGD", 3: "CMS", 4: "LPS", 5: "MLD"}

# subcatchment result variable indices
(SUB_RAINFALL, SUB_SNOWDEPTH, SUB_EVAP, SUB_INFIL, SUB_RUNOFF, SUB_GWFLOW,
 SUB_GWELEV, SUB_SOILMOIST) = range(8)

# Named standard variables per element type, in storage order. Pollutant
# variables follow these and are named from the file's own pollutant IDs.
SUB_VAR_NAMES = ["RAINFALL", "SNOW_DEPTH", "EVAP_LOSS", "INFIL_LOSS",
                 "RUNOFF", "GW_FLOW", "GW_ELEV", "SOIL_MOIST"]
NODE_VAR_NAMES = ["DEPTH", "HEAD", "VOLUME", "LATFLOW", "INFLOW", "FLOODING"]
LINK_VAR_NAMES = ["FLOW", "DEPTH", "VELOCITY", "VOLUME", "CAPACITY"]

# ── output dialects ────────────────────────────────────────────────────────
# System variables are the one block whose LAYOUT changed across SWMM
# versions: 5.2 and earlier write 14; 5.3 inserted SYS_PET for 15. Comparisons
# between dialects run over the intersection of the named variables, matched by
# NAME rather than index (see harness.compare.common_sys_vars).
SYS_VARS_52 = ["TEMPERATURE", "RAINFALL", "SNOW_DEPTH", "INFIL_LOSS",
               "RUNOFF_FLOW", "DW_INFLOW", "GW_INFLOW", "RDII_INFLOW",
               "DIRECT_INFLOW", "TOTAL_LATFLOW", "FLOOD_LOSSES",
               "OUTFALL_FLOWS", "STORAGE_VOLUME", "EVAP_RATE"]
SYS_VARS_53 = SYS_VARS_52 + ["PET_RATE"]

SYS_VARS_BY_DIALECT = {"swmm52": SYS_VARS_52, "swmm53": SYS_VARS_53}
SYS_VAR_COUNT_TO_DIALECT = {14: "swmm52", 15: "swmm53"}


class Out:
    """Random-access reader for a SWMM .out file."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._b = self.path.read_bytes()
        if len(self._b) < 7 * 4 + 6 * 4:
            raise ValueError(f"{self.path}: too small to be a .out file")

        (self.magic, self.version, fu, self.n_sub, self.n_node,
         self.n_link, self.n_pollut) = struct.unpack("<7i", self._b[:28])
        (self.id_pos, self.prop_pos, self.result_pos, self.n_periods,
         self.err_code, magic2) = struct.unpack("<6i", self._b[-24:])
        if self.magic != MAGIC or magic2 != MAGIC:
            raise ValueError(f"{self.path}: bad magic ({self.magic}, {magic2})")
        self.flow_units = FLOW_UNITS.get(fu, str(fu))

        # standard saved-variable counts (format invariants: standard set + one
        # extra per pollutant).
        self.sub_vars = 8 + self.n_pollut
        self.node_vars = 6 + self.n_pollut
        self.link_vars = 5 + self.n_pollut

        self._read_ids()

        # per-period record geometry
        floats_per_period = (self.n_sub * self.sub_vars
                             + self.n_node * self.node_vars
                             + self.n_link * self.link_vars)
        # sys vars are whatever remains; derived, not assumed
        results_end = len(self._b) - 24
        self.bytes_per_period = ((results_end - self.result_pos) // self.n_periods
                                 if self.n_periods else 0)
        rem_floats = (self.bytes_per_period - 8) // 4 - floats_per_period
        self.sys_vars = max(rem_floats, 0)

        # byte offset (within a period record, after the 8-byte datetime) of
        # each element block
        self._sub_off = 0
        self._node_off = self.n_sub * self.sub_vars * 4
        self._link_off = self._node_off + self.n_node * self.node_vars * 4
        self._sys_off = self._link_off + self.n_link * self.link_vars * 4
        self._sub_ix = {i: k for k, i in enumerate(self.subcatch_ids)}

    # ── dialect ──────────────────────────────────────────────────────────
    @property
    def dialect(self) -> str:
        """Output dialect id, derived from the system-variable count.

        SWMM 5.2 and earlier write 14 system variables; 5.3 added SYS_PET for
        15. The engine version integer is NOT used (it differs 53000 vs 60000
        for engines that write an identical layout).
        """
        return SYS_VAR_COUNT_TO_DIALECT.get(self.sys_vars, f"unknown{self.sys_vars}")

    def sys_var_names(self) -> list[str]:
        """System-variable names for this file's dialect, in storage order."""
        return list(SYS_VARS_BY_DIALECT.get(self.dialect, [])) or [
            f"SYS_{i}" for i in range(self.sys_vars)]

    # ── ids ──────────────────────────────────────────────────────────────
    def _read_ids(self):
        pos = self.id_pos
        b = self._b

        def take(n):
            nonlocal pos
            ids = []
            for _ in range(n):
                (ln,) = struct.unpack_from("<i", b, pos)
                pos += 4
                ids.append(b[pos:pos + ln].decode("ascii", "replace"))
                pos += ln
            return ids

        self.subcatch_ids = take(self.n_sub)
        self.node_ids = take(self.n_node)
        self.link_ids = take(self.n_link)
        self.pollut_ids = take(self.n_pollut)
        self._node_ix = {i: k for k, i in enumerate(self.node_ids)}
        self._link_ix = {i: k for k, i in enumerate(self.link_ids)}

    # ── series ───────────────────────────────────────────────────────────
    def datetimes(self) -> np.ndarray:
        """SWMM datetime (days since 1899-12-30) at each reporting period."""
        n, bpp = self.n_periods, self.bytes_per_period
        if n <= 0:
            return np.empty(0, dtype=np.float64)
        u8 = np.frombuffer(self._b, dtype=np.uint8)
        take = (self.result_pos + np.arange(n, dtype=np.int64) * bpp)[:, None] \
            + np.arange(8, dtype=np.int64)
        return u8[take].reshape(-1).view("<f8").astype(np.float64)

    def _strided(self, off0: int) -> np.ndarray:
        """One float32 per period, read at `off0` + k * bytes_per_period.

        The .out layout interleaves every element's variables inside a period
        record, so one element-variable series is a strided gather, not a
        contiguous slice. Doing that with `struct.unpack_from` in a Python loop
        costs one interpreter round-trip per period per variable per element:
        a full-corpus sweep compares ~22 billion cells, and at ~270k cells/s
        that is a day of pure comparison — longer than the nightly window and
        far longer than a CI job may run. Gathering the bytes with numpy and
        viewing them as float32 is the same arithmetic, vectorised.
        """
        n, bpp = self.n_periods, self.bytes_per_period
        if n <= 0:
            return np.empty(0, dtype=np.float64)
        last = off0 + (n - 1) * bpp + 4
        if last > len(self._b):
            raise ValueError(
                f"{self.path}: result block ends at {last} but the file is "
                f"{len(self._b)} bytes — truncated or mis-declared header")
        u8 = np.frombuffer(self._b, dtype=np.uint8)
        # (n, 4) byte offsets -> gather -> reinterpret as little-endian float32
        take = (off0 + np.arange(n, dtype=np.int64) * bpp)[:, None] \
            + np.arange(4, dtype=np.int64)
        return u8[take].reshape(-1).view("<f4").astype(np.float64)

    def _series(self, base_off: int, idx: int, var: int, nvars: int) -> np.ndarray:
        return self._strided(
            self.result_pos + 8 + base_off + (idx * nvars + var) * 4)

    def node_series(self, node_id: str, var: int) -> np.ndarray:
        return self._series(self._node_off, self._node_ix[node_id], var,
                            self.node_vars)

    def link_series(self, link_id: str, var: int) -> np.ndarray:
        return self._series(self._link_off, self._link_ix[link_id], var,
                            self.link_vars)

    def subcatch_series(self, sub_id: str, var: int) -> np.ndarray:
        return self._series(self._sub_off, self._sub_ix[sub_id], var,
                            self.sub_vars)

    def sys_series(self, var: int) -> np.ndarray:
        """System-level result series by storage index (see sys_var_names())."""
        if not 0 <= var < self.sys_vars:
            raise IndexError(f"system var {var} out of range (0..{self.sys_vars - 1})")
        return self._strided(self.result_pos + 8 + self._sys_off + var * 4)

    # ── generic accessors (element kind as a string) ──────────────────────
    def ids(self, kind: str) -> list[str]:
        return {"sub": self.subcatch_ids, "node": self.node_ids,
                "link": self.link_ids, "sys": ["SYSTEM"]}[kind]

    def series(self, kind: str, eid: str, var: int) -> np.ndarray:
        if kind == "sys":
            return self.sys_series(var)
        return {"sub": self.subcatch_series, "node": self.node_series,
                "link": self.link_series}[kind](eid, var)

    def var_names(self, kind: str) -> list[str]:
        """All variable names for an element kind, standard + per-pollutant.

        Pollutant variables are named ``POLL:<id>`` from this file's own
        pollutant list, so quality comparison does not depend on index order
        matching between two files (see compare.common_vars).
        """
        if kind == "sys":
            return self.sys_var_names()
        std = {"sub": SUB_VAR_NAMES, "node": NODE_VAR_NAMES,
               "link": LINK_VAR_NAMES}[kind]
        return list(std) + [f"POLL:{p}" for p in self.pollut_ids]

    # ── raw section access (for byte-level parity) ─────────────────────────
    def results_bytes(self) -> bytes:
        """The raw computed-results section (datetimes + values, all periods)."""
        return self._b[self.result_pos:self.result_pos + self.n_periods * self.bytes_per_period]

    def body_after_version(self) -> bytes:
        """Everything except the 4-byte version field (which legitimately
        differs 53000 vs 60000). Equality here == true bit parity."""
        return self._b[8:]


class Surface2DOutput:
    """Reader for the engine's 2D CF/UGRID HDF5 output ([2D_OPTIONS] OUTPUT_FILE).

    Datasets (see Default2DOutputPlugin.hpp): static /Mesh2_face_{x,y,z};
    time-varying [nTime, nFace] /Mesh2_face_depth|_head|_vx|_vy; /time;
    /mass_balance_2d group with m3 terms + @continuity_error.
    """

    def __init__(self, path: str | Path):
        import h5py  # lazy: only 2D suites need it
        self.path = Path(path)
        self._f = h5py.File(self.path, "r")

    def close(self):
        self._f.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    @property
    def times(self) -> np.ndarray:
        return np.asarray(self._f["time"])

    @property
    def face_x(self) -> np.ndarray:
        return np.asarray(self._f["Mesh2_face_x"])

    @property
    def face_y(self) -> np.ndarray:
        return np.asarray(self._f["Mesh2_face_y"])

    @property
    def face_z(self) -> np.ndarray:
        return np.asarray(self._f["Mesh2_face_z"])

    def face_series(self, name: str) -> np.ndarray:
        """Full [nTime, nFace] dataset, e.g. 'depth', 'head', 'vx', 'vy'."""
        return np.asarray(self._f[f"Mesh2_face_{name}"])

    def face_at(self, name: str, time_index: int) -> np.ndarray:
        return np.asarray(self._f[f"Mesh2_face_{name}"][time_index])

    def mass_balance(self) -> dict[str, float]:
        out: dict[str, float] = {}
        grp = self._f.get("mass_balance_2d")
        if grp is None:
            return out
        for k, v in grp.attrs.items():
            try:
                out[k] = float(v)
            except (TypeError, ValueError):
                pass
        for k in grp:
            arr = np.asarray(grp[k])
            if arr.size == 1:
                out[k] = float(arr)
        return out


if __name__ == "__main__":
    from . import use_utf8_stdio
    use_utf8_stdio()
    import sys
    o = Out(sys.argv[1])
    print(f"{o.path.name}: v{o.version} units={o.flow_units} "
          f"sub={o.n_sub} node={o.n_node} link={o.n_link} pol={o.n_pollut} "
          f"periods={o.n_periods} bpp={o.bytes_per_period} "
          f"sub/node/link/sys vars={o.sub_vars}/{o.node_vars}/{o.link_vars}/{o.sys_vars}")
    if o.n_link:
        s = o.link_series(o.link_ids[0], LINK_FLOW)
        print(f"  link[0]={o.link_ids[0]} FLOW: min={s.min():.5g} max={s.max():.5g}")
    if o.n_node:
        s = o.node_series(o.node_ids[0], NODE_DEPTH)
        print(f"  node[0]={o.node_ids[0]} DEPTH: min={s.min():.5g} max={s.max():.5g}")
