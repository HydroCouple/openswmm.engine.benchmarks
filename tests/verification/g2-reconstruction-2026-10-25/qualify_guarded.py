"""Qualify the guarded candidate using immutable pinned-v2 binaries."""
from pathlib import Path
import concurrent.futures as cf,hashlib,json,os,subprocess,sys
R=Path(__file__).resolve().parents[3];V=R.parent/'openswmm.engine/tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';PIN=O/'pinned-v2';D=O/'guarded-qualification';D.mkdir(exist_ok=True)
def run(name,command,cwd):
 env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(PIN/'engine');env['OMP_NUM_THREADS']='1';env['SWMM_RK2_TEST_OUT']=str(cwd)
 for k in ['OPENSWMM_G2_LEGACY_GRADIENT','OPENSWMM_G2_LEGACY_WALL','OPENSWMM_G2_TRACE']:env.pop(k,None)
 with (D/(name+'.log')).open('w') as f:
  try:r=subprocess.run(command,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=600);code=r.returncode
  except subprocess.TimeoutExpired:code='TIMEOUT'
 row=dict(name=name,returncode=code);(D/(name+'-status.json')).write_text(json.dumps(row,indent=2)+'\n');print(row,flush=True)
def native():
 for name in ['g2_native_reconstruction','g2_existing_cpu','g2_existing_marcher']:
  work=D/name;work.mkdir(exist_ok=True);run(name,[str(V/'native-v2'/name),'--gtest_output=json:'+str(work/'results.json')],work)
def analytical():
 work=O/'analytical-guarded';work.mkdir(exist_ok=True)
 identity=dict(binaries={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [PIN/'bin/openswmm',PIN/'engine/libopenswmm.engine.6.0.0.dylib']},source=json.loads((O/'candidate-source-v2.json').read_text()))
 (work/'variant.json').write_text(json.dumps(identity,indent=2)+'\n')
 run('analytical',[str(R/'.venv/bin/python'),str(R/'run_regression.py'),'--suite','analytical/hydraulic_jumps','--exe',str(PIN/'bin/openswmm'),'--output-dir',str(work),'--max-wall','300'],R)
with cf.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda f:f(),[native,analytical]))
