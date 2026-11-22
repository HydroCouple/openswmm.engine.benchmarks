"""Declared 30 s momentum diagnostics on immutable or isolated audit binaries."""
from pathlib import Path
import csv,datetime as dt,hashlib,json,os,re,shutil,subprocess,sys,time
R=Path(__file__).resolve().parents[3];sys.path.insert(0,str(R));os.chdir(R)
from harness import engines
from suites.uk_2d import sampling,checks,observations
import numpy as np
O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';B=O.parent/'wall-assessment-2026-10-25/6a-cs0-none-cw0.01'
PIN=B.parent/'pinned-clock/bin/openswmm';BUILD=R.parent/'openswmm.engine/tests/verification/g2_geometry_momentum_2026-10-25/audit-build'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def prepare(name):
 w=O/name;assert not w.exists();w.mkdir();text=(B/'model.inp').read_text(encoding='utf-8')
 # End clocks only: all hydrodynamic, reconstruction and output controls fixed.
 text,n=re.subn(r'^END_TIME\s+.*$','END_TIME 00:00:30',text,flags=re.M);assert n==1
 (w/'model.inp').write_text(text,encoding='utf-8');case=json.loads((B/'case.json').read_text(encoding='utf-8'));case.update(id=name,end=30,model_sha256=sha(w/'model.inp'))
 case['deviations']+=['30 second diagnostic only; no full-duration qualification.']
 save(w/'case.json',case);shutil.copy2(B/'probe-locations.csv',w/'probe-locations.csv');shutil.copytree(B/'reference',w/'reference')
 return w

def run(name):
 w=prepare(name);exe=PIN if name=='frozen30' else BUILD/'src/cli/openswmm'
 libs=[exe.parent,exe.parent.parent/'engine'] if name=='frozen30' else [exe.parent,BUILD/'src/engine']
 env=engines.env(1,list(map(str,libs)))
 if name.startswith('audit-enabled'):env['OPENSWMM_G2_MOMENTUM_AUDIT']=str(w/'momentum-ledger.csv')
 ident=dict(executable=str(exe),executable_sha256=sha(exe),libraries={str(p):sha(p) for d in libs for p in d.glob('libopenswmm.engine*.dylib')},input_sha256=sha(w/'model.inp'),control_input_sha256=sha(B/'model.inp'),driver_sha256=sha(__file__),diagnostic_duration_s=30)
 save(w/'manifest.json',ident);started=time.monotonic()
 with (w/'process.log').open('w',encoding='utf-8') as f:
  p=subprocess.Popen([str(exe),str(w/'model.inp'),str(w/'model.rpt'),str(w/'model.out')],cwd=w,env=env,stdout=f,stderr=subprocess.STDOUT)
  save(w/'status.json',dict(state='RUNNING',pid=p.pid,driver_pid=os.getpid(),started_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
  code=p.wait(timeout=7200)
 assert code==0,(name,code)
 assert sha(exe)==ident['executable_sha256'] and sha(w/'model.inp')==ident['input_sha256']
 case=json.loads((w/'case.json').read_text(encoding='utf-8'));probes=list(csv.DictReader((w/'probe-locations.csv').open(encoding='utf-8')));data=sampling.extract(w/'surface.h5',case,probes,w)
 result=dict(case=name,returncode=code,wall_s=time.monotonic()-started,**checks.numerical(case,data));assert all(result['checks'].values()),result
 result['observed']=observations.compare(w/'reference',case,data['times'],data['values'],probes)
 np.savez_compressed(w/'extracted.npz',times=data['times'],values=data['values']);save(w/'metrics.json',result);save(w/'status.json',dict(state='COMPLETE',checks=result['checks']))
 print(name,'COMPLETE',result['wall_s'],flush=True)
if __name__=='__main__':
 for name in sys.argv[1].split(','):run(name)
