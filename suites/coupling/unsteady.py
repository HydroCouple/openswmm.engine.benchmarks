"""Run one synthetic exchange event through the C API in an isolated process.

This is a stability demonstration. No measured hydrograph is inferred from
Table 1's peak ratios and durations. SI input only.
"""
from __future__ import annotations

import ctypes as ct
import csv
import json
import math
import sys
from pathlib import Path


def simulate(library: Path, inp: Path, output: Path, minimum_duration_s: float = 599.0,
             save_output: bool = False) -> dict:
    lib = ct.CDLL(str(library))
    ptr, dbl, integer = ct.c_void_p, ct.c_double, ct.c_int
    signatures = {
        "swmm_engine_create": ([], ptr),
        "swmm_engine_destroy": ([ptr], None),
        "swmm_engine_open": ([ptr, ct.c_char_p, ct.c_char_p, ct.c_char_p, ptr], integer),
        "swmm_engine_initialize": ([ptr], integer),
        "swmm_engine_start": ([ptr, integer], integer),
        "swmm_engine_step": ([ptr, ct.POINTER(dbl)], integer),
        "swmm_engine_end": ([ptr], integer),
        "swmm_engine_report": ([ptr], integer),
        "swmm_engine_close": ([ptr], integer),
        "swmm_2d_triangle_count": ([ptr, ct.POINTER(integer)], integer),
        "swmm_2d_get_coupling_volume_bulk": ([ptr, ct.POINTER(dbl)], integer),
        "swmm_2d_get_depths_bulk": ([ptr, ct.POINTER(dbl)], integer),
        "swmm_get_routing_continuity_error": ([ptr, ct.POINTER(dbl)], integer),
    }
    for name, (args, result) in signatures.items():
        func = getattr(lib, name)
        func.argtypes, func.restype = args, result
    engine = lib.swmm_engine_create()
    if not engine:
        raise RuntimeError("engine allocation failed")

    def call(name, *args):
        code = getattr(lib, name)(engine, *args)
        if code != 0:
            raise RuntimeError(f"{name} returned {code}")

    try:
        call("swmm_engine_open", str(inp).encode(), str(inp.with_suffix('.rpt')).encode(),
             str(inp.with_suffix('.out')).encode() if save_output else b"", None)
        call("swmm_engine_initialize")
        call("swmm_engine_start", int(save_output))
        count = integer()
        call("swmm_2d_triangle_count", ct.byref(count))
        volumes, depths = (dbl * count.value)(), (dbl * count.value)()
        elapsed = dbl()
        previous_t = previous_v = spill = drain = 0.0
        last_sign = reversals = 0
        minimum_depth, maximum_depth = math.inf, 0.0
        with output.with_suffix('.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['time_s', 'net_to_surface_m3', 'q_to_surface_lps'])
            while True:
                call("swmm_engine_step", ct.byref(elapsed))
                if elapsed.value == 0:
                    break
                t = elapsed.value * 86400
                call("swmm_2d_get_coupling_volume_bulk", volumes)
                call("swmm_2d_get_depths_bulk", depths)
                v = sum(volumes)
                delta = v - previous_v
                q = 1000 * delta / (t - previous_t)
                if not all(math.isfinite(x) for x in (v, q, *depths)):
                    raise RuntimeError("non-finite hydraulic state")
                sign = 1 if q > 1e-5 else -1 if q < -1e-5 else 0
                if sign and last_sign and sign != last_sign:
                    reversals += 1
                if sign:
                    last_sign = sign
                spill += max(delta, 0)
                drain += max(-delta, 0)
                minimum_depth = min(minimum_depth, min(depths))
                maximum_depth = max(maximum_depth, max(depths))
                writer.writerow([t, v, q])
                previous_t, previous_v = t, v
        if previous_t < minimum_duration_s:
            raise RuntimeError(f"early completion at {previous_t}s")
        call("swmm_engine_end")
        continuity = dbl()
        call("swmm_get_routing_continuity_error", ct.byref(continuity))
        call("swmm_engine_report")
        call("swmm_engine_close")
        result = dict(duration_s=previous_t, spill_m3=spill, drain_m3=drain,
                      net_to_surface_m3=previous_v, reversals=reversals,
                      min_depth_m=minimum_depth, max_depth_m=maximum_depth,
                      continuity_pct=100 * continuity.value)
        output.write_text(json.dumps(result, indent=2, allow_nan=False))
        return result
    finally:
        lib.swmm_engine_destroy(engine)


if __name__ == '__main__':
    simulate(*(Path(p).resolve() for p in sys.argv[1:4]),
             *([float(sys.argv[4])] if len(sys.argv) > 4 else []))
