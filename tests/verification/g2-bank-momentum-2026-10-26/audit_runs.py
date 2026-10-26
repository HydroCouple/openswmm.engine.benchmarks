"""Require field equivalence before interpreting corrected-operator momentum receipts."""
from pathlib import Path
import concurrent.futures as cf,csv,datetime,hashlib,json,os,re,shutil,subprocess,sys,time
import h5py,numpy as np
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R))
from suites.uk_2d import sampling,checks,observations
from harness import engines
O=R/'results/uk_2d/g2-bank-momentum-2026-10-26';B=R/'results/uk_2d/g2-reconstruction-2026-10-25/clean-combined';V=R.parent/'openswmm.engine/tests/verification/g2_bank_momentum_2026-10-26';PIN=O/'pinned-audit'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def compare(a,b):
 result={}
 with h5py.File(a/'surface.h5') as f,h5py.File(b/'surface.h5') as g:
  for key in ['Mesh2_face_depth','Mesh2_face_vx','Mesh2_face_vy']:
   n=min(len(f[key]),len(g[key]));changed=0;maximum=0.
   for i in range(n):
    x=f[key][i];y=g[key][i];changed+=int(np.count_nonzero(x!=y));maximum=max(maximum,float(abs(x-y).max()))
   result[key]=dict(frames=n,changed_values=changed,max_absolute_difference=maximum)
 return dict(bit_identical=all(r['changed_values']==0 for r in result.values()),fields=result)
def execute(name,end,enabled):
 w=O/name;w.mkdir(exist_ok=False);text=(B/'model.inp').read_text();text,n=re.subn(r'^END_TIME\s+.*$',f'END_TIME 00:00:{end:02}',text,flags=re.M);assert n==1
 (w/'model.inp').write_text(text);case=json.loads((B/'case.json').read_text());case.update(id=name,end=end,model_sha256=sha(w/'model.inp'));save(w/'case.json',case);shutil.copy2(B/'probe-locations.csv',w/'probe-locations.csv');shutil.copytree(B/'reference',w/'reference')
 x=PIN/'bin/openswmm';lib=PIN/'engine/libopenswmm.engine.6.0.0.dylib';save(w/'manifest.json',dict(input_sha256=sha(w/'model.inp'),executable_sha256=sha(x),library_sha256=sha(lib),audit_enabled=enabled,duration_s=end))
 env=engines.env(1,[str(x.parent),str(lib.parent)])
 for key in list(env):
  if key.startswith('OPENSWMM_G2_') or key=='OPENSWMM_2D_MUSCL_OFF':env.pop(key)
 if enabled:env['OPENSWMM_G2_MOMENTUM_AUDIT']=str(w/'momentum-ledger.csv')
 start=time.monotonic()
 with (w/'process.log').open('w') as f:
  p=subprocess.Popen([str(x),str(w/'model.inp'),str(w/'model.rpt'),str(w/'model.out')],cwd=w,env=env,stdout=f,stderr=subprocess.STDOUT);save(w/'status.json',dict(state='RUNNING',pid=p.pid,driver_pid=os.getpid(),started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));print(name,'RUNNING',p.pid,flush=True)
  try:code=p.wait(timeout=10800)
  except BaseException:p.terminate();p.wait(timeout=30);raise
 assert code==0
 probes=list(csv.DictReader((w/'probe-locations.csv').open()));data=sampling.extract(w/'surface.h5',{**case,'uk_test':case['uk_test'] if end>=30 else 'audit'},probes,w);assert len(data['times'])==end*10
 result=dict(returncode=0,wall_s=time.monotonic()-start,**checks.numerical(case,data));assert all(result['checks'].values());
 if end==30:result['observed']=observations.compare(w/'reference',case,data['times'],data['values'],probes)
 save(w/'metrics.json',result);np.savez_compressed(w/'extracted.npz',times=data['times'],values=data['values']);save(w/'status.json',dict(state='COMPLETE',checks=result['checks']));print(name,'COMPLETE',result['wall_s'],flush=True)
if __name__=='__main__':
 PIN.mkdir(exist_ok=False);(PIN/'bin').mkdir();(PIN/'engine').mkdir();shutil.copy2(V/'build/src/cli/openswmm',PIN/'bin/openswmm');shutil.copy2(V/'build/src/engine/libopenswmm.engine.6.0.0.dylib',PIN/'engine/libopenswmm.engine.6.0.0.dylib')
 for name in ['libopenswmm.engine.dylib','libopenswmm.engine.6.dylib']:(PIN/'engine'/name).symlink_to('libopenswmm.engine.6.0.0.dylib')
 with cf.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda args:execute(*args),[('audit-disabled-1',1,False),('audit-enabled-1',1,True)]))
 eq=dict(enabled_vs_disabled=compare(O/'audit-enabled-1',O/'audit-disabled-1'),disabled_vs_frozen=compare(O/'audit-disabled-1',B))
 eq['status']='PASS' if all(row['bit_identical'] for row in eq.values()) else 'FAIL';save(O/'instrumentation-equivalence-short.json',eq);assert eq['status']=='PASS','No ledger interpretation or longer audit with failed equivalence'
 execute('audit-enabled-30',30,True);eq=compare(O/'audit-enabled-30',B);eq['status']='PASS' if eq['bit_identical'] else 'FAIL';save(O/'instrumentation-equivalence.json',eq);assert eq['status']=='PASS'
