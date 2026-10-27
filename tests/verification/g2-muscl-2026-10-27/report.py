"""Assemble completed-run evidence, preserving original UK panel layouts and axes."""
from pathlib import Path
import csv
import hashlib
import html
import importlib.util
import json
import os
import shutil
import sys

import h5py
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))
from run import OUT, PREVIOUS, sha, save
from suites.uk_2d import observations

os.environ.setdefault('MPLCONFIGDIR', str(OUT / 'mpl-cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

SPEC = importlib.util.spec_from_file_location('muscl_front', ROOT / 'tests/verification/g2-bank-momentum-2026-10-26/front.py')
FRONT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FRONT)
FRONT.O = OUT
STRICT = ROOT / 'results/uk_2d/g2-source-reconciliation-2026-10-26/strict-reference'
QUANTITIES = [('G2', 'level_m'), ('G2', 'speed_mps'), ('G4', 'level_m'), ('G4', 'speed_mps'), ('G5', 'level_m')]


def read(path):
    return json.loads(Path(path).read_text())


def table(headers, rows):
    return '<div class="table"><table><thead><tr>' + ''.join('<th>' + html.escape(str(v)) + '</th>' for v in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(str(v)) + '</td>' for v in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def metric(record, probe, quantity, strict=False):
    metrics = record['strict']['metrics'] if strict else record['metrics']['observed']['metrics']
    return next((m['rmse'] for m in metrics if m['probe'] == probe and m['quantity'] == quantity), None)


def main():
    qualification = read(OUT / 'qualification/summary.json')
    assert read(OUT / 'replay-equivalence.json')['status'] == 'PASS'
    assert qualification['baseline_cpu_returncode'] == 0
    design = read(OUT / 'executed-design.json')
    protected = ROOT / 'corpus/uk-ea-2d/uk-ea-2013-t6a/model.inp'
    assert sha(protected) == design['protected_editable_input_sha256']
    sources = {'coarse-order2': PREVIOUS / 'clean-combined', 'coarse-order1': OUT / 'coarse-order1',
               'coarse-muscl-off': OUT / 'coarse-muscl-off', 'broad-order2': PREVIOUS / 'clean-broad005-30',
               'broad-order1': OUT / 'broad-order1', 'broad-muscl-off': OUT / 'broad-muscl-off'}
    sources.update({'coarse-' + mode: OUT / ('coarse-' + mode) for mode in design['selected_modes']})
    labels = {'coarse-order2': 'Corrected order 2 / coarse', 'coarse-order1': 'First order / coarse',
              'coarse-muscl-off': 'MUSCL off, RK2 / coarse', 'broad-order2': 'Corrected order 2 / broad .05 m',
              'broad-order1': 'First order / broad .05 m', 'broad-muscl-off': 'MUSCL off, RK2 / broad .05 m'}
    labels.update({'coarse-' + mode: mode.replace('-', ' ').capitalize() + ' / coarse' for mode in design['selected_modes']})
    records = {}
    fronts = {}
    reference_hashes = set()
    for name, source in sources.items():
        assert read(source / 'status.json')['state'] == 'COMPLETE', name
        metrics = read(source / 'metrics.json')
        assert metrics['returncode'] == 0 and all(metrics['checks'].values())
        manifest = read(source / 'manifest.json')
        assert sha(source / 'model.inp') == manifest['input_sha256']
        assert sha(source / 'driver.py') == manifest['driver_sha256']
        reference_hashes.add(sha(source / 'reference/observations.csv'))
        if name.startswith('coarse-') and name[7:] in design['selected_modes']:
            mode = name[7:]
            assert next(r['qualified_for_diagnostic'] for r in qualification['modes'] if r['mode'] == mode)
        rows = list(csv.DictReader((source / 'probes.csv').open()))
        assert len(rows) == 1800 and float(rows[-1]['time_s']) == 30
        with np.load(source / 'extracted.npz') as data:
            times, values = data['times'], data['values']
            probes = list(csv.DictReader((source / 'probe-locations.csv').open()))
            strict = observations.compare(STRICT, {}, times, values, probes)
        records[name] = dict(label=labels[name], source=str(source), metrics=metrics, strict=strict)
        fronts[name] = FRONT.inspect(name, source)
        dest = OUT / 'cases' / name
        dest.mkdir(parents=True, exist_ok=True)
        for filename in ['model.inp', 'case.json', 'manifest.json', 'metrics.json', 'probes.csv',
                         'probe-locations.csv', 'probe-map.json', 'volume.csv', 'status.json', 'process.log', 'driver.py']:
            if (source / filename).is_file():
                shutil.copy2(source / filename, dest / filename)
        shutil.copytree(source / 'reference', dest / 'reference', dirs_exist_ok=True)
        records[name]['rows'] = rows
    assert len(reference_hashes) == 1
    shutil.copytree(STRICT, OUT / 'strict-reference', dirs_exist_ok=True)
    groups = {'coarse-methods': ['coarse-order2', 'coarse-order1', 'coarse-muscl-off'],
              'broad-methods': ['broad-order2', 'broad-order1', 'broad-muscl-off'],
              'limiter-study': ['coarse-order2'] + ['coarse-' + mode for mode in design['selected_modes']]}
    observed = list(csv.DictReader((sources['coarse-order2'] / 'reference/observations.csv').open()))
    strict_obs = list(csv.DictReader((STRICT / 'observations.csv').open()))
    display = read(ROOT / 'suites/uk_2d/figure-display-specs.json')['figures']
    figures = []
    for group, names in groups.items():
        for quantity, gauges, number in [('level_m', ['G2', 'G4', 'G5', 'G6'], '4.25'), ('speed_mps', ['G2', 'G4'], '4.26')]:
            fig, axes = plt.subplots(len(gauges), 1, figsize=(11, 2.7 * len(gauges)))
            for ax, gauge in zip(axes, gauges):
                for name in names:
                    rows = [r for r in records[name]['rows'] if r['probe'] == gauge]
                    ax.plot([float(r['time_s']) for r in rows], [float(r[quantity]) if float(r['depth_m']) > 1e-4 else np.nan for r in rows], label=labels[name], lw=1.25)
                for obs, marker, color, label in [(observed, 'D', '#333333', 'Historical recovered subset'),
                                                  (strict_obs, 'o', '#ba2190', 'Strict connected-marker subset')]:
                    rows = [r for r in obs if r['probe'] == gauge and r['quantity'] == quantity]
                    if rows:
                        ax.scatter([float(r['time_s']) for r in rows], [float(r['value']) for r in rows], marker=marker,
                                   s=13 if marker == 'D' else 8, facecolors='none', edgecolors=color, label=label, zorder=10)
                if gauge == 'G6':
                    ax.text(.02, .1, 'Measured series unavailable', transform=ax.transAxes)
                ax.set(title=gauge, xlabel='Time (s)', ylabel='Level (m)' if quantity == 'level_m' else 'Speed (m/s)')
                ax.set_xlim(0, 30)
                ax.grid(alpha=.2)
                ax.legend(loc='upper left', bbox_to_anchor=(1.01, 1), fontsize=7)
            fig.suptitle('Test 6A: ' + group.replace('-', ' ') + ' — UK Figure ' + number + ' panels\nCorrected engine; fixed physics; 30 s diagnostic')
            fig.tight_layout()
            stem = group + '-uk-' + number.replace('.', '-')
            fig.savefig(OUT / (stem + '-full-range.png'), dpi=145)
            for ax, gauge in zip(axes, gauges):
                ax.set(xlim=display[number]['panels'][gauge]['xlim'], ylim=display[number]['panels'][gauge]['ylim'])
            fig.savefig(OUT / (stem + '.png'), dpi=145)
            plt.close(fig)
            figures += [stem + '.png', stem + '-full-range.png']
    for group, names in groups.items():
        fig, axes = plt.subplots(2, 1, figsize=(10, 7), layout='constrained')
        for name in names:
            good = [r for r in fronts[name] if r['valid']]
            line, = axes[0].plot([r['time_s'] for r in good], [r['front_x_at_G2_y_m'] for r in good], label=labels[name])
            for side, style in [('up', '-'), ('down', '--')]:
                axes[1].plot([r['time_s'] for r in good], [r[side + '_normal_Fr_stationary'] for r in good], color=line.get_color(), ls=style)
        axes[0].axhline(2.65, color='black', ls=':', label='G2 x')
        axes[0].set(ylabel='Local fitted front x at y=−0.6 m', title='Depth-gradient front; no measured spatial front map')
        axes[0].legend(fontsize=7)
        axes[1].axhline(1, color='black', ls=':')
        axes[1].set(xlabel='Time (s)', ylabel='Normal Froude number', title='Solid: upstream; dashed: downstream; stationary frame')
        fig.savefig(OUT / (group + '-front-history.png'), dpi=150)
        plt.close(fig)
        figures.append(group + '-front-history.png')
    front20 = {name: next(row for row in rows if row['time_s'] == 20) for name, rows in fronts.items()}
    save(OUT / 'front-at-20s.json', front20)
    compact = {name: {k: v for k, v in record.items() if k != 'rows'} for name, record in records.items()}
    summary = dict(status='COMPLETE', cases=compact, qualification=qualification, front_at_20s=front20,
                   replay=read(OUT / 'replay-equivalence.json'), design=design,
                   observations='Visibility-selected digitized markers; strict subset is a coverage sensitivity, not a replacement full record.',
                   protected_editable_input_sha256=sha(protected))
    save(OUT / 'summary.json', summary)
    historical = table(['Configuration', 'G2 level (m)', 'G2 speed (m/s)', 'G4 level (m)', 'G4 speed (m/s)', 'G5 level (m)'],
                       [[labels[name]] + [f'{metric(record, *q):.6g}' for q in QUANTITIES] for name, record in records.items()])
    strict_table = table(['Configuration', 'Strict G2 level RMSE (m)', 'Strict G2 speed RMSE (m/s)'],
                         [[labels[name], f'{metric(record, "G2", "level_m", True):.6g}', f'{metric(record, "G2", "speed_mps", True):.6g}'] for name, record in records.items()])
    coverage = table(['G2 quantity', 'Historical covered duration (s)', 'Strict covered duration (s)'],
                     [[quantity, next(m['covered_duration_s'] for m in records['coarse-order2']['metrics']['observed']['metrics'] if m['probe'] == 'G2' and m['quantity'] == quantity),
                       next(m['covered_duration_s'] for m in records['coarse-order2']['strict']['metrics'] if m['probe'] == 'G2' and m['quantity'] == quantity)] for quantity in ['level_m', 'speed_mps']])
    state20 = table(['Configuration', 'G2 depth at 20 s (m)', 'G2 speed at 20 s (m/s)', 'Fitted front x at G2 y (m)'],
                    [[labels[name], next(r['depth_m'] for r in record['rows'] if r['probe'] == 'G2' and float(r['time_s']) == 20),
                      next(r['speed_mps'] for r in record['rows'] if r['probe'] == 'G2' and float(r['time_s']) == 20),
                      f"{front20[name]['front_x_at_G2_y_m']:.6g}" if front20[name]['valid'] else 'Invalid local fit'] for name, record in records.items()])
    qualification_table = table(['Experiment', 'Native checks passed', 'Analytical checks passed', 'Test 6 diagnostic admitted'],
        [[r['mode'], f"{r['native_tests'] - len(r['native_failures'])}/{r['native_tests']}",
          f"{r['analytical_passed']}/{r['analytical_cases']}", r['qualified_for_diagnostic']] for r in qualification['modes']])
    narrative = read(OUT / 'interpretation.json')
    assert narrative.get('reviewed') is True
    body = '<h1>Test 6A: first order, MUSCL and limiter controls on the corrected engine</h1><p>27 October 2026 · Completed controlled diagnostic study</p>'
    body += '<p class="finding">' + html.escape(narrative['finding']) + '</p>'
    body += '<h2>What changed</h2><p>The same immutable corrected engine used in the preceding reconstruction study now runs native first order and MUSCL-off/RK2 on both the coarse and broad 0.05 m constrained meshes. First order changes spatial reconstruction and time integration together; MUSCL-off keeps RK2. Geometry, Manning n=.01, Cs=0, Coriolis OFF, free-slip walls, initial depths and 0.1 s reporting stay fixed. Cs=0 supplies no turbulent stress and selects the assessed global momentum path. Every new hydraulic comparison lasts 30 s.</p>'
    body += '<p>Experimental limiter controls use a separately archived source and binary. The inactive branch reproduces all ten saved time/depth/velocity frames of the original corrected first second bit for bit. Shared velocity limiting applies the smaller velocity-component limiter to both components. Shared-all limiting applies the smallest existing factor to surface, depth and both velocity components. Slope-removal ablations isolate scalar versus velocity reconstruction. The same final slopes feed interior and reflecting-wall faces. Archived source revisions and binary hashes define execution identity; generated checkout labels in analytical scores do not replace those identities.</p>'
    body += '<h2>Qualification and excluded controls</h2>' + qualification_table + '<p>' + html.escape(narrative['qualification']) + '</p>'
    body += '<h2>Measured-subset results</h2><p>Values below are segmented time-weighted RMSE on the unchanged historical recovered UCL marker subset. They are not comparisons against other models. G2 level coverage is approximately 7.025 s and speed coverage 17.916 s within the 30 s window. The stricter connected-marker subset has different coverage, so its absolute scores must not be compared with historical-subset scores as an improvement. Gaps longer than one second are excluded; isolated points remain plotted but have zero interval weight in RMSE.</p>' + historical + strict_table
    body += coverage + '<p>' + html.escape(narrative['accuracy']) + '</p>'
    for group in groups:
        body += '<h2>' + html.escape(group.replace('-', ' ').capitalize()) + '</h2>'
        for number in ['4-25', '4-26']:
            stem = group + '-uk-' + number
            body += f'<figure><img src="{stem}.png" alt="{group} UK Figure {number} panel layout"><figcaption>Original UK panel axes. <a href="{stem}-full-range.png">Full 30-second range</a>.</figcaption></figure>'
        body += f'<img src="{group}-front-history.png" alt="{group} fitted front and normal flow">'
    body += '<h2>Front position and interpretation</h2><p>' + html.escape(narrative['front']) + '</p>' + state20
    for name in ['coarse-order2', 'coarse-surface-only', 'coarse-common-velocity']:
        if (OUT / (name + '-front-20s.png')).is_file():
            body += f'<figure><img src="{name}-front-20s.png" alt="{html.escape(labels[name])} depth-gradient front at 20 s"><figcaption>{html.escape(labels[name])}: computed depth, fitted front and G2 at 20 s.</figcaption></figure>'
    body += '<p>Front detection uses the previously tested depth-gradient method: a 0.005 m sampling grid, Gaussian smoothing σ=.02 m, search x=2.2–3.5 m over y=−.8 to −.4 m, followed by a robust local line fit. Normal states are sampled 0.10 m either side. Curvature, motion and transverse flow limit one-dimensional jump interpretations; these samples are not an integrated momentum/energy ledger or measured jump-position map. Invalid fits are retained explicitly.</p>'
    body += '<h2>Decision</h2><p>' + html.escape(narrative['decision']) + '</p><p>The assessed snapshot retains the known full-SWE partially wet crest-isolation failure. This study does not qualify a new shoreline closure, change production defaults, fit physics coefficients, replace measured references or promote canonical regression anchors. Complete measured time series and independent digitization review remain unavailable. Runtime values share a busy host and are not performance comparisons.</p>'
    body += '<h2>Evidence and reproduction</h2><p><a href="summary.json">All cases and scores</a> · <a href="experiment-design.json">Pre-execution experimental design</a> · <a href="executed-design.json">Qualification-based admissions</a> · <a href="replay-equivalence.json">Full-field replay</a> · <a href="diagnostic.patch">Isolated diagnostic patch</a> · <a href="front-at-20s.json">Front states at 20 s</a></p>'
    for name in records:
        body += f'<p>{html.escape(labels[name])}: <a href="cases/{name}/model.inp">executed input</a>, <a href="cases/{name}/probes.csv">all gauge histories</a>, <a href="cases/{name}/manifest.json">execution identity</a>, <a href="{name}-front.json">front history</a>.</p>'
    style = 'body{max-width:1150px;margin:48px auto;padding:0 24px;font:17px/1.6 system-ui;color:#193042}h1{line-height:1.15}h2{margin-top:2em;color:#075969}.finding{padding:20px;background:#e5f1f4;border-left:5px solid #007c91}table{border-collapse:collapse;font-size:14px;width:100%}.table{overflow:auto}td,th{padding:9px;border-bottom:1px solid #cbd8df;text-align:left}th{background:#edf3f6}img{max-width:100%;height:auto}a{color:#006b86}'
    (OUT / 'report.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Test 6A MUSCL controls</title><style>' + style + '</style><main>' + body + '</main></html>')
    source = OUT / 'source'
    source.mkdir(exist_ok=True)
    for path in Path(__file__).parent.iterdir():
        if path.suffix in ['.py', '.md']:
            shutil.copy2(path, source / path.name)
    included = [p for p in OUT.iterdir() if p.is_file() and p.suffix in ['.json', '.patch', '.png', '.html']]
    included += [p for folder in ['cases', 'source', 'strict-reference', 'qualification'] for p in (OUT / folder).rglob('*') if p.is_file() and p.suffix in ['.json', '.csv', '.md', '.py', '.inp', '.log'] and ('/analytical/' not in str(p) or p.name == 'scores.json')]
    manifest = {str(p.relative_to(OUT)): sha(p) for p in included if p.name != 'publication-manifest.json'}
    save(OUT / 'publication-manifest.json', dict(status='COMPLETE', files=manifest, scope='Thin completed-run evidence; raw HDF5, binaries and full source archive remain local.'))
    print(json.dumps(dict(cases=len(records), sealed_files=len(manifest), figures=len(figures)), indent=2))


if __name__ == '__main__':
    main()
