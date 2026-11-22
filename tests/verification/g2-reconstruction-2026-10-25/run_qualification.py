"""Native and analytical qualification of isolated, independently switched corrections."""
from pathlib import Path
import concurrent.futures as cf,datetime as dt,hashlib,json,os,subprocess,sys,time
R=Path(__file__).resolve().parents[3];E=R.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';P=R/'.venv/bin/python';BUILD=V/'build';X=BUILD/'src/cli/openswmm'
PIN=R/'results/uk_2d/wall-assessment-2026-10-25/pinned-clock/engine'
VARIANTS={'combined':{},'gradient-only':{'OPENSWMM_G2_LEGACY_WALL':'1'},'wall-only':{'OPENSWMM_G2_LEGACY_GRADIENT':'1'},'legacy-replay':{'OPENSWMM_G2_LEGACY_GRADIENT':'1','OPENSWMM_G2_LEGACY_WALL':'1'}}
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2,allow_nan=False)+'\n',encoding='utf-8')
def env(variant,library):
 e=os.environ.copy();e['DYLD_LIBRARY_PATH']=str(library);e['OMP_NUM_THREADS']='1'
 for k in ['OPENSWMM_G2_LEGACY_GRADIENT','OPENSWMM_G2_LEGACY_WALL','OPENSWMM_2D_MUSCL_OFF','OPENSWMM_G2_MOMENTUM_AUDIT']:e.pop(k,None)
 e.update(VARIANTS.get(variant,{}));return e

def native(profile,exe_name,variant='combined'):
 folder=O/'native'/profile;folder.mkdir(parents=True,exist_ok=True);exe=V/('native-baseline' if profile=='original' else 'native-candidate')/exe_name
 lib=PIN if profile=='original' else BUILD/'src/engine';path=folder/(exe_name+('.'+variant if profile!='original' else '')+'.json');log=path.with_suffix('.log')
 with log.open('w',encoding='utf-8') as f:r=subprocess.run([str(exe),'--gtest_output=json:'+str(path)],env=env(variant,lib),cwd=V/'source',stdout=f,stderr=subprocess.STDOUT,timeout=1200)
 result=json.loads(path.read_text(encoding='utf-8'));row=dict(profile=profile,variant=variant,executable=exe_name,returncode=r.returncode,tests=result['tests'],failures=result['failures'],environment=VARIANTS.get(variant,{}),report=str(path.relative_to(O)))
 print(json.dumps(row),flush=True);return row

def jumps(variant):
 folder=O/('analytical-'+variant);assert not folder.exists();folder.mkdir()
 lib=BUILD/'src/engine/libopenswmm.engine.6.0.0.dylib';identity=dict(variant=variant,environment=VARIANTS[variant],executable_sha256=sha(X),library_sha256=sha(lib),source=json.loads((O/'candidate-source.json').read_text(encoding='utf-8')),started_utc=dt.datetime.now(dt.timezone.utc).isoformat())
 save(folder/'variant.json',identity)
 with (folder/'driver.log').open('w',encoding='utf-8') as f:r=subprocess.run([str(P),str(R/'run_regression.py'),'--suite','analytical/hydraulic_jumps','--exe',str(X),'--output-dir',str(folder),'--max-wall','300'],cwd=R,env=env(variant,lib.parent),stdout=f,stderr=subprocess.STDOUT,timeout=7200)
 assert sha(X)==identity['executable_sha256'] and sha(lib)==identity['library_sha256']
 scores=json.loads((folder/'scores.json').read_text(encoding='utf-8'));row=dict(variant=variant,returncode=r.returncode,cases=len(scores['cells']),passed=sum(c['verdict']=='PASS' for c in scores['cells']),failures=[dict(case=c['case'],verdict=c['verdict'],checks=c.get('checks',{}),note=c.get('note')) for c in scores['cells'] if c['verdict']!='PASS'])
 save(folder/'qualification.json',row);print(json.dumps(row),flush=True);return row
if __name__=='__main__':
 action=sys.argv[1]
 if action=='native':
  rows=[native('original','g2_native_reconstruction')]+[native('candidate','g2_native_reconstruction',v) for v in VARIANTS]
  jobs=[(p,n) for p in ['original','candidate'] for n in ['g2_existing_cpu','g2_existing_marcher']]
  with cf.ThreadPoolExecutor(max_workers=2) as pool:rows+=list(pool.map(lambda x:native(*x),jobs))
  save(O/'native-summary.json',rows)
 elif action=='jumps':
  with cf.ThreadPoolExecutor(max_workers=2) as pool:rows=list(pool.map(jumps,['combined','gradient-only','wall-only']))
  save(O/'analytical-summary.json',rows)
 else:raise ValueError(action)
