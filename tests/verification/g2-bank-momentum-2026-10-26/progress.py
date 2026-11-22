"""Read live public binary output only; process state is reported separately."""
from pathlib import Path
import ctypes,datetime,json,os
R=Path(__file__).resolve().parents[3];O=R/'results/uk_2d/g2-bank-momentum-2026-10-26';lib=ctypes.CDLL(str(R/'results/uk_2d/g2-reconstruction-2026-10-25/pinned-clean/engine/libopenswmm.engine.6.0.0.dylib'))
lib.swmm_output_open_live.argtypes=[ctypes.c_char_p];lib.swmm_output_open_live.restype=ctypes.c_void_p;lib.swmm_output_get_period_count.argtypes=[ctypes.c_void_p];lib.swmm_output_get_period_count.restype=ctypes.c_int;lib.swmm_output_get_period_time.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_double)];lib.swmm_output_close.argtypes=[ctypes.c_void_p]
for name in ['bank005','bank0025','audit-disabled-1','audit-enabled-1','audit-enabled-30']:
 w=O/name
 if not (w/'status.json').exists():continue
 status=json.loads((w/'status.json').read_text(encoding='utf-8'));row=dict(case=name,status=status)
 if status.get('pid'):
  try:os.kill(status['pid'],0);row['process_exists']=True
  except ProcessLookupError:row['process_exists']=False
  except PermissionError:row['process_exists']='permission-limited'
 if (w/'model.out').exists():
  handle=lib.swmm_output_open_live(str(w/'model.out').encode())
  if handle:
   try:
    n=lib.swmm_output_get_period_count(handle);t=ctypes.c_double()
    if n:assert lib.swmm_output_get_period_time(handle,n-1,ctypes.byref(t))==0
    row.update(saved_seconds=round((t.value-46023)*86400,3) if n else 0,periods=n,mtime_utc=datetime.datetime.fromtimestamp((w/'model.out').stat().st_mtime,datetime.timezone.utc).isoformat())
   finally:lib.swmm_output_close(handle)
 print(json.dumps(row))
