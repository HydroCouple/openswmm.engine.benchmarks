#!/usr/bin/env python3
"""Pull node-head / link-flow / link-depth series out of a model.out via
harness.readers.Out, plus the pressurization-front position series."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import config  # noqa: F401  (repo-root bootstrap)
from .cases import Case, link_id, node_id

from harness.readers import LINK_DEPTH, LINK_FLOW, NODE_HEAD, Out


def read_run(out_path: Path, case: Case) -> dict:
    """{t, heads[n_nodes,T], flows[n_links,T], depths[n_links,T]} — heads are
    absolute elevations (SWMM .out HEAD), t in seconds from sim start."""
    o = Out(out_path)
    d = o.datetimes()
    t = np.round((d - d[0]) * 86400.0) + case.report_step
    n_nodes = len(case.node_x())
    heads = np.empty((n_nodes, o.n_periods))
    for i in range(n_nodes):
        heads[i] = o.node_series(node_id(i), NODE_HEAD)
    nc = case.n_conduits
    flows = np.empty((nc, o.n_periods))
    depths = np.empty((nc, o.n_periods))
    for i in range(nc):
        flows[i] = o.link_series(link_id(i), LINK_FLOW)
        depths[i] = o.link_series(link_id(i), LINK_DEPTH)
    return {"t": t, "heads": heads, "flows": flows, "depths": depths}


def heads_at(res: dict, t: float) -> np.ndarray:
    """Node heads at the report step nearest t."""
    k = int(np.argmin(np.abs(res["t"] - t)))
    return res["heads"][:, k]


def mean_heads(res: dict, window_s: float) -> np.ndarray:
    """Time-mean node heads over the final window (steady grading)."""
    mask = res["t"] >= (res["t"][-1] - window_s)
    return res["heads"][:, mask].mean(axis=1)


def front_series(res: dict, case: Case, frac: float = 0.95) -> np.ndarray:
    """Pressurization-front chainage per report step: downstream end of the
    contiguous run of full links (depth >= frac*D) starting at link 0."""
    x = case.node_x()
    diam = np.array([c["diam"] for c in case.conduits()])
    full = res["depths"] >= frac * diam[:, None]          # [n_links, T]
    out = np.zeros(res["t"].shape)
    for k in range(full.shape[1]):
        col = full[:, k]
        n = 0
        while n < len(col) and col[n]:
            n += 1
        out[k] = x[n]                                     # 0 if link 0 not full
    return out


def arrival_time(t: np.ndarray, xf: np.ndarray, station: float) -> float:
    """First time the front reaches `station` (nan if it never does)."""
    idx = np.nonzero(xf >= station)[0]
    return float(t[idx[0]]) if idx.size else float("nan")


def write_extracted_csv(path: Path, res: dict, case: Case) -> None:
    """Node heads per report step (long-form, reviewable)."""
    x = case.node_x()
    with open(path, "w") as f:
        f.write("t_s," + ",".join(f"h_x{xi:g}" for xi in x) + "\n")
        for k, tk in enumerate(res["t"]):
            f.write(f"{tk:g}," +
                    ",".join(f"{v:.5f}" for v in res["heads"][:, k]) + "\n")
