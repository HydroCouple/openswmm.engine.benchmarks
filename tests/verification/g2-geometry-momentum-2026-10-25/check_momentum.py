"""Independent frozen-field equivalence and control-volume receipt checks."""
from pathlib import Path
import csv,hashlib,json,os,sys
R=Path(__file__).resolve().parents[3];os.chdir(R)
import h5py,numpy as np
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';B=O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01'
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def compare(a,b):
 result={}
 with h5py.File(a/'surface.h5') as f,h5py.File(b/'surface.h5') as g:
  for key in ['Mesh2_face_depth','Mesh2_face_vx','Mesh2_face_vy']:
   n=min(f[key].shape[0],g[key].shape[0]);maximum=0;changed=0
   for i in range(n):
    x=f[key][i];y=g[key][i];maximum=max(maximum,float(np.max(abs(x-y))));changed+=int(np.count_nonzero(x!=y))
   result[key]=dict(frames=n,max_absolute_difference=maximum,changed_values=changed)
 return dict(bit_identical=all(v['changed_values']==0 for v in result.values()),fields=result)
def main():
 for name in ['frozen30','audit-disabled','audit-enabled','audit-enabled-v2']:
  assert json.loads((O/name/'status.json').read_text(encoding='utf-8'))['state']=='COMPLETE',name
 equivalence={}
 for label,a,b in [('short_vs_archived120',O/'frozen30',B),('audit_disabled_vs_frozen',O/'audit-disabled',O/'frozen30'),('audit_enabled_vs_disabled',O/'audit-enabled',O/'audit-disabled'),('final_reset_receipt_vs_original_enabled',O/'audit-enabled-v2',O/'audit-enabled')]:equivalence[label]=compare(a,b)
 equivalence['status']='PASS' if all(v['bit_identical'] for v in equivalence.values()) else 'FAIL'
 save(O/'instrumentation-equivalence.json',equivalence)
 assert equivalence['status']=='PASS','Instrumentation equivalence failed; no ledger interpretation authorized'
 rows=list(csv.DictReader((O/'audit-enabled-v2/momentum-ledger.csv').open(encoding='utf-8')));assert len(rows)==1200,len(rows)
 assert all(np.isfinite(float(v)) for row in rows for v in row.values()),'Nonfinite momentum receipt'
 residual=[];momerr=[];summaries=[]
 with h5py.File(O/'audit-enabled-v2/surface.h5') as f:
  x=f['Mesh2_face_x'][:];y=f['Mesh2_face_y'][:];a=f['Mesh2_face_area'][:]
  masks=[np.ones(len(x),bool),(x>=1.5)&(x<=4.5),(x>=2.2)&(x<=3.5)&(y>=-1.3)&(y<=1.3),np.arange(len(x))==19081]
  for row in rows:
   cv=int(row['cv']);t=float(row['time_s']);i=round(t/.1)-1;assert abs(t-(i+1)*.1)<1e-7
   h=f['Mesh2_face_depth'][i][masks[cv]]
   independent=[float(np.dot(a[masks[cv]]*h,f['Mesh2_face_v'+d][i][masks[cv]])) for d in ['x','y']]
   for j,d in enumerate(['x','y']):
    actual=float(row['momentum_'+d]);terms=sum(float(row[k+'_'+d]) for k in ['face','bed','wall','friction','dry','rk_final_dry'])
    residual.append(abs(actual-terms));momerr.append(abs(actual-independent[j]))
  for cv,mask in enumerate(masks):
   rec=[r for r in rows if int(r['cv'])==cv];last=rec[-1];entry=dict(cv=cv,description=['Whole fluid mesh','Building reach: centroid x in [1.5,4.5], all y','G2/jump: centroid x in [2.2,3.5], y in [-1.3,1.3]','G2 containing cell 19081'][cv],cell_count=int(mask.sum()),area_m2=float(a[mask].sum()),final_cumulative={k:float(v) for k,v in last.items() if k not in ['time_s','cv']})
   entry['max_stage_vs_receipt_residual']=max(abs(float(r['stage_delta_'+d])-sum(float(r[k+'_'+d]) for k in ['face','bed','wall','friction','dry'])) for r in rec for d in ['x','y'])
   entry['max_accepted_vs_stages_and_final_reset_residual']=max(abs(float(r['momentum_'+d])-float(r['stage_delta_'+d])-float(r['rk_final_dry_'+d])) for r in rec for d in ['x','y'])
   summaries.append(entry)
 result=dict(status='PASS' if max(residual)<1e-9 and max(momerr)<1e-11 else 'UNRESOLVED',units='Momentum/rho and impulse/rho: m4/s',max_accepted_vs_receipt_residual=max(residual),max_independent_saved_field_momentum_error=max(momerr),control_volumes=summaries,qualification='Receipt closure tests accounting, not physical accuracy. Face term includes numerical momentum transport, pressure and numerical diffusion; bed correction separated. Beginning-state wall force is a diagnostic counterfactual, excluded from the physical ledger. Euler-stage receipts include 1/2 weights for both RK2 stages; the final accepted dry reset is counted once. CV boundaries follow selected-cell faces, not ideal rectangular cuts.')
 save(O/'momentum-audit.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
