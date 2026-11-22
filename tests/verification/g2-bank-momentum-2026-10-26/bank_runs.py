"""Declared bank-only refinement with immutable corrected engine and GUI mesher."""
from pathlib import Path
import concurrent.futures as cf,csv,datetime,hashlib,json,os,re,shutil,subprocess,sys,time
import numpy as np
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R))
from suites.uk_2d import tin,sampling,checks,observations
from suites.uk_2d.wall_sensitivity import solid_groups
from harness import engines
O=R/'results/uk_2d/g2-bank-momentum-2026-10-26'
B=R/'results/uk_2d/g2-reconstruction-2026-10-25/clean-combined'
PIN=B.parent/'pinned-clean';X=PIN/'bin/openswmm';LIB=PIN/'engine/libopenswmm.engine.6.0.0.dylib'
M=R/'tests/verification/g2-diagnosis-2026-10-25/mesher-build/uk_gui_mesher'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def section(text,name):return re.search(r'\['+name+r'\]([\s\S]*?)(?=\n\[|\Z)',text)[1].strip()
def replace(text,name,rows):return re.sub(r'\['+name+r'\][\s\S]*?(?=\n\[|\Z)','['+name+']\n'+'\n'.join(rows)+'\n',text)
def execute(name,size):
 w=O/name;w.mkdir(exist_ok=False);md=w/'mesh';md.mkdir()
 save(w/'status.json',dict(state='MESHING',pid=os.getpid()))
 request=tin.geometry();request['min_cell_size']=size/4
 request['refinement_boxes']=[dict(xmin=a,xmax=b,ymin=c,ymax=d,max_area=float(np.sqrt(3)/4*size**2),transition_width=.4) for a,b in [(-7.55,-.8),(0,8)] for c,d in [(-1.8,-1.46),(1.46,1.8)]]
 save(md/'mesh-request.json',request)
 with (md/'mesher.log').open('w',encoding='utf-8') as f:subprocess.run([str(M),str(md/'mesh-request.json'),str(md/'mesh-output.json')],stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
 output=json.loads((md/'mesh-output.json').read_text(encoding='utf-8'));xy=np.array(output['vertices']);v=np.column_stack([xy,tin.bed(xy)]);c=np.array(output['triangles'],int)
 audit,walls=tin.audit(v,c,request);assert not output['stats']['refine_capped']
 np.savez_compressed(md/'mesh.npz',vertices=v,cells=c)
 save(md/'mesh-provenance.json',dict(request=request,audit=audit,stats=output['stats'],mesher_sha256=sha(M),adapter_sha256=sha(R/'suites/uk_2d/mesher/main.cpp'),scope='Bank strips and 0.4 m graded transition only, x<=8 m. Global mesher regeneration can perturb neighboring triangulation; not an exactly nested mesh. Existing bank-toe constraints and crest/domain walls retained.'))
 original=(B/'model.inp').read_text(encoding='utf-8');text=replace(original,'2D_VERTICES',[' '.join(f'{a:.17g}' for a in row) for row in v]);depth=np.where(v[c,0].mean(1)<0,.4,.02)
 text=replace(text,'2D_TRIANGLES',[f'{a} {b} {d} .01 {h:.17g}' for (a,b,d),h in zip(c,depth)])
 groups=solid_groups(text,1);text=replace(text,'2D_BOUNDARY_CONDITIONS',[f"{r['cell']} {r['edge']} WALL * * {g}" for g,rows in groups.items() for r in rows])
 for sec in ['OPTIONS','TITLE','JUNCTIONS','OUTFALLS','CONDUITS','XSECTIONS','REPORT','2D_OPTIONS']:assert section(original,sec)==section(text,sec),sec
 (w/'model.inp').write_text(text,encoding='utf-8');case=json.loads((B/'case.json').read_text(encoding='utf-8'));case.update(id=name,end=30,cell_count=len(c),initial_volume_m3=float(tin.areas(v,c)@depth),model_sha256=sha(w/'model.inp'));case['deviations']+=['Declared bank-resolution 30 s diagnostic, fixed physics and geometry, no canonical promotion.'];save(w/'case.json',case)
 assert abs(case['initial_volume_m3']-16.618)<1e-9
 shutil.copy2(B/'probe-locations.csv',w/'probe-locations.csv');shutil.copytree(B/'reference',w/'reference');shutil.copy2(__file__,w/'driver.py')
 manifest=dict(input_sha256=sha(w/'model.inp'),control_input_sha256=sha(B/'model.inp'),executable_sha256=sha(X),library_sha256=sha(LIB),driver_sha256=sha(__file__),observations_sha256=sha(w/'reference/observations.csv'),mesh_audit=audit,declared_target_edge_m=size,physics='FLAT/MEAN defaults, FULL_SWE order2 global RK2 Cs0, n=.01, Coriolis OFF, free-slip walls, original uniform-depth initialization',duration_s=30)
 save(w/'manifest.json',manifest)
 env=engines.env(1,[str(X.parent),str(LIB.parent)])
 for key in list(env):
  if key.startswith('OPENSWMM_G2_') or key=='OPENSWMM_2D_MUSCL_OFF':env.pop(key)
 start=time.monotonic()
 with (w/'process.log').open('w',encoding='utf-8') as f:
  p=subprocess.Popen([str(X),str(w/'model.inp'),str(w/'model.rpt'),str(w/'model.out')],cwd=w,env=env,stdout=f,stderr=subprocess.STDOUT);save(w/'status.json',dict(state='RUNNING',pid=p.pid,driver_pid=os.getpid(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),cells=len(c)));print(name,'RUNNING',p.pid,len(c),flush=True)
  try:code=p.wait(timeout=10800)
  except BaseException:p.terminate();p.wait(timeout=30);raise
 assert code==0 and sha(X)==manifest['executable_sha256'] and sha(LIB)==manifest['library_sha256']
 probes=list(csv.DictReader((w/'probe-locations.csv').open(encoding='utf-8')));data=sampling.extract(w/'surface.h5',case,probes,w);assert len(data['times'])==300 and abs(float(data['times'][-1])-30)<1e-8
 result=dict(returncode=0,wall_s=time.monotonic()-start,**checks.numerical(case,data));assert all(result['checks'].values());result['observed']=observations.compare(w/'reference',case,data['times'],data['values'],probes)
 save(w/'metrics.json',result);np.savez_compressed(w/'extracted.npz',times=data['times'],values=data['values']);save(w/'status.json',dict(state='COMPLETE',checks=result['checks']));print(name,'COMPLETE',result['wall_s'],flush=True)
def guarded(row):
 try:execute(*row)
 except BaseException as e:
  save(O/row[0]/'status.json',dict(state='FAILED',error=repr(e)));raise
if __name__=='__main__':
 with cf.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(guarded,[('bank005',.05),('bank0025',.025)]))
