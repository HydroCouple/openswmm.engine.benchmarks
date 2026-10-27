"""Controlled Test 6A reconstruction diagnostics against an immutable engine image."""
from pathlib import Path
import argparse
import concurrent.futures as cf
import csv
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from harness import engines
from suites.uk_2d import sampling, checks, observations

OUT = ROOT / 'results/uk_2d/g2-muscl-2026-10-27'
PREVIOUS = ROOT / 'results/uk_2d/g2-reconstruction-2026-10-25'
PIN = PREVIOUS / 'pinned-clean'
EXPECTED_EXE = 'cf831af7586e5f2447c8de3ad0a776d88d6d6c38b4ea882725c1340467222927'
EXPECTED_LIB = '3cfc7aa091be45e1261052bab12cb0d1a57085c4563594d4537624fc479c0dad'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def execute(name, duration=30, pin=PIN, flags=None):
    flags = dict(flags or {})
    broad = name.startswith('broad-')
    base = PREVIOUS / ('clean-broad005-30' if broad else 'clean-combined')
    work = OUT / name
    assert not work.exists(), work
    executable = pin / 'bin/openswmm'
    library = pin / 'engine/libopenswmm.engine.6.0.0.dylib'
    if pin == PIN:
        assert sha(executable) == EXPECTED_EXE and sha(library) == EXPECTED_LIB
    work.mkdir(parents=True)
    original = (base / 'model.inp').read_text()
    text, n = re.subn(r'^END_TIME\s+.*$', f'END_TIME 00:{duration // 60:02}:{duration % 60:02}', original, flags=re.M)
    assert n == 1
    if 'order1' in name:
        text, n = re.subn(r'^RECONSTRUCTION_ORDER\s+.*$', 'RECONSTRUCTION_ORDER 1', text, flags=re.M)
        assert n == 1
    if 'muscl-off' in name:
        flags['OPENSWMM_2D_MUSCL_OFF'] = '1'
    # Verify the only deck changes are the explicitly declared duration/order.
    normalize = lambda s: re.sub(r'^RECONSTRUCTION_ORDER\s+.*$', 'RECONSTRUCTION_ORDER 2',
                                re.sub(r'^END_TIME\s+.*$', 'END_TIME NORMALIZED', s, flags=re.M), flags=re.M)
    assert normalize(original) == normalize(text)
    (work / 'model.inp').write_text(text)
    case = json.loads((base / 'case.json').read_text())
    case.update(id=name, end=duration, model_sha256=sha(work / 'model.inp'))
    if duration < 30:
        # The full Test 6 extractor requests fixed snapshots through 30 s.
        # This short replay qualifies field identity, not the full case.
        case.update(parent_uk_test=case['uk_test'], uk_test='diagnostic-preflight')
    case['deviations'] += ['Declared reconstruction diagnostic; no canonical input or regression-anchor promotion.']
    save(work / 'case.json', case)
    shutil.copy2(base / 'probe-locations.csv', work / 'probe-locations.csv')
    shutil.copytree(base / 'reference', work / 'reference')
    shutil.copy2(__file__, work / 'driver.py')
    manifest = dict(input_sha256=sha(work / 'model.inp'), control_input_sha256=sha(base / 'model.inp'),
                    executable=str(executable), library=str(library), executable_sha256=sha(executable),
                    library_sha256=sha(library), driver_sha256=sha(__file__), environment=flags,
                    duration_s=duration, observations_sha256=sha(work / 'reference/observations.csv'),
                    scope='Corrected 336ca729 solver snapshot; fixed physics; historical visible-marker subset.')
    save(work / 'manifest.json', manifest)
    env = engines.env(1, [str(executable.parent), str(library.parent)])
    for key in list(env):
        if key.startswith('OPENSWMM_G2_') or key == 'OPENSWMM_2D_MUSCL_OFF':
            env.pop(key, None)
    env.update(flags)
    env['OPENSWMM_2D_BACKEND'] = 'cpu'
    started = time.monotonic()
    try:
        with (work / 'process.log').open('w') as log:
            process = subprocess.Popen([str(executable), str(work / 'model.inp'), str(work / 'model.rpt'),
                                        str(work / 'model.out')], cwd=work, env=env, stdout=log, stderr=subprocess.STDOUT)
            save(work / 'status.json', dict(state='RUNNING', pid=process.pid, driver_pid=os.getpid(),
                                           started_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
            code = process.wait(timeout=7200)
        assert code == 0, code
        assert sha(executable) == manifest['executable_sha256'] and sha(library) == manifest['library_sha256']
        probes = list(csv.DictReader((work / 'probe-locations.csv').open()))
        data = sampling.extract(work / 'surface.h5', case, probes, work)
        assert len(data['times']) == duration * 10 and abs(data['times'][-1] - duration) < 1e-8
        result = dict(returncode=code, wall_s=time.monotonic() - started, **checks.numerical(case, data))
        assert all(result['checks'].values()), result
        result['observed'] = (observations.compare(work / 'reference', case, data['times'], data['values'], probes)
                              if duration >= 5 else dict(status='not_assessed', reason='Short numerical replay only', metrics=[]))
        save(work / 'metrics.json', result)
        np.savez_compressed(work / 'extracted.npz', times=data['times'], values=data['values'])
        save(work / 'status.json', dict(state='COMPLETE', checks=result['checks'], wall_s=result['wall_s']))
        print(name, 'COMPLETE', round(result['wall_s'], 2), flush=True)
    except BaseException as error:
        save(work / 'status.json', dict(state='FAILED', error=repr(error)))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('cases', nargs='+')
    parser.add_argument('--duration', type=int, default=30)
    parser.add_argument('--pin', type=Path, default=PIN)
    parser.add_argument('--flags', default='{}')
    args = parser.parse_args()
    OUT.mkdir(exist_ok=True)
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda name: execute(name, args.duration, args.pin, json.loads(args.flags)), args.cases))
