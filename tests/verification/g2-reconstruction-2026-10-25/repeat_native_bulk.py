"""Repeat broader tests with separate artifact roots; retain preliminary results."""
from pathlib import Path
import hashlib,json,os,subprocess
R=Path(__file__).resolve().parents[3];E=R.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';rows=[]
for profile in ['original','candidate']:
 d=O/'native-isolated'/profile;d.mkdir(parents=True,exist_ok=True);art=d/'artifacts';art.mkdir(exist_ok=True)
 exe=V/('native-baseline' if profile=='original' else 'native-candidate')/'g2_existing_marcher';lib=R/'results/uk_2d/wall-assessment-2026-10-25/pinned-clock/engine' if profile=='original' else V/'build/src/engine'
 env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(lib);env['OMP_NUM_THREADS']='1';env['SWMM_RK2_TEST_OUT']=str(art)
 for k in ['OPENSWMM_G2_LEGACY_GRADIENT','OPENSWMM_G2_LEGACY_WALL','OPENSWMM_2D_MUSCL_OFF']:env.pop(k,None)
 with (d/'process.log').open('w') as f:r=subprocess.run([str(exe),'--gtest_output=json:'+str(d/'results.json')],cwd=art,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=1200)
 result=json.loads((d/'results.json').read_text());fail=[]
 for suite in result['testsuites']:
  for test in suite['testsuite']:
   if test.get('failures'):fail.append(dict(name=suite['name']+'.'+test['name'],details=test['failures']))
 row=dict(profile=profile,returncode=r.returncode,tests=result['tests'],failures=fail,skipped=result.get('disabled',0),artifact_root=str(art));rows.append(row);print(json.dumps(row),flush=True)
(O/'native-bulk-isolated.json').write_text(json.dumps(rows,indent=2)+'\n')
