"""Rubinato 2017: observed steady fit, numerical diagnostics, synthetic events.

Requires the engine's two Rubinato native test executables. Experimental fit
is report-only; completion, direction, steady-state drift and continuity are
separate numerical checks. Synthetic events never receive an observed label.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
from harness import engines, scoring

SUITE = 'coupling'
RESULTS = REPO_ROOT / 'results' / SUITE
COLLECTION = REPO_ROOT / 'corpus/rubinato-2017'


def options(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-bin', type=Path, default=engines.BIN)
    ap.add_argument('--library', type=Path)
    ap.add_argument('--output-dir', type=Path, default=RESULTS)
    ap.add_argument('--skip-unsteady', action='store_true')
    ap.add_argument('--max-wall', type=float, default=300)
    # run_regression.py forwards every extra option to every suite; rejecting
    # another suite's --tier ended `--suite all` here, before any other ran.
    return ap.parse_known_args(argv)[0]


def read_csv(path):
    with path.open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv=None):
    args = options(argv)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    native = args.native_bin.resolve()
    suffix = '.exe' if os.name == 'nt' else ''
    envelope = scoring.new_envelope(SUITE, engines.engine_sha())
    envelope['interpretation'] = ('PASS means numerical checks passed, not experimental validation. '
                                  'Steady fit is report-only; synthetic events have no measured reference.')
    manifest = {}
    env = engines.env(threads=1, dylib_dirs=[str(native)])
    env['OPENSWMM_2D_BACKEND'] = 'cpu'
    for kind in ('steady', 'model'):
        exe = native / ('test_engine_2d_exchange_rubinato_' + kind + suffix)
        if not exe.exists():
            scoring.save_cell(out/'scores.json', envelope, dict(case='native-'+kind, solver='cpu',
                reference_class='observed', verdict='UNAVAILABLE', note=f'Build {exe.name}'))
            continue
        manifest[exe.name] = digest(exe)
        try:
            with (out / (kind+'.log')).open('w', encoding='utf-8') as log:
                result = subprocess.run([str(exe)], cwd=out, env=env, stdout=log,
                                        stderr=subprocess.STDOUT, timeout=args.max_wall)
            if result.returncode:
                raise RuntimeError(f'{exe.name} exited {result.returncode}')
        except (subprocess.TimeoutExpired, RuntimeError) as exc:
            scoring.save_cell(out/'scores.json', envelope, dict(case='native-'+kind, solver='cpu',
                reference_class='observed', verdict='ERROR', note=str(exc)))
            continue
        if kind == 'steady':
            continue
        rows = read_csv(out/'rubinato2017_model_out/model_vs_table2.csv')
        if len(rows) != 51:
            raise RuntimeError(f'Expected 36 steady comparisons + 15 legacy anchors, got {len(rows)}')
        shaft_rows = read_csv(out/'rubinato2017_model_out/shaft_vs_table2.csv')
        if len(shaft_rows) != 36:
            raise RuntimeError(f'Expected 36 physical-shaft comparisons, got {len(shaft_rows)}')
        rows += shaft_rows
        reference = read_csv(COLLECTION/'rubinato-2017-flume-steady-s1/reference/table2_steady_exchange.csv')
        for row in rows:
            s = row['scenario']
            index = int(row['case'].split('_')[1])-1
            ref = [r for r in reference if r['scenario'] == s][index]
            expected, numerical = float(row['q_e_lps']), abs(float(row['q_num_lps']))
            drift = 100 * abs(float(row['q_num_lps'])-float(row['q_previous_lps'])) / max(numerical, 1e-12)
            continuity = float(row['continuity_pct'])
            checks = dict(completed=float(row['duration_s']) >= 299,
                          direction=(float(row['q_num_lps']) > 0) == (s in ('S3','S4')),
                          steady_drift_2pct=drift <= 2, routing_continuity_2pct=abs(continuity) <= 2)
            cell = dict(case=row['case'], solver='cpu', reference_class='observed',
                        verdict='PASS' if all(checks.values()) else 'FAIL',
                        q_observed_lps=expected, q_model_lps=numerical,
                        signed_q_to_surface_lps=float(row['q_num_lps']),
                        relative_bias_pct=100*(numerical/expected-1),
                        residual_over_xi=(numerical-expected)/float(ref['xi_f_lps']),
                        within_xi_plus_2pct=abs(numerical-expected) <= float(ref['xi_f_lps'])+0.02*expected,
                        continuity_err=continuity, steady_drift_pct=drift, checks=checks,
                        surface_depth_m=float(row['surface_depth_m']), node_head_m=float(row['node_head_m']),
                        surface_depth_residual_mm=None if not ref['h_s_m'] else
                            1000*(float(row['surface_depth_m'])-float(ref['h_s_m'])),
                        node_head_residual_mm=None if not ref['h_p_m'] else
                            1000*(float(row['node_head_m'])-float(ref['h_p_m'])),
                        model_variant='physical_shaft' if row['case'].endswith('_SHAFT') else 'junction_surrogate',
                        fit_gate='report', experimental_qualification=False)
            scoring.save_cell(out/'scores.json', envelope, cell)
        fine = read_csv(out/'rubinato2017_model_out/fine_mesh_equalisation.csv')
        ratio = float(fine[0]['q_num_lps'])/float(fine[1]['q_num_lps'])
        scoring.save_cell(out/'scores.json', envelope, dict(case='fine-mesh-equalisation', solver='cpu',
            reference_class='self_consistency', verdict='PASS' if ratio > 0.5 else 'FAIL',
            capped_over_uncapped=ratio, values=fine, note='Anti-choking check; not mesh convergence.'))

    if not args.skip_unsteady:
        libraries = ([args.library.resolve()] if args.library else
                     sorted(native.glob('*openswmm.engine*.dylib')) +
                     sorted(native.glob('*openswmm.engine*.so')) + sorted(native.glob('*openswmm.engine*.dll')))
        if not libraries:
            scoring.save_cell(out/'scores.json', envelope, dict(case='synthetic-events', solver='cpu',
                reference_class='self_consistency', verdict='UNAVAILABLE', note='Native engine shared library missing'))
        else:
            library = libraries[0]
            manifest[library.name] = digest(library)
            spec = importlib.util.spec_from_file_location('rubinato_decks', COLLECTION/'_tools/make_decks.py')
            decks = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(decks)
            refdir = COLLECTION/'rubinato-2017-flume-unsteady-synthetic/reference'
            rig = decks.read_rig(refdir/'rig_geometry.yaml')
            for test in read_csv(refdir/'table1_unsteady_tests.csv'):
                for bound in ('LOWER','EXPECTED','UPPER'):
                    name = 'synthetic-'+test['test_id']+'-'+bound.lower()
                    work = out/name
                    work.mkdir(exist_ok=True)
                    deck = decks.unsteady_deck(rig, float(test['q3max_over_q1']), float(test['duration_s']))
                    preset = 'RUBINATO2017'+('_'+bound if bound != 'EXPECTED' else '')
                    (work/'model.inp').write_text(deck.replace('COEFFS=RUBINATO2017','COEFFS='+preset), encoding='utf-8')
                    try:
                        with (work/'run.log').open('w', encoding='utf-8') as log:
                            r = subprocess.run([sys.executable, str(Path(__file__).with_name('unsteady.py')),
                                str(library), str(work/'model.inp'), str(work/'metrics.json')],
                                env=env, stdout=log, stderr=subprocess.STDOUT, timeout=args.max_wall)
                        if r.returncode:
                            raise RuntimeError(f'worker exit {r.returncode}; see {work.name}/run.log')
                        metrics = json.loads((work/'metrics.json').read_text(encoding='utf-8'))
                        checks = dict(nonnegative_depth=metrics['min_depth_m'] >= -1e-12,
                                      routing_continuity_2pct=abs(metrics['continuity_pct']) <= 2,
                                      both_directions=metrics['spill_m3'] > 1e-3 and metrics['drain_m3'] > 1e-3,
                                      pulse_exercised=metrics['reversals'] >= 2)
                        cell = dict(case=name, solver='cpu', reference_class='self_consistency',
                                    verdict='PASS' if all(checks.values()) else 'FAIL', checks=checks,
                                    continuity_err=metrics['continuity_pct'], metrics=metrics,
                                    note='Synthetic ramp/plateau event; not the measured T1-T9 hydrograph.')
                    except (subprocess.TimeoutExpired, RuntimeError) as exc:
                        cell = dict(case=name, solver='cpu', reference_class='self_consistency',
                                    verdict='ERROR', note=str(exc))
                    scoring.save_cell(out/'scores.json', envelope, cell)
                    print(name, cell['verdict'], flush=True)
    (out/'binary_manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    return envelope


def report(argv=None):
    out = options(argv).output_dir.resolve()
    envelope = scoring.load(out/'scores.json')
    if not envelope:
        return []
    lines = ['# Rubinato coupling comparison', '',
             'Review evidence. PASS denotes numerical checks only; absolute observed fit is report-only.', '',
             '| Case | Numerical checks | Bias (%) | 1D continuity (%) |',
             '|---|---|---|---|']
    for c in envelope['cells']:
        bias = f"{c['relative_bias_pct']:.2f}" if 'relative_bias_pct' in c else '-'
        cont = f"{c['continuity_err']:.3f}" if 'continuity_err' in c else '-'
        lines.append(f"| {c['case']} | {c['verdict']} | {bias} | {cont} |")
    path = out/'comparison.md'
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    return [path]


if __name__ == '__main__':
    envelope = run(sys.argv[1:])
    report(sys.argv[1:])
    print(scoring.summary(envelope))
    sys.exit(scoring.exit_code(envelope))
