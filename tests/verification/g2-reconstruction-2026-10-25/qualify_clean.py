"""Qualification of the bounded, linear-exact primitive-velocity prototype."""
from pathlib import Path
import concurrent.futures as cf,hashlib,json,os,subprocess
R=Path(__file__).resolve().parents[3];V=R.parent/'openswmm.engine/tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';PIN=O/'pinned-clean';D=O/'clean-qualification';D.mkdir(exist_ok=True)
def run(name,command,cwd,extra={}):
 env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(PIN/'engine');env['OMP_NUM_THREADS']='1';env['SWMM_RK2_TEST_OUT']=str(cwd)
 for k in list(env):
  if k.startswith('OPENSWMM_G2_'):env.pop(k)
 env.update(extra)
 with (D/(name+'.log')).open('w',encoding='utf-8') as f:
  try:r=subprocess.run(command,cwd=cwd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1200);code=r.returncode
  except subprocess.TimeoutExpired:code='TIMEOUT'
 row=dict(name=name,returncode=code,flags=extra);(D/(name+'-status.json')).write_text(json.dumps(row,indent=2)+'\n',encoding='utf-8');print(row,flush=True)
def native():
 for name in ['g2_native_reconstruction','g2_existing_cpu','g2_existing_marcher']:
  work=D/name;work.mkdir(exist_ok=True);run(name,[str(V/'native-v2'/name),'--gtest_output=json:'+str(work/'results.json')],work)
def analytical():
 for name,flags in [('combined',{})]:
  work=O/('analytical-clean-'+name);work.mkdir(exist_ok=True);(work/'variant.json').write_text(json.dumps(dict(prototype=json.loads((O/'vertex-prototype.json').read_text(encoding='utf-8')),flags=flags),indent=2)+'\n',encoding='utf-8')
  run('analytical-'+name,[str(R/'.venv/bin/python'),str(R/'run_regression.py'),'--suite','analytical/hydraulic_jumps','--exe',str(PIN/'bin/openswmm'),'--output-dir',str(work),'--max-wall','300'],R,flags)
with cf.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda f:f(),[native,analytical]))
