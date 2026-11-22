"""Compare completed runs only; extending the end time must not alter the prefix."""
from pathlib import Path
import json
import h5py
import numpy as np

R = Path(__file__).resolve().parents[3]
O = R / 'results/uk_2d/g2-reconstruction-2026-10-25'
for name in ['clean-combined', 'clean-combined-120']:
    assert json.loads((O / name / 'status.json').read_text(encoding='utf-8'))['state'] == 'COMPLETE'
fields = {}
with h5py.File(O / 'clean-combined/surface.h5') as a, h5py.File(O / 'clean-combined-120/surface.h5') as b:
    assert len(a['time']) == 300 and len(b['time']) == 1200
    for name in ['Mesh2_face_depth', 'Mesh2_face_vx', 'Mesh2_face_vy']:
        maximum = 0.
        changed = 0
        for i in range(300):
            x, y = a[name][i], b[name][i]
            maximum = max(maximum, float(np.max(abs(x - y))))
            changed += int(np.count_nonzero(x != y))
        fields[name] = dict(max_absolute_difference=maximum, changed_values=changed)
value = dict(status='PASS' if all(x['changed_values'] == 0 for x in fields.values()) else 'FAIL',
             prefix_s=30, full_duration_s=120, fields=fields)
(O / 'duration-equivalence.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
assert value['status'] == 'PASS', value
print(value)
