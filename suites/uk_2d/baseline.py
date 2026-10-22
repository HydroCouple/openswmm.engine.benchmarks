"""Explicitly record an initially reviewed baseline; refuses failing/incomplete runs."""
import argparse
import datetime as dt
import json
import shutil
from pathlib import Path
from .build import COLLECTION
from .sources import digest


def promote(run_dir, reviewer, reason, atol=1e-6, rtol=1e-5):
    path=Path(run_dir)
    metrics=json.loads((path/'metrics.json').read_text(encoding='utf-8'))
    manifest=json.loads((path/'run-manifest.json').read_text(encoding='utf-8'))
    case=json.loads((path/'case.json').read_text(encoding='utf-8'))
    if not reviewer.strip() or not reason.strip():raise ValueError('Reviewer and reason are required')
    if not all(metrics['checks'].values()):raise ValueError('Cannot promote failing numerical checks')
    target=COLLECTION/case['id']/'baselines/cpu-full-swe-rk2'
    if (target/'baseline.json').exists():raise ValueError('Existing baseline requires a separate reviewed replacement; no automatic overwrite')
    target.mkdir(parents=True,exist_ok=True)
    shutil.copy2(path/'extracted.npz',target/'baseline.npz')
    record={k:manifest[k] for k in ['engine_sha','model_sha256','probes_sha256','analysis_sha256']}
    record.update(reviewer=reviewer,reason=reason,date=dt.datetime.now(dt.timezone.utc).isoformat(),
                  binary_sha256=manifest['binaries'],atol=atol,rtol=rtol,data_sha256=digest((target/'baseline.npz').read_bytes()),
                  qualification='Initial local numerical regression anchor; no observed accuracy or cross-platform qualification implied')
    (target/'baseline.json').write_text(json.dumps(record,indent=2)+'\n', encoding='utf-8')
    return target

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('run_dir',type=Path);ap.add_argument('--reviewer',required=True);ap.add_argument('--reason',required=True)
    args=ap.parse_args();print(promote(args.run_dir,args.reviewer,args.reason))
