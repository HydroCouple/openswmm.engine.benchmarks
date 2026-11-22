"""Verify the committed counterexample against completed original mesh output."""
from pathlib import Path
import hashlib
import json
import h5py
import numpy as np

R = Path(__file__).resolve().parents[3]
O = R / 'results/uk_2d/g2-reconstruction-2026-10-25'
BASE = O.parent / 'wall-assessment-2026-10-25/6a-cs0-none-cw0.01'
E = R.parent / 'openswmm.engine/tests/unit/engine/data/swe_reconstruction'
meta = json.loads((E / 'bank_corner.json').read_text(encoding='utf-8'))
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(BASE / 'model.inp') == meta['source_input_sha256']
assert sha(E / 'bank_corner.mesh') == meta['fixture_sha256']
assert json.loads((BASE / 'metrics.json').read_text(encoding='utf-8'))['returncode'] == 0
with h5py.File(BASE / 'surface.h5') as f:
    assert len(f['time']) == 1200
    xyz = np.column_stack([f['Mesh2_node_x'][:], f['Mesh2_node_y'][:], f['Mesh2_node_z'][:]])
    cells = f['Mesh2_face_nodes'][:] - int(f['Mesh2_face_nodes'].attrs.get('start_index', 0))
    selected = np.flatnonzero((f['Mesh2_face_x'][:] < -6.45) & (f['Mesh2_face_y'][:] < -.7))
assert selected.tolist() == meta['original_cell_ids']
vertices = np.unique(cells[selected])
assert vertices.tolist() == meta['original_vertex_ids']
lines = (E / 'bank_corner.mesh').read_text(encoding='utf-8').splitlines()
nv, nt = map(int, lines[0].split())
actual_xyz = np.array([[float(x) for x in line.split()] for line in lines[1:1 + nv]])
actual_cells = np.array([[int(x) for x in line.split()] for line in lines[1 + nv:]])
remap = {int(v): i for i, v in enumerate(vertices)}
expected_cells = np.array([[remap[int(v)] for v in row] for row in cells[selected]])
assert np.array_equal(actual_xyz, xyz[vertices]) and np.array_equal(actual_cells, expected_cells)
assert (nv, nt) == (141, 234)
value = dict(status='PASS', vertices=nv, triangles=nt, exact_coordinates_and_elevations=True,
             exact_connectivity=True, source_input_sha256=meta['source_input_sha256'],
             fixture_sha256=meta['fixture_sha256'],
             limitation='The crop introduces artificial exterior walls; it is a bounded-energy numerical counterexample, not the laboratory domain.')
(O / 'fixture-audit.json').write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
print(value)
