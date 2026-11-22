"""Verify observational momentum receipts against independent saved cell momentum."""
from pathlib import Path
import argparse,csv,json
import h5py,numpy as np
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-bank-momentum-2026-10-26'
TERMS=['face','bed','wall_flux','wall_bed','friction','dry','rk_final_dry']
def inspect(name):
 w=O/name;assert json.loads((w/'status.json').read_text(encoding='utf-8'))['state']=='COMPLETE'
 eq=O/('instrumentation-equivalence.json' if name.endswith('30') else 'instrumentation-equivalence-short.json');assert json.loads(eq.read_text(encoding='utf-8'))['status']=='PASS'
 rows=list(csv.DictReader((w/'momentum-ledger.csv').open(encoding='utf-8')));end=json.loads((w/'case.json').read_text(encoding='utf-8'))['end'];assert len(rows)==end*10*6
 assert all(np.isfinite(float(v)) for row in rows for v in row.values())
 g2=next(r['face'] for r in json.loads((w/'probe-map.json').read_text(encoding='utf-8')) if r['id']=='G2');error=[];savederr=[];spliterr=[];stageerr=[];summaries=[];rates=[]
 with h5py.File(w/'surface.h5') as f:
  x=f['Mesh2_face_x'][:];y=f['Mesh2_face_y'][:];area=f['Mesh2_face_area'][:]
  masks=[np.ones(len(x),bool),(x>=1.5)&(x<=4.5),(x>=2.2)&(x<=3.5)&(y>=-1.3)&(y<=1.3),(x>=-.8)&(x<=1.5),(x>=-7.55)&(x<=8)&(abs(y)>1.46),np.arange(len(x))==g2]
  labels=['Whole domain','Building reach x1.5..4.5','G2 box x2.2..3.5,y-1.3..1.3','Gate reach x-.8..1.5','Target bank cells x<=8','G2 containing cell']
  for row in rows:
   i=round(float(row['time_s'])/.1)-1;cv=int(row['cv']);assert abs(float(row['time_s'])-(i+1)*.1)<1e-7
   for d in ['x','y']:
    mom=float(row['momentum_'+d]);error.append(abs(mom-sum(float(row[k+'_'+d]) for k in TERMS)))
    independent=float(np.dot(area[masks[cv]]*f['Mesh2_face_depth'][i][masks[cv]],f['Mesh2_face_v'+d][i][masks[cv]]));savederr.append(abs(mom-independent))
    spliterr.append(abs(float(row['face_'+d])-sum(float(row[k+'_'+d]) for k in ['center_adv','center_pressure','riemann_remainder'])))
    stageerr.append(abs(mom-float(row['stage_delta_'+d])-float(row['rk_final_dry_'+d])))
  for cv,mask in enumerate(masks):
   subset=[r for r in rows if int(r['cv'])==cv];last=subset[-1];summaries.append(dict(cv=cv,description=labels[cv],cell_count=int(mask.sum()),area_m2=float(area[mask].sum()),final={k:float(v) for k,v in last.items()}))
   # One-second windows reduce output-step jitter; term signs follow vector components.
   for start in np.arange(0,end,1):
    stop=start+1;a=None if start==0 else subset[round(start*10)-1];b=subset[round(stop*10)-1]
    row=dict(cv=cv,start_s=float(start),end_s=float(stop))
    for k in TERMS+['momentum','center_adv','center_pressure','riemann_remainder']:
     for d in ['x','y']:
      key=k+'_'+d;row[key]=(float(b[key])-(float(a[key]) if a else 0))/(stop-start)
    rates.append(row)
 result=dict(status='PASS' if max(error)<1e-9 and max(savederr)<1e-11 and max(spliterr)<1e-9 and max(stageerr)<1e-9 else 'FAIL',max_accepted_momentum_residual_m4ps=max(error),max_saved_field_momentum_error_m4ps=max(savederr),max_centered_flux_split_residual_m4ps=max(spliterr),max_stage_reset_residual_m4ps=max(stageerr),control_volumes=summaries,scope='Accounting verification only. Centered advective/pressure split uses hydrostatically reconstructed face states and the same positivity scaling; remainder includes Riemann upwinding, not an independently measured energy loss. Wall flux is reflective Riemann reaction; wall bed correction is separate. Each RK2 Euler receipt carries half weight and final dry reset is counted once.')
 (O/(name+'-ledger-check.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 with (O/(name+'-momentum-rates.csv')).open('w',newline='',encoding='utf-8') as f:wri=csv.DictWriter(f,fieldnames=list(rates[0]));wri.writeheader();wri.writerows(rates)
 assert result['status']=='PASS',result
 print(json.dumps({k:v for k,v in result.items() if k!='control_volumes'},indent=2))
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('case');inspect(p.parse_args().case)
