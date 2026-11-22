"""Keep the ordered audit/diagnostics alive across foreground interruptions."""
from pathlib import Path
import datetime as dt,json,os,subprocess,time
R=Path(__file__).resolve().parents[3];V=Path(__file__).parent;O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25';P=R/'.venv/bin/python'
def status(state,phase,**extra):(O/'task-status.json').write_text(json.dumps(dict(state=state,phase=phase,pid=os.getpid(),updated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),**extra),indent=2)+'\n',encoding='utf-8')
try:
 status('RUNNING','momentum instrumentation equivalence')
 started=time.monotonic()
 while True:
  p=O/'audit-enabled-v2/status.json'
  if p.exists():
   s=json.loads(p.read_text(encoding='utf-8'))
   if s['state']=='COMPLETE':break
   if s['state']=='FAILED':raise RuntimeError(str(s))
  if time.monotonic()-started>3600:raise TimeoutError('Momentum diagnostic completion')
  time.sleep(10)
 subprocess.run([str(P),str(V/'check_momentum.py')],cwd=R,check=True)
 assert json.loads((O/'momentum-audit.json').read_text(encoding='utf-8'))['status']=='PASS'
 status('RUNNING','reconstruction, then broader refinement')
 subprocess.run([str(P),str(V/'run_priorities.py')],cwd=R,check=True)
 status('DIAGNOSTICS_COMPLETE','interpretation and article verification pending')
except BaseException as e:
 status('FAILED','ordered audit diagnostics',error=str(e));raise
