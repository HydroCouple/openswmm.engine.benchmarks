"""UK-compatible diagnostics; only observed/analytical independent overlays allowed."""
from __future__ import annotations
import csv
import html
import json
import os
from pathlib import Path
import numpy as np
from .sources import SPECIFICATIONS


def build_report(out):
    if not (out/'scores.json').exists():return []
    cache=out/'.fontcache';cache.mkdir(exist_ok=True)
    config=out/'.fontconfig.xml'
    dirs=[p for p in ['/System/Library/Fonts','/Library/Fonts','/usr/share/fonts'] if Path(p).exists()]
    if dirs:
        config.write_text('<?xml version="1.0"?><fontconfig>'+''.join('<dir>'+html.escape(p)+'</dir>' for p in dirs)+'<cachedir>'+html.escape(str(cache))+'</cachedir></fontconfig>', encoding='utf-8')
        os.environ['FONTCONFIG_FILE']=str(config)
    os.environ.setdefault('MPLCONFIGDIR',str(out/'.mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    scores=json.loads((out/'scores.json').read_text(encoding='utf-8'));coverage=scores['coverage']
    text=['# UK 2D benchmark assessment — execution report','',
          'Numerical checks and SWMM2D regression. Observed fit is reported only where reference measurements or a documented digitized subset are available. No comparison with other hydraulic models.',
          '',f'Coverage: {coverage.get("executed",0)}/{coverage.get("requested",0)} requested scenarios executed; '
          f'{coverage.get("observed_compared",0)} compared with observations; {coverage.get("regression_checked",0)} checked against reviewed own baselines.',
          '', '**This is partial qualification evidence. A numerical PASS is not a measured-validation claim.**','',
          '| Case | Numerical checks | Continuity (%) | Own regression | Measured fit | Wall time (s) |',
          '|---|---|---:|---|---|---:|']
    for cell in scores['cells']:
        if cell['solver'] in ('coverage','swmm2d-own-baseline'):continue
        continuity=f"{cell['continuity_err']:.3g}" if 'continuity_err' in cell else '—'
        wall=f"{cell['wall_s']:.2f}" if 'wall_s' in cell else '—'
        regression=next((b['verdict'] for b in scores['cells'] if b['case']==cell['case'] and b['solver']=='swmm2d-own-baseline'),cell.get('regression_status','unavailable'))
        observed=cell.get('observed_status','unavailable').replace('_',' ')
        text.append(f'| {cell["case"]} | {cell["verdict"]} | {continuity} | {regression} | {observed} | {wall} |')
    exclusions=[c for c in scores['cells'] if c.get('verdict') in ('SKIP','UNAVAILABLE','ERROR','FAIL','BASELINE-FAIL')]
    if exclusions:
        text += ['','## Execution exclusions and failures','','| Case | State | Detail |','|---|---|---|']
        for cell in exclusions:text.append(f"| {cell['case']} | {cell['verdict']} | {str(cell.get('note',cell.get('checks',''))).replace('|','/')} |")
    if (out/'assessment-history.json').exists():
        text += ['','[Assessment assembly history](assessment-history.json). Test 4 replaced an initial budget exclusion with a separate complete canonical run. The earlier timeout evidence is preserved; no incomplete run is scored as a pass.','']
    if (out/'hardware.json').exists():
        hardware=json.loads((out/'hardware.json').read_text(encoding='utf-8'))
        text += ['','## Hardware and runtime scope','',
                 f"{hardware['processor']}; {hardware['physical_cores']} physical cores; {hardware['memory_gib']} GiB installed RAM; {hardware['solver_threads']} solver thread. CPU clock frequency was not fixed or recorded. Minimum recommended hardware has not been qualified.",'',
                 hardware['runtime_scope'],'','[Hardware record](hardware.json).','']
    text+=['','## Coverage and source gaps','',
           'Tests 8A/8B lack authoritative inputs in the supplied archive. Test 6A lacks original measured series; a conservative digitized subset is available. Test 7 requires faithful river/structure/coupling import. Missing cases remain UNAVAILABLE.','',
           'The figure register accounts for the complete UK Chapter 4 output contract. Generated outputs below cover executed cases only; pending counterparts are listed separately.','']
    analytical=out/'analytical/scores.json'
    if analytical.exists():
        supplement=json.loads(analytical.read_text(encoding='utf-8'))
        text += ['## Separate analytical equilibrium supplement','',
                 'These two 60-second stationary lakes use the same CPU FULL_SWE second-order profile. The exact reference is equilibrium over the represented piecewise-flat bed; neither is a UK scenario or a transient convergence test. Predeclared limits are 1 µm depth drift, 1 µm/s spurious speed and 0.5% continuity error.','',
                 '| Lake | Maximum depth drift (m) | Maximum spurious speed (m/s) | Check |','|---|---:|---:|---|']
        for cell in supplement['cells']:
            m=cell['metrics']
            text.append(f"| {cell['case']} | {m['linf_m']:.6g} | {m['max_speed_mps']:.6g} | {cell['verdict']} |")
        text += ['','[Analytical run identities and metrics](analytical/scores.json).','']
    repeated=out/'regression/scores.json'
    if repeated.exists():
        repeat=json.loads(repeated.read_text(encoding='utf-8'))
        text += ['## Independent repeated-run regression checks','',
                 'These are separate executions against initially reviewed SWMM2D baselines. Agreement is change control, not experimental validation. Cross-platform tolerance qualification remains outstanding.','',
                 'The main cohort’s own-regression column records baseline availability at execution time. Initial anchors were reviewed afterwards; the independent repeated executions below establish the two actual repeat checks.','',
                 '| Case | Own baseline verdict | Maximum absolute probe change |','|---|---|---:|']
        for cell in repeat['cells']:
            if cell['solver']=='swmm2d-own-baseline':text.append(f"| {cell['case']} | {cell['verdict']} | {cell['max_absolute_change']:.6g} |")
        text += ['','[Full repeated-run evidence](regression/report.html).','']
    cross=list(csv.DictReader((SPECIFICATIONS/'report-crosswalk.csv').open(encoding='utf-8')))
    display_source=Path(__file__).with_name('figure-display-specs.json')
    display_record=json.loads(display_source.read_text(encoding='utf-8'))
    display=display_record['figures']
    (out/'figure-display-specs.json').write_text(json.dumps(display_record,indent=2)+'\n',encoding='utf-8')
    generated={'Table 4.1','Table 4.13'}
    completed={cell['case'] for cell in scores['cells'] if cell.get('checks') and cell['solver']=='swmm2d-cpu-full-swe-rk2'}
    for work in sorted(out.glob('uk-ea-*')):
        if work.name not in completed or not (work/'metrics.json').exists():continue
        case=json.loads((work/'case.json').read_text(encoding='utf-8'));metrics=json.loads((work/'metrics.json').read_text(encoding='utf-8'))
        probes=list(csv.DictReader((work/'probes.csv').open(encoding='utf-8')))
        ids=list(dict.fromkeys(r['probe'] for r in probes))
        reference=work/'reference'
        observed_rows=list(csv.DictReader((reference/'observations.csv').open(encoding='utf-8'))) if (reference/'observations.csv').exists() else []
        figdir=work/'figures';figdir.mkdir(exist_ok=True)
        key=case['uk_test']
        text += [f'## Test {key.upper()}: {case["title"]}','',
                 f'Historical spacing {case["dx"]:g} m; {case["cell_count"]:,} Cartesian quads; duration {case["end"]:g} s; saved interval {case["step"]:g} s.',
                 '',f'Final volume {metrics["final_volume_m3"]:.9g} m³; independent volume residual {metrics["volume_residual_m3"]} m³.',
                 '',f'Maximum calendar-clock rounding to the authored output grid: {metrics["clock_rounding_max_s"]:.6g} s.','']
        text += ['Geometry/setup qualifications: '+ ' '.join(case['deviations'])] if case['deviations'] else []
        if metrics['observed']['status']=='compared':
            text += ['### Exploratory comparison with digitized UCL markers','',
                     'Only visible isolated laboratory diamonds were recovered. Overlapped/occluded markers and G6 were omitted. '
                     'These statistics describe a visibility-selected, pixel-binned subset, primarily before 30 s. They do not estimate fit to the complete original experiment. '
                     'Instrument uncertainty is unknown; per-axis digitization uncertainty is conservatively one pixel. The engine reports flux-reconstructed RT0 cell speed. Original instrument and averaging metadata are still needed to confirm the measurement operator.','',
                     '| Gauge | Quantity | Samples | Covered time (s) | Bias | MAE | RMSE | Maximum absolute residual |',
                     '|---|---|---:|---:|---:|---:|---:|---:|']
            for row in metrics['observed']['metrics']:
                text.append(f"| {row['probe']} | {row['quantity']} | {row['n']} | {row['covered_duration_s']:.3f} | {row['bias']:.6g} | {row['mae']:.6g} | {row['rmse']:.6g} | {row['max_absolute_residual']:.6g} |")
            text += [f'[Recovered reference samples]({work.name}/reference/observations.csv) · [Digitization audit]({work.name}/reference/digitization-audit.json)','', 'Values are dimensional: metres for levels, metres per second for speed. Observed fit remains report-only.','']
            text += ['**G2 has material level and speed discrepancies. These results do not establish successful laboratory validation.** Original records and geometry, sampling and numerical sensitivity studies are needed to investigate the differences.','']
        table={'1':'4.2','2':'4.3','3':'4.4','4':'4.5','5':'4.6','6a':'4.7','6b':'4.8'}.get(key)
        identity=json.loads((work/'run-manifest.json').read_text(encoding='utf-8'))
        text += [f'### Configuration counterpart to UK Table {table}','',
                 '| Setting | Value |','|---|---|',
                 f"| Engine revision | {identity['engine_sha']} |",
                 f"| Platform | {identity['platform']} |",
                 '| Formulation/backend | CPU FULL_SWE, explicit |',
                 '| Requested reconstruction/tiering/CFL | Order 2 / one tier / 0.4 |',
                 '| Wet/dry and movement thresholds | 0.0001 m |',
                 f"| Manning n | {case['n']} |",
                 f"| Nominal mesh / active cells | {case['dx']} m / {case['cell_count']} |",
                 f"| End time / probe output interval | {case['end']} s / {case['step']} s |",'']
        generated.add('Table '+table)
        groups=[('level_m','Water-surface elevation (m)'),('speed_mps','Speed (m/s)')]
        for quantity,label in groups:
            fig,axes=plt.subplots(len(ids),1,figsize=(8,max(3,2.4*len(ids))),squeeze=False)
            for ax,p in zip(axes[:,0],ids):
                rows=[r for r in probes if r['probe']==p];times=np.array([float(r['time_s']) for r in rows]);vals=np.array([float(r[quantity]) if float(r['depth_m'])>1e-4 else np.nan for r in rows])
                ax.plot(times,vals,label='SWMM2D',color='#17678c',lw=1)
                obs=[r for r in observed_rows if r['probe']==p and r['quantity']==quantity]
                if obs:ax.scatter([float(r['time_s']) for r in obs],[float(r['value']) for r in obs],s=12,marker='D',facecolors='none',edgecolors='#aa367b',label='UCL digitized subset')
                if key=='1' and quantity=='level_m':
                    ax.axhline(10.35,color='#666666',ls=':',label='High-stage equilibrium 10.35 m')
                    ax.axhline(10.25,color='#916524',ls='--',label='Pond retention level 10.25 m')
                ax.set(title=f'Test {key.upper()} — point {p}',ylabel=label,xlabel='Elapsed time (s)');ax.grid(alpha=.25);ax.legend(fontsize=8)
            fig.tight_layout();fig.savefig(figdir/(quantity+'.png'),dpi=150);plt.close(fig)
            text += [f'![Test {key.upper()} {label} histories]({work.name}/figures/{quantity}.png)','']
        # UK-selected gauge panels, in addition to complete probe histories.
        subsets={
            '1': [('level_m',['1','2'],None,'4.3')],
            '2': [('level_m',['4','3','2','1'],None,'4.5-a'),('level_m',['8','7','6','5'],None,'4.5-b'),('level_m',['12','11','10','9'],None,'4.5-c')],
            '3': [('level_m',['1','2'],None,'4.8-level'),('speed_mps',['1'],None,'4.8-speed')],
            '4': [('level_m',['1','3','5','6'],None,'4.10'),('speed_mps',['1','3','5','6'],None,'4.11')],
            '5': [('level_m',['1','3','5','7'],None,'4.16'),('speed_mps',['1','3','4','7'],None,'4.17')],
            '6a': [('level_m',['G2','G4','G5','G6'],60,'4.25'),('speed_mps',['G2','G4'],60,'4.26')],
            '6b': [('level_m',['G2','G4','G5','G6'],600,'4.27'),('speed_mps',['G2','G4'],600,'4.28')]
        }
        for quantity,points,window,source in subsets.get(key,[]):
            frame=display[source];scale=frame['seconds_per_unit'];source_label=frame.get('source_figure',source)
            fig,axes=plt.subplots(len(points),1,figsize=(7,2.5*len(points)),squeeze=False)
            for ax,point in zip(axes[:,0],points):
                rows=[r for r in probes if r['probe']==point and (window is None or float(r['time_s'])<=window)]
                ax.plot([float(r['time_s'])/scale for r in rows],[float(r[quantity]) if float(r['depth_m'])>1e-4 else np.nan for r in rows],color='#17678c',label='SWMM2D')
                obs=[r for r in observed_rows if r['probe']==point and r['quantity']==quantity]
                if obs:ax.scatter([float(r['time_s'])/scale for r in obs],[float(r['value']) for r in obs],s=15,marker='D',facecolors='none',edgecolors='#aa367b',label='UCL digitized subset')
                if key=='1':
                    ax.axhline(10.35,color='#666666',ls=':',label='High-stage equilibrium')
                    ax.axhline(10.25,color='#916524',ls='--',label='Pond retention constraint')
                ax.set(title=f'Test {key.upper()}: {point}',xlabel='Time ('+frame['time_unit']+')',ylabel='Level (m)' if quantity=='level_m' else 'Speed (m/s)')
                ax.grid(alpha=.25);ax.legend()
            fig.suptitle(f'UK Figure {source_label}: corresponding SWMM2D diagnostic',y=1.002)
            fig.tight_layout();name='uk-'+source.replace('.','-')+'.png'
            # Preserve source axes and a full-range companion, so historical
            # framing never hides a discrepancy or removes the full history.
            full_name=name.replace('.png','-full-range.png')
            fig.savefig(figdir/full_name,dpi=150,bbox_inches='tight')
            for ax,point in zip(axes[:,0],points):
                panel=frame['panels'][point];ax.set(xlim=panel['xlim'],ylim=panel['ylim'])
            fig.savefig(figdir/name,dpi=150,bbox_inches='tight')
            text += [f'![UK Figure {source_label} with original axes]({work.name}/figures/{name})','',
                     f'![UK Figure {source_label} full-range companion]({work.name}/figures/{full_name})','',
                     'The first frame preserves the original UK time units and axis limits; the companion retains the complete ordinate range of these traces. Full-duration histories appear above.','']
            if key!='6a':generated.add('Figure '+source_label)
            plt.close(fig)
        if key=='1':generated|={'Figure 4.3'}
        if key=='2':generated|={'Figure 4.5'}
        if key=='3':generated|={'Figure 4.8'}
        if key=='4':generated|={'Figure 4.10','Figure 4.11'}
        if key=='6b':generated|={'Figure 4.27','Figure 4.28'}
        # 6A diagnostic traces are not counted as the required measured overlays.
        if key=='6a':text+=['Figures 4.25–4.26 are reproduced with the recoverable digitized measurement subset only; G6 and the original full records remain unavailable.','']
        data=np.load(work/'fields.npz')
        verts=data['vertices'];conn=data['cells'];polys=[verts[c[c>=0]] for c in conn]
        fields=[('max_depth','Output-sampled peak depth (m)'),('max_speed','Output-sampled peak speed (m/s)'),('final_depth','Final depth (m)')]
        for variable,label in fields:
            fig,ax=plt.subplots(figsize=(9,4));collection=PolyCollection(polys,array=data[variable],cmap='viridis',edgecolors='none')
            ax.add_collection(collection);ax.autoscale();ax.set_aspect('equal');ax.set(xlabel='x (m)',ylabel='y (m)',title=f'Test {key.upper()}: {label}')
            fig.colorbar(collection,ax=ax,label=label);fig.tight_layout();fig.savefig(figdir/(variable+'.png'),dpi=160);plt.close(fig)
            text += [f'![Test {key.upper()}: {label}]({work.name}/figures/{variable}.png)','']
        snapshots=sorted((name for name in data.files if name.startswith('depth_') and name.endswith('s')),key=lambda name:float(name[6:-1]))
        if snapshots:text += ['### Required Appendix A field snapshots','','These are instantaneous saved fields; peak maps above have a different time basis.','']
        for variable in snapshots:
            suffix=variable[6:];seconds=float(suffix[:-1]);fig,axes=plt.subplots(1,2,figsize=(11,6 if key=='4' else 3))
            for ax,field,label in [(axes[0],variable,'Depth (m)'),(axes[1],'speed_'+suffix,'Speed (m/s)')]:
                collection=PolyCollection(polys,array=data[field],cmap='viridis',edgecolors='none');ax.add_collection(collection);ax.autoscale();ax.set_aspect('equal')
                if key=='6a':ax.set(xlim=(-8,10),ylim=(-2,2))
                if key=='6b':ax.set(xlim=(-155,210),ylim=(-40,40))
                ax.set(xlabel='x (m)',ylabel='y (m)',title=label);fig.colorbar(collection,ax=ax,label=label,fraction=.04,pad=.04,shrink=.5 if key in ('6a','6b') else 1)
            fig.suptitle(f'Test {key.upper()}: saved fields at {seconds:g} s');fig.tight_layout();name=f'snapshot-{suffix}.png';fig.savefig(figdir/name,dpi=140);plt.close(fig)
            text += [f'![Test {key.upper()} depth and speed at {seconds:g} s]({work.name}/figures/{name})','']
        # Regenerate setup illustrations from the actual represented geometry.
        setup_field=data['z']+data['max_depth'] if key=='6b' else data['z']
        setup_label='Output-sampled peak level (m)' if key=='6b' else 'Bed elevation (m)'
        fig,ax=plt.subplots(figsize=(9,4));collection=PolyCollection(polys,array=setup_field,cmap='terrain',edgecolors='none')
        ax.add_collection(collection);ax.autoscale();ax.set_aspect('equal')
        if key=='6b':ax.set(xlim=(-155,210),ylim=(-40,40))
        if key=='6a':ax.set(xlim=(-8,10),ylim=(-2,2))
        # The original authored probe coordinates are available in probe-map.json.
        authored=json.loads((work/'probe-map.json').read_text(encoding='utf-8'))
        for point in authored:
            ax.plot(point['x'],point['y'],'o',ms=3,color='#762746');ax.annotate(point['id'],(point['x'],point['y']),fontsize=7)
        if key=='6b':
            for n,line in enumerate(sorted((work/'profiles').glob('*.csv')),1):
                points=np.loadtxt(line,delimiter=',',skiprows=1);ax.plot(points[:,1],points[:,2],'k--',lw=.8,label=f'Section {n}')
            ax.legend(fontsize=8)
        ax.set(xlabel='x (m)',ylabel='y (m)',title=f'Test {key.upper()}: represented geometry and source probes');fig.colorbar(collection,ax=ax,label=setup_label)
        fig.tight_layout();fig.savefig(figdir/'setup.png',dpi=160);plt.close(fig)
        text += [f'![Test {key.upper()} represented geometry and probes]({work.name}/figures/setup.png)','']
        setup_items={'2':'Figure 4.4','5':'Figure 4.15','6a':'Figure 4.24','6b':'Figure 4.29'}
        if key in setup_items:generated.add(setup_items[key])
        if key in ('1','3'):
            unique=np.unique(data['x']);bed=np.array([data['z'][data['x']==x].mean() for x in unique])
            fig,ax=plt.subplots(figsize=(8,3));ax.plot(unique,bed,color='#6b563c');ax.set(xlabel='x (m)',ylabel='Represented bed elevation (m)',title=f'Test {key.upper()}: longitudinal discrete bed profile');ax.grid(alpha=.25)
            fig.tight_layout();fig.savefig(figdir/'bed-profile.png',dpi=150);plt.close(fig)
            text += [f'![Test {key.upper()} represented bed profile]({work.name}/figures/bed-profile.png)',''];generated.add('Figure 4.1' if key=='1' else 'Figure 4.7')
        if key=='2':
            fig,ax=plt.subplots(figsize=(7,6));collection=PolyCollection(polys,array=(data['final_depth']>1e-4).astype(float),cmap='Blues',edgecolors='none',clim=(0,1));ax.add_collection(collection);ax.autoscale();ax.set_aspect('equal')
            ax.set(xlabel='x (m)',ylabel='y (m)',title='UK Figure 4.6: final extent, depth > 0.1 mm');fig.tight_layout();fig.savefig(figdir/'uk-4-6.png',dpi=150);plt.close(fig)
            text += [f'![Test 2 final inundation extent]({work.name}/figures/uk-4-6.png)',''];generated.add('Figure 4.6')
        if key=='5':
            nx=round((case['bounds'][1]-case['bounds'][0])/case['dx']);ny=round((case['bounds'][3]-case['bounds'][2])/case['dx'])
            xs=case['bounds'][0]+(np.arange(nx)+.5)*case['dx'];ys=case['bounds'][2]+(np.arange(ny)+.5)*case['dx']
            ix=np.rint((data['x']-xs[0])/case['dx']).astype(int);iy=np.rint((data['y']-ys[0])/case['dx']).astype(int)
            for field,level,label,source in [('max_depth',.5,'Peak depth 0.5 m','4.18'),('max_speed',3.,'Peak speed 3 m/s','4.19')]:
                grid=np.full((ny,nx),np.nan);grid[iy,ix]=data[field]
                fig,ax=plt.subplots(figsize=(8,7));ax.contour(xs,ys,np.ma.masked_invalid(grid),levels=[level],colors=['#17678c'])
                ax.set_aspect('equal');ax.set(xlabel='Easting (m)',ylabel='Northing (m)',title=f'UK Figure {source}: {label}, full domain');fig.tight_layout();name='uk-'+source.replace('.','-')+'.png';fig.savefig(figdir/name,dpi=160);plt.close(fig)
                text += [f'![UK Figure {source} contour threshold, full domain]({work.name}/figures/{name})',''];generated.add('Figure '+source)
        if key=='4' and 'depth_3600s' in data and 'depth_10800s' in data:
            nx=round((case['bounds'][1]-case['bounds'][0])/case['dx']);ny=round((case['bounds'][3]-case['bounds'][2])/case['dx'])
            x=data['x'].reshape(ny,nx);y=data['y'].reshape(ny,nx)
            fig,ax=plt.subplots(figsize=(6,7))
            for t,color in [(3600,'#17678c'),(10800,'#b15d1d')]:
                ax.contour(x,y,data[f'depth_{t}s'].reshape(ny,nx),levels=[.15],colors=[color])
                ax.plot([],[],color=color,label=f'{t/3600:g} h')
            ax.axhline(1000,color='#444',ls='--',lw=.7);ax.set(xlim=(0,1000),ylim=(0,2000),xlabel='x (m)',ylabel='y (m)',title='UK Figure 4.12: 0.15 m depth contours')
            ax.set_aspect('equal');ax.legend();fig.tight_layout();fig.savefig(figdir/'uk-4-12.png',dpi=160);plt.close(fig)
            text += [f'![UK Figure 4.12 contour counterpart]({work.name}/figures/uk-4-12.png)',''];generated.add('Figure 4.12')
            # The source section runs along y=1000 m, through points 1-5.
            # This line lies on cell faces: average its two adjacent rows and disclose it.
            lower=np.flatnonzero(y[:,0]<1000)[-1];upper=lower+1
            for field,label,source,limit in [('depth_3600s','Depth (m)','4.13',.7),('speed_3600s','Speed (m/s)','4.14',1.8)]:
                vals=(data[field].reshape(ny,nx)[lower]+data[field].reshape(ny,nx)[upper])/2
                fig,ax=plt.subplots(figsize=(8,3));ax.plot(x[lower],vals,color='#17678c',label='SWMM2D, adjacent-row mean')
                ax.set(xlim=(0,500),ylim=(0,limit),xlabel='Distance from inlet (m)',ylabel=label,title=f'UK Figure {source}: section at 1 h');ax.grid(alpha=.25);ax.legend()
                fig.tight_layout();name='uk-'+source.replace('.','-')+'.png';fig.savefig(figdir/name,dpi=160);plt.close(fig)
                text += [f'![UK Figure {source} section counterpart]({work.name}/figures/{name})',''];generated.add('Figure '+source)
        profile_dir=work/'profiles'
        if profile_dir.exists():
            from suites.uk_2d.profiles import sample
            for profile in sorted(profile_dir.glob('*.csv')):
                points=np.loadtxt(profile,delimiter=',',skiprows=1);values=sample(points,data)
                with (work/(profile.stem+'-extracted.csv')).open('w',newline='',encoding='utf-8') as stream:
                    writer=csv.writer(stream);writer.writerow(['chainage_m','x','y','sampled_peak_level_m','sampled_peak_speed_mps','represented_bed_m']);writer.writerows(values)
                bands=[(0,2000,'4.20'),(2000,5000,'4.21'),(5000,10000,'4.22'),(10000,15000,'4.23')] if key=='5' else [(0,float(values[-1,0]),'4.30' if profile.stem.endswith('1') else '4.31')]
                for left,right,source in bands:
                    fig,axes=plt.subplots(2,1,figsize=(8,5));mask=(values[:,0]>=left)&(values[:,0]<=right)
                    for ax,column,label in [(axes[0],3,'Peak level (m)'),(axes[1],4,'Peak speed (m/s)')]:
                        ax.plot(values[mask,0],values[mask,column],color='#17678c',label='SWMM2D')
                        if column==3:ax.plot(values[mask,0],values[mask,5],color='#8c7858',ls='--',label='Represented bed (geometry)')
                        ax.set(xlabel='Source chainage (m)',ylabel=label,xlim=(left,right));ax.grid(alpha=.25);ax.legend(fontsize=8)
                    if key=='6b':axes[0].set_ylabel('Peak depth (m)')
                    fig.suptitle(f'UK Figure {source}: source profile; output-sampled peaks');fig.tight_layout();name='uk-'+source.replace('.','-')+'.png'
                    full_name=name.replace('.png','-full-range.png');fig.savefig(figdir/full_name,dpi=160)
                    frame=display_record['profiles'][source]
                    axes[0].set(xlim=frame['xlim'],ylim=frame['level_or_depth_ylim']);axes[1].set(xlim=frame['xlim'],ylim=frame['speed_ylim'])
                    fig.savefig(figdir/name,dpi=160);plt.close(fig)
                    text += [f'![UK Figure {source} profile with original axes]({work.name}/figures/{name})','',
                             f'![UK Figure {source} full-range profile]({work.name}/figures/{full_name})',''];generated.add('Figure '+source)
                text += [f'Profile {profile.stem}: {int(np.isnan(values[:,3]).sum())}/{len(values)} source points lie outside the discretized wet-domain mesh; these remain gaps.','']
        if case.get('forcing'):
            forcing=np.asarray(case['forcing']);fig,ax=plt.subplots(figsize=(8,3));ax.plot(forcing[:,0],forcing[:,1],color='#17678c')
            ax.set(xlabel='Elapsed time (s)',ylabel='Stage (m)' if key=='1' else 'Total inflow (m³/s)',title=f'Test {key.upper()}: prescribed boundary');ax.grid(alpha=.25)
            fig.tight_layout();fig.savefig(figdir/'forcing.png',dpi=150);plt.close(fig)
            text += [f'![Test {key.upper()} prescribed boundary]({work.name}/figures/forcing.png)','']
            if key=='1':generated.add('Figure 4.2')
        text += [f'[Probe data]({work.name}/probes.csv) · [Water-volume history]({work.name}/volume.csv) · '
                 f'[Run identity]({work.name}/run-manifest.json) · [Metrics]({work.name}/metrics.json)','']
        if (work/'probe-locations.csv').exists():text += [f'[Authored probe locations]({work.name}/probe-locations.csv) · [Executed model]({work.name}/model.inp)','']
        if key=='1':
            rows=[r for r in probes if r['probe']=='2'];high=min(rows,key=lambda r:abs(float(r['time_s'])-39600));last=rows[-1]
            constraints=[dict(probe='2',scope='End of high-stage hold',time_s=float(high['time_s']),reference_level_m=10.35,computed_level_m=float(high['level_m'])),
                         dict(probe='2',scope='End of canonical retention run',time_s=float(last['time_s']),reference_level_m=10.25,computed_level_m=float(last['level_m']))]
            text += ['### Scoped equilibrium constraints','',
                     '| Point 2 constraint | Time (s) | Reference level (m) | Computed level (m) | Signed residual (mm) |','|---|---:|---:|---:|---:|']
            for constraint in constraints:
                constraint['signed_residual_mm']=1000*(constraint['computed_level_m']-constraint['reference_level_m'])
                text.append(f"| {constraint['scope']} | {constraint['time_s']:g} | {constraint['reference_level_m']:.2f} | {constraint['computed_level_m']:.9f} | {constraint['signed_residual_mm']:.6f} |")
            (work/'equilibrium-constraints.json').write_text(json.dumps(dict(scope='Finite-time comparison with equilibrium constraints; no exact transient reference or qualified pass tolerance',metrics=constraints),indent=2)+'\n',encoding='utf-8')
            text += ['','These are finite-time residuals, with no exact transient curve or qualified pass tolerance. Mesh, terrain representation and wet/dry sensitivity are still required.','',f'[Equilibrium comparison data]({work.name}/equilibrium-constraints.json).','']
        text += ['Own baseline: '+metrics['regression']['status']+'. Observed fit: '+metrics['observed']['status']+'.','']
    text += ['## UK output register','',
             'Status below records diagnostic quantity coverage, not pixel-identical panel reproduction. Exact source axes, selected panels, contour paths and missing observations still require qualification.',
             '', '[Machine-readable register](report-output-register.csv). Source pages locate captions; multipage figures may begin earlier. The display-specification record identifies individual chart pages.','', '| UK item | Caption PDF page | Quantity | Status | Counterpart |','|---|---:|---|---|---|']
    aliases={'4.1':['bed-profile.png'],'4.2':['forcing.png'],'4.3':['uk-4-3.png'],
             '4.4':['setup.png','forcing.png'],'4.5':['uk-4-5-a.png','uk-4-5-b.png','uk-4-5-c.png'],'4.7':['bed-profile.png'],
             '4.8':['uk-4-8-level.png','uk-4-8-speed.png'],'4.9':['setup.png','snapshot-10800s.png'],
             '4.15':['setup.png'],'4.24':['setup.png'],'4.29':['setup.png']}
    register=[]
    for row in cross:
        item=row['source_item'];kind,number=item.split(' ');paths=[]
        if kind=='Figure':
            key=row['uk_test'];case_name='uk-ea-2013-t'+(key.zfill(2) if key.isdigit() else key)
            if case_name in completed:
                for file in aliases.get(number,['uk-'+number.replace('.','-')+'.png']):
                    relative=Path(case_name)/'figures'/file
                    if (out/relative).exists():paths.append(relative.as_posix())
        status='diagnostic quantity generated; final layout pending' if item in generated else 'pending'
        if paths and number in ('4.25','4.26'):status='digitized subset compared; original records/G6 incomplete; original axes and full-range frames available'
        elif paths and (number in display or number in display_record['profiles'] or number in ('4.5','4.8')):status='source gauges/sections, units and axes matched; full-range companion retained; equilibrium constraints only' if number=='4.3' else 'source gauges/sections, units and axes matched; full-range companion retained; diagnostic only'
        links=' · '.join(f'[view {i+1}]({p})' for i,p in enumerate(paths)) or ('configuration/summary above' if item in generated else '—')
        text.append(f'| {item} | {row["caption_pdf_page_1based"]} | {row["quantity_or_view"]} | {status} | {links} |')
        register.append(dict(source_item=item,uk_test=row['uk_test'],caption_pdf_page_1based=row['caption_pdf_page_1based'],quantity=row['quantity_or_view'],status=status,counterpart_paths=';'.join(paths)))
    with (out/'report-output-register.csv').open('w',newline='',encoding='utf-8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(register[0]));writer.writeheader();writer.writerows(register)
    text += ['','## Reproducibility and limitations','',
             'Each run manifest records the executed binaries, input and source hashes, analysis identity, solver request and platform. '
             'Where build_provenance is supplied it records the isolated source revision, documented patch and verified executed binary hashes. Without it, a checkout SHA is contextual and does not establish binary provenance. '
             'The initial assessment build includes the separately hashed derived-velocity output refresh correction: it refreshes reported velocity at output time instead of retaining a 30-second diagnostic cache and does not change solver advance. '
             'Full qualification still requires geometry and output-cadence sensitivity, original Test 6A observations and the remaining cases.',
             '', 'Peak fields above are maxima over saved output times. They are not certified internal-step maxima. '
             'Dry probe intervals (depth at or below 0.1 mm) are omitted from level/speed plots. The primary configuration explicitly requests CPU FULL_SWE, reconstruction order 2 and one timestep tier. '
             'Initial baselines are local regression anchors; cross-platform tolerances remain provisional.',
             '', '[Environment Agency source project](https://www.gov.uk/flood-and-coastal-erosion-risk-management-research-reports/2d-benchmarking-evaluating-the-latest-generation-of-the-hydraulic-models-for-fcrm).']
    path=out/'report.md';path.write_text('\n'.join(text)+'\n', encoding='utf-8')
    from suites.uk_2d.render import render
    page=out/'report.html';page.write_text(render(path.read_text(encoding='utf-8')),encoding='utf-8')
    from suites.uk_2d.sources import digest
    (out/'report-manifest.json').write_text(json.dumps(dict(renderer_sha256=digest(Path(__file__).read_bytes()),html_renderer_sha256=digest(Path(__file__).with_name('render.py').read_bytes()),
        profile_sampler_sha256=digest(Path(__file__).with_name('profiles.py').read_bytes()),display_specs_sha256=digest(display_source.read_bytes()),
        source_crosswalk_sha256=digest((SPECIFICATIONS/'report-crosswalk.csv').read_bytes()),scores_sha256=digest((out/'scores.json').read_bytes())),indent=2)+'\n',encoding='utf-8')
    return [path,page]
