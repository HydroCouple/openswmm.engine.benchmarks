"""Controlled Test 6 wall-drag hypotheses; measured fit remains report-only.

Run from a pinned CLI/library directory. Corpus inputs are read from the
committed revision, preserving any separately edited GUI working copy.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
import datetime as dt
import json
from pathlib import Path
import re
import shutil
import subprocess

import numpy as np
from harness import engines
from . import sampling, checks, observations, tin
from .sources import ROOT, digest
from .suite import binary_manifest, analysis_hash
from .build import clock


def solid_groups(text, scale):
    sections={}; name=None
    for raw in text.splitlines():
        line=raw.split(';',1)[0].strip()
        if line.startswith('['): name=line.strip('[]'); sections[name]=[]
        elif line and name: sections[name].append(line.split())
    vertices=np.array([[float(v) for v in row[:3]] for row in sections['2D_VERTICES']])
    cells=np.array([[int(v) for v in row[:3]] for row in sections['2D_TRIANGLES']])
    building=np.array(tin.geometry()['constraints'][0]['points'])/1.0
    groups={key:[] for key in ['THROAT','OBSTRUCTION','OTHER_WALLS']}
    owners={}
    for c,ids in enumerate(cells):
        for e in range(3):
            pair=tuple(sorted((int(ids[(e+1)%3]),int(ids[(e+2)%3]))))
            owners.setdefault(pair,[]).append((c,e))
    def on_building(p):
        for a,b in zip(building[:-1],building[1:]):
            d=b-a; t=np.dot(p-a,d)/np.dot(d,d)
            if -1e-8<=t<=1+1e-8 and np.linalg.norm(p-(a+t*d))<1e-8:return True
        return False
    for (a,b),slots in owners.items():
        if len(slots)!=1:continue
        p,q=vertices[[a,b],:2]/scale
        throat=all(abs(abs(v[1])-.5)<1e-8 and -.8-1e-8<=v[0]<=1e-8 for v in [p,q]) and abs(p[1]-q[1])<1e-8
        group='THROAT' if throat else 'OBSTRUCTION' if on_building(p) and on_building(q) else 'OTHER_WALLS'
        c,e=slots[0];groups[group].append(dict(cell=c,edge=e,length_m=float(np.linalg.norm(q-p)*scale)))
    for group,wanted in [('THROAT',1.6),('OBSTRUCTION',2.4)]:
        length=sum(r['length_m'] for r in groups[group])
        if not np.isclose(length,wanted*scale,rtol=0,atol=1e-7):raise ValueError(f'Wrong {group} wall length {length}')
    return groups


def model_text(base,groups,selected,cw,cs,report_step):
    # All controls use the same accepted-cell velocity publication and global
    # stage schedule. Cs=0 disables SGS stress while retaining that output path.
    options={'CORIOLIS':'OFF','TURBULENCE_MODEL':'SMAGORINSKY','SMAGORINSKY_CS':f'{cs:.17g}',
             'REPORT_2D_VARIABLES':'DEPTH VELOCITY TURBULENCE ENVELOPES'}
    for key,value in options.items():
        if re.search(r'^'+key+r'\s+',base,re.M):base=re.sub(r'^'+key+r'\s+.*$',key+' '+value,base,flags=re.M)
        else:base=base.replace('[2D_OPTIONS]','[2D_OPTIONS]\n'+key+' '+value)
    for key in ['REPORT_STEP','WET_STEP','DRY_STEP']:
        base=re.sub(r'^'+key+r'\s+.*$',key+' '+clock(report_step),base,flags=re.M)
    rows=[]
    for group,edges in groups.items():
        for row in edges:
            coefficient=cw if group in selected else 0
            kind='WALL_DRAG' if coefficient else 'WALL'
            param=f'{coefficient:.17g}' if coefficient else '*'
            rows.append(f"{row['cell']} {row['edge']} {kind} {param} * {group}")
    # Last authoritative section; replace the existing section rather than
    # relying on duplicate-section merging in either reader.
    return re.sub(r'\[2D_BOUNDARY_CONDITIONS\][\s\S]*?(?=\n\[|\Z)',
                  '[2D_BOUNDARY_CONDITIONS]\n'+'\n'.join(rows)+'\n',base)


def verify_report_clock(exe,output,step,identity):
    """Require actual native HDF5 frames before launching costly TIN runs."""
    import h5py
    from harness import runner
    from suites.analytical.momentum2d.suite import deck
    work=Path(output)/f'preflight-clock-{step:g}s';work.mkdir(exist_ok=True)
    text=deck('wall',2,.2).replace('END_TIME 00:00:20','END_TIME 00:00:01')
    text=re.sub(r'^REPORT_STEP\s+.*$','REPORT_STEP '+clock(step),text,flags=re.M)
    text=re.sub(r'^ROUTING_STEP\s+.*$','ROUTING_STEP '+str(min(step,1.)),text,flags=re.M)
    model=work/'model.inp';model.write_text(text);(work/'surface.h5').unlink(missing_ok=True)
    execution=runner.run(exe,model,work/'model.rpt',work/'model.out',cwd=work,timeout=60,
                         dylib_dirs=[str(exe.parent),str(exe.parent.parent/'engine')])
    (work/'execution.json').write_text(json.dumps(execution,indent=2))
    if not execution['ok']:raise ValueError('Native report-clock preflight failed: '+str(execution))
    with h5py.File(work/'surface.h5','r') as data:
        times=data['time'][:]
        expected=np.arange(step,1+step/2,step)
        if times.shape!=expected.shape:raise ValueError(f'Report-clock preflight: {len(times)} frames, expected {len(expected)}')
        actual=(times-np.floor(times[0]))*86400
        error=float(np.max(abs(actual-expected)))
        if error>.002:raise ValueError(f'Report-clock preflight: incorrect native time grid, error {error}')
        u=data['Mesh2_face_vx'][:];v=data['Mesh2_face_vy'][:]
        velocity_error=float(max(np.max(abs(u-(.2/(1+.04*.2*expected))[:,None])),np.max(abs(v))))
        if velocity_error>2e-6:raise ValueError('Report-clock analytical velocity preflight failed')
    if binary_manifest(exe)!=identity:raise ValueError('Pinned binary changed during preflight')
    (work/'verification.json').write_text(json.dumps(dict(status='PASS',step_s=step,frames=len(times),clock_error_max_s=error,velocity_error_max_m_s=velocity_error,input_sha256=digest(text.encode()),binaries=identity),indent=2))


def run(args):
    output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
    exe=args.exe.resolve();identity=binary_manifest(exe)
    if len(identity)<2:raise ValueError('Pin both CLI and engine library next to it before assessment')
    verify_report_clock(exe,output,.1,identity)
    verify_report_clock(exe,output,1.,identity)
    requests=[]
    for key in args.tests.split(','):
        if key not in ('6a','6b'):raise ValueError('Only 6a and 6b are supported')
        relative=f'corpus/uk-ea-2d/uk-ea-2013-t{key}'
        def committed(name):return subprocess.check_output(['git','show',f'{args.corpus_revision}:{relative}/{name}'],cwd=ROOT)
        base=committed('model.inp').decode();case=json.loads(committed('case.json'))
        if digest(base.encode())!=case['model_sha256']:raise ValueError('Committed model/case hashes differ')
        groups=solid_groups(base,1 if key=='6a' else 20)
        for cs in [float(v) for v in args.cs.split(',')]:
            for location in args.locations.split(','):
                selected={'none':[],'throat':['THROAT'],'obstruction':['OBSTRUCTION'],'both':['THROAT','OBSTRUCTION'],'all':list(groups)}[location]
                name=f'{key}-cs{cs:g}-{location}-cw{args.cw:g}'
                work=output/name;work.mkdir(exist_ok=True)
                (work/'metrics.json').unlink(missing_ok=True) # a failed rerun must not retain a completed verdict
                text=model_text(base,groups,selected,args.cw,cs,case['step'])
                (work/'model.inp').write_text(text)
                (work/'canonical-case.json').write_text(json.dumps(case,indent=2))
                variant=dict(case,id=name,model_sha256=digest(text.encode()))
                variant['deviations']=case['deviations']+['Experimental wall/Smagorinsky sensitivity; original corpus preserved.']
                (work/'case.json').write_text(json.dumps(variant,indent=2))
                source=ROOT/relative
                shutil.copy2(source/'probes.csv',work/'probe-locations.csv')
                if key=='6a':shutil.copytree(source/'reference',work/'reference',dirs_exist_ok=True)
                manifest=dict(case=name,uk_test=key,selected_groups=selected,cw=args.cw,cs=cs,
                              coefficient_scope='declared diagnostic sensitivity; not fitted material roughness',
                              velocity_operator='accepted cell q/h for every control and treatment',
                              report_step_encoding=clock(case['step']),
                              wall_groups=groups,corpus_revision=args.corpus_revision,canonical_input_sha256=case['model_sha256'],
                              input_sha256=digest(text.encode()),binaries=identity,analysis_sha256=analysis_hash(),
                              driver_sha256=digest(Path(__file__).read_bytes()),
                              probe_sha256=digest((work/'probe-locations.csv').read_bytes()),
                              observations_sha256=digest((work/'reference/observations.csv').read_bytes()) if key=='6a' else None,
                              created=dt.datetime.now(dt.timezone.utc).isoformat())
                (work/'manifest.json').write_text(json.dumps(manifest,indent=2))
                requests.append((work,case,manifest))
    def execute(request):
        work,case,manifest=request
        if binary_manifest(exe)!=identity:raise ValueError('Pinned binary changed before execution')
        (work/'surface.h5').unlink(missing_ok=True)
        import time
        started=time.monotonic()
        with (work/'process.log').open('w') as stream:
            result=subprocess.run([str(exe),str(work/'model.inp'),str(work/'model.rpt'),str(work/'model.out')],
                 cwd=work,env=engines.env(1,[str(exe.parent),str(exe.parent.parent/'engine')]),
                 stdout=stream,stderr=subprocess.STDOUT,timeout=args.max_wall)
        metric=dict(case=work.name,returncode=result.returncode,wall_s=time.monotonic()-started)
        if result.returncode!=0:raise ValueError(f'{work.name}: engine failed; see process.log')
        if binary_manifest(exe)!=identity:raise ValueError('Pinned binary changed during execution')
        probes=list(csv.DictReader((work/'probe-locations.csv').open()))
        data=sampling.extract(work/'surface.h5',case,probes,work)
        metric.update(checks.numerical(case,data))
        metric['observed']=observations.compare(work/'reference',case,data['times'],data['values'],probes) if case['uk_test']=='6a' else dict(status='not_applicable',metrics=[])
        log=(work/'process.log').read_text()
        removed=re.search(r'energy removed/rho=([0-9.eE+\-]+)',log)
        metric['wall_energy_removed_over_rho_m5_s2']=float(removed[1]) if removed else 0.
        np.savez_compressed(work/'extracted.npz',times=data['times'],values=data['values'])
        (work/'metrics.json').write_text(json.dumps(metric,indent=2,allow_nan=False))
        print(json.dumps(dict(case=work.name,checks=metric['checks'],wall_s=metric['wall_s'])),flush=True)
        return metric
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:results=list(pool.map(execute,requests))
    completed=[json.loads(p.read_text()) for p in sorted(output.glob('*/metrics.json'))]
    (output/'summary.json').write_text(json.dumps(completed,indent=2,allow_nan=False))
    write_report(output)
    return results


def write_report(output):
    """Own configurations vs measured markers; source axes plus full companions."""
    import os
    output=Path(output)
    os.environ.setdefault('MPLCONFIGDIR',str(output.resolve()/'.plot-cache'))
    os.environ.setdefault('XDG_CACHE_HOME',str(output.resolve()/'.cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from .wall_report import methods, bias_table
    output=Path(output)
    records=[]
    for path in sorted(output.glob('*/metrics.json')):
        metric=json.loads(path.read_text());manifest=json.loads(path.with_name('manifest.json').read_text())
        rows=list(csv.DictReader(path.with_name('probes.csv').open()))
        records.append((path.parent,manifest,metric,rows))
    status='Completed configurations are listed below.'
    plan_path=output/'assessment-plan.json'
    if plan_path.exists():
        plan=json.loads(plan_path.read_text())
        expected={f"{p['test']}-cs{p['cs']:g}-{location}-cw{plan['cw']:g}"
                  for p in plan['phases'] for location in p['locations']}
        complete=expected <= {r[0].name for r in records}
        status=(f'All {len(expected)} planned configurations have completed.' if complete else
                f'Interim report: {len(records)} of {len(expected)} planned configurations have completed. The assessment is unfinished.')
    lines=['# Test 6: selective wall-friction sensitivity','',
           status,'',
           'These runs compare HydroCouple configurations only with the available measured subset. '
           'Cw is a declared diagnostic coefficient, not calibrated wall-material roughness. '
           'Bed roughness, mesh, initial depths and Coriolis OFF are held fixed. '
           'Every control uses accepted cell q/h velocity output and the same global stage schedule; '
           'Cs=0 means no interior Smagorinsky stress. Thus the historical free-slip RT0 velocity '
           'report is not silently used as the control for a different velocity operator.','',
           'Source: [Environment Agency SC120002 (2013), Figures 4.25–4.28](https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf).','',
           'Test 6A observations are digitized isolated UCL markers, not the original complete '
           'measurement series. G6 is unavailable. Reported errors apply only to the recoverable '
           'sample intervals. Test 6B has no independent measured reference.','',
           *methods(records, output),
           '| Case | G2 speed RMSE (m/s) | G4 speed RMSE (m/s) | G2 level RMSE (m) | '
           'G4 level RMSE (m) | G5 level RMSE (m) | Volume residual (m³) | Wall energy/rho (m⁵/s²) |',
           '|---|---:|---:|---:|---:|---:|---:|---:|']
    for work,manifest,metric,rows in records:
        values={(r['probe'],r['quantity']):r['rmse'] for r in metric['observed']['metrics']}
        cells=[f"{values[k]:.6g}" if k in values else '—' for k in [('G2','speed_mps'),('G4','speed_mps'),('G2','level_m'),('G4','level_m'),('G5','level_m')]]
        lines.append('| '+work.name+' | '+' | '.join(cells)+f" | {metric['volume_residual_m3']:.6g} | {metric['wall_energy_removed_over_rho_m5_s2']:.6g} |")
    lines += bias_table(records)
    lines += ['', '## Corresponding UK report panels', '',
              'The first image of each pair retains the source panel axes; '
              'the companion exposes values outside those limits and the full duration.']
    display=json.loads(Path(__file__).with_name('figure-display-specs.json').read_text())['figures']
    for key in sorted({r[1]['uk_test'] for r in records}):
        for cs in sorted({r[1]['cs'] for r in records if r[1]['uk_test']==key}):
            selected=[r for r in records if r[1]['uk_test']==key and r[1]['cs']==cs]
            refs=list(csv.DictReader((selected[0][0]/'reference/observations.csv').open())) if key=='6a' else []
            for quantity,points,source in [('level_m',['G2','G4','G5','G6'],'4.25' if key=='6a' else '4.27'),('speed_mps',['G2','G4'],'4.26' if key=='6a' else '4.28')]:
                frame=display[source];scale=frame['seconds_per_unit']
                fig,axes=plt.subplots(len(points),1,figsize=(8,2.7*len(points)),squeeze=False)
                for ax,point in zip(axes[:,0],points):
                    for work,manifest,metric,rows in selected:
                        history=[r for r in rows if r['probe']==point]
                        ax.plot([float(r['time_s'])/scale for r in history],
                                [float(r[quantity]) if float(r['depth_m'])>1e-4 else np.nan for r in history],
                                label=' + '.join(manifest['selected_groups']) or 'Free slip')
                    obs=[r for r in refs if r['probe']==point and r['quantity']==quantity]
                    if obs:ax.scatter([float(r['time_s'])/scale for r in obs],[float(r['value']) for r in obs],s=14,marker='D',facecolors='none',edgecolors='black',label='UCL digitized subset',zorder=10)
                    elif key=='6a':ax.text(.02,.95,'Measured series unavailable',va='top',transform=ax.transAxes,fontsize=8)
                    ax.set(title=point,xlabel='Time ('+frame['time_unit']+')',ylabel='Level (m)' if quantity=='level_m' else 'Speed (m/s)')
                    ax.grid(alpha=.25);ax.legend(fontsize=8)
                fig.suptitle(f'Test {key.upper()}, Cs={cs:g}; UK Figure {source} panels',y=1.002)
                fig.tight_layout()
                stem=f'{key}-cs{cs:g}-uk-{source.replace(".","-")}'
                fig.savefig(output/(stem+'-full-range.png'),dpi=150,bbox_inches='tight')
                for ax,point in zip(axes[:,0],points):ax.set(xlim=frame['panels'][point]['xlim'],ylim=frame['panels'][point]['ylim'])
                fig.savefig(output/(stem+'.png'),dpi=150,bbox_inches='tight');plt.close(fig)
                lines+=['',f'![UK Figure {source} corresponding panels, original axes]({stem}.png)','',f'![Full-duration and ordinate-range companion]({stem}-full-range.png)']
    lines+=['','All cases retain model inputs, exact CLI/library hashes, wall groups, numerical checks and measured-fit metrics. '
            'A reduction at one gauge alone does not establish wall friction as the missing cause. '
            'Joint level/speed histories and mesh/timestep sensitivity must support any selected closure.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    (output/'report-provenance.json').write_text(json.dumps(dict(
        renderer_sha256=digest(Path(__file__).read_bytes()),
        methods_sha256=digest(Path(__file__).with_name('wall_report.py').read_bytes()),
        cases={work.name:manifest['input_sha256'] for work,manifest,metric,rows in records},
        note='Report generation is separate from execution; per-case manifests retain the execution driver identity.'
    ),indent=2)+'\n')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--exe',type=Path,required=True)
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--corpus-revision',default='0e60707')
    ap.add_argument('--tests',default='6a,6b')
    ap.add_argument('--cs',default='0,0.1')
    ap.add_argument('--locations',default='none,throat,obstruction,both')
    ap.add_argument('--cw',type=float,default=.01)
    ap.add_argument('--jobs',type=int,default=2)
    ap.add_argument('--max-wall',type=float,default=14400)
    args=ap.parse_args()
    if not np.isfinite(args.cw) or args.cw<=0 or args.jobs<1:ap.error('Positive finite Cw and jobs required')
    run(args)

if __name__=='__main__':main()
