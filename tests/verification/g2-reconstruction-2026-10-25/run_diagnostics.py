"""Uncoupled fixed-physics diagnostics; no general solver promotion is implied."""
from pathlib import Path
import concurrent.futures as cf,csv,datetime as dt,hashlib,json,os,re,shutil,subprocess,sys,time
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R));os.chdir(R)
from harness import engines
from suites.uk_2d import sampling,checks,observations
import h5py,numpy as np
E=R.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';B=R/'results/uk_2d/wall-assessment-2026-10-25/6a-cs0-none-cw0.01';X=O/'pinned-v1/bin/openswmm';LIB=O/'pinned-v1/engine/libopenswmm.engine.6.0.0.dylib'
VARIANTS={'legacy-replay':{'OPENSWMM_G2_LEGACY_GRADIENT':'1','OPENSWMM_G2_LEGACY_WALL':'1'},'gradient-only':{'OPENSWMM_G2_LEGACY_WALL':'1'},'combined':{}}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def execute(name,duration=30):
 variant=name.split('-120')[0];work=O/name;assert not work.exists();work.mkdir();text=(B/'model.inp').read_text();text,n=re.subn(r'^END_TIME\s+.*$',f'END_TIME 00:{duration//60:02}:{duration%60:02}',text,flags=re.M);assert n==1
 (work/'model.inp').write_text(text);case=json.loads((B/'case.json').read_text());case.update(id=name,end=duration,model_sha256=sha(work/'model.inp'));case['deviations']+=['Isolated native reconstruction candidate; no canonical promotion.'];save(work/'case.json',case)
 for file in ['probe-locations.csv']:shutil.copy2(B/file,work/file)
 shutil.copytree(B/'reference',work/'reference');shutil.copy2(__file__,work/'driver.py')
 manifest=dict(variant=variant,input_sha256=sha(work/'model.inp'),control_input_sha256=sha(B/'model.inp'),executable_sha256=sha(X),library_sha256=sha(LIB),environment=VARIANTS[variant],driver_sha256=sha(__file__),source=json.loads((O/'candidate-source.json').read_text()),duration_s=duration)
 save(work/'manifest.json',manifest);env=engines.env(1,[str(X.parent),str(LIB.parent)])
 for key in ['OPENSWMM_G2_LEGACY_GRADIENT','OPENSWMM_G2_LEGACY_WALL','OPENSWMM_2D_MUSCL_OFF','OPENSWMM_G2_MOMENTUM_AUDIT']:env.pop(key,None)
 env.update(VARIANTS[variant]);started=time.monotonic()
 try:
  with (work/'process.log').open('w') as f:
   p=subprocess.Popen([str(X),str(work/'model.inp'),str(work/'model.rpt'),str(work/'model.out')],env=env,cwd=work,stdout=f,stderr=subprocess.STDOUT);save(work/'status.json',dict(state='RUNNING',pid=p.pid,driver_pid=os.getpid(),started_utc=dt.datetime.now(dt.timezone.utc).isoformat()));code=p.wait(timeout=7200)
  assert code==0 and sha(X)==manifest['executable_sha256'] and sha(LIB)==manifest['library_sha256']
  probes=list(csv.DictReader((work/'probe-locations.csv').open()));data=sampling.extract(work/'surface.h5',case,probes,work);result=dict(returncode=code,wall_s=time.monotonic()-started,**checks.numerical(case,data));assert all(result['checks'].values()),result
  result['observed']=observations.compare(work/'reference',case,data['times'],data['values'],probes);save(work/'metrics.json',result);np.savez_compressed(work/'extracted.npz',times=data['times'],values=data['values']);save(work/'status.json',dict(state='COMPLETE',checks=result['checks']));print(name,'COMPLETE',result['wall_s'],flush=True)
 except BaseException as error:save(work/'status.json',dict(state='FAILED',error=repr(error)));raise

def replay_check():
 original=R/'results/uk_2d/g2-geometry-momentum-2026-10-25/frozen30';work=O/'legacy-replay';results={}
 with h5py.File(original/'surface.h5') as a,h5py.File(work/'surface.h5') as b:
  for name in ['Mesh2_face_depth','Mesh2_face_vx','Mesh2_face_vy']:
   maximum=0;changed=0
   for i in range(300):x=a[name][i];y=b[name][i];maximum=max(maximum,float(np.max(abs(x-y))));changed+=int(np.count_nonzero(x!=y))
   results[name]=dict(max_absolute_difference=maximum,changed_values=changed)
 value=dict(status='PASS' if all(v['changed_values']==0 for v in results.values()) else 'FAIL',fields=results);save(O/'legacy-replay-equivalence.json',value);assert value['status']=='PASS',value
if __name__=='__main__':
 mode=sys.argv[1]
 if mode=='replay':execute('legacy-replay');replay_check()
 elif mode=='candidates':
  assert json.loads((O/'legacy-replay-equivalence.json').read_text())['status']=='PASS'
  analytical=json.loads((O/'analytical-summary.json').read_text());assert all(r['passed']==16 for r in analytical if r['variant'] in ['combined','gradient-only'])
  focused=json.loads((O/'native-focused-summary.json').read_text());assert next(r for r in focused['cases'] if r['variant']=='combined')['failures']==[]
  with cf.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(execute,['gradient-only','combined']))
 else:raise ValueError(mode)
