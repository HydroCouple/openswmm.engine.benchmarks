"""Render the published quantities against independent references only."""
from __future__ import annotations
import json
import os
from pathlib import Path
import numpy as np
from .references import ROOT,write_csv,digest
os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'results/uk_river/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from suites.uk_2d.render import render


def read(path):
    return np.genfromtxt(path,delimiter=',',names=True,dtype=None,encoding='utf-8')


def save(fig,path):
    fig.tight_layout();fig.savefig(path,dpi=160);plt.close(fig)


def build(out):
    out=Path(out);scores=out/'scores.json'
    if not scores.exists():return []
    env=json.loads(scores.read_text(encoding='utf-8'));figures=out/'figures';figures.mkdir(exist_ok=True)
    cells=[c for c in env['cells'] if c['solver']=='swmm2d-cpu-full-swe-rk2']
    completed={c['case'] for c in cells if c.get('checks')}
    lines=['# W5-105 river benchmark supplement','',
        'SWMM2D reproductions of an earlier river-model benchmark collection, separate from the numbered SC120002 2D tests. All comparison lines are analytical or measured references. No competitor trace or ranking is used.','',
        'PASS below denotes complete, finite numerical output and conservation within 0.5%. It does not denote successful physical validation. Independent-reference residuals and numerical baseline changes are reported separately.','',
        '| Case | Numerical execution | Independent reference | Wall time (s) |','|---|---|---|---:|']
    for c in cells:lines.append(f'| {c["case"]} | {c["verdict"]} | {c.get("reference_status",c.get("note","unavailable"))} | {c.get("wall_s",0):.2f} |')
    coverage=env.get('coverage',{})
    lines+=['',f'Coverage: {coverage.get("executed",0)}/{coverage.get("requested",0)} requested executions. Complete coverage: {coverage.get("complete",False)}. Scientific validation remains incomplete.','',
        'The executed binary and source identities are in each run manifest. All reference CSV files are checksum locked. Errors below have dimensional units of metres. No phase, time shift, roughness, or measurement scale is fitted to reduce them.','']
    register=[]
    for c in cells:
        if c['case'] not in completed:continue
        work=out/c['case'];case=json.loads((work/'case.json').read_text(encoding='utf-8'));key=case['key'];m=json.loads((work/'metrics.json').read_text(encoding='utf-8'))
        # Use the copied reference belonging to this run, not a possibly newer corpus file.
        meta=json.loads((work/'reference/reference.json').read_text(encoding='utf-8'))
        identity=json.loads((work/'run-manifest.json').read_text(encoding='utf-8'))
        if digest((work/'model.inp').read_bytes())!=case['model_sha256']:raise ValueError('Executed model changed before reporting')
        for name,sha in identity['reference_hashes'].items():
            if digest((work/'reference'/name).read_bytes())!=sha:raise ValueError('Executed reference changed before reporting')
        if meta['kind']!='unavailable' and digest((work/'reference/reference.csv').read_bytes())!=meta['csv_sha256']:
            raise ValueError('Reference CSV identity mismatch before reporting')
        lines += ['## '+case['title'],'',f'Continuity error: {m["continuity_pct"]:.6g}%. Saved output covers the full {case["end"]:g} s simulation.','',
            ' '.join(case['deviations']),'',m['reference_fit'].get('scope',m['reference_fit'].get('reason','')),'']
        if m['reference_fit']['metrics']:
            lines+=['| Quantity / gauge | Samples | Bias (m) | RMSE (m) | Maximum absolute residual (m) |','|---|---:|---:|---:|---:|']
            for row in m['reference_fit']['metrics']:
                label=row.get('probe',str(row.get('time_s','final profile')))
                lines.append(f'| {label} | {row["n"]} | {row["bias_m"]:.6g} | {row["rmse_m"]:.6g} | {row["linf_m"]:.6g} |')
        figure=None
        if key.startswith('a'):
            original=read(work/'reference/reference.csv');pred=read(work/'profile.csv');res=read(work/'comparison.csv')
            fig,axes=plt.subplots(2,1,figsize=(9,7),sharex=True)
            axes[0].plot(original['chainage_m'],original['level_m'],'k-',label='Published analytical water level')
            axes[0].plot(pred['chainage_m'],pred['computed_level_m'],color='#007f87',label='SWMM2D cross-channel mean')
            axes[0].plot(original['chainage_m'],original['bed_m'],color='#997247',label='Source bed')
            axes[0].set_ylabel('Elevation (m)');axes[0].legend(fontsize=8)
            axes[1].plot(res['chainage_m'],res['depth_error_pct'],color='#007f87');axes[1].axhline(0,color='k',lw=.5)
            axes[1].set(xlabel='Source chainage (m; flow towards 0)',ylabel='Depth error (%)',xlim=(0,100))
            figure=figures/(key+'-profile.png');save(fig,figure)
            register.append([c['case'],f'TR2A Graphs {4*(int(key[1:])-1)+1}–{4*int(key[1:])}',
                'Water-level profile and residual; own quasi-steady solution only. Direct steady solver counterpart is not claimed.',str(figure.relative_to(out))])
        elif key.startswith('l'):
            fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True)
            source=read(work/'reference/reference.csv')
            for ax,probe in zip(axes.flat,['S1','S2','S3','S4']):
                values=read(work/(probe+'-comparison.csv'))
                ax.plot(source['time_s'],source[probe],color='black',lw=1,label='Published laboratory measurements')
                ax.plot(values['time_s'],values['computed_level_m'],color='#007f87',label='SWMM2D')
                ax.set(title=probe,xlabel='Time since gate release (s)',ylabel='Water level above bed (m)',xlim=(0,10),ylim=(0,.35))
                ax.grid(alpha=.2)
            axes[0,0].legend(fontsize=8);figure=figures/(key+'-gauges.png');save(fig,figure)
            register.append([c['case'],'TR2L Graphs 1–12','Four gauge histories, 0–10 s; laboratory references only. Physical channel/instantaneous release differs from report initialization.',str(figure.relative_to(out))])
        elif key.startswith('f-'):
            fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey=True)
            for ax,t in zip(axes.flat,[18000,36000,54000,72000]):
                row=read(work/f'profile-{t}s.csv')
                ax.plot(row['distance_from_upstream_m']/1000,row['analytical_depth_m'],'k-',label='Translated analytical initial profile')
                ax.plot(row['distance_from_upstream_m']/1000,row['computed_depth_m'],color='#007f87',label='SWMM2D')
                ax.set(title=f'{t/3600:g} hours',xlabel='Distance from upstream (km)',ylabel='Depth (m)',xlim=(0,1000),ylim=(0,10));ax.grid(alpha=.2)
            axes[0,0].legend(fontsize=7);figure=figures/(key+'-profiles.png');save(fig,figure)
            register.append([c['case'],'TR2F Graphs 1–6','Depth profiles at 5/10/15/20 h; paired panels avoid confounding reference and simulation times.',str(figure.relative_to(out))])
        elif key=='e':
            probes=read(work/'probes.csv');fig,axes=plt.subplots(2,2,figsize=(11,7),sharex=True,sharey=True)
            for ax,p in zip(axes.flat,['C0','C25000','C50000','C75000']):
                rows=probes[probes['probe']==p]
                ax.plot(rows['time_s']/3600,rows['level_m'],color='#007f87',label='SWMM2D numerical history')
                ax.set(title=p,xlabel='Elapsed time (hours)',ylabel='Water elevation (m)',xlim=(2,4),ylim=(18.5,22));ax.grid(alpha=.2)
            axes[0,0].legend(fontsize=8);figure=figures/'e-histories.png';save(fig,figure)
            register.append([c['case'],'TR2E Graphs 1–4','Same four gauge positions and 2–4 h window. No unqualified analytical curve is drawn.',str(figure.relative_to(out))])
        if figure:lines+=['',f'![{case["title"]} — independent-reference view]({figure.relative_to(out).as_posix()})','']
        base=m['regression'];lines+=['',f'Own numerical baseline: {base["status"]}. This is change control, separate from reference fit.','']
    # Compare the two measured runs only with the shared laboratory target; no ranking of engines.
    if {'uk-river-l','uk-river-l-fine'}<=completed:
        lines+=['## Laboratory mesh sensitivity','',
            'This is a two-grid diagnostic, not an order-of-convergence estimate. Both grids fit the physical taper walls. Gate opening and gauge sampling remain additional uncertainty sources.','',
            '| Gauge | 0.05 m RMSE (m) | 0.025 m RMSE (m) |','|---|---:|---:|']
        coarse=json.loads((out/'uk-river-l/metrics.json').read_text(encoding='utf-8'))['reference_fit']['metrics']
        fine=json.loads((out/'uk-river-l-fine/metrics.json').read_text(encoding='utf-8'))['reference_fit']['metrics']
        for a,b in zip(coarse,fine):lines.append(f'| {a["probe"]} | {a["rmse_m"]:.6g} | {b["rmse_m"]:.6g} |')
    lines+=['','## Measured bridge targets and remaining coverage','',
        'Test J Table 4.1 supplies measured afflux values of 0.035/0.070 m for the two arch-bridge flows and 0.032/0.062 m for the two flat-soffit flows. They are preserved in the corpus. No SWMM2D bridge result is supplied here: a faithful structure plus paired no-bridge representation is still required. No projected opening or arbitrary point-loss substitute is labelled as the historical test.','',
        'Test E has numerical results but no qualified analytical residuals. The published report identifies a sine/cosine phase conflict, while the analytical linear-friction coefficient depends on an unspecified representative velocity. Neither parameter is fitted here.','',
        'The Test K and Test L result-PDF filenames are swapped; their cover titles and report identifiers determine their identity. The added references do not fill the original numbered 2D Test 6A or Test 8 input/measurement gaps.','',
        'The output register identifies available figure counterparts. Initial solver profiles and the measured laboratory comparison do not replace the source report\'s other diagnostic panels. No blanket claim of identical complete report coverage is made.','']
    repeat=out/'regression-repeat.json'
    if repeat.exists():
        records=json.loads(repeat.read_text(encoding='utf-8'))['cases']
        if {r['case'] for r in records}!=completed:raise ValueError('Repeated-run coverage differs from report coverage')
        lines+=['## Separate numerical repeat','',
            'Each executable configuration was run again against its reviewed numerical anchor, using matching input, analysis, reference and binary identities. This is a repeatability check, separate from the reference residuals above. Cross-platform tolerances remain unqualified.','',
            '| Configuration | Baseline check | Maximum absolute change in saved probe quantities |','|---|---|---:|']
        for row in records:
            if row['assessment_manifest_sha256']!=digest((out/row['case']/'run-manifest.json').read_bytes()) or row['assessment_data_sha256']!=digest((out/row['case']/'extracted.npz').read_bytes()):
                raise ValueError('Assessment changed after repeat evidence attachment')
            lines.append(f'| {row["case"]} | {row["verdict"]} | {row["maximum_absolute_change"]:.9g} |')
        lines+=['','[Repeated-run identity records](regression-repeat.json)','']
    for key,report,quantity in [('j','TR2J Table 4.1','Four measured afflux targets; executable bridge counterpart pending'),('e','TR2E Appendix A','Analytical parameter/phase qualification pending')]:
        register.append(['uk-river-'+key,report,quantity,'unavailable'])
    write_csv(out/'report-output-register.csv',['case','source_output','counterpart_scope','path'],register)
    text='\n'.join(lines).rstrip();(out/'report.md').write_text(text+'\n',encoding='utf-8')
    (out/'report.html').write_text(render(text).replace('<title>UK 2D benchmark evidence</title>','<title>UK river benchmark supplement</title>'),encoding='utf-8')
    return [out/'report.md',out/'report.html']
