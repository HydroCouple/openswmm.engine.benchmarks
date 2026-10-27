"""Read live simulation progress through the public binary-output API."""
from pathlib import Path
import ctypes
import json
import sys

sys.path.insert(0, str(Path(__file__).parent))
from run import OUT, PIN

library = ctypes.CDLL(str(PIN / 'engine/libopenswmm.engine.6.0.0.dylib'))
library.swmm_output_open_live.argtypes = [ctypes.c_char_p]
library.swmm_output_open_live.restype = ctypes.c_void_p
library.swmm_output_get_period_count.argtypes = [ctypes.c_void_p]
library.swmm_output_get_period_count.restype = ctypes.c_int
library.swmm_output_get_period_time.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_double)]
library.swmm_output_close.argtypes = [ctypes.c_void_p]
for path in sorted(OUT.glob('*/status.json')):
    status = json.loads(path.read_text())
    row = dict(case=path.parent.name, state=status['state'])
    if status['state'] == 'RUNNING' and (path.parent / 'model.out').exists():
        handle = library.swmm_output_open_live(str(path.parent / 'model.out').encode())
        if handle:
            try:
                count = library.swmm_output_get_period_count(handle)
                time = ctypes.c_double()
                if count:
                    assert library.swmm_output_get_period_time(handle, count - 1, ctypes.byref(time)) == 0
                    row['saved_seconds'] = round((time.value - 46023) * 86400, 3)
            finally:
                library.swmm_output_close(handle)
    print(json.dumps(row))
