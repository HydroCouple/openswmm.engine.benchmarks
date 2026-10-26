"""Replay a published corrected Test 6A deck without changing canonical inputs."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R))
from harness import engines
from suites.uk_2d import sampling, checks, observations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence-root', type=Path, required=True,
                        help='Published evidence/g2-reconstruction directory')
    parser.add_argument('--case', choices=['clean-combined', 'clean-combined-120', 'clean-broad005-30'],
                        default='clean-combined-120')
    parser.add_argument('--exe', type=Path, required=True)
    parser.add_argument('--library-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True,
                        help='New reviewable results directory; existing directories are refused')
    args = parser.parse_args()
    source = args.evidence_root.resolve() / args.case
    work = args.output.resolve()
    if work.exists():
        raise ValueError('Use a new results directory: ' + str(work))
    expected = json.loads((source / 'manifest.json').read_text())
    sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
    if sha(source / 'model.inp') != expected['input_sha256']:
        raise ValueError('Published executed input identity differs')
    work.mkdir(parents=True)
    for name in ['model.inp', 'case.json', 'probe-locations.csv']:
        shutil.copy2(source / name, work / name)
    shutil.copy2(source / 'manifest.json', work / 'source-manifest.json')
    shutil.copytree(source / 'reference', work / 'reference')
    executable = args.exe.resolve()
    env = engines.env(1, [str(executable.parent), str(args.library_dir.resolve())])
    for key in list(env):
        if key.startswith('OPENSWMM_G2_') or key == 'OPENSWMM_2D_MUSCL_OFF':
            env.pop(key)
    identity = dict(input_sha256=sha(work / 'model.inp'), executable_sha256=sha(executable),
                    driver_sha256=sha(__file__), source_case=args.case,
                    supplied_library_dir=str(args.library_dir.resolve()),
                    note='Replay identity; rebuilding from source need not reproduce executable bytes. Compare complete fields and numerical checks before interpreting differences.')
    (work / 'replay-identity.json').write_text(json.dumps(identity, indent=2) + '\n')
    started = time.monotonic()
    with (work / 'process.log').open('w') as log:
        result = subprocess.run([str(executable), str(work / 'model.inp'), str(work / 'model.rpt'),
                                 str(work / 'model.out')], cwd=work, env=env,
                                stdout=log, stderr=subprocess.STDOUT, timeout=10800)
    if result.returncode != 0:
        raise RuntimeError('Solver failed; see process.log')
    case = json.loads((work / 'case.json').read_text())
    with (work / 'probe-locations.csv').open() as stream:
        probes = list(csv.DictReader(stream))
    data = sampling.extract(work / 'surface.h5', case, probes, work)
    if len(data['times']) != round(case['end'] / case['step']) or abs(float(data['times'][-1]) - case['end']) > 1e-8:
        raise RuntimeError('Output is incomplete despite the process return code')
    metrics = dict(returncode=0, wall_s=time.monotonic() - started, **checks.numerical(case, data))
    metrics['observed'] = observations.compare(work / 'reference', case, data['times'], data['values'], probes)
    (work / 'metrics.json').write_text(json.dumps(metrics, indent=2, allow_nan=False) + '\n')
    if not all(metrics['checks'].values()):
        raise RuntimeError('Numerical checks failed; see metrics.json')
    print(work)


if __name__ == '__main__':
    main()
