"""Reproduce the native audit against a specifically identified engine image."""
from pathlib import Path
import argparse,csv,hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()

def run():
    ap=argparse.ArgumentParser();ap.add_argument('--source',type=Path,required=True);ap.add_argument('--library',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy();env['DYLD_LIBRARY_PATH']=str(a.library.parent);env['OMP_NUM_THREADS']='1'
    for key in list(env):
        if key.startswith('OPENSWMM_G2_') or key=='OPENSWMM_2D_MUSCL_OFF':env.pop(key)
    commands=[['cmake','-S',str(HERE),'-B',str(a.output/'build'),'-G','Ninja','-DCMAKE_BUILD_TYPE=Release','-DENGINE_SOURCE='+str(a.source),'-DENGINE_LIBRARY='+str(a.library)],['cmake','--build',str(a.output/'build')]]
    with (a.output/'build.log').open('w') as f:
        for c in commands:subprocess.run(c,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    exe=a.output/'build/partial_wet_audit'
    for name,args in [('native',[]),('ridge-extended',['ridge'])]:
        with (a.output/(name+'.log')).open('w') as f:subprocess.run([str(exe),str(a.output/(name+'.csv')),*args],env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=120)
    fields=['src/engine/2d/solver/ExplicitInertialSolver.cpp','src/engine/2d/solver/ExplicitInertialSolver.hpp','src/engine/2d/solver/SweKernels.hpp','src/engine/2d/solver/InertialKernels.hpp','src/engine/2d/data/SolverOptions2D.hpp']
    identity=dict(library=str(a.library),library_sha256=sha(a.library),executable_sha256=sha(exe),source=str(a.source),engine_sources={p:sha(a.source/p) for p in fields},audit_sources={p.name:sha(p) for p in HERE.iterdir() if p.suffix in ['.cpp','.txt']},native_cases=len(list(csv.DictReader((a.output/'native.csv').open()))),ridge_cases=len(list(csv.DictReader((a.output/'ridge-extended.csv').open()))))
    assert identity['native_cases']==108 and identity['ridge_cases']==24
    (a.output/'execution.json').write_text(json.dumps(identity,indent=2)+'\n')
if __name__=='__main__':run()
