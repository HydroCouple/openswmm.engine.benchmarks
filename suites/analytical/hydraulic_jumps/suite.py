"""Independent hydraulic-jump and wall-reflected bore regression checks."""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import h5py
import numpy as np
from harness import engines,runner,scoring
from suites.uk_2d.suite import binary_manifest
from suites.uk_2d.sources import digest
from . import references as m

ROOT=Path(__file__).resolve().parents[3]
SUITE='analytical/hydraulic_jumps'
T=.5
YCENTRE=m.NY*m.DY/2-.1

def assess(path,ref,cx):
    with h5py.File(path,'r') as f:
        raw=f['time'][:];times=(raw-np.floor(raw[0]))*86400
        if times.shape!=(10,) or not np.allclose(times,np.arange(.1,1.01,.1),atol=.002,rtol=0):
            raise ValueError('Incomplete or misaligned analytical output schedule')
        h=f['Mesh2_face_depth'][4];ux=f['Mesh2_face_vx'][4];uy=f['Mesh2_face_vy'][4];area=f['Mesh2_face_area'][:]
        a=math.radians(ref['angle']);co,si=math.cos(a),math.sin(a);u=ux*co+uy*si;v=-ux*si+uy*co;y=-f['Mesh2_face_x'][:]*si+f['Mesh2_face_y'][:]*co
        front=ref['shock_speed']*T
        region=(abs(cx)<.5)&(abs(y-YCENTRE)<.1)
        href=np.where(cx<front,m.H1,ref['h2']);uref=np.where(cx<front,ref['ul'],ref['u2'])
        weight=area[region];l1=float(np.sum(weight*abs(h[region]-href[region]))/np.sum(weight*href[region]));ul1=float(np.sum(weight*abs(u[region]-uref[region]))/np.sum(weight*np.maximum(abs(uref[region]),.1)));vl1=float(np.average(abs(v[region]-ref['vt']),weights=weight)/m.U1)
        j=np.arange(m.NY);keep=abs(-.1+(j+.5)*m.DY-YCENTRE)<.1
        profile=h.reshape(ref['nx'],m.NY,2)[:,keep,:].mean((1,2));x=ref['x0']+(np.arange(ref['nx'])+.5)*m.DX
        middle=(m.H1+ref['h2'])/2;cross=np.flatnonzero((profile[:-1]<middle)&(profile[1:]>=middle)&(x[:-1]>-.8)&(x[:-1]<.8))
        position=None if not len(cross) else float(x[cross[0]]+(middle-profile[cross[0]])/(profile[cross[0]+1]-profile[cross[0]])*m.DX)
        initial=float(np.sum(area*(m.H1 if ref['kind']=='wall' else np.where(cx<0,m.H1,ref['h2']))));relative_volume=abs(float(area@h)-initial)/initial
        left=(cx>front-.3)&(cx<front-.15)&(abs(y-YCENTRE)<.1);right=(cx>front+.15)&(cx<front+.3)&(abs(y-YCENTRE)<.1)
        if ref['kind']=='wall':right=(cx>front+.1)&(cx<-.02)&(abs(y-YCENTRE)<.1)
        ql=float(np.average(h[left]*u[left],weights=area[left]));qr=float(np.average(h[right]*u[right],weights=area[right]));ml=float(np.average(h[left]*u[left]**2+.5*m.G*h[left]**2,weights=area[left]));mr=float(np.average(h[right]*u[right]**2+.5*m.G*h[right]**2,weights=area[right]));residual=abs(ref['shock_speed']*(qr-ql)-(mr-ml))/max(abs(ml),abs(mr),1e-12)
        checks=dict(finite=bool(np.isfinite(h).all() and np.isfinite(u).all() and np.isfinite(v).all()),nonnegative_depth=bool((h>=0).all()),window_depth_l1=l1<.05,window_normal_velocity_l1=ul1<.08,window_transverse_velocity_l1=vl1<.05,shock_position=position is not None and abs(position-front)<3*m.DX,closed_volume=relative_volume<1e-10,momentum_jump=residual<.03)
        np.savez_compressed(path.with_name('window-fields.npz'),h=h[region],u=u[region],v=v[region],cx=cx[region],cy=y[region])
        return dict(checks=checks,window_depth_l1=l1,window_normal_velocity_l1=ul1,window_transverse_velocity_l1=vl1,shock_position_m=position,expected_shock_position_m=front,closed_volume_relative_error=relative_volume,momentum_jump_relative_residual=residual)


def options(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exe',type=Path,default=engines.REFACT_EXE)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'results/analytical_hydraulic_jumps')
    parser.add_argument('--max-wall',type=float,default=300)
    parser.add_argument('--build-provenance',type=Path)
    args,_=parser.parse_known_args(argv or [])
    if args.max_wall<=0:parser.error('--max-wall must be positive')
    return args


def run(argv=None):
    args=options(argv);output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    exe=args.exe.resolve();available=engines.available(exe)
    binaries=binary_manifest(exe) if available else {}
    provenance=json.loads(args.build_provenance.read_text(encoding='utf-8')) if args.build_provenance else None
    if provenance and available and provenance['binaries']!=binaries:
        raise ValueError('Build provenance differs from executed CLI/library identities')
    envelope=scoring.new_envelope(SUITE,provenance['engine_sha'] if provenance else engines.engine_sha())
    envelope['qualification']='Analytical verification in a causal window, not validation of the UK Test6 building geometry or its jump trajectory.'
    plan=dict(gravity_m_s2=m.G,initial_depth_m=m.H1,initial_velocity_m_s=m.U1,dx_m=m.DX,dy_m=m.DY,
              simulated_duration_s=1,assessment_time_s=T,window=dict(xmin=-.5,xmax=.5,y_centre=YCENTRE,y_half_width=.1),
              kinds=['stationary','moving-upstream','oblique','wall'],angles_deg=[0,64],orders=[1,2],
              criteria=dict(depth_relative_l1=.05,normal_velocity_relative_l1=.08,transverse_velocity_relative_l1=.05,
                            shock_position_cells=3,closed_volume_relative=1e-10,momentum_jump_relative=.03),
              reference='Compressive Rankine-Hugoniot solution; zero post-bore velocity for wall reflection. Outer-wall disturbances cannot reach the assessed window by0.5s.',
              binaries=binaries,suite_sha256=digest(Path(__file__).read_bytes()),reference_sha256=digest(Path(m.__file__).read_bytes()))
    (output/'plan.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    for kind in plan['kinds']:
        for angle in plan['angles_deg']:
            for order in plan['orders']:
                name=f'{kind}-angle{angle}-order{order}';work=output/name;work.mkdir(exist_ok=True)
                for filename in ['metrics.json','surface.h5','window-fields.npz']:(work/filename).unlink(missing_ok=True)
                text,reference,cx=m.make(kind,order,angle);model=work/'model.inp';model.write_text(text,encoding='utf-8')
                (work/'reference.json').write_text(json.dumps(reference,indent=2)+'\n',encoding='utf-8')
                manifest=dict(input_sha256=digest(model.read_bytes()),binaries=binaries,reference=reference,
                              suite_sha256=plan['suite_sha256'],reference_sha256=plan['reference_sha256'])
                (work/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
                cell=dict(case=name,solver='swmm2d-cpu-full-swe',reference_class='analytic')
                if not available:cell.update(verdict='UNAVAILABLE',note='Engine executable missing')
                else:
                    execution=runner.run(exe,model,work/'model.rpt',work/'model.out',cwd=work,timeout=args.max_wall,
                                         dylib_dirs=[str(exe.parent),str(exe.parent.parent/'engine')])
                    (work/'execution.json').write_text(json.dumps(execution,indent=2)+'\n',encoding='utf-8')
                    (work/'process.log').write_text(execution['stdout']+'\n'+execution['stderr']+'\n',encoding='utf-8')
                    cell['wall']=execution['wall']
                    try:
                        if binary_manifest(exe)!=binaries:raise ValueError('Executed binary changed during the run')
                        if not execution['launched']:cell.update(verdict='UNAVAILABLE',note=execution['stderr'])
                        elif not execution['ok']:cell.update(verdict='ERROR',note=execution['stderr'] or 'Engine run failed')
                        else:
                            metric=assess(work/'surface.h5',reference,cx)
                            cell.update(verdict='PASS' if all(metric['checks'].values()) else 'FAIL',**metric)
                            (work/'metrics.json').write_text(json.dumps(metric,indent=2,allow_nan=False)+'\n',encoding='utf-8')
                    except Exception as error:cell.update(verdict='ERROR',note=str(error))
                scoring.save_cell(output/'scores.json',envelope,cell)
    write_report(output,envelope)
    return envelope


def write_report(output,envelope):
    lines=['# Hydraulic-jump verification','','CPU full SWE, triangular meshes, first and second order, free-slip walls, Cs=0. '+
           'Stationary and upstream-moving jumps, a tangential-flow oblique jump, and a wall-reflected bore are compared with independent mass/momentum jump relations. '+
           'The exact states use g=9.80665m/s2, upstream depth0.03m and normal speed1.7m/s. No hydraulic software supplies a reference.','',
           'Each case runs1s with0.1s outputs; the reference is assessed at0.5s in the declared central window. '+
           'The outer solid-wall disturbances are outside its causal domain. Global closed volume is checked separately. '+
           'The two orientations rotate both geometry and velocities; they are accuracy checks, not an assumption of exact second-order rotational invariance.','',
           '| Case | Verdict | Depth relative L1 | Front position (m) | Momentum jump residual |','|---|---|---:|---:|---:|']
    for cell in envelope['cells']:
        lines.append('| '+cell['case']+' | '+cell['verdict']+' | '+
                     ' | '.join(f"{cell[key]:.6g}" if cell.get(key) is not None else 'unavailable' for key in ['window_depth_l1','shock_position_m','momentum_jump_relative_residual'])+' |')
    lines+=['','The frozen geometry, window and criteria are in [plan.json](plan.json). Full case inputs, references, binary identities, saved fields and metrics are retained. '+
            'Passing these tests does not establish measured accuracy or the correct jump position in UK Test6. The canonical UK corpus and its anchors are never modified.']
    path=Path(output)/'report.md';path.write_text('\n'.join(lines)+'\n',encoding='utf-8');return path


def report(argv=None):
    args=options(argv)
    return [write_report(args.output_dir,json.loads((args.output_dir/'scores.json').read_text(encoding='utf-8')))]


if __name__=='__main__':
    import sys
    raise SystemExit(scoring.exit_code(run(sys.argv[1:])))
