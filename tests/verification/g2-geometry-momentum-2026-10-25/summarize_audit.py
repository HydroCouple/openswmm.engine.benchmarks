"""Assemble the completed audit and declared diagnostics, with measured-only panels."""
from pathlib import Path
import csv,datetime as dt,hashlib,json,os,shutil,sys
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R));os.chdir(R)
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';B=O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01';L=O.parent/'g2-jump-assessment-2026-10-25/local005'
os.environ.setdefault('MPLCONFIGDIR',str(O/'.plot-cache'))
import h5py,numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.tri import Triangulation
from matplotlib.collections import LineCollection
from suites.uk_2d import render,tin
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def main():
 eq=json.loads((O/'instrumentation-equivalence.json').read_text());assert eq['status']=='PASS'
 momentum=json.loads((O/'momentum-audit.json').read_text());assert momentum['status']=='PASS'
 labels={'frozen30':'Original order 2 / coarse','order1-30':'Native order 1 / coarse','muscl-off-30':'No MUSCL, RK2 / coarse','broad005-30':'Order 2 / broad .05 m','broad005-muscloff-30':'No MUSCL, RK2 / broad .05 m','previous-local':'Order 2 / previous local .05 m'}
 records=[]
 for name,label in labels.items():
  work=L if name=='previous-local' else O/name
  assert json.loads((work/'status.json').read_text())['state']=='COMPLETE'
  metric=json.loads((work/'metrics.json').read_text());assert metric['returncode']==0 and all(metric['checks'].values())
  manifest=json.loads((work/'manifest.json').read_text());assert sha(work/'model.inp')==manifest['input_sha256']
  rows=[r for r in csv.DictReader((work/'probes.csv').open()) if float(r['time_s'])<=30];assert len(rows)==1800
  records.append((name,label,work,metric,rows))
 obs=list(csv.DictReader((B/'reference/observations.csv').open()));spec=json.loads((R/'suites/uk_2d/figure-display-specs.json').read_text())['figures'];figures=['geometry-building-dem-and-normals.png','geometry-gate-and-bank-sections.png','linear-reconstruction-patch.png']
 for quantity,points,source in [('level_m',['G2','G4','G5','G6'],'4.25'),('speed_mps',['G2','G4'],'4.26')]:
  fig,axs=plt.subplots(len(points),1,figsize=(9,2.6*len(points)))
  for ax,point in zip(axs,points):
   for name,label,work,metric,rows in records:
    rr=[r for r in rows if r['probe']==point];ax.plot([float(r['time_s']) for r in rr],[float(r[quantity]) if float(r['depth_m'])>1e-4 else np.nan for r in rr],label=label,lw=1.3)
   rr=[r for r in obs if r['probe']==point and r['quantity']==quantity]
   if rr:ax.scatter([float(r['time_s']) for r in rr],[float(r['value']) for r in rr],marker='D',s=13,facecolors='none',edgecolors='black',label='Recovered UCL measurement subset',zorder=10)
   else:ax.text(.03,.1,'Measured series unavailable',transform=ax.transAxes)
   ax.set(title=point,xlabel='Time (s)',ylabel='Level (m)' if quantity=='level_m' else 'Speed (m/s)');ax.legend(fontsize=7,loc='upper left',bbox_to_anchor=(1.01,1),borderaxespad=0);ax.grid(alpha=.25)
  fig.suptitle(f'Test 6A: geometry audit follow-up, UK Figure {source} panels\n30 s diagnostics; original measured records unavailable');fig.tight_layout()
  stem='audit-uk-'+source.replace('.','-');fig.savefig(O/(stem+'-full-range.png'),dpi=150);figures.append(stem+'-full-range.png')
  for ax,point in zip(axs,points):ax.set(xlim=spec[source]['panels'][point]['xlim'],ylim=spec[source]['panels'][point]['ylim'])
  fig.savefig(O/(stem+'.png'),dpi=150);figures.append(stem+'.png');plt.close(fig)
 fronts=[];states={}
 for name,label,work,metric,rows in records:
  with h5py.File(work/'surface.h5') as f:
   conn=f['Mesh2_face_nodes'][:]-int(f['Mesh2_face_nodes'].attrs.get('start_index',0));tri=Triangulation(f['Mesh2_node_x'][:],f['Mesh2_node_y'][:],conn)
   xs=np.linspace(1.5,4.5,601);ids=tri.get_trifinder()(xs,np.full_like(xs,-.6));assert (ids>=0).all()
   for t in np.arange(1,30.01,.5):
    i=round(t/.1)-1;h=f['Mesh2_face_depth'][i][ids];speed=np.hypot(f['Mesh2_face_vx'][i][ids],f['Mesh2_face_vy'][i][ids]);fr=speed/np.sqrt(9.80665*np.maximum(h,1e-12));cuts=np.flatnonzero((fr[:-1]>=1)&(fr[1:]<1));fronts.append(dict(case=name,time_s=float(t),first_downstream_Fr1_x_m=float((xs[cuts[0]]+xs[cuts[0]+1])/2) if len(cuts) else None))
  rr=min([r for r in rows if r['probe']=='G2'],key=lambda r:abs(float(r['time_s'])-20));states[name]={k:float(v) for k,v in rr.items() if k!='probe'};states[name]['froude']=states[name]['speed_mps']/np.sqrt(9.80665*states[name]['depth_m'])
 # Matched spatial reconstruction comparison at the same two meshes.
 fig,axes=plt.subplots(2,2,figsize=(12,8),layout='constrained')
 names=['frozen30','muscl-off-30','broad005-30','broad005-muscloff-30']
 for ax,name in zip(axes.flat,names):
  label=labels[name]
  with h5py.File(O/name/'surface.h5') as f:
   conn=f['Mesh2_face_nodes'][:]-int(f['Mesh2_face_nodes'].attrs.get('start_index',0));tri=Triangulation(f['Mesh2_node_x'][:],f['Mesh2_node_y'][:],conn);h=f['Mesh2_face_depth'][199];fr=np.hypot(f['Mesh2_face_vx'][199],f['Mesh2_face_vy'][199])/np.sqrt(9.80665*np.maximum(h,1e-12));x=f['Mesh2_face_x'][:];y=f['Mesh2_face_y'][:]
  art=ax.tripcolor(tri,facecolors=h,vmin=0,vmax=.16,cmap='viridis',rasterized=True)
  near=(x>1)&(x<5.5)&(abs(y)<1.5);owners={}
  for cell in np.flatnonzero(near):
   row=conn[cell]
   for a,b in zip(row,np.roll(row,-1)):owners.setdefault(tuple(sorted((int(a),int(b)))),[]).append(cell)
  edges=[[[tri.x[a],tri.y[a]],[tri.x[b],tri.y[b]]] for (a,b),cc in owners.items() if len(cc)==2 and (fr[cc[0]]-1)*(fr[cc[1]]-1)<0]
  ax.add_collection(LineCollection(edges,colors='cyan',linewidths=.8));p=np.array(tin.geometry()['constraints'][0]['points']);ax.fill(p[:,0],p[:,1],color='.65',edgecolor='black');ax.plot(2.65,-.6,'wo',mec='black');ax.annotate('G2',(2.65,-.6),xytext=(2.1,-1.1),color='white',arrowprops={'arrowstyle':'->','color':'white'});ax.set(xlim=(1,5.5),ylim=(-1.5,1.5),aspect='equal',title=label,xlabel='x (m)',ylabel='y (m)')
 fig.colorbar(art,ax=list(axes.flat),label='Depth at 20 s (m)',shrink=.8);fig.suptitle('Spatial reconstruction and refinement: same drawing geometry, bed and RK2\nCyan edges straddle Fr=1; no measured spatial front map');fig.savefig(O/'audit-local-depth-20s.png',dpi=150);figures.append('audit-local-depth-20s.png');plt.close(fig)
 with (O/'front-positions.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=list(fronts[0]));w.writeheader();w.writerows(fronts)
 save(O/'G2-state-20s.json',states)
 fig,ax=plt.subplots(figsize=(9,4.5))
 for name,label,*_ in records:
  rr=[r for r in fronts if r['case']==name];ax.plot([r['time_s'] for r in rr],[r['first_downstream_Fr1_x_m'] for r in rr],label=label)
 ax.axhline(2.65,color='black',ls='--',label='G2');ax.set(title='Sampled critical transition along y=-0.6 m\nCell-constant Fr crossing; no measured front trajectory',xlabel='Time (s)',ylabel='First downstream Fr=1 crossing x (m)');ax.legend(fontsize=8);ax.grid(alpha=.25);fig.tight_layout();fig.savefig(O/'audit-front-position.png',dpi=150);figures.append('audit-front-position.png');plt.close(fig)
 ledger=list(csv.DictReader((O/'audit-enabled-v2/momentum-ledger.csv').open()));fig,axs=plt.subplots(2,1,figsize=(10,7))
 for ax,cv in zip(axs,[1,2]):
  rr=[r for r in ledger if int(r['cv'])==cv];t=[float(r['time_s']) for r in rr]
  for term in ['face','bed','wall','friction','dry','rk_final_dry']:ax.plot(t,[float(r[term+'_x']) for r in rr],label=term)
  ax.plot(t,[float(r['momentum_x']) for r in rr],'k--',label='Accepted x momentum');ax.set(title=momentum['control_volumes'][cv]['description'],xlabel='Time (s)',ylabel='Cumulative x impulse / rho (m⁴/s)');ax.legend(fontsize=8,ncol=3);ax.grid(alpha=.25)
 fig.suptitle('Control-volume momentum accounting, frozen order-2 solver\nFace term includes pressure, transport and numerical dissipation');fig.tight_layout();fig.savefig(O/'momentum-balance.png',dpi=150);figures.append('momentum-balance.png');plt.close(fig)
 summary=[]
 for name,label,work,metric,rows in records:summary.append(dict(name=name,label=label,input_sha256=sha(work/'model.inp'),metrics=metric,diagnostic_duration_s=30))
 save(O/'summary.json',summary)
 lines=['# Test 6A: effective geometry and momentum audit','','All new simulations are explicitly limited to 30 s for diagnosis. They do not replace the canonical 120 s benchmark, its reviewed anchors, or the earlier full-duration controls. No coefficients, gauge positions, geometry or time offsets were fitted.','',
 '## Effective geometry','',
 'An independent reconstruction of the executed cell edges confirms the 1.0 m internal gate opening, the 0.8 by 0.4 m building at 64 degrees, the dimensioned bank planes, and every exterior WALL slot. All actual saved solver normals and lengths agree with geometric reconstruction to roundoff; building normals point into the solid. Constant-pressure normal and first-moment identities pass. This rules out the specific misplaced-boundary or reversed-normal explanations tested here.','',
 'The source DEM differs from that exact drawing representation. At the throat, 19 wet pixels of 0.05 m give a 0.95 m sampled width. Around the building, elevation-threshold pixel areas are 0.405–0.415 m² at 0.02–0.4 m water levels, compared with the 0.32 m² drawing polygon. These are raster diagnostics, not an independent survey of the laboratory walls. The asymmetric raster banks and building halo are recorded without changing the dimensioned geometry or claiming that either representation reproduces the physical experiment better. The post-gate sample window is explicitly truncated and is not reported as the channel width.','',
 '## Gate, initial conditions and output cadence','',
 'The executed throat and adjoining cells have zero bed elevation, without a bed step at the gate. The source DEM wet-throat floor is approximately 0.0000465 m, a negligible vertical offset. AA/CC drawing sections include 0.34 m banks rising 0.155 m inside vertical walls 3.6 m apart; the central flat bed is 2.92 m wide. BB at the throat is rectangular. A rectangular plan view does not imply a flat rectangular cross-section throughout.','',
 'The control initializes depths 0.4 m upstream and 0.02 m downstream; over sloping banks this creates a nonuniform water surface. The preceding full-duration uniform-level control barely changed G2 errors. The assessed 120 s run contains all 1,200 frames at 0.1 s spacing; calendar timestamps lie about 1 ms above the nominal grid, and corresponding accepted-momentum states agree to roundoff. At audit time the protected editable input had a 360 s report interval and omitted the explicit Smagorinsky/Cs=0 configuration used to publish conserved-momentum velocities in these assessed runs. Cs=0 adds no eddy stress; this configuration also selects the qualified global momentum path. The default editable-file output path reconstructs velocity differently. It is therefore not an equivalent replay of these assessed decks. The [archived 120 s executed input](original120/model.inp) is retained for reproduction. The [gate/clock record](gate-clock-followup.json) preserves the distinction.','',
 '## Momentum accounting','',
 f"The audit-disabled, enabled, and original frozen runs have bit-identical saved depth and velocity fields. The 30 s frozen run also reproduces the first 30 s of the archived 120 s control exactly. The ledger separates total numerical interior flux, hydrostatic bed correction, wall reaction, Manning friction, Euler dry resets and the final accepted RK2 dry reset. The first receipt pass omitted that final reset (maximum unexplained momentum 0.000108 m4/s); its incomplete record is retained, and the amended receipts reproduce the original fields bit for bit. Both RK2 Euler stages carry weight 1/2. Maximum accepted-momentum closure residual is {momentum['max_accepted_vs_receipt_residual']:.4g} m4/s; independently reconstructed saved-field momentum differs by at most {momentum['max_independent_saved_field_momentum_error']:.4g} m4/s.",'',
 'The numerical interior-flux term contains pressure, advection and numerical dissipation. Closure establishes that the recorded terms account for the computed momentum; it does not establish that the flow field or jump location is physically correct. Control volumes comprise selected cells with their actual faces, rather than exact rectangular cuts.','',
 'Every exterior solid edge already has a reflecting wall condition. Optional tangential wall drag belongs on intended wet physical walls, not interior triangle edges. The preceding all-wall Cw=.01 sensitivity changed G2 speed RMSE from 0.821976 to 0.818514 m/s and level RMSE from 0.055899 to 0.056692 m, which did not resolve the mismatch.','',
 'The wall calculation uses the depth after interior volume gathering, whereas the interior Riemann flux uses beginning-stage states. Beginning-stage wall forces are retained as a diagnostic counterfactual and are excluded from the accepted ledger. Their differences do not by themselves prove a defect or establish the G2 cause.','',
 '## Reconstruction and coordinated refinement','',
 'The native order-1 option changes spatial reconstruction and RK2 to forward Euler together. It therefore measures combined method-order sensitivity. A separate existing MUSCL-off switch disables spatial reconstruction while retaining RK2 and the same input and mesh, isolating that spatial contribution. The additional broad-mesh MUSCL-off case was declared adaptively after the coarse controls agreed; it tests whether that result persists with refinement. This is explicitly an adaptive follow-up, not an original blind control. The broader .05 m target mesh covers the whole reservoir, constriction, gate and building through x=8 m with a 2 m graded transition to .1 m background. Its 91,420 cells pass the same exact drawing and connectivity audit. Manning n=.01, Coriolis OFF, Cs=0, free-slip walls and original uniform-depth initial conditions remain fixed. The previous local .05 m mesh is shown for context using its first 30 s; its run completed 120 s.','',
 'An independent offline patch audit reproduces the frozen fully-wet Green–Gauss formula for exact linear scalar fields x and y. Constant fields cancel to roundoff, but the gradient matrix is not identity in every fully interior flat-bed TIN cell. In the building reach, the 95th-percentile matrix error is about 0.244 on the control mesh and 0.254 on the broader mesh (dimensionless Frobenius norms). The G2 containing cell itself is nearly linear-exact. Boundary and shoreline cells are excluded. This identifies an operator-consistency limitation for follow-up; it is not a native solver patch test or proof that this limitation causes the G2 error. The [linear-field audit](linear-reconstruction-audit.json) preserves the formula source identity and independent computation.','',
 'The gauge plots reproduce the panels and axis ranges of UK Figures 4.25 and 4.26, with additional full-range views. The source is the [Environment Agency SC120002/R report](https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf); geometry follows Figure (a) of the bundled May 2010 Test 6 specification.','',
 'Comparisons use only the visibility-selected recovered UCL measurement markers. Original full measured records and independent second-person digitization review remain unavailable. RMSE retains the same segmented time weights and excludes gaps longer than 1 s. These diagnostics do not establish convergence or select a model by one gauge.','',
 '| Configuration | G2 level RMSE (m) | G2 speed RMSE (m/s) | G4 speed RMSE (m/s) | G5 level RMSE (m) |','|---|---:|---:|---:|---:|']
 for name,label,work,metric,rows in records:
  vals={(r['probe'],r['quantity']):r['rmse'] for r in metric['observed']['metrics']};lines.append('| '+label+' | '+' | '.join(f'{vals[k]:.6g}' for k in [('G2','level_m'),('G2','speed_mps'),('G4','speed_mps'),('G5','level_m')])+' |')
 for name in figures:lines+=['',f'![Test 6A audit: {name}]({name})']
 lines+=['','## Executed inputs and histories','']
 for name,label,work,*_ in records:lines.append(f"- {label}: [input]({name}/model.inp), [probe history]({name}/probes.csv), [metrics]({name}/metrics.json), [identity]({name}/manifest.json).")
 interpretation=json.loads((O/'interpretation.json').read_text());lines+=['','## Interpretation','',interpretation['finding'],'',interpretation['qualification'],'','## Next engineering checks','']+[f"{i}. {item}" for i,item in enumerate(interpretation['next_priorities'],1)]+['','[Geometry checks](geometry-audit.json). [Momentum checks](momentum-audit.json). [Non-perturbation checks](instrumentation-equivalence.json). [Case summary](summary.json). [Front samples](front-positions.csv). [G2 states at 20 s](G2-state-20s.json). [Report identity](report-provenance.json).']
 (O/'report.html').write_text(render.render('\n'.join(lines)+'\n'))
 save(O/'report-provenance.json',dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),figures=figures,figure_sha256={n:sha(O/n) for n in figures},cases={name:sha(work/'model.inp') for name,label,work,*_ in records},geometry_sha256=sha(O/'geometry-audit.json'),momentum_sha256=sha(O/'momentum-audit.json'),equivalence_sha256=sha(O/'instrumentation-equivalence.json'),interpretation_sha256=sha(O/'interpretation.json'),report_sha256=sha(O/'report.html'),script_sha256=sha(__file__)))
 print(json.dumps(states,indent=2))
if __name__=='__main__':main()
