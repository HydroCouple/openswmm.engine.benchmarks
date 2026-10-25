"""Run UK cases against independent references and approved SWMM2D baselines."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
import os
import platform
import re
import shutil
from pathlib import Path
import numpy as np
from harness import engines, runner, scoring, runtime
from suites.uk_2d import sampling, checks, observations
from suites.uk_2d.build import COLLECTION, case_id
from suites.uk_2d.sources import ROOT, digest

SUITE='uk_2d'
RESULTS=ROOT/'results/uk_2d'
KEYS=['1','2','3','4','5','6a','6b','7','8a','8b']


def options(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--tier',choices=['pr','nightly','weekly'],default='nightly')
    ap.add_argument('--only',help='Comma-separated UK test keys or corpus IDs')
    ap.add_argument('--exe',type=Path,default=engines.REFACT_EXE)
    ap.add_argument('--output-dir',type=Path,default=RESULTS)
    ap.add_argument('--max-wall',type=float,default=300)
    ap.add_argument('--require-complete',action='store_true')
    ap.add_argument('--require-regression',action='store_true')
    ap.add_argument('--require-observed',action='store_true')
    ap.add_argument('--retain-h5',action='store_true')
    ap.add_argument('--build-provenance',type=Path,help='Verified clean build identity manifest')
    args=ap.parse_args(argv)
    if args.max_wall<=0:ap.error('--max-wall must be positive')
    return args


def analysis_hash():
    # Extraction/check identity deliberately excludes report presentation.
    return digest(b''.join((Path(__file__).parent/n).read_bytes() for n in ['sampling.py','checks.py','observations.py']))


def validate_case(path):
    c=json.loads((path/'case.json').read_text(encoding='utf-8'))
    import jsonschema
    jsonschema.validate(c,json.loads(Path(__file__).with_name('case.schema.json').read_text(encoding='utf-8')))
    for field,file in [('model_sha256','model.inp'),('probes_sha256','probes.csv')]:
        if digest((path/file).read_bytes())!=c[field]:raise ValueError('Case input hash mismatch: '+file)
    text=(path/'model.inp').read_text(encoding='utf-8')
    for key in ['REPORT_STEP','WET_STEP','DRY_STEP']:
        field=re.search(r'^'+key+r'\s+(\S+)',text,re.M)
        if field is not None and field.group(1).count(':')!=2:
            raise ValueError(key+' must use explicit HH:MM:SS clock units; bare numbers use legacy hours')
    token=re.search(r'^REPORT_STEP\s+(\S+)',text,re.M)
    if token is None:raise ValueError('Missing REPORT_STEP')
    value=token.group(1)
    interval=sum(float(v)*60**i for i,v in enumerate(reversed(value.split(':')))) if ':' in value else float(value)
    if not np.isclose(interval,c['step'],atol=1e-10,rtol=0):
        raise ValueError('Authored REPORT_STEP differs from the case output interval')
    if c['step']<=0 or c['end']<=0 or c['cell_count']<=0:raise ValueError('Invalid case dimensions')
    return c


def selected(args):
    keys=['1','3'] if args.tier=='pr' else KEYS
    if args.only:
        requested=args.only.split(',')
        mapping={case_id(k):k for k in KEYS}|{k:k for k in KEYS}
        if any(k not in mapping for k in requested):raise ValueError('Unknown --only case')
        keys=list(dict.fromkeys(mapping[k] for k in requested))
    return keys


def binary_manifest(exe):
    paths={exe.resolve()}
    for directory in [exe.parent,exe.parent.parent/'engine']:
        for pattern in ['*openswmm*.dylib','*openswmm*.so*','*openswmm*.dll']:
            paths.update(p.resolve() for p in directory.glob(pattern) if p.is_file())
    return {str(p):digest(p.read_bytes()) for p in sorted(paths)}


def run(argv=None):
    args=options(argv);out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    scorepath=out/'scores.json'
    envelope=scoring.new_envelope(SUITE,engines.engine_sha())
    envelope.update(interpretation='PASS denotes numerical checks only. Observed fit is report-only. Baseline agreement is change control.',
                    coverage={},requested_cases=selected(args),source_gaps={'6a':'Original measured series missing','8a':'Authoritative input dataset missing','8b':'Authoritative input dataset missing'})
    done=[];fit=[];regressed=[]
    exe=args.exe.resolve()
    binaries=binary_manifest(exe) if engines.available(exe) else {}
    build_provenance=json.loads(args.build_provenance.read_text(encoding='utf-8')) if args.build_provenance else None
    runtime_ledger=runtime.load()
    if build_provenance:envelope['engine_sha']=build_provenance['engine_sha']
    if build_provenance and build_provenance.get('binaries')!=binaries:
        raise ValueError('Build provenance binary hashes differ from executed artifacts')
    for key in envelope['requested_cases']:
        ident=case_id(key);path=COLLECTION/ident;work=out/ident
        cell=dict(case=ident,solver='swmm2d-cpu-full-swe-rk2',reference_class='self_consistency')
        if not (path/'case.json').exists():
            cell.update(verdict='UNAVAILABLE',note=('Original inputs missing' if key.startswith('8') else 'Faithful geometry/coupling implementation pending'))
        elif runtime.skip_reason(runtime_ledger,SUITE,ident,args.max_wall):
            why=runtime.skip_reason(runtime_ledger,SUITE,ident,args.max_wall)
            runtime.warn(ident+': '+why)
            cell.update(verdict='SKIP',note=why+'; full canonical run remains required for qualification')
        elif not engines.available(exe):cell.update(verdict='UNAVAILABLE',note='Primary engine executable unavailable')
        else:
            try:
                case=validate_case(path)
                estimate=int(np.ceil(case['end']/case['step'])*case['cell_count']*8*6)
                if shutil.disk_usage(out).free < estimate+1024**3:
                    raise ValueError(f'Insufficient output space: need conservative {estimate/1024**3:.2f} GiB plus 1 GiB reserve')
                work.mkdir(parents=True,exist_ok=True)
                for name in ['model.inp','case.json']:shutil.copy2(path/name,work/name)
                for sidecar in ['mesh-provenance.json','source-scale-audit.json']:
                    if (path/sidecar).exists():shutil.copy2(path/sidecar,work/sidecar)
                    else:(work/sidecar).unlink(missing_ok=True)
                shutil.copy2(path/'probes.csv',work/'probe-locations.csv')
                for directory in ['reference','profiles']:
                    if (work/directory).exists():shutil.rmtree(work/directory)
                    if (path/directory).exists():shutil.copytree(path/directory,work/directory)
                # No output cache: every requested execution is fresh.
                for name in ['surface.h5','extracted.npz','metrics.json','observed-fit.json']:
                    (work/name).unlink(missing_ok=True)
                manifest=dict(schema_version=1,engine_sha=build_provenance['engine_sha'] if build_provenance else engines.engine_sha(),
                              engine_checkout_context=engines.engine_sha(),benchmark_sha=engines.git_sha(ROOT),
                              binaries=binaries,model_sha256=case['model_sha256'],probes_sha256=case['probes_sha256'],
                              source_hashes=case['source_hashes'],analysis_sha256=analysis_hash(),
                              reference_hashes={p.name:digest(p.read_bytes()) for p in sorted((path/'reference').glob('*')) if p.is_file()},
                              build_provenance=build_provenance,case_sha256=digest((path/'case.json').read_bytes()),
                              platform=platform.platform(),machine=platform.machine(),threads=1,
                              requested=dict(backend='CPU',momentum='FULL_SWE',reconstruction_order=2,lts_tiers=1,cfl=.4),
                              case=ident,created=dt.datetime.now(dt.timezone.utc).isoformat(),
                              reproducibility_note='Clean archived source build; full identity in build_provenance.' if build_provenance else 'Binary hashes identify executed artifacts. Checkout SHA is contextual; this existing build is not asserted to be a clean build of that SHA.')
                result=runner.run(exe,work/'model.inp',work/'model.rpt',work/'model.out',cwd=work,
                                  dylib_dirs=[str(exe.parent),str(exe.parent.parent/'engine')],timeout=args.max_wall,extra_env={'OPENSWMM_2D_BACKEND':'cpu'})
                (work/'process.log').write_text(result.get('stdout','')+'\n'+result['stderr']+'\n', encoding='utf-8')
                manifest.update(process=result)
                (work/'run-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n', encoding='utf-8')
                if not result['ok']:raise ValueError(f'Engine exit {result["returncode"]}: {result["stderr"]}')
                report=(work/'model.rpt').read_text(errors='replace', encoding='utf-8')
                if 'ERROR' in report:raise ValueError('Fatal diagnostic in engine report')
                if 'MOMENTUM_EQUATION FULL_SWE' not in report or '2D solver: cpu' not in report:
                    raise ValueError('Requested primary solver not confirmed in report')
                diagnostics=report+'\n'+result.get('stdout','')+'\n'+result['stderr']
                if any(s in diagnostics.lower() for s in ['falls back','falling back','fallback','reduced to 1']):
                    raise ValueError('Unqualified solver fallback diagnostic')
                probes=list(csv.DictReader((work/'probe-locations.csv').open(encoding='utf-8')))
                data=sampling.extract(work/'surface.h5',case,probes,work)
                metrics=checks.numerical(case,data)
                metrics.update(wall_s=result['wall'],peak_scope=data['peak_scope'],clock_rounding_max_s=data['clock_rounding_max_s'],deviations=case['deviations'])
                obs=observations.compare(work/'reference',case,data['times'],data['values'],probes) if key=='6a' else dict(status='not_applicable',metrics=[])
                base=checks.regression(path/'baselines/cpu-full-swe-rk2',case,data['times'],data['values'],analysis_hash())
                metrics.update(observed=obs,regression=base)
                np.savez_compressed(work/'extracted.npz',times=data['times'],values=data['values'])
                (work/'metrics.json').write_text(json.dumps(metrics,indent=2,allow_nan=False)+'\n', encoding='utf-8')
                (work/'observed-fit.json').write_text(json.dumps(obs,indent=2,allow_nan=False)+'\n', encoding='utf-8')
                cell.update(verdict='PASS' if all(metrics['checks'].values()) else 'FAIL',
                            continuity_err=metrics['continuity_err'],checks=metrics['checks'],
                            wall_s=result['wall'],observed_status=obs['status'],regression_status=base['status'])
                done.append(key)
                if obs['status']=='compared':fit.append(key)
                if base['status']=='checked':
                    regressed.append(key)
                    scoring.save_cell(scorepath,envelope,dict(case=ident,solver='swmm2d-own-baseline',reference_class='blessed_baseline',**{k:v for k,v in base.items() if k!='review'}))
                if not args.retain_h5 and cell['verdict']=='PASS':(work/'surface.h5').unlink()
            except Exception as exc:cell.update(verdict='ERROR',note=f'{type(exc).__name__}: {exc}')
        print(ident,cell['verdict'],cell.get('note',''),flush=True)
        scoring.save_cell(scorepath,envelope,cell)
    requested=envelope['requested_cases']
    required=requested if args.require_complete or args.tier=='weekly' else [k for k in requested if k in ('1','3')]
    missing=set(required)-set(done)
    missing_reg=set(required)-set(regressed) if args.require_regression else set()
    missing_fit={'6a'}-set(fit) if args.require_observed else set()
    envelope['coverage']=dict(requested=len(requested),executed=len(done),observed_compared=len(fit),regression_checked=len(regressed),
                              complete=set(requested)==set(done),required_missing=sorted(missing),
                              observed_validation_complete=False,
                              qualification_note='Fit to a visible digitized subset is exploratory; original data and scientific qualification remain pending')
    verdict='ERROR' if missing or missing_reg or missing_fit or not requested else 'PASS'
    scoring.save_cell(scorepath,envelope,dict(case='required-coverage',solver='coverage',reference_class='self_consistency',verdict=verdict,
                      missing_cases=sorted(missing),missing_regressions=sorted(missing_reg),missing_observed=sorted(missing_fit)))
    return envelope


def report(argv=None):
    from suites.uk_2d.figures import build_report
    args=options(argv)
    return build_report(args.output_dir.resolve())

if __name__=='__main__':
    import sys
    env=run(sys.argv[1:]);report(sys.argv[1:]);sys.exit(scoring.exit_code(env))
