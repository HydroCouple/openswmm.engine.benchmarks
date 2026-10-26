"""Seal reviewed completed evidence, excluding raw fields, binaries and planning files."""
from pathlib import Path
import hashlib
import importlib.util
import json
import shutil

R = Path(__file__).resolve().parents[3]
W = Path(__file__).parent
O = R / 'results/uk_2d/g2-reconstruction-2026-10-25'
read = lambda p: json.loads(Path(p).read_text())
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
spec = importlib.util.spec_from_file_location('reconstruction_report', W / 'report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)
assert read(O / 'qualification.json')['status'] == 'PASS'
provenance = read(O / 'report-provenance.json')
review = read(O / 'review.json')
assert review['status'] == 'PASS' and set(review['figures']) == set(provenance['figures'])
assert sha(O / 'report.html') == provenance['report_sha256']
source = O / 'verification-source'
source.mkdir(exist_ok=True)
for p in W.glob('*.py'):
    shutil.copy2(p, source / p.name)
files = {'qualification.json', 'interpretation.json', 'report.html', 'report-provenance.json',
         'review.json', 'summary.json', 'G2-state-20s.json', 'front-positions.csv',
         'source-equivalence.json', 'duration-equivalence.json', 'legacy-replay-equivalence.json',
         'full-field-diagnostics.json', 'execution-identities.json', 'fixture-audit.json',
         'native-test-source.cpp', 'bank_corner.json', 'bank_corner.mesh',
         'solver-clean.patch', 'product.patch', 'candidate-rejections.json'}
files.update(provenance['figures'])
for name, (_, duration) in report.CASES.items():
    assert read(O / name / 'status.json')['state'] == 'COMPLETE'
    for filename in ['model.inp', 'case.json', 'manifest.json', 'metrics.json', 'probes.csv',
                     'probe-locations.csv', 'probe-map.json', 'volume.csv', 'status.json', 'process.log']:
        if (O / name / filename).is_file():
            files.add(name + '/' + filename)
    files.update(str(p.relative_to(O)) for p in (O / name / 'reference').rglob('*') if p.is_file())
for group in ['original-final-test', 'clean-final-test', 'registered-unit',
              'clean-qualification', 'integration-qualification']:
    for p in (O / group).rglob('*'):
        if p.is_file() and p.suffix in ['.json', '.log'] and 'results.json' == p.name:
            files.add(str(p.relative_to(O)))
    for p in (O / group).glob('*.log'):
        files.add(str(p.relative_to(O)))
for name in ['analytical-clean-combined', 'analytical-integration-combined',
             'analytical-vertex-init-gradient-only', 'analytical-wall-only']:
    files.add(name + '/scores.json')
files.update(str(p.relative_to(O)) for p in source.glob('*.py'))
assert all(Path(name).suffix not in ['.h5', '.npz', '.dylib'] for name in files)
assert not any('plan' in Path(name).name.lower() or Path(name).name == 'design.json' for name in files)
value = dict(qualification='fixed-physics reassessment',
             cases={name: duration for name, (_, duration) in report.CASES.items()},
             files={name: sha(O / name) for name in sorted(files)})
(O / 'publication-manifest.json').write_text(json.dumps(value, indent=2) + '\n')
print('Sealed', len(files), 'artifacts; raw fields and binaries remain local.')
