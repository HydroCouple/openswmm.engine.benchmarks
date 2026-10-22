"""Independent-reference river suite; no competitor comparisons or fitted shifts."""
from __future__ import annotations
import argparse
import csv
import datetime as dt
import json
from pathlib import Path
import shutil
import numpy as np
from harness import engines,runner,scoring
from suites.uk_2d import sampling
from suites.uk_2d.suite import binary_manifest
from .build import KEYS,reference
from .references import ROOT,CORPUS,HERE,digest,write_json,write_csv

_LOADED_ANALYSIS=digest(Path(__file__).read_bytes()+Path(sampling.__file__).read_bytes())


def options(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--only',default=','.join(KEYS));ap.add_argument('--tier',choices=['pr','nightly','weekly'],default='nightly')
    ap.add_argument('--exe',type=Path,default=engines.REFACT_EXE)
    ap.add_argument('--output-dir',type=Path,default=ROOT/'results/uk_river')
    ap.add_argument('--max-wall',type=float,default=600)
    ap.add_argument('--build-provenance',type=Path);ap.add_argument('--require-complete',action='store_true')
    ap.add_argument('--require-regression',action='store_true')
    args=ap.parse_args(argv)
    args.keys=list(dict.fromkeys(args.only.split(',')))
    if set(args.keys)-set(KEYS):ap.error('Unknown river case')
    if args.tier=='pr' and args.only==','.join(KEYS):args.keys=['a1','l']
    if args.max_wall<=0:ap.error('--max-wall must be positive')
    return args


def analysis_hash():
    return digest(Path(__file__).read_bytes()+Path(sampling.__file__).read_bytes())


def validate(path):
    case=json.loads((path/'case.json').read_text(encoding='utf-8'))
    for name in ['model','probes']:
        file=path/('model.inp' if name=='model' else 'probes.csv')
        if digest(file.read_bytes())!=case[name+'_sha256']:raise ValueError('Altered '+name)
    ref=reference(case['key']);meta=json.loads((ref/'reference.json').read_text(encoding='utf-8'))
    if meta['kind']!='unavailable' and digest((ref/'reference.csv').read_bytes())!=meta['csv_sha256']:
        raise ValueError('Altered independent reference')
    return case,meta


def norms(predicted,observed):
    residual=np.asarray(predicted)-np.asarray(observed)
    if not np.isfinite(residual).all() or residual.size==0:raise ValueError('Empty/non-finite reference comparison')
    return dict(n=int(residual.size),bias_m=float(residual.mean()),rmse_m=float(np.sqrt(np.mean(residual**2))),
                linf_m=float(abs(residual).max()))


def compare(key,case,data,h5,work):
    import h5py
    ref=reference(key);meta=json.loads((ref/'reference.json').read_text(encoding='utf-8'))
    if meta['kind']=='unavailable':return dict(status='unavailable',reason=meta['reason'],metrics=[])
    records=np.genfromtxt(ref/'reference.csv',delimiter=',',names=True,dtype=None,encoding='utf-8')
    metrics=[]
    if key.startswith('l'):
        for index,name in enumerate(['S1','S2','S3','S4']):
            # t=0 is an authored initial state, not an HDF5 output; exclude it from fit.
            times=records['time_s'];keep=(times>=data['times'][0])&(times<=data['times'][-1])
            obs=records[name][keep];pred=np.interp(times[keep],data['times'],data['values'][:,3*index+1])
            metrics.append(dict(probe=name,**norms(pred,obs),covered_duration_s=float(times[keep][-1]-times[keep][0])))
            write_csv(work/(name+'-comparison.csv'),['time_s','measured_level_m','computed_level_m','residual_m'],zip(times[keep],obs,pred,pred-obs))
        return dict(status='compared',kind='observed',metrics=metrics,time_shift_s=0,source_samples_per_probe=len(records),
                    scope='All source observations after the first required output; no visibility selection or fitted time shift. Rounding +/-0.0005 m; instrument uncertainty unknown.')
    with h5py.File(h5) as f:
        x=f['Mesh2_face_x'][:];z=f['Mesh2_face_z'][:];unique=np.unique(x)
        if key.startswith('a'):
            h=f['Mesh2_face_depth'][-1];eta=np.array([np.mean((h+z)[x==v]) for v in unique])
            # Compare at published interior sections; interpolate cross-channel mean levels.
            chain=records['chainage_m'];keep=(100-chain>=unique[0])&(100-chain<=unique[-1])
            pred=np.interp(100-chain[keep],unique,eta);obs=records['level_m'][keep]
            depth=obs-records['bed_m'][keep]
            write_csv(work/'comparison.csv',['chainage_m','analytical_level_m','computed_level_m','residual_m','depth_error_pct'],zip(chain[keep],obs,pred,pred-obs,100*(pred-obs)/depth))
            write_csv(work/'profile.csv',['chainage_m','computed_level_m','bed_m'],zip(100-unique,eta,[z[x==v].mean() for v in unique]))
            metrics.append(dict(quantity='level_m',**norms(pred,obs)))
        else:
            c=meta['wave_celerity_mps'];initial_x=records['distance_from_upstream_m']
            for t in [0,18000,36000,54000,72000]:
                if t==0:continue
                index=int(round(t/case['step']))-1
                if abs(data['times'][index]-t)>1e-8:raise ValueError('Missing monoclinal profile time')
                depth=f['Mesh2_face_depth'][index];pred=np.array([depth[x==v].mean() for v in unique])
                obs=np.interp(unique-c*t,initial_x,records['depth_m'])
                write_csv(work/f'profile-{t}s.csv',['distance_from_upstream_m','analytical_depth_m','computed_depth_m','residual_m'],zip(unique,obs,pred,pred-obs))
                metrics.append(dict(time_s=t,quantity='depth_m',**norms(pred,obs)))
    return dict(status='compared',kind='analytic',metrics=metrics,
        scope='Dimensional reference errors are reported, not a calibrated accuracy gate. See case deviations for wall/friction and tabulation differences.')


def regression(path,case,data,identity,reference_hash,required=False):
    folder=path/'baselines/cpu-full-swe-rk2';meta=folder/'baseline.json'
    if not meta.exists():return dict(status='unavailable',verdict='ERROR' if required else 'UNAVAILABLE',reason='No explicitly reviewed numerical baseline')
    m=json.loads(meta.read_text(encoding='utf-8'))
    expected=dict(model_sha256=case['model_sha256'],probes_sha256=case['probes_sha256'],analysis_sha256=analysis_hash(),reference_sha256=reference_hash)
    if any(m.get(k)!=v for k,v in expected.items()):raise ValueError('Baseline identity mismatch')
    if digest((folder/'baseline.npz').read_bytes())!=m['data_sha256']:raise ValueError('Baseline data hash mismatch')
    with np.load(folder/'baseline.npz') as f:
        if not np.array_equal(f['times'],data['times']) or f['values'].shape!=data['values'].shape:raise ValueError('Baseline sample grid mismatch')
        passed=np.allclose(f['values'],data['values'],rtol=m['rtol'],atol=m['atol'])
        return dict(status='checked',verdict='BASELINE-PASS' if passed else 'BASELINE-FAIL',maximum_absolute_change=float(abs(f['values']-data['values']).max()))


def run(argv=None):
    args=options(argv);out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    if analysis_hash()!=_LOADED_ANALYSIS:raise ValueError('Analysis source changed after module loading; restart the run')
    exe=args.exe.resolve();binaries=binary_manifest(exe) if exe.is_file() else {}
    provenance=json.loads(args.build_provenance.read_text(encoding='utf-8')) if args.build_provenance else None
    if provenance and provenance['binaries']!=binaries:raise ValueError('Build provenance binary mismatch')
    envelope=scoring.new_envelope('uk_river',provenance['engine_sha'] if provenance else engines.engine_sha())
    envelope.update(requested=args.keys,interpretation='PASS denotes numerical execution/conservation. Published reference fit is reported separately; no competitor reference is used.',coverage={})
    complete=[];compared=[]
    for key in args.keys:
        ident='uk-river-'+key;path=CORPUS/ident;work=out/ident
        cell=dict(case=ident,solver='swmm2d-cpu-full-swe-rk2',reference_class='self_consistency',
            independent_reference_class='observed' if key.startswith('l') or key=='j' else 'unavailable' if key=='e' else 'analytic')
        if key=='j':cell.update(verdict='UNAVAILABLE',note='Measured afflux targets imported; a faithful bridge and paired no-bridge model is pending.')
        elif not exe.is_file():cell.update(verdict='ERROR',note='Primary executable missing')
        else:
            try:
                case,meta=validate(path);work.mkdir(parents=True,exist_ok=True)
                for name in ['model.inp','case.json']:shutil.copy2(path/name,work/name)
                shutil.copy2(path/'probes.csv',work/'probe-locations.csv')
                if (work/'reference').exists():shutil.rmtree(work/'reference')
                shutil.copytree(reference(key),work/'reference')
                for name in ['surface.h5','extracted.npz','metrics.json','comparison.csv','profile.csv','fields.npz']:
                    (work/name).unlink(missing_ok=True)
                for pattern in ['*-comparison.csv','profile-*s.csv']:
                    for p in work.glob(pattern):p.unlink()
                if shutil.disk_usage(work).free<2*1024**3:raise ValueError('Insufficient disk reserve')
                result=runner.run(exe,work/'model.inp',work/'model.rpt',work/'model.out',cwd=work,timeout=args.max_wall,
                    dylib_dirs=[str(exe.parent),str(exe.parent.parent/'engine')],extra_env={'OPENSWMM_2D_BACKEND':'cpu'})
                (work/'process.log').write_text(result.get('stdout','')+'\n'+result['stderr'],encoding='utf-8')
                identity=dict(case=ident,engine_sha=envelope['engine_sha'],checkout_context=engines.engine_sha(),binaries=binaries,
                    build_provenance=provenance,model_sha256=case['model_sha256'],probes_sha256=case['probes_sha256'],analysis_sha256=analysis_hash(),
                    reference_hashes={p.name:digest(p.read_bytes()) for p in sorted(reference(key).glob('*')) if p.is_file()},
                    process=result,created=dt.datetime.now(dt.timezone.utc).isoformat(),
                    provenance_note='Executed binary hashes identify this build; checkout context alone does not establish build identity.')
                write_json(work/'run-manifest.json',identity)
                if not result['ok']:raise ValueError('Engine did not finish: '+result['stderr'][-1000:])
                text=(work/'model.rpt').read_text(errors='replace', encoding='utf-8')
                if 'ERROR' in text or 'MOMENTUM_EQUATION FULL_SWE' not in text or '2D solver: cpu' not in text:
                    raise ValueError('Fatal diagnostic or requested solver not confirmed')
                if any(s in (text+result.get('stdout','')+result['stderr']).lower() for s in ['fallback','falling back','falls back']):raise ValueError('Solver fallback')
                if analysis_hash()!=_LOADED_ANALYSIS:raise ValueError('Analysis source changed during execution; restart the run')
                probes=list(csv.DictReader((path/'probes.csv').open(encoding='utf-8')))
                data=sampling.extract(work/'surface.h5',case,probes,work)
                continuity=100*data['ledger']['continuity_error']
                checks=dict(finite_depth=data['minimum_depth_m']>=-1e-10,continuity=abs(continuity)<=.5)
                reference_fit=compare(key,case,data,work/'surface.h5',work)
                reference_hash=digest((reference(key)/'reference.json').read_bytes())
                base=regression(path,case,data,identity,reference_hash,args.require_regression)
                metrics=dict(checks=checks,continuity_pct=continuity,reference_fit=reference_fit,regression=base,wall_s=result['wall'])
                write_json(work/'metrics.json',metrics)
                np.savez_compressed(work/'extracted.npz',times=data['times'],values=data['values'])
                cell.update(verdict='PASS' if all(checks.values()) else 'FAIL',checks=checks,continuity_err=continuity,
                    wall_s=result['wall'],reference_status=reference_fit['status'],regression_status=base['status'])
                complete.append(key)
                if reference_fit['status']=='compared':compared.append(key)
                if base['status']=='checked' or args.require_regression:
                    scoring.save_cell(out/'scores.json',envelope,dict(case=ident,solver='swmm2d-own-baseline',reference_class='blessed_baseline',**base))
            except Exception as exc:cell.update(verdict='ERROR',note=f'{type(exc).__name__}: {exc}')
        print(ident,cell['verdict'],cell.get('note',''),flush=True)
        scoring.save_cell(out/'scores.json',envelope,cell)
    missing=sorted(set(args.keys)-set(complete))
    envelope['coverage']=dict(requested=len(args.keys),executed=len(complete),independent_reference_compared=len(compared),
        complete=not missing,unexecuted=missing,reference_unavailable=sorted(set(complete)-set(compared)),
        scientific_validation_complete=False)
    scoring.save_cell(out/'scores.json',envelope,dict(case='required-coverage',solver='coverage',reference_class='self_consistency',
        verdict='ERROR' if args.require_complete and missing else 'PASS',missing_cases=missing))
    return envelope


def report(argv=None):
    from .report import build
    return build(options(argv).output_dir.resolve())
