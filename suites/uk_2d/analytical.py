"""Separate exact lake-at-rest supplement using the same primary solver profile."""
from __future__ import annotations
import json
import datetime as dt
from pathlib import Path
import numpy as np
from harness import runner,scoring,engines
from .build import COLLECTION
from .sources import digest


def deck(stage):
    # Piecewise-flat cells, exact stationary surface eta=stage where wet.
    # The comparison is against this represented bed, not a smooth-bed norm.
    x=np.linspace(0,100,21);X,Y=np.meshgrid(x,x)
    z=.5*np.exp(-((X-50)**2+(Y-50)**2)/200)
    vertices=np.column_stack([X.ravel(),Y.ravel(),z.ravel()])
    cells=[]
    for j in range(20):
        for i in range(20):
            v=j*21+i;cells.append([v,v+1,v+22,v+21])
    cells=np.array(cells);bed=vertices[cells,2].mean(axis=1);initial=np.maximum(stage-bed,0)
    # Reuse only the primary options and dry dummy network; replace all 2D geometry/BCs.
    base=(COLLECTION/'uk-ea-2013-t01/model.inp').read_text(encoding='utf-8').split('[2D_VERTICES]')[0]
    base=base.replace('END_TIME 20:00:00','END_TIME 00:01:00').replace('REPORT_STEP 0:01:00','REPORT_STEP 0:00:01').replace('WET_STEP 0:01:00','WET_STEP 0:00:01').replace('DRY_STEP 0:01:00','DRY_STEP 0:00:01')
    base=base.replace(';; UK EA 2013 Test 1: Disconnected water body',';; Separate exact stationary lake supplement; not a UK scenario')
    lines=[base,'[2D_VERTICES]']+[' '.join(f'{v:.12g}' for v in row) for row in vertices]+['[2D_QUADS]']
    lines += [f'{" ".join(map(str,c))} .03 {h:.12g}' for c,h in zip(cells,initial)]
    return '\n'.join(lines)+'\n',bed,initial


def run(exe,out,max_wall,provenance=None):
    import h5py
    env=scoring.new_envelope('uk_2d_analytical_supplement',provenance['engine_sha'] if provenance else engines.engine_sha())
    from .suite import binary_manifest
    binaries=binary_manifest(exe)
    if provenance and binaries!=provenance['binaries']:raise ValueError('Analytical build identity mismatch')
    env['build_provenance']=provenance
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    for name,stage in [('immersed',1.),('emerged',.3)]:
        ident='analytic-lake-at-rest-'+name;work=out/ident;work.mkdir(exist_ok=True)
        text,bed,ref=deck(stage);(work/'model.inp').write_text(text,encoding='utf-8')
        for artifact in ['surface.h5','comparison.npz']:(work/artifact).unlink(missing_ok=True)
        cell=dict(case=ident,solver='swmm2d-cpu-full-swe-rk2',reference_class='analytic',scope='Exact equilibrium of the represented piecewise-flat bed; separate from UK scenarios')
        try:
            result=runner.run(exe,work/'model.inp',work/'model.rpt',work/'model.out',cwd=work,timeout=max_wall,dylib_dirs=[str(exe.parent)])
            (work/'process.log').write_text(result.get('stdout','')+'\n'+result['stderr']+'\n',encoding='utf-8')
            if not result['ok']:raise ValueError(result['stderr'])
            report=(work/'model.rpt').read_text(encoding='utf-8',errors='replace')
            if 'ERROR' in report or 'MOMENTUM_EQUATION FULL_SWE' not in report or '2D solver: cpu' not in report:
                raise ValueError('Requested analytical solver not confirmed in report')
            with h5py.File(work/'surface.h5') as f:
                if any(f[name].shape!=(60,400) for name in ['Mesh2_face_depth','Mesh2_face_vx','Mesh2_face_vy']):
                    raise ValueError('Incomplete lake supplement output')
                times=np.asarray(f['time']);units=f['time'].attrs.get('units','')
                if isinstance(units,bytes):units=units.decode()
                if units=='days since 1899-12-30 00:00:00':
                    origin=(dt.datetime(2026,1,1)-dt.datetime(1899,12,30)).days;times=(times-origin)*86400
                elif units!='seconds since 2026-01-01 00:00:00':raise ValueError('Unrecognized analytical output time units')
                if times.shape!=(60,) or not np.allclose(times,np.arange(1,61),atol=.02,rtol=0):
                    raise ValueError('Misaligned analytical output times')
                h=f['Mesh2_face_depth'][:];u=f['Mesh2_face_vx'][:];v=f['Mesh2_face_vy'][:]
                if not all(np.isfinite(a).all() for a in [h,u,v]):raise ValueError('Non-finite supplement output')
                err=h-ref;speed=np.hypot(u,v)
                norms=dict(l1_m=float(abs(err).mean()),l2_m=float(np.sqrt(np.mean(err**2))),linf_m=float(abs(err).max()),max_speed_mps=float(speed.max()))
                mass=100*float(f['mass_balance_2d'].attrs['continuity_error'])
                if not np.isfinite(mass) or h.min() < -1e-10:raise ValueError('Invalid analytical depth or continuity ledger')
                # Predeclared well-balanced preservation targets; no calibration.
                passed=norms['linf_m']<=1e-6 and norms['max_speed_mps']<=1e-6 and abs(mass)<=.5
                cell.update(verdict='PASS' if passed else 'FAIL',metrics=norms,continuity_err=mass,wall_s=result['wall'],
                            tolerance=dict(depth_linf_m=1e-6,max_speed_mps=1e-6),input_sha256=digest(text.encode()),executable_sha256=digest(exe.read_bytes()),binaries=binaries)
                cell['norm_scope']='All 60 saved output times and all 400 cells; final fields and per-cell maxima retained separately'
                np.savez_compressed(work/'comparison.npz',bed=bed,reference_depth=ref,computed_depth=h[-1],speed=speed[-1],
                                    maximum_depth_drift=abs(err).max(axis=0),maximum_speed=speed.max(axis=0))
        except Exception as exc:cell.update(verdict='ERROR',note=str(exc))
        print(ident,cell['verdict'],flush=True)
        scoring.save_cell(out/'scores.json',env,cell)
    return env

if __name__=='__main__':
    import argparse,sys
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--exe',type=Path,default=engines.REFACT_EXE);ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--build-provenance',type=Path)
    args=ap.parse_args();identity=json.loads(args.build_provenance.read_text(encoding='utf-8')) if args.build_provenance else None
    sys.exit(scoring.exit_code(run(args.exe.resolve(),args.output_dir.resolve(),120,identity)))
