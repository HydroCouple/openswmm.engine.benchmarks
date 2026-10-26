"""Independent completed-run field diagnostics, including maximum mass drift."""
from pathlib import Path
import json
import h5py
import numpy as np

R = Path(__file__).resolve().parents[3]
O = R / 'results/uk_2d/g2-reconstruction-2026-10-25'
work = O / 'clean-combined-120'
assert json.loads((work / 'status.json').read_text())['state'] == 'COMPLETE'
with h5py.File(work / 'surface.h5') as f:
    area, bed, x = f['Mesh2_face_area'][:], f['Mesh2_face_z'][:], f['Mesh2_face_x'][:]
    h0 = np.where(x < 0, .4, .02)
    volume0 = float(area @ h0)
    energy0 = float(area @ (9.80665 * (.5 * h0 * h0 + bed * h0)))
    maximum_mass_error = maximum_speed = 0.
    maximum_energy_ratio = 0.
    minimum_depth = float('inf')
    frames = len(f['time'])
    for start in range(0, frames, 32):
        h = f['Mesh2_face_depth'][start:start + 32]
        u = f['Mesh2_face_vx'][start:start + 32]
        v = f['Mesh2_face_vy'][start:start + 32]
        assert np.isfinite(h).all() and np.isfinite(u).all() and np.isfinite(v).all()
        minimum_depth = min(minimum_depth, float(h.min()))
        maximum_speed = max(maximum_speed, float(np.hypot(u, v).max()))
        maximum_mass_error = max(maximum_mass_error, float(np.max(abs(h @ area - volume0))))
        energy = (.5 * h * (u * u + v * v) + 9.80665 * (.5 * h * h + bed * h)) @ area
        maximum_energy_ratio = max(maximum_energy_ratio, float(energy.max() / energy0))
value = dict(frames=frames, minimum_depth_m=minimum_depth, maximum_speed_mps=maximum_speed,
             initial_volume_m3=volume0, maximum_volume_error_m3=maximum_mass_error,
             maximum_relative_volume_error=maximum_mass_error / volume0,
             maximum_discrete_energy_ratio=maximum_energy_ratio,
             scope='Independent diagnostics on saved fields; energy is not an additional fitted acceptance criterion.')
(O / 'full-field-diagnostics.json').write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
print(value)
