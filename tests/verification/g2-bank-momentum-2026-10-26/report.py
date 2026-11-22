"""Generate only from completed cases and verified, nonperturbing receipts."""
from pathlib import Path
import csv,hashlib,html,json,os,shutil,sys
import numpy as np
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-bank-momentum-2026-10-26';W=Path(__file__).parent
os.environ.setdefault('MPLCONFIGDIR',str(O/'mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import h5py
from front import inspect
read=lambda p:json.loads(Path(p).read_text(encoding='utf-8'))
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,indent=2,allow_nan=False)+'\n',encoding='utf-8')
CASES={'coarse':R/'results/uk_2d/g2-reconstruction-2026-10-25/clean-combined','bank005':O/'bank005','bank0025':O/'bank0025','broad005':R/'results/uk_2d/g2-reconstruction-2026-10-25/clean-broad005-30'}
LABELS={'coarse':'Corrected / original mesh','bank005':'Banks 0.05 m','bank0025':'Banks 0.025 m','broad005':'Broad 0.05 m (previous)'}
COLORS={'coarse':'#555555','bank005':'#007c91','bank0025':'#c75146','broad005':'#8a63b8'}
def table(headers,rows):return '<table><thead><tr>'+''.join('<th>'+html.escape(str(v))+'</th>' for v in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(v))+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table>'
def main():
 assert read(O/'instrumentation-equivalence.json')['status']=='PASS'
 ledger=read(O/'audit-enabled-30-ledger-check.json');assert ledger['status']=='PASS'
 records={};fronts={};hashes=set()
 for name,root in CASES.items():
  assert read(root/'status.json')['state']=='COMPLETE',name
  metrics=read(root/'metrics.json');assert metrics['returncode']==0 and all(metrics['checks'].values())
  rows=list(csv.DictReader((root/'probes.csv').open(encoding='utf-8')));assert len(rows)==1800 and float(rows[-1]['time_s'])==30
  assert sha(root/'model.inp')==read(root/'manifest.json')['input_sha256']
  hashes.add(sha(root/'reference/observations.csv'))
  records[name]=dict(label=LABELS[name],metrics=metrics,rows=rows,source=str(root));fronts[name]=inspect(name,root)
 assert len(hashes)==1
 design=read(O/'design.json');assert sha(R/'corpus/uk-ea-2d/uk-ea-2013-t6a/model.inp')==design['protected_input_sha256']
 source=O/'source';source.mkdir(exist_ok=True)
 for p in W.iterdir():
  if p.suffix in ['.py','.md']:shutil.copy2(p,source/p.name)
 # Thin control archives retain exact executed inputs and same reference subset.
 for name,root in CASES.items():
  dest=O/'cases'/name;dest.mkdir(parents=True,exist_ok=True)
  for filename in ['model.inp','case.json','manifest.json','metrics.json','probes.csv','probe-locations.csv','probe-map.json','volume.csv','status.json','process.log']:
   if (root/filename).is_file():shutil.copy2(root/filename,dest/filename)
  shutil.copytree(root/'reference',dest/'reference',dirs_exist_ok=True)
 obs=list(csv.DictReader((CASES['coarse']/'reference/observations.csv').open(encoding='utf-8')));display=read(R/'suites/uk_2d/figure-display-specs.json')['figures'];figures=[]
 for quantity,points,number in [('level_m',['G2','G4','G5','G6'],'4.25'),('speed_mps',['G2','G4'],'4.26')]:
  fig,axes=plt.subplots(len(points),1,figsize=(10,2.7*len(points)))
  for ax,point in zip(axes,points):
   for name,rec in records.items():
    rows=[r for r in rec['rows'] if r['probe']==point];ax.plot([float(r['time_s']) for r in rows],[float(r[quantity]) if float(r['depth_m'])>1e-4 else np.nan for r in rows],label=LABELS[name],color=COLORS[name],lw=1.3)
   rows=[r for r in obs if r['probe']==point and r['quantity']==quantity]
   if rows:ax.scatter([float(r['time_s']) for r in rows],[float(r['value']) for r in rows],s=13,marker='D',facecolors='none',edgecolors='black',label='Recovered UCL subset',zorder=10)
   else:ax.text(.02,.1,'Measured series unavailable',transform=ax.transAxes)
   ax.set(title=point,xlabel='Time (s)',ylabel='Level (m)' if quantity=='level_m' else 'Speed (m/s)');ax.grid(alpha=.2);ax.legend(fontsize=7,loc='upper left',bbox_to_anchor=(1.01,1),borderaxespad=0)
  fig.suptitle('Test 6A: bank refinement, UK Figure '+number+' panels\nFixed physics and drawing geometry; all curves end at 30 s');fig.tight_layout()
  stem='bank-uk-'+number.replace('.','-');fig.savefig(O/(stem+'-full-range.png'),dpi=150);figures.append(stem+'-full-range.png')
  for ax,point in zip(axes,points):ax.set(xlim=display[number]['panels'][point]['xlim'],ylim=display[number]['panels'][point]['ylim'])
  fig.savefig(O/(stem+'.png'),dpi=150);figures.append(stem+'.png');plt.close(fig)
 fig,axs=plt.subplots(2,1,figsize=(10,7),layout='constrained')
 for name,rows in fronts.items():
  good=[r for r in rows if r['valid']];axs[0].plot([r['time_s'] for r in good],[r['front_x_at_G2_y_m'] for r in good],label=LABELS[name],color=COLORS[name]);axs[1].plot([r['time_s'] for r in good],[r['up_normal_Fr_stationary'] for r in good],color=COLORS[name]);axs[1].plot([r['time_s'] for r in good],[r['down_normal_Fr_stationary'] for r in good],'--',color=COLORS[name])
 axs[0].axhline(2.65,color='black',ls=':',label='G2 x');axs[0].set(ylabel='Depth-gradient front x at y=-0.6 m',title='Local fitted front; no measured spatial front map');axs[0].legend(fontsize=8)
 axs[1].axhline(1,color='black',ls=':');axs[1].set(xlabel='Time (s)',ylabel='Normal Froude number, stationary frame',title='Solid: 0.10 m upstream; dashed: 0.10 m downstream');fig.savefig(O/'front-history.png',dpi=160);plt.close(fig);figures.append('front-history.png')
 rates=list(csv.DictReader((O/'audit-enabled-30-momentum-rates.csv').open(encoding='utf-8')))
 fig,axs=plt.subplots(2,1,figsize=(11,7),layout='constrained')
 for ax,cv,title in zip(axs,[1,2],['Building reach','G2 control volume']):
  rows=[r for r in rates if int(r['cv'])==cv];t=[(float(r['start_s'])+float(r['end_s']))/2 for r in rows]
  for term,label in [('face','Numerical face flux'),('bed','Interior bed source'),('wall_flux','Wall reaction'),('wall_bed','Wall bed source'),('friction','Manning friction'),('dry','Euler dry reset'),('rk_final_dry','Final RK dry reset'),('momentum','Accepted momentum rate')]:ax.plot(t,[float(r[term+'_x']) for r in rows],label=label,lw=1.2,ls='--' if term=='momentum' else '-')
  ax.set(title=title+': x-momentum receipts',ylabel='Force / density (m⁴/s²)',xlabel='Time (s)');ax.legend(fontsize=7,loc='upper left',bbox_to_anchor=(1.01,1));ax.grid(alpha=.2)
 fig.savefig(O/'momentum-budget.png',dpi=160);plt.close(fig);figures.append('momentum-budget.png')
 # Independent stored mechanical energy: diagnostic, not an extra acceptance threshold.
 energy={}
 for name,root in CASES.items():
  with h5py.File(root/'surface.h5') as f:
   area=f['Mesh2_face_area'][:];bed=f['Mesh2_face_z'][:];x=f['Mesh2_face_x'][:];h0=np.where(x<0,.4,.02);E0=float(area@(9.80665*(.5*h0*h0+bed*h0)));maximum=0.;minimum=1e100
   for i in range(300):
    h=f['Mesh2_face_depth'][i];u=f['Mesh2_face_vx'][i];v=f['Mesh2_face_vy'][i];E=float(area@(.5*h*(u*u+v*v)+9.80665*(.5*h*h+bed*h)));maximum=max(maximum,E);minimum=min(minimum,E)
   energy[name]=dict(initial_energy_over_density_m5ps2=E0,max_saved_ratio=maximum/E0,final_ratio=E/E0,scope='Discrete flat-cell mechanical energy at saved times; no independent energy-equation closure or unsaved extrema claim')
 save(O/'energy.json',energy)
 def rmse(name,probe,quantity):return next(m['rmse'] for m in records[name]['metrics']['observed']['metrics'] if m['probe']==probe and m['quantity']==quantity)
 metrics_table=table(['Case','G2 level (m)','G2 speed (m/s)','G4 level (m)','G4 speed (m/s)','G5 level (m)'],[[LABELS[name]]+[f'{rmse(name,p,q):.6f}' for p,q in [('G2','level_m'),('G2','speed_mps'),('G4','level_m'),('G4','speed_mps'),('G5','level_m')]] for name in CASES])
 front20={name:next(r for r in rows if r['time_s']==20) for name,rows in fronts.items()};assert all(r['valid'] for r in front20.values());save(O/'front-at-20s.json',front20)
 front_table=table(['Case','Front x (m)','Fit RMS (m)','Upstream normal Fr','Downstream normal Fr'],[[LABELS[name],f"{row['front_x_at_G2_y_m']:.4f}",f"{row['fit_rms_m']:.4f}",f"{row['up_normal_Fr_stationary']:.3f}",f"{row['down_normal_Fr_stationary']:.3f}"] for name,row in front20.items()])
 # Interpretation is reviewed separately after all results exist.
 interpretation=read(O/'interpretation.json');assert interpretation['reviewed'] is True
 summary=dict(state='COMPLETE',cases={name:dict(label=LABELS[name],duration_s=30,metrics=records[name]['metrics']) for name in CASES},audit_equivalence=read(O/'instrumentation-equivalence.json'),momentum_audit=ledger,front_at_20s=front20,energy=energy,interpretation=interpretation,observations_sha256=next(iter(hashes)),protected_input_sha256=design['protected_input_sha256']);save(O/'summary.json',summary)
 body=f'''<h1>Test 6A: targeted bank resolution and corrected momentum audit</h1><p>26 October 2026 · Completed 30-second diagnostic study</p><p class="finding">{html.escape(interpretation['finding'])}</p><h2>Controlled comparison</h2><p>The corrected coarse mesh is compared with two GUI-constrained meshes refining only the bank strips and their 0.4 m graded transitions, through the reservoir and downstream to x=8 m. Targets are 0.05 and 0.025 m; the background target stays 0.10 m. Existing bank toes, outer-wall crests, internal gate and rotated building constraints are retained. The previous broad 0.05 m mesh is context for refinement across the entire flume width. All four cases use the same corrected solver and recovered observations.</p><p>FLAT cell closure and MEAN face mode remain the defaults. Full SWE, order 2, global RK2 via Cs=0, CFL 0.4, n=0.01, zero wall drag and Coriolis OFF remain fixed. Initial depths are 0.4 m upstream and 0.02 m downstream, including banks. Area remains 354 m² and initial volume 16.618 m³. New meshes have 71,946 and 98,224 cells versus 61,642 in the coarse mesh. They are regenerated and not strictly nested: neighboring triangulation may change. No dimensions, coefficients or observation timing were fitted.</p><p>Each new case completes 30 s / 300 frames and passes depth, continuity and independent-volume checks. This is a diagnostic comparison covering the recovered observation window, not a new 120 s qualification. Original inputs and regression anchors are unchanged.</p><h2>Effective bank geometry</h2><p>For each mesh, independent horizontal cuts compare the cell-centred flat-bed wetted area with the exact drawing section. Away from the throat, its flat base is 2.92 m wide and each bank rises 0.155 m over 0.34 m. At a uniform stage η ≤ 0.155 m, exact wetted area is 2.92η+η²/(0.155/0.34). At the throat the section is 1 m wide and rectangular.</p><p>The 95th-percentile bed relief of target bank cells falls from 0.04313 m to 0.02444 m and 0.01234 m. At G2 and stage 0.02 m, cross-section area errors are −0.170%, −0.0805%, −0.1137% respectively; the broad 0.05 m mesh gives −0.0419%. Pointwise cut error is not monotonic and does not establish convergence. These uniform-stage diagnostics are not the actual transient water surface or a direct face-flux calculation.</p><img src="cross-section-errors.png" alt="Exact versus cell-centred wetted cross-section area"><h2>Measured-subset comparison</h2><p>RMSE uses the unchanged visibility-selected recovered UCL measurement markers and time weights. No other model outputs are plotted. Original complete measurement records and independent digitization review remain outstanding. G6 measured levels remain unavailable.</p>{metrics_table}<img src="bank-uk-4-25.png" alt="UK Figure 4.25 level panels with original axes"><p><a href="bank-uk-4-25-full-range.png">Level panels over the full simulated 30 s range</a></p><img src="bank-uk-4-26.png" alt="UK Figure 4.26 velocity panels with original axes"><p><a href="bank-uk-4-26-full-range.png">Speed panels with unconstrained vertical display range</a></p><h2>Front orientation and normal flow</h2><p>A local front is detected from the strongest rising depth gradient, independently of the Froude-number threshold: a 0.005 m sample grid, Gaussian smoothing σ = 0.02 m, search x = 2.2–3.5 m over y = −0.8 to −0.4 m, and a robust line fit. Four synthetic tests check detection, orientation, translation and rejection. This differs from the previous cell-constant Fr=1 crossing; positions from the two methods must not be mixed.</p>{front_table}<p>G2 is at x = 2.65 m, y = −0.6 m. Normal-flow states average a short tangent band 0.10 m on each side. Their Froude numbers confirm whether the sampled front separates supercritical and subcritical normal flow. They are not measurements, and unsteadiness, curvature, transverse flow and sampling distance preclude interpreting their 1D jump residual as a conservation failure. Estimated front speed and frame-relative mass, momentum and specific energy are retained in the JSON records with this limitation.</p><img src="front-history.png" alt="Local front positions and upstream/downstream normal Froude histories"><div class="grid">'''+''.join(f'<div><img src="{name}-front-20s.png" alt="{html.escape(LABELS[name])} front at 20 s"></div>' for name in CASES)+f'''</div><h2>Does the corrected momentum balance close?</h2><p>Instrumentation is confined to a separate frozen corrected source copy. Enabled and disabled 1 s outputs match each other and the original corrected run bit for bit. The complete instrumented 30 s run also matches all 300 depth and velocity frames exactly. It cannot explain an apparent discrepancy by changing the solution being observed.</p><p>Six control volumes cover the entire model, building reach, G2 neighborhood, gate reach, bank strips and G2 containing cell. Receipts retain numerical interior flux, interior bed correction, reflective-wall Riemann reaction, wall bed correction, Manning friction, Euler dry reset and final accepted RK2 dry reset. Both Euler-stage receipts carry half weight. Maximum accepted-momentum closure residual is {ledger['max_accepted_momentum_residual_m4ps']:.4g} m⁴/s; independently reconstructed saved momentum differs by at most {ledger['max_saved_field_momentum_error_m4ps']:.4g} m⁴/s.</p><p>{html.escape(interpretation['momentum'])}</p><img src="momentum-budget.png" alt="One-second x-momentum receipt rates"><p>The face flux is additionally split into a centred physical advective reference, centred hydrostatic pressure and a Riemann remainder. This is a defined diagnostic decomposition, not a unique separation of numerical dissipation or a measurement of physical turbulence. Saved mechanical energy is computed independently from depth, velocity and bed; it is not an energy-equation ledger.</p><h2>Practical implication</h2><p>{html.escape(interpretation['next'])}</p><p>This study follows the practical FLAT/MEAN path. The earlier dry-ridge result identifies unresolved sub-cell geometry but does not prove a cause for G2 or make a full VFR rewrite a prerequisite to this diagnosis. No product solver change, fitted wall drag or baseline promotion results from the present study.</p><h2>Evidence and reproduction</h2><p><a href="summary.json">Complete summary</a> · <a href="design.json">Declared study</a> · <a href="instrumentation-equivalence.json">Full field equivalence</a> · <a href="audit-enabled-30-ledger-check.json">Momentum closure</a> · <a href="audit-enabled-30/momentum-ledger.csv">Raw cumulative receipts</a> · <a href="audit-enabled-30-momentum-rates.csv">One-second rates</a> · <a href="momentum-receipts.patch">Observational source patch</a> · <a href="instrumentation.json">Source identities</a> · <a href="mesh-resolution.csv">Mesh resolution</a> · <a href="cross-sections.csv">Cross-sections</a> · <a href="stage-volumes.csv">Stage-storage curves</a> · <a href="front-at-20s.json">Front states</a> · <a href="energy.json">Energy diagnostic</a></p>'''
 for name in CASES:body+=f'<p>{html.escape(LABELS[name])}: <a href="cases/{name}/model.inp">executed input</a> · <a href="cases/{name}/manifest.json">identity</a> · <a href="cases/{name}/metrics.json">all metrics</a> · <a href="cases/{name}/probes.csv">gauges</a> · <a href="{name}-front.json">normal-flow diagnostic</a></p>'
 body+='<p><a href="source/README.md">Reproduction prerequisites and sequence</a>. Scripts: '+ ' · '.join(f'<a href="source/{p.name}">{p.name}</a>' for p in sorted(source.glob('*.py')))+'. Raw HDF5, compiled images and isolated source/build trees remain local. The earlier unrelated porewater test failure is unchanged; no new general engine-suite pass is claimed.</p>'
 (O/'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Test 6A bank resolution and momentum audit</title><style>body{max-width:1120px;margin:48px auto;padding:0 24px;font:17px/1.6 system-ui;color:#193042;background:#fafcfd}h1{line-height:1.15}h2{margin-top:2em;color:#075969}.finding{padding:20px;background:#e5f1f4;border-left:5px solid #007c91}table{width:100%;border-collapse:collapse;font-size:14px}th,td{border-bottom:1px solid #cbd8df;padding:9px;text-align:left}img{width:100%;height:auto;margin:14px 0}a{color:#006b86}.grid{display:grid;grid-template-columns:1fr;gap:8px}</style><main>'+body+'</main></html>',encoding='utf-8')
 files=['report.html','summary.json','design.json','instrumentation.json','momentum-receipts.patch','instrumentation-equivalence-short.json','instrumentation-equivalence.json','audit-enabled-1-ledger-check.json','audit-enabled-30-ledger-check.json','audit-enabled-30-momentum-rates.csv','audit-enabled-30/momentum-ledger.csv','audit-enabled-30/manifest.json','audit-enabled-30/status.json','audit-enabled-30/metrics.json','mesh-resolution.csv','cross-sections.csv','stage-volumes.csv','front-at-20s.json','front-tests.log','energy.json','interpretation.json','cross-section-errors.png']+figures
 files += [name+'-front.json' for name in CASES]+[name+'-front-20s.png' for name in CASES]
 files += [str(p.relative_to(O)) for directory in [O/'cases',O/'source'] for p in directory.rglob('*') if p.is_file()]
 for name in ['bank005','bank0025']:files += [name+'/mesh/'+p for p in ['mesh-request.json','mesh-provenance.json']]
 save(O/'publication-manifest.json',dict(state='COMPLETE',qualification='Fixed-physics bank study and nonperturbing momentum audit',files={name:sha(O/name) for name in sorted(set(files))}))
 print('Report assembled with',len(set(files)),'sealed artifacts')
if __name__=='__main__':main()
