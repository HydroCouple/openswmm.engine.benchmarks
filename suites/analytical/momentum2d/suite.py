"""Independent analytical and conservation checks for optional 2D momentum physics."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import h5py
import numpy as np
from harness import engines, runner, scoring
from suites.uk_2d.suite import binary_manifest

ROOT = Path(__file__).resolve().parents[3]
SUITE = "analytical/momentum2d"


def deck(kind: str, order: int, parameter: float, n: int = 6) -> str:
    """Flat triangular domain; stage boundaries for uniform inertial oscillation.

    Closed walls are used for the lake and shear-decay conservation cases.
    All indices and triangular edge numbers follow the engine's opposite-vertex rule.
    """
    lines = ["[TITLE]", f"Optional momentum verification: {kind}", "[OPTIONS]",
             "FLOW_UNITS CMS", "FLOW_ROUTING DYNWAVE", "INFILTRATION HORTON",
             "START_DATE 01/01/2026", "START_TIME 00:00:00",
             "END_DATE 01/01/2026", "END_TIME 00:00:20", "REPORT_STEP 00:00:01",
             "REPORT_START_DATE 01/01/2026", "REPORT_START_TIME 00:00:00",
             "ROUTING_STEP 1", "IGNORE_RAINFALL YES", "IGNORE_SNOWMELT YES",
             "IGNORE_GROUNDWATER YES", "IGNORE_QUALITY YES", "[2D_OPTIONS]",
             "MOMENTUM_EQUATION FULL_SWE", f"RECONSTRUCTION_ORDER {order}",
             "LTS_TIERS 1", "BACKEND CPU", "CFL_NUMBER 0.4", "MAX_TIMESTEP 0.25",
             "H_MOVE 0.0001", "DRY_DEPTH 0.00001", "RAINFALL_MODE NONE",
             "OUTPUT_FILE surface.h5", "OUTPUT_PRECISION FLOAT64", "OUTPUT_COMPRESSION 1",
             "REPORT_2D_VARIABLES DEPTH VELOCITY TURBULENCE"]
    if kind == "wall":
        # One quad across the channel width gives spatially uniform plug flow.
        # Both side walls have Cw=.02. Open ends copy uniform depth/velocity;
        # normal fluxes cancel, leaving du/dt=-(2*Cw/B)*|u|u, B=1 m.
        lines += ["CORIOLIS OFF", "TURBULENCE_MODEL SMAGORINSKY", "SMAGORINSKY_CS 0",
                  "[2D_VERTICES]"]
        vertices = [(2*x,y) for x in range(5) for y in (0,1)]
        lines += [f"{x} {y} 0" for x,y in vertices]
        lines += ["[2D_QUADS]"] + [f"{2*i} {2*i+2} {2*i+3} {2*i+1} 1e-12 .5" for i in range(4)]
        lines += ["[2D_INITIAL_VELOCITY]"] + [f"{i} {parameter:.17g} 0" for i in range(4)]
        lines += ["[2D_BOUNDARY_CONDITIONS]", "0 2 SPECIFIED_STAGE .5", "3 0 SPECIFIED_STAGE .5"]
        for i in range(4):
            lines += [f"{i} 1 WALL_DRAG .02 * TOP", f"{i} 3 WALL_DRAG .02 * BOTTOM"]
        return "\n".join(lines)+"\n"
    if kind == "inertial":
        lines += ["CORIOLIS CONSTANT_F", f"CORIOLIS_F {parameter:.17g}",
                  "TURBULENCE_MODEL NONE"]
    else:
        lines += ["CORIOLIS OFF", "TURBULENCE_MODEL SMAGORINSKY",
                  f"SMAGORINSKY_CS {parameter:.17g}"]
    vertices = [(100*x/n, 100*y/n) for y in range(n+1) for x in range(n+1)]
    cells = []
    for y in range(n):
        for x in range(n):
            a = y*(n+1)+x
            cells += [(a,a+1,a+n+2), (a,a+n+2,a+n+1)]
    lines += ["[2D_VERTICES]"] + [f"{x:.17g} {y:.17g} 0" for x,y in vertices]
    lines += ["[2D_TRIANGLES]"] + [f"{a} {b} {c} 1e-12 0.5" for a,b,c in cells]
    lines += ["[2D_INITIAL_VELOCITY]"]
    for i, ids in enumerate(cells):
        y = sum(vertices[j][1] for j in ids)/3
        u, v = (.2,.3) if kind == "inertial" else ((.2*np.sin(np.pi*y/100),0) if kind == "shear" else (0,0))
        lines.append(f"{i} {u:.17g} {v:.17g}")
    owners = {}
    for i,ids in enumerate(cells):
        for k in range(3):
            pair = tuple(sorted((ids[(k+1)%3],ids[(k+2)%3])))
            owners.setdefault(pair, []).append((i,k))
    lines += ["[2D_BOUNDARY_CONDITIONS]"]
    for sides in owners.values():
        if len(sides) == 1:
            i,k = sides[0]
            lines.append(f"{i} {k} " + ("SPECIFIED_STAGE 0.5" if kind == "inertial" else "WALL"))
    return "\n".join(lines)+"\n"


def assess(path: Path, kind: str, parameter: float) -> dict:
    with h5py.File(path, "r") as data:
        h = data["Mesh2_face_depth"][:]
        u, v = data["Mesh2_face_vx"][:], data["Mesh2_face_vy"][:]
        t = data["time"][:]
        t = (t-np.floor(t[0]))*86400
        checks = {"finite": bool(np.isfinite(h).all() and np.isfinite(u).all() and np.isfinite(v).all()),
                  "positive_depth": bool((h >= 0).all())}
        result = {"checks": checks}
        if kind in ("inertial", "wall"):
            # Engine report dates carry its historical millisecond calendar
            # offset. Compare against the authored integer-second schedule,
            # while checking/reporting that offset instead of fitting phase.
            scheduled = np.arange(1,21,dtype=float)
            result["report_calendar_offset_max_s"] = float(np.max(abs(t-scheduled)))
            checks["report_schedule"] = result["report_calendar_offset_max_s"] < .002
            t = scheduled
            if kind == "wall":
                expected_u = parameter/(1+.04*abs(parameter)*t)
                expected_v = np.zeros_like(t)
            else:
                expected_u = .2*np.cos(parameter*t)+.3*np.sin(parameter*t)
                expected_v = .3*np.cos(parameter*t)-.2*np.sin(parameter*t)
            error = max(float(np.max(abs(u-expected_u[:,None]))), float(np.max(abs(v-expected_v[:,None]))))
            result["max_velocity_error_m_s"] = error
            checks["analytical_velocity"] = error < 2e-6
            checks["uniform_depth"] = bool(np.max(abs(h-.5)) < 1e-8)
        elif kind == "lake":
            checks["lake_at_rest"] = bool(np.max(abs(h-.5)) < 1e-12 and np.max(abs(u))+np.max(abs(v)) < 1e-12)
            checks["zero_strain"] = bool(np.max(abs(data["Mesh2_face_strain_rate"][:])) < 1e-12)
        else:
            # Equal-area triangles. Conservation/energy are self-consistency
            # properties, not an independent turbulence validation dataset.
            volume = h.mean(axis=1)
            energy = (.5*h*(u*u+v*v)+.5*9.81*h*h).mean(axis=1)
            initial_u = .2*np.sin(np.pi*data["Mesh2_face_y"][:]/100)
            initial_energy = float((.25*initial_u**2+.5*9.81*.25).mean())
            checks["closed_volume"] = bool(np.max(abs(volume-.5)) < 1e-10)
            checks["total_energy"] = bool(np.max(energy) <= initial_energy+1e-8)
            checks["nonzero_viscosity"] = bool(np.max(data["Mesh2_face_eddy_viscosity"][:]) > 0)
            result["initial_energy_per_area"] = initial_energy
            result["final_energy_per_area"] = float(energy[-1])
        return result


def run(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exe", type=Path, default=engines.REFACT_EXE)
    parser.add_argument("--output-dir", type=Path, default=ROOT/"results/analytical_momentum2d")
    args, _ = parser.parse_known_args(argv or [])
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    identity = {"exe": str(args.exe.resolve()), "binaries": binary_manifest(args.exe)} if args.exe.is_file() else {}
    for order in (1,2):
        for kind, values in (("inertial",(-.01,0.,.01)),("lake",(.1,)),("shear",(.05,.1,.2)),("wall",(-.2,.2))):
            for value in values:
                name = f"{kind}-order{order}-{value:g}"
                work = output/name
                work.mkdir(exist_ok=True)
                model = work/"model.inp"
                model.write_text(deck(kind,order,value), encoding="utf-8")
                cell = dict(case=name, solver="swmm2d-cpu-full-swe", reference_class="self_consistency" if kind == "shear" else "analytic")
                if not engines.available(args.exe):
                    cell.update(verdict="UNAVAILABLE", note="Engine executable missing")
                else:
                    (work/"surface.h5").unlink(missing_ok=True)
                    execution = runner.run(args.exe.resolve(),model,work/"model.rpt",work/"model.out",cwd=work,timeout=120,
                                           dylib_dirs=[str(args.exe.resolve().parent.parent/"engine"), str(args.exe.resolve().parent)])
                    (work/"execution.json").write_text(json.dumps(execution,indent=2),encoding="utf-8")
                    try:
                        if binary_manifest(args.exe) != identity["binaries"]:
                            raise RuntimeError("Engine binaries changed during execution; rerun with a fixed build")
                        if not execution["ok"]:
                            raise RuntimeError(execution["stderr"] or execution["stdout"][-1000:])
                        metrics = assess(work/"surface.h5",kind,value)
                        cell.update(verdict="PASS" if all(metrics["checks"].values()) else "FAIL", **metrics)
                    except Exception as error:
                        cell.update(verdict="ERROR",note=str(error))
                (work/"manifest.json").write_text(json.dumps({**identity,"input_sha256":hashlib.sha256(model.read_bytes()).hexdigest(),"kind":kind,"order":order,"parameter":value},indent=2),encoding="utf-8")
                scoring.save_cell(output/"scores.json",envelope,cell)
    write_report(output, envelope)
    print(scoring.summary(envelope))
    return envelope


def write_report(output, envelope):
    lines = ["# Optional 2D momentum verification", "",
             "CPU full shallow-water solver; both reconstruction orders. Inertial cases use "
             "an artificial signed f for a controlled analytic test, not a geographic site. "
             "The exact uniform velocities are u=0.2 cos(ft)+0.3 sin(ft), "
             "v=0.3 cos(ft)-0.2 sin(ft). Boundary stage is held at 0.5 m.", "",
             "Wall-channel cases use two side walls with Cw=0.02, width B=1 m and "
             "u(t)=u0/(1+2*Cw*abs(u0)*t/B), for both flow signs. "
             "Lake cases verify rest; shear cases check closed water volume, total energy "
             "and nonzero viscosity. Shear cases are self-consistency checks, not empirical "
             "turbulence validation. Analytical velocity tolerance is 2e-6 m/s. Calendar "
             "dates are checked within 2 ms of the authored report schedule; phase is not fitted.", "",
             "| Case | Reference | Verdict | Maximum velocity error (m/s) |", "| --- | --- | --- | --- |"]
    for cell in envelope["cells"]:
        error = cell.get("max_velocity_error_m_s")
        lines.append(f"| {cell['case']} | {cell['reference_class']} | {cell['verdict']} | {error if error is not None else '—'} |")
    lines += ["", "Each case folder preserves the input, exact executed binary/input hashes, "
              "execution log, report and HDF5 fields. The analytical sign, energy, nonlinear "
              "stress convergence, skew mesh, wet/dry and geostrophic convergence checks also "
              "run in the engine's test_engine_2d_momentum_physics executable. These checks "
              "do not establish a coefficient calibration or resolve the UK Test 6 mismatch."]
    path = output/"report.md"
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")
    return path


def report(argv=None):
    parser=argparse.ArgumentParser()
    parser.add_argument("--output-dir",type=Path,default=ROOT/"results/analytical_momentum2d")
    args,_=parser.parse_known_args(argv or [])
    return [write_report(args.output_dir,json.loads((args.output_dir/"scores.json").read_text(encoding="utf-8")))]


if __name__ == "__main__":
    import sys
    sys.exit(scoring.exit_code(run(sys.argv[1:])))
