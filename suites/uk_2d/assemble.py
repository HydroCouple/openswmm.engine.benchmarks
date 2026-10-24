"""Assemble dated evidence without presenting unchanged cases as new executions."""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
from .sources import digest


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def copy_tree(source,dest):
    # Hydraulic outputs remain in their original dated run directories.
    shutil.copytree(source,dest,ignore=shutil.ignore_patterns('*.h5','*.out','.*'),dirs_exist_ok=True)


def merged(original,replacement,output,expected):
    old,new=read(original/'scores.json'),read(replacement/'scores.json')
    completed={c['case'] for c in new['cells'] if c['solver']=='swmm2d-cpu-full-swe-rk2' and
               c['verdict']=='PASS' and c.get('checks') and all(c['checks'].values())}
    if completed!=set(expected) or not new.get('coverage',{}).get('complete'):
        raise ValueError('Replacement cohort must contain exactly the expected completed cases')
    if old['engine_sha']!=new['engine_sha']:raise ValueError('Do not mix engine revisions in a mesh correction assessment')
    copy_tree(original,output)
    history=output/'history';history.mkdir(exist_ok=True)
    shutil.copy2(original/'scores.json',history/'original-scores.json')
    shutil.copy2(replacement/'scores.json',history/'replacement-scores.json')
    if (original/'assessment-history.json').exists():
        shutil.copy2(original/'assessment-history.json',history/'prior-assembly-history.json')
    identities={}
    for ident in sorted(completed):
        target=output/ident
        # A fresh directory prevents old Cartesian plots surviving in TIN evidence.
        if target.exists():
            copy_tree(target,history/('cartesian-'+ident))
            shutil.rmtree(target)
        copy_tree(replacement/ident,target)
    envelope=json.loads(json.dumps(old))
    envelope['cells']=[c for c in old['cells'] if c['case'] not in completed]
    envelope['cells'] += [c for c in new['cells'] if c['case'] in completed]
    for c in envelope['cells']:
        ident=c['case']
        if c['solver']!='swmm2d-cpu-full-swe-rk2' or not c.get('checks'):continue
        source=replacement if ident in completed else original
        m=read(source/ident/'run-manifest.json')
        identities[ident]=dict(source_directory=str(source/ident),
                               run_manifest_sha256=digest((source/ident/'run-manifest.json').read_bytes()),
                               model_sha256=m['model_sha256'],executed=m['created'])
    for name in ['observed_compared','regression_checked']:
        field='observed_status' if name=='observed_compared' else 'regression_status'
        status='compared' if name=='observed_compared' else 'checked'
        envelope['coverage'][name]=sum(c.get(field)==status for c in envelope['cells'] if c['solver']=='swmm2d-cpu-full-swe-rk2')
    (output/'scores.json').write_text(json.dumps(envelope,indent=2)+'\n', encoding='utf-8')
    record=dict(assembled=dt.datetime.now(dt.timezone.utc).isoformat(),
        reason='Test 6A/6B domain-constrained GUI TIN and side-bank geometry replace the raster-mask flat-bed inputs. Other cases retain their original runs and still require mesh correction.',
        replaced_cases=sorted(completed),case_sources=identities,
        historical_evidence='history/: original scores, previous assembly record and superseded Test 6 records. Historical results are not current validation or regression targets.')
    (output/'assessment-history.json').write_text(json.dumps(record,indent=2)+'\n', encoding='utf-8')
    return envelope


def regression(original,replacement,output,expected):
    old,new=read(original/'scores.json'),read(replacement/'scores.json')
    checked={c['case'] for c in new['cells'] if c['solver']=='swmm2d-own-baseline' and c['verdict']=='BASELINE-PASS'}
    if checked!=set(expected) or not new.get('coverage',{}).get('complete'):
        raise ValueError('Corrected cases require separate passing repeated executions')
    if old['engine_sha']!=new['engine_sha']:raise ValueError('Repeated cohort engine mismatch')
    copy_tree(original,output)
    for ident in checked:copy_tree(replacement/ident,output/ident)
    envelope=json.loads(json.dumps(old))
    envelope['cells']=[c for c in old['cells'] if c['case'] not in checked and c['solver']!='coverage']
    envelope['cells'] += [c for c in new['cells'] if c['case'] in checked]
    physical=[c for c in envelope['cells'] if c['solver']=='swmm2d-cpu-full-swe-rk2']
    count=len(physical)
    envelope['coverage']=dict(requested=count,executed=count,regression_checked=count,complete=True,
        observed_compared=sum(c.get('observed_status')=='compared' for c in physical),required_missing=[])
    envelope['requested_cases']=[c['case'] for c in physical]
    (output/'scores.json').write_text(json.dumps(envelope,indent=2)+'\n', encoding='utf-8')
    (output/'assessment-history.json').write_text(json.dumps(dict(original=str(original),replacement=str(replacement),
        replaced_cases=sorted(checked),scope='Existing Test 1/3 repeats plus separate full-duration corrected Test 6 repeats; original manifests retained.'),indent=2)+'\n', encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--replacement',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--regression',action='store_true')
    args=parser.parse_args()
    if args.output.exists():parser.error('Output must be a new dated directory')
    if args.regression:regression(args.original,args.replacement,args.output,['uk-ea-2013-t6a','uk-ea-2013-t6b'])
    else:merged(args.original,args.replacement,args.output,['uk-ea-2013-t6a','uk-ea-2013-t6b'])
