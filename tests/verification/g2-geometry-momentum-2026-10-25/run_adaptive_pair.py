"""Adaptive paired mesh diagnostic declared after the coarse order comparison."""
from pathlib import Path
import datetime as dt,importlib.util,json,os,time
V=Path(__file__).parent;R=V.parents[2];O=R/'results/uk_2d/g2-geometry-momentum-2026-10-25'
spec=importlib.util.spec_from_file_location('priorities',V/'run_priorities.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
def status(state,**kw):(O/'adaptive-status.json').write_text(json.dumps(dict(state=state,pid=os.getpid(),updated_utc=dt.datetime.now(dt.timezone.utc).isoformat(),**kw),indent=2)+'\n')
try:
 status('RUNNING',case='broad005-muscloff-30');m.run('broad005-muscloff-30');status('COMPLETE')
except BaseException as e:status('FAILED',error=repr(e));raise
