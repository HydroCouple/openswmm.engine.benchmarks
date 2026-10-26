"""Saved binary output progress; incomplete output alone does not imply a live process."""
from pathlib import Path
import ctypes,datetime as dt,json
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'results/uk_2d/g2-reconstruction-2026-10-25'
lib=ctypes.CDLL(str(OUT/'pinned-clean/engine/libopenswmm.engine.6.0.0.dylib'))
lib.swmm_output_open_live.argtypes=[ctypes.c_char_p];lib.swmm_output_open_live.restype=ctypes.c_void_p
lib.swmm_output_get_period_count.argtypes=[ctypes.c_void_p];lib.swmm_output_get_period_count.restype=ctypes.c_int
lib.swmm_output_get_period_time.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.POINTER(ctypes.c_double)]
lib.swmm_output_is_live.argtypes=[ctypes.c_void_p];lib.swmm_output_close.argtypes=[ctypes.c_void_p]
origin=(dt.datetime(2026,1,1)-dt.datetime(1899,12,30)).days
rows=[]
for name in ['clean-combined','vertex-gradient-only','clean-combined-120','clean-broad005-30']:
    folder=OUT/name;path=folder/'model.out'
    if not path.exists():continue
    h=lib.swmm_output_open_live(str(path).encode())
    if not h:rows.append(dict(case=name,status='Header not ready'));continue
    try:
        n=lib.swmm_output_get_period_count(h);stamp=ctypes.c_double()
        if n:assert lib.swmm_output_get_period_time(h,n-1,ctypes.byref(stamp))==0
        rows.append(dict(case=name,saved_seconds=round((stamp.value-origin)*86400,2) if n else 0,required_seconds=120 if name.endswith("120") else 30,complete_records=n,output_incomplete=bool(lib.swmm_output_is_live(h)),output_updated_utc=dt.datetime.fromtimestamp(path.stat().st_mtime,dt.timezone.utc).isoformat(),state=json.loads((folder/'status.json').read_text())))
    finally:lib.swmm_output_close(h)
print(json.dumps(rows,indent=2))
