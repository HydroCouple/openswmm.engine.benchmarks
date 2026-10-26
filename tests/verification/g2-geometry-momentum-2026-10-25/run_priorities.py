"""Same-mesh order control followed by coordinated broad refinement, 30 s only."""
from pathlib import Path
import concurrent.futures,csv,datetime as dt,hashlib,json,os,re,shutil,subprocess,sys,time
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R));os.chdir(R)
from harness import engines
from suites.uk_2d import tin,sampling,checks,observations
from suites.uk_2d.wall_sensitivity import solid_groups
import numpy as np
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';B=O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01';X=B.parent/'pinned-clock/bin/openswmm'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def section(text,name):return re.search(r'\['+name+r'\]([\s\S]*?)(?=\n\[|\Z)',text)[1].strip()
def replace(text,name,rows):return re.sub(r'\['+name+r'\][\s\S]*?(?=\n\[|\Z)','['+name+']\n'+'\n'.join(rows)+'\n',text)
def run(name):
 assert json.loads((O/'momentum-audit.json').read_text())['status']=='PASS','Momentum audit first'
 w=O/name;assert not w.exists();w.mkdir();original=(B/'model.inp').read_text();text,n=re.subn(r'^END_TIME\s+.*$','END_TIME 00:00:30',original,flags=re.M);assert n==1
 case=json.loads((B/'case.json').read_text());factor={}
 if name=='order1-30':
  text,n=re.subn(r'^RECONSTRUCTION_ORDER\s+.*$','RECONSTRUCTION_ORDER 1',text,flags=re.M);assert n==1
  assert re.sub(r'^RECONSTRUCTION_ORDER\s+.*$','RECONSTRUCTION_ORDER 2',text,flags=re.M)==re.sub(r'^END_TIME\s+.*$','END_TIME 00:00:30',original,flags=re.M)
  factor=dict(only_change='Reconstruction order 2 to 1, plus declared duration 120 to 30 s')
 elif name=='muscl-off-30':
  factor=dict(only_change='Disable MUSCL spatial reconstruction by OPENSWMM_2D_MUSCL_OFF=1; retain native order 2 and RK2, plus duration 120 to 30 s')
 elif name in ['broad005-30','broad005-muscloff-30']:
  meshdir=O/'broad-mesh';v=np.load(meshdir/'mesh.npz')['vertices'];c=np.load(meshdir/'mesh.npz')['cells'];request=json.loads((meshdir/'mesh-request.json').read_text());audit,walls=tin.audit(v,c,request)
  text=replace(text,'2D_VERTICES',[' '.join(f'{a:.17g}' for a in row) for row in v])
  depth=np.where(v[c,0].mean(1)<0,.4,.02)
  text=replace(text,'2D_TRIANGLES',[f'{a} {b} {d} .01 {h:.17g}' for (a,b,d),h in zip(c,depth)])
  groups=solid_groups(text,1);text=replace(text,'2D_BOUNDARY_CONDITIONS',[f"{r['cell']} {r['edge']} WALL * * {g}" for g,rows in groups.items() for r in rows])
  for sec in ['TITLE','JUNCTIONS','OUTFALLS','CONDUITS','XSECTIONS','REPORT','2D_OPTIONS']:assert section(original,sec)==section(text,sec),sec
  case.update(cell_count=len(c),initial_volume_m3=float(tin.areas(v,c)@depth));shutil.copy2(meshdir/'mesh-provenance.json',w/'mesh-provenance.json')
  factor=dict(only_change='Broader .05 m constrained mesh, same exact drawing/terrain/depth/roughness, plus duration 120 to 30 s',mesh_audit=audit)
 else:raise ValueError(name)
 (w/'model.inp').write_text(text);case.update(id=name,end=30,model_sha256=sha(w/'model.inp'));case['deviations']+=['Declared 30 s diagnostic, not canonical or full qualification.'];save(w/'case.json',case)
 shutil.copy2(B/'probe-locations.csv',w/'probe-locations.csv');shutil.copytree(B/'reference',w/'reference');shutil.copy2(__file__,w/'driver.py')
 lib=X.parent.parent/'engine/libopenswmm.engine.6.0.0.dylib'
 if name=='broad005-muscloff-30':factor['additional_change']='Disable MUSCL spatial reconstruction, retain RK2; paired with broad005-30'
 manifest=dict(input_sha256=sha(w/'model.inp'),executable_sha256=sha(X),library_sha256=sha(lib),driver_sha256=sha(__file__),control_input_sha256=sha(B/'model.inp'),observations_sha256=sha(w/'reference/observations.csv'),factor_audit=factor)
 save(w/'manifest.json',manifest);started=time.monotonic()
 env=engines.env(1,[str(X.parent),str(lib.parent)])
 env.pop('OPENSWMM_2D_MUSCL_OFF',None)
 env.pop('OPENSWMM_G2_MOMENTUM_AUDIT',None)
 if name in ['muscl-off-30','broad005-muscloff-30']:env['OPENSWMM_2D_MUSCL_OFF']='1'
 manifest['environment_overrides']={'OPENSWMM_2D_MUSCL_OFF':'1'} if name in ['muscl-off-30','broad005-muscloff-30'] else {}
 save(w/'manifest.json',manifest)
 with (w/'process.log').open('w') as f:
  p=subprocess.Popen([str(X),str(w/'model.inp'),str(w/'model.rpt'),str(w/'model.out')],cwd=w,env=env,stdout=f,stderr=subprocess.STDOUT)
  save(w/'status.json',dict(state='RUNNING',pid=p.pid,driver_pid=os.getpid(),started_utc=dt.datetime.now(dt.timezone.utc).isoformat()));code=p.wait(timeout=7200)
 assert code==0 and sha(X)==manifest['executable_sha256'] and sha(lib)==manifest['library_sha256']
 probes=list(csv.DictReader((w/'probe-locations.csv').open()));data=sampling.extract(w/'surface.h5',case,probes,w)
 result=dict(case=name,returncode=code,wall_s=time.monotonic()-started,**checks.numerical(case,data));assert all(result['checks'].values())
 result['observed']=observations.compare(w/'reference',case,data['times'],data['values'],probes)
 save(w/'metrics.json',result);np.savez_compressed(w/'extracted.npz',times=data['times'],values=data['values']);save(w/'status.json',dict(state='COMPLETE',checks=result['checks']));print(name,'COMPLETE',result['wall_s'],flush=True)
if __name__=='__main__':
 # Preserve requested order: same-mesh reconstruction first, broader mesh second.
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(run,['order1-30','muscl-off-30']))
 run('broad005-30')
