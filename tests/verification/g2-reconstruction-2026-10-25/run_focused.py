"""Final native patch and thread-count checks; reference tolerances stay fixed."""
from pathlib import Path
import hashlib,json,os,subprocess
R=Path(__file__).resolve().parents[3];E=R.parent/'openswmm.engine';V=E/'tests/verification/g2_reconstruction_2026-10-25';O=R/'results/uk_2d/g2-reconstruction-2026-10-25';D=O/'native-focused';D.mkdir(exist_ok=True)
variants={'original':{},'combined':{},'gradient-only':{'OPENSWMM_G2_LEGACY_WALL':'1'},'wall-only':{'OPENSWMM_G2_LEGACY_GRADIENT':'1'},'legacy-replay':{'OPENSWMM_G2_LEGACY_GRADIENT':'1','OPENSWMM_G2_LEGACY_WALL':'1'}};rows=[]
for name,changes in variants.items():
 exe=V/('native-baseline' if name=='original' else 'native-candidate')/'g2_native_reconstruction';lib=R/'results/uk_2d/wall-assessment-2026-10-25/pinned-clock/engine' if name=='original' else V/'build/src/engine';env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(lib);env['OMP_NUM_THREADS']='1'
 for key in ['OPENSWMM_G2_LEGACY_GRADIENT','OPENSWMM_G2_LEGACY_WALL']:env.pop(key,None)
 env.update(changes)
 with (D/(name+'.log')).open('w',encoding='utf-8') as f:r=subprocess.run([str(exe),'--gtest_output=json:'+str(D/(name+'.json'))],cwd=D,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=60)
 result=json.loads((D/(name+'.json')).read_text(encoding='utf-8'));failed=[t['name'] for s in result['testsuites'] for t in s['testsuite'] if t.get('failures')];row=dict(variant=name,returncode=r.returncode,tests=result['tests'],failures=failed,environment=changes);rows.append(row);print(row,flush=True)
(O/'native-focused-summary.json').write_text(json.dumps(dict(test_source_sha256=hashlib.sha256((E/'tests/unit/engine/test_2d_swe_reconstruction.cpp').read_bytes()).hexdigest(),cases=rows),indent=2)+'\n',encoding='utf-8')
