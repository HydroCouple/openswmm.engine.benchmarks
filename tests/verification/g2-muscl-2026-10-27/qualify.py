"""Record native and analytical outcomes before interpreting experimental Test 6 runs."""
from pathlib import Path
import concurrent.futures as cf
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).parent))
from run import OUT, sha, save

WORK = ROOT.parent / 'openswmm.engine/tests/verification/g2_muscl_2026-10-27'
PIN = OUT / 'pinned-experiments'
MODES = ['baseline', 'surface-only', 'velocity-only', 'common-velocity', 'common-all']
# Slope-removal ablations deliberately sacrifice linear reconstruction accuracy.
# These three checks explicitly require nonzero exact slopes; all other native
# safety/consistency checks and all analytical cases remain mandatory.
ACCURACY = {'AdmissibleLinearFieldsAreExactOnIrregularTin',
            'TangentialLinearSurfaceAtReflectingWall', 'WallPressureUsesReconstructedBeginningState'}


def qualify(mode):
    out = OUT / 'qualification' / mode
    out.mkdir(parents=True)
    env = os.environ.copy()
    env['DYLD_LIBRARY_PATH'] = str(PIN / 'engine')
    env['OMP_NUM_THREADS'] = '1'
    env['SWMM_RK2_TEST_OUT'] = str(out)
    for key in list(env):
        if key.startswith('OPENSWMM_G2_') or key == 'OPENSWMM_2D_MUSCL_OFF':
            env.pop(key)
    env['OPENSWMM_G2_RECONSTRUCTION'] = mode
    identity = dict(mode=mode, executable_sha256=sha(PIN / 'bin/openswmm'),
                    library_sha256=sha(PIN / 'engine/libopenswmm.engine.6.0.0.dylib'),
                    native_sha256=sha(WORK / 'native/reconstruction'), environment={'OPENSWMM_G2_RECONSTRUCTION': mode})
    save(out / 'identity.json', identity)
    with (out / 'native.log').open('w', encoding='utf-8') as log:
        result = subprocess.run([str(WORK / 'native/reconstruction'), '--gtest_output=json:' + str(out / 'native.json')],
                                cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=180)
    native = json.loads((out / 'native.json').read_text(encoding='utf-8'))
    failures = [test['name'] for suite in native['testsuites'] for test in suite['testsuite'] if test.get('failures')]
    with (out / 'analytical.log').open('w', encoding='utf-8') as log:
        analytical_code = subprocess.run([str(ROOT / '.venv/bin/python'), str(ROOT / 'run_regression.py'),
            '--suite', 'analytical/hydraulic_jumps', '--exe', str(PIN / 'bin/openswmm'),
            '--output-dir', str(out / 'analytical'), '--max-wall', '300'], cwd=ROOT, env=env,
            stdout=log, stderr=subprocess.STDOUT, timeout=600).returncode
    scores = json.loads((out / 'analytical/scores.json').read_text(encoding='utf-8'))
    cells = scores['cells']
    passed = sum(cell['verdict'] == 'PASS' for cell in cells)
    ablation = mode in ['surface-only', 'velocity-only']
    disallowed = sorted(set(failures) - (ACCURACY if ablation else set()))
    summary = dict(**identity, native_tests=native['tests'], native_failures=failures,
                   native_returncode=result.returncode, analytical_returncode=analytical_code,
                   analytical_cases=len(cells), analytical_passed=passed,
                   qualified_for_diagnostic=native['tests'] == 12 and not disallowed and len(cells) == passed == 16,
                   full_native_accuracy_pass=not failures,
                   note='Slope-removal ablations cannot qualify as production second-order methods.' if ablation else 'All native checks required.')
    save(out / 'summary.json', summary)
    print(json.dumps(summary), flush=True)
    return summary


if __name__ == '__main__':
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        rows = list(pool.map(qualify, MODES))
    # CPU regression is run on the unmodified diagnostic branch.
    out = OUT / 'qualification'
    env = os.environ.copy()
    env['DYLD_LIBRARY_PATH'] = str(PIN / 'engine')
    env['OMP_NUM_THREADS'] = '1'
    for key in list(env):
        if key.startswith('OPENSWMM_G2_') or key == 'OPENSWMM_2D_MUSCL_OFF':
            env.pop(key)
    with (out / 'cpu.log').open('w', encoding='utf-8') as log:
        code = subprocess.run([str(WORK / 'native/cpu'), '--gtest_output=json:' + str(out / 'cpu.json')],
                              cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=300).returncode
    save(out / 'summary.json', dict(modes=rows, baseline_cpu_returncode=code))
    assert rows[0]['qualified_for_diagnostic'] and code == 0
