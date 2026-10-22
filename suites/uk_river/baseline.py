"""Explicit initial numerical anchors; never promote an existing baseline in place."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import shutil
from .references import CORPUS,digest,write_json
from .suite import analysis_hash


def promote(results,key,review):
    work=Path(results)/('uk-river-'+key);metrics=json.loads((work/'metrics.json').read_text(encoding='utf-8'))
    case=json.loads((work/'case.json').read_text(encoding='utf-8'));identity=json.loads((work/'run-manifest.json').read_text(encoding='utf-8'))
    if not review.strip():raise ValueError('A specific review record is required')
    if not metrics['checks'] or not all(metrics['checks'].values()):raise ValueError('Cannot anchor a failed numerical case')
    if identity['analysis_sha256']!=analysis_hash():raise ValueError('Analysis changed after this execution')
    if digest((work/'model.inp').read_bytes())!=case['model_sha256']:raise ValueError('Executed input changed')
    current=json.loads((CORPUS/case['id']/'case.json').read_text(encoding='utf-8'))
    if current['model_sha256']!=case['model_sha256']:raise ValueError('Corpus input changed since execution')
    target=CORPUS/case['id']/'baselines/cpu-full-swe-rk2'
    target.mkdir(parents=True,exist_ok=False)
    shutil.copy2(work/'extracted.npz',target/'baseline.npz')
    write_json(target/'baseline.json',dict(model_sha256=case['model_sha256'],probes_sha256=case['probes_sha256'],analysis_sha256=analysis_hash(),
        reference_sha256=digest((work/'reference/reference.json').read_bytes()),data_sha256=digest((target/'baseline.npz').read_bytes()),
        rtol=1e-7,atol=1e-8,review=review,engine_sha=identity['engine_sha'],binaries=identity['binaries'],
        meaning='Initial numerical change-control anchor only; not laboratory/analytical acceptance or qualified cross-platform tolerance.'))
    return target


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--results',type=Path,required=True)
    ap.add_argument('--only',required=True);ap.add_argument('--review',required=True)
    args=ap.parse_args()
    for key in args.only.split(','):print(promote(args.results,key,args.review))
