"""Gate diagnostic execution on qualification and a bit-identical zero-change replay."""
from pathlib import Path
import concurrent.futures as cf
import json
import sys

import h5py
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from run import OUT, PREVIOUS, execute, save, sha

PIN = OUT / 'pinned-experiments'


def main():
    qualification = json.loads((OUT / 'qualification/summary.json').read_text())
    baseline = next(r for r in qualification['modes'] if r['mode'] == 'baseline')
    assert baseline['qualified_for_diagnostic'] and qualification['baseline_cpu_returncode'] == 0
    execute('experimental-replay-1s', duration=1, pin=PIN)
    fields = {}
    with h5py.File(PREVIOUS / 'clean-combined/surface.h5') as original, h5py.File(OUT / 'experimental-replay-1s/surface.h5') as candidate:
        for key in ['time', 'Mesh2_face_depth', 'Mesh2_face_vx', 'Mesh2_face_vy']:
            a = original[key][:10]
            b = candidate[key][:]
            fields[key] = dict(changed_values=int(np.count_nonzero(a != b)), maximum_absolute_difference=float(np.max(abs(a - b))))
    equivalence = dict(status='PASS' if not any(r['changed_values'] for r in fields.values()) else 'FAIL', fields=fields,
                       comparison='Diagnostic baseline branch versus frozen corrected control, all ten saved frames.')
    save(OUT / 'replay-equivalence.json', equivalence)
    assert equivalence['status'] == 'PASS'
    selected = [r['mode'] for r in qualification['modes'] if r['mode'] != 'baseline' and r['qualified_for_diagnostic']]
    protected_sha = 'd40e3cb0b2c3123764bf6b54a4f10c53b2e388fff702890fe32eed07b948bd10'
    assert sha(PREVIOUS.parents[2] / 'corpus/uk-ea-2d/uk-ea-2013-t6a/model.inp') == protected_sha
    save(OUT / 'executed-design.json', dict(selected_modes=selected, excluded_modes=[r for r in qualification['modes'] if not r['qualified_for_diagnostic']],
         basis='Predeclared native/analytical gates, before reading any experimental G2 score.',
         protected_editable_input_sha256=protected_sha))
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda mode: execute('coarse-' + mode, pin=PIN, flags={'OPENSWMM_G2_RECONSTRUCTION': mode}), selected))


if __name__ == '__main__':
    main()
