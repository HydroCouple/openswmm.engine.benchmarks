"""Attach independent repeated-run evidence without changing the assessment."""
import argparse
import json
from pathlib import Path
import numpy as np
from .references import digest,write_json


def attach(assessment,repeated):
    assessment=Path(assessment);repeated=Path(repeated)
    scores=json.loads((repeated/'scores.json').read_text(encoding='utf-8'))
    if not scores.get('coverage',{}).get('complete'):raise ValueError('Repeat execution coverage is incomplete')
    rows=[]
    for cell in scores['cells']:
        if cell['solver']!='swmm2d-cpu-full-swe-rk2':continue
        if cell['verdict']!='PASS':raise ValueError('Repeat numerical checks failed')
        a=assessment/cell['case'];b=repeated/cell['case']
        original=json.loads((a/'run-manifest.json').read_text(encoding='utf-8'))
        current=json.loads((b/'run-manifest.json').read_text(encoding='utf-8'))
        for field in ['model_sha256','probes_sha256','analysis_sha256','binaries','reference_hashes']:
            if original[field]!=current[field]:raise ValueError('Different repeat identity: '+field)
        metrics=json.loads((b/'metrics.json').read_text(encoding='utf-8'))
        if metrics['regression'].get('verdict')!='BASELINE-PASS':raise ValueError('Repeat did not pass its reviewed baseline')
        with np.load(a/'extracted.npz') as x,np.load(b/'extracted.npz') as y:
            if not np.array_equal(x['times'],y['times']) or x['values'].shape!=y['values'].shape:raise ValueError('Different repeat sample grid')
            difference=float(abs(x['values']-y['values']).max())
        rows.append(dict(case=cell['case'],verdict='BASELINE-PASS',maximum_absolute_change=difference,
            model_sha256=original['model_sha256'],analysis_sha256=original['analysis_sha256'],
            assessment_manifest_sha256=digest((a/'run-manifest.json').read_bytes()),repeat_manifest_sha256=digest((b/'run-manifest.json').read_bytes()),
            assessment_data_sha256=digest((a/'extracted.npz').read_bytes()),repeat_data_sha256=digest((b/'extracted.npz').read_bytes())))
    executed={c['case'] for c in json.loads((assessment/'scores.json').read_text(encoding='utf-8'))['cells']
              if c['solver']=='swmm2d-cpu-full-swe-rk2' and c.get('checks')}
    if {r['case'] for r in rows}!=executed:raise ValueError('Repeat does not cover every executed assessment configuration')
    write_json(assessment/'regression-repeat.json',dict(scope='Separate complete repeated executions against explicitly reviewed numerical anchors; not a reference-accuracy verdict.',cases=rows))
    return rows


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--assessment',type=Path,required=True);ap.add_argument('--repeated',type=Path,required=True)
    args=ap.parse_args();print(json.dumps(attach(args.assessment,args.repeated),indent=2))
