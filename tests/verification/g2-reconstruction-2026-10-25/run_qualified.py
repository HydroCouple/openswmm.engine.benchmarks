"""Uncoupled fixed-physics diagnostics; no general solver promotion is implied."""
from pathlib import Path
import concurrent.futures as cf,csv,datetime as dt,hashlib,json,os,re,shutil,subprocess,sys,time
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R));os.chdir(R)
from harness import engines
from suites.uk_2d import sampling,checks,observations
import h5py,numpy as np
E=R.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';B=R/'results/uk_2d/wall-assessment-2026-10-25/6a-cs0-none-cw0.01';X=O/'pinned-clean/bin/openswmm';LIB=O/'pinned-clean/engine/libopenswmm.engine.6.0.0.dylib'
VARIANTS={'clean-combined':{},'clean-broad005':{}}
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n')
def execute(name,duration=30):
 variant=name.split('-120')[0].split('-30')[0];base=R/'results/uk_2d/g2-geometry-momentum-2026-10-25/broad005-30' if 'broad005' in name else B;work=O/name;assert not work.exists();work.mkdir();text=(base/'model.inp').read_text();text,n=re.subn(r'^END_TIME\s+.*$',f'END_TIME 00:{duration//60:02}:{duration%60:02}',text,flags=re.M);assert n==1
 (work/'model.inp').write_text(text);case=json.loads((base/'case.json').read_text());case.update(id=name,end=duration,model_sha256=sha(work/'model.inp'));case['deviations']+=['Isolated native reconstruction candidate; no canonical promotion.'];save(work/'case.json',case)
 for file in ['probe-locations.csv']:shutil.copy2(base/file,work/file)
 shutil.copytree(base/'reference',work/'reference');shutil.copy2(__file__,work/'driver.py')
 manifest=dict(variant=variant,input_sha256=sha(work/'model.inp'),control_input_sha256=sha(base/'model.inp'),executable_sha256=sha(X),library_sha256=sha(LIB),environment=VARIANTS[variant],driver_sha256=sha(__file__),source=dict(solver_sha256=sha(O/'solver-clean.cpp'),base_revision='50e146750bc723dfeacdb903909d49465f8031b0'),duration_s=duration)
 save(work/'manifest.json',manifest);env=engines.env(1,[str(X.parent),str(LIB.parent)])
 for key in list(env):
  if key.startswith('OPENSWMM_G2_') or key=='OPENSWMM_2D_MUSCL_OFF':env.pop(key,None)
 env.update(VARIANTS[variant]);started=time.monotonic()
 try:
  with (work/'process.log').open('w') as f:
   p=subprocess.Popen([str(X),str(work/'model.inp'),str(work/'model.rpt'),str(work/'model.out')],env=env,cwd=work,stdout=f,stderr=subprocess.STDOUT);save(work/'status.json',dict(state='RUNNING',pid=p.pid,driver_pid=os.getpid(),started_utc=dt.datetime.now(dt.timezone.utc).isoformat()));code=p.wait(timeout=7200)
  assert code==0 and sha(X)==manifest['executable_sha256'] and sha(LIB)==manifest['library_sha256']
  probes=list(csv.DictReader((work/'probe-locations.csv').open()));data=sampling.extract(work/'surface.h5',case,probes,work);assert len(data['times'])==duration*10 and abs(float(data['times'][-1])-duration)<1e-8,(len(data['times']),data['times'][-1]);result=dict(returncode=code,wall_s=time.monotonic()-started,**checks.numerical(case,data));assert all(result['checks'].values()),result
  result['observed']=observations.compare(work/'reference',case,data['times'],data['values'],probes);save(work/'metrics.json',result);np.savez_compressed(work/'extracted.npz',times=data['times'],values=data['values']);save(work/'status.json',dict(state='COMPLETE',checks=result['checks']));print(name,'COMPLETE',result['wall_s'],flush=True)
 except BaseException as error:save(work/'status.json',dict(state='FAILED',error=repr(error)));raise

if __name__=='__main__':
 native=json.loads((O/'clean-qualification/g2_native_reconstruction/results.json').read_text());assert native['tests']==12 and native['failures']==0
 analytical=json.loads((O/'analytical-clean-combined/scores.json').read_text());assert len(analytical['cells'])==16 and all(x['verdict']=='PASS' for x in analytical['cells'])
 marcher=json.loads((O/'clean-qualification/g2_existing_marcher/results.json').read_text());failed=[s['name']+'.'+t['name'] for s in marcher['testsuites'] for t in s['testsuite'] if t.get('failures')];assert failed==['CoupledGroundwaterRk2.FiniteContactProtectsAcceptedMassAndWaterAndDoesNotRecycleStageInflows']
 with cf.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda row:execute(*row),[('clean-combined-120',120),('clean-broad005-30',30)]))
