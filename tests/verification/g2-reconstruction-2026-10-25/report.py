"""Completed-run, measured-only qualification report; never read live HDF5."""
from pathlib import Path
import csv
import datetime as dt
import hashlib
import json
import os
import shutil
import sys

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R))
O = R / 'results/uk_2d/g2-reconstruction-2026-10-25'
OLD = O.parent / 'g2-geometry-momentum-2026-10-25'
BASE = O.parent / 'wall-assessment-2026-10-25/6a-cs0-none-cw0.01'
os.environ.setdefault('MPLCONFIGDIR', str(O / '.plot-cache'))
import h5py
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.tri import Triangulation
from suites.uk_2d import render, tin

CASES = {'original120': ('Original reconstruction, 120 s', 120),
         'original30': ('Original reconstruction, 30 s', 30),
         'original-broad005-30': ('Original reconstruction, broad .05 m, 30 s', 30),
         'clean-combined': ('Corrected gradients + walls, 30 s', 30),
         'vertex-gradient-only': ('Corrected gradients, original walls, 30 s', 30),
         'clean-combined-120': ('Corrected gradients + walls, 120 s', 120),
         'clean-broad005-30': ('Corrected gradients + walls, broad .05 m, 30 s', 30)}
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
read = lambda p: json.loads(Path(p).read_text())


def save(p, data):
    Path(p).write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def tests(p):
    data = read(p)
    rows = [dict(name=s['name'] + '.' + t['name'], failed=bool(t.get('failures')),
                 skipped=t.get('status') == 'NOTRUN' or t.get('result') == 'SKIPPED',
                 details={k: v for k, v in t.items() if k not in ['failures']})
            for s in data['testsuites'] for t in s['testsuite']]
    return dict(tests=data['tests'], failures=data['failures'],
                failed=[x['name'] for x in rows if x['failed']], rows=rows)


def qualify():
    before = tests(O / 'original-final-test/results.json')
    after = tests(O / 'clean-final-test/results.json')
    assert before['tests'] == after['tests'] == 12 and before['failures'] == 6 and after['failures'] == 0
    baseline = tests(O / 'native-isolated/original/results.json')
    native = {}
    for group in ['clean-qualification', 'integration-qualification']:
        native[group] = {name: tests(O / group / name / 'results.json')
                         for name in ['g2_native_reconstruction', 'g2_existing_cpu', 'g2_existing_marcher']}
        assert native[group]['g2_native_reconstruction']['failures'] == 0
        assert native[group]['g2_existing_cpu']['failures'] == 0
        assert set(native[group]['g2_existing_marcher']['failed']) <= set(baseline['failed'])
    analytical = {}
    for name in ['analytical-clean-combined', 'analytical-integration-combined',
                 'analytical-vertex-init-gradient-only']:
        scores = read(O / name / 'scores.json')['cells']
        assert len(scores) == 16 and all(x['verdict'] == 'PASS' for x in scores)
        analytical[name] = dict(cases=16, passed=16)
    assert read(O / 'legacy-replay-equivalence.json')['status'] == 'PASS'
    assert read(O / 'source-equivalence.json')['status'] == 'PASS'
    assert read(O / 'duration-equivalence.json')['status'] == 'PASS'
    assert read(O / 'fixture-audit.json')['status'] == 'PASS'
    registered = tests(O / 'registered-unit/results.json')
    assert registered['tests'] == 12 and registered['failures'] == 0
    value = dict(status='PASS', new_native_failures=[], original=before, corrected=after,
                 baseline_native=baseline, native=native, analytical=analytical, registered_unit=registered,
                 limitation='The original porewater donor failure is retained; the standalone broad native driver skips one OpenMP-specific coupled test. This is not a claim that every engine test passes.')
    save(O / 'qualification.json', value)
    return value


def archive_controls():
    # Thin originals retain their executed identity and their original scientific records.
    for name, source in [('original120', BASE), ('original30', OLD / 'frozen30'),
                         ('original-broad005-30', OLD / 'broad005-30')]:
        dest = O / name
        dest.mkdir(exist_ok=True)
        for filename in ['model.inp', 'case.json', 'manifest.json', 'metrics.json', 'probes.csv',
                         'probe-locations.csv', 'probe-map.json', 'volume.csv', 'status.json', 'process.log']:
            if (source / filename).is_file():
                shutil.copy2(source / filename, dest / filename)
        shutil.copytree(source / 'reference', dest / 'reference', dirs_exist_ok=True)
        if not (dest / 'status.json').exists():
            duration = CASES[name][1]
            rows = list(csv.DictReader((dest / 'probes.csv').open()))
            metric = read(dest / 'metrics.json')
            assert metric['returncode'] == 0 and all(metric['checks'].values())
            assert len(rows) == duration * 60 and float(rows[-1]['time_s']) == duration
            save(dest / 'status.json', dict(state='COMPLETE',
                 basis='Archived finalized numerical metrics and complete six-gauge output history'))


def main():
    for name in ['clean-combined', 'vertex-gradient-only', 'clean-combined-120', 'clean-broad005-30']:
        assert read(O / name / 'status.json')['state'] == 'COMPLETE', name
    qualification = qualify()
    archive_controls()
    records = {}
    for name, (label, duration) in CASES.items():
        work = O / name
        identity = read(work / 'manifest.json')
        metric = read(work / 'metrics.json')
        assert sha(work / 'model.inp') == identity['input_sha256']
        assert metric['returncode'] == 0 and all(metric['checks'].values())
        rows = list(csv.DictReader((work / 'probes.csv').open()))
        assert len(rows) == 6 * duration * 10 and float(rows[-1]['time_s']) == duration
        records[name] = dict(label=label, duration=duration, metrics=metric, rows=rows)
    assert len({sha(O / name / 'reference/observations.csv') for name in CASES}) == 1
    obs = list(csv.DictReader((BASE / 'reference/observations.csv').open()))
    display = read(R / 'suites/uk_2d/figure-display-specs.json')['figures']
    figures = []
    colors = {'original120': '.45', 'original30': '.45', 'clean-combined': '#087f5b',
              'original-broad005-30': '#862e9c',
              'vertex-gradient-only': '#d95f02', 'clean-combined-120': '#087f5b',
              'clean-broad005-30': '#4263eb'}
    plot_labels = {'original120': 'Original / coarse (120 s)', 'original30': 'Original / coarse (30 s)',
                   'original-broad005-30': 'Original / broad 0.05 m (30 s)',
                   'vertex-gradient-only': 'Gradients only / original walls (30 s)',
                   'clean-combined': 'Corrected / coarse (30 s)',
                   'clean-combined-120': 'Corrected / coarse (120 s)',
                   'clean-broad005-30': 'Corrected / broad 0.05 m (30 s)'}
    plotted = ['original120', 'original-broad005-30', 'vertex-gradient-only', 'clean-combined-120', 'clean-broad005-30']
    for quantity, points, source in [('level_m', ['G2', 'G4', 'G5', 'G6'], '4.25'),
                                     ('speed_mps', ['G2', 'G4'], '4.26')]:
        fig, axes = plt.subplots(len(points), 1, figsize=(10, 2.8 * len(points)))
        for ax, point in zip(axes, points):
            for name in plotted:
                record = records[name]
                rr = [r for r in record['rows'] if r['probe'] == point]
                ax.plot([float(r['time_s']) for r in rr],
                        [float(r[quantity]) if float(r['depth_m']) > 1e-4 else np.nan for r in rr],
                        color=colors[name], label=plot_labels[name], lw=1.3)
            rr = [r for r in obs if r['probe'] == point and r['quantity'] == quantity]
            if rr:
                ax.scatter([float(r['time_s']) for r in rr], [float(r['value']) for r in rr],
                           marker='D', s=14, facecolors='none', edgecolors='black',
                           label='Recovered UCL measurement subset', zorder=10)
            else:
                ax.text(.02, .08, 'Measured series unavailable', transform=ax.transAxes)
            ax.set(title=point, xlabel='Time (s)', ylabel='Level (m)' if quantity == 'level_m' else 'Speed (m/s)')
            ax.legend(fontsize=7, loc='upper left', bbox_to_anchor=(1.01, 1), borderaxespad=0)
            ax.grid(alpha=.25)
        fig.suptitle(f'Test 6A: qualified reconstruction, UK Figure {source} panels\nFixed physical inputs; measured subset only; refined run ends at 30 s')
        fig.tight_layout()
        stem = 'reconstruction-uk-' + source.replace('.', '-')
        fig.savefig(O / (stem + '-full-range.png'), dpi=150)
        figures.append(stem + '-full-range.png')
        for ax, point in zip(axes, points):
            ax.set(xlim=display[source]['panels'][point]['xlim'], ylim=display[source]['panels'][point]['ylim'])
        fig.savefig(O / (stem + '.png'), dpi=150)
        figures.append(stem + '.png')
        plt.close(fig)
    states = {}
    fronts = []
    fig, axes = plt.subplots(2, 2, figsize=(12, 9), layout='constrained')
    for ax, name, source in zip(axes.flat, ['original30', 'original-broad005-30', 'clean-combined', 'clean-broad005-30'],
                               [OLD / 'frozen30', OLD / 'broad005-30', O / 'clean-combined', O / 'clean-broad005-30']):
        # Every source here has a completed status; this function never opens running output.
        with h5py.File(source / 'surface.h5') as f:
            conn = f['Mesh2_face_nodes'][:] - int(f['Mesh2_face_nodes'].attrs.get('start_index', 0))
            tri = Triangulation(f['Mesh2_node_x'][:], f['Mesh2_node_y'][:], conn)
            h = f['Mesh2_face_depth'][199]
            fr = np.hypot(f['Mesh2_face_vx'][199], f['Mesh2_face_vy'][199]) / np.sqrt(9.80665 * np.maximum(h, 1e-12))
            x, y = f['Mesh2_face_x'][:], f['Mesh2_face_y'][:]
            art = ax.tripcolor(tri, facecolors=h, vmin=0, vmax=.16, cmap='viridis', rasterized=True)
            owners = {}
            for cell in np.flatnonzero((x > 1) & (x < 5.5) & (abs(y) < 1.5)):
                row = conn[cell]
                for a, b in zip(row, np.roll(row, -1)):
                    owners.setdefault(tuple(sorted((int(a), int(b)))), []).append(cell)
            edges = [[[tri.x[a], tri.y[a]], [tri.x[b], tri.y[b]]]
                     for (a, b), cells in owners.items() if len(cells) == 2 and (fr[cells[0]] - 1) * (fr[cells[1]] - 1) < 0]
            ax.add_collection(LineCollection(edges, colors='cyan', linewidths=.8))
            xs = np.linspace(1.5, 4.5, 601)
            ids = tri.get_trifinder()(xs, np.full_like(xs, -.6))
            assert (ids >= 0).all()
            for t in np.arange(1, 30.01, .5):
                i = round(t / .1) - 1
                depth = f['Mesh2_face_depth'][i][ids]
                speed = np.hypot(f['Mesh2_face_vx'][i][ids], f['Mesh2_face_vy'][i][ids])
                froude = speed / np.sqrt(9.80665 * np.maximum(depth, 1e-12))
                cuts = np.flatnonzero((froude[:-1] >= 1) & (froude[1:] < 1))
                fronts.append(dict(case=name, time_s=float(t), crossing_x_m=float((xs[cuts[0]] + xs[cuts[0] + 1]) / 2) if len(cuts) else None))
        polygon = np.array(tin.geometry()['constraints'][0]['points'])
        ax.fill(polygon[:, 0], polygon[:, 1], color='.65', edgecolor='black')
        ax.plot(2.65, -.6, 'wo', mec='black')
        ax.annotate('G2', (2.65, -.6), xytext=(2.1, -1.1), color='white', arrowprops={'arrowstyle': '->', 'color': 'white'})
        title = plot_labels[name].replace(' (30 s)', '').replace(' / ', '\n')
        ax.set(xlim=(1, 5.5), ylim=(-1.5, 1.5), aspect='equal', title=title, xlabel='x (m)', ylabel='y (m)')
    fig.colorbar(art, ax=list(axes.flat), label='Depth at 20 s (m)', shrink=.7)
    fig.suptitle('Reconstruction and coordinated refinement at 20 s\nCyan edges straddle Fr=1; measured spatial front maps unavailable')
    fig.savefig(O / 'reconstruction-depth-20s.png', dpi=150)
    figures.append('reconstruction-depth-20s.png')
    plt.close(fig)
    with (O / 'front-positions.csv').open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(fronts[0])); w.writeheader(); w.writerows(fronts)
    for name, record in records.items():
        row = min([r for r in record['rows'] if r['probe'] == 'G2'], key=lambda r: abs(float(r['time_s']) - 20))
        states[name] = {k: float(v) for k, v in row.items() if k != 'probe'}
    save(O / 'G2-state-20s.json', states)
    fig, ax = plt.subplots(figsize=(10, 5))
    for name in ['original30', 'original-broad005-30', 'clean-combined', 'clean-broad005-30']:
        rows = [x for x in fronts if x['case'] == name]
        ax.plot([x['time_s'] for x in rows], [x['crossing_x_m'] for x in rows], label=plot_labels[name], color=colors[name])
    ax.axhline(2.65, ls='--', color='black', label='G2')
    ax.set(title='Sampled downstream critical transition along y=-0.6 m\nCell-constant Fr crossing; no measured front trajectory', xlabel='Time (s)', ylabel='First downstream Fr=1 crossing x (m)')
    ax.legend(fontsize=8); ax.grid(alpha=.25); fig.tight_layout()
    fig.savefig(O / 'reconstruction-front-position.png', dpi=150)
    figures.append('reconstruction-front-position.png'); plt.close(fig)
    save(O / 'summary.json', {name: {k: v for k, v in record.items() if k != 'rows'} for name, record in records.items()})
    # Interpretation is deliberately authored after reading all gauges, never inferred from one instant.
    interpretation = read(O / 'interpretation.json')
    fields = read(O / 'full-field-diagnostics.json')
    lines = ['# Test 6A: reconstruction qualification and measured-data reassessment', '',
             'Completed on 26 October 2026. This study changes the numerical reconstruction and reflecting-wall state. Drawing geometry, bank slopes, Manning n=0.01, Coriolis OFF, Smagorinsky Cs=0, free-slip walls, zero wall drag, initial depths and 0.1 s output remain fixed. Cs=0 adds no eddy stress; it selects the existing global momentum path and accepted q/h velocity output. No physical coefficient, gauge location, clock offset or laboratory curve was fitted.', '',
             '## Findings', '', interpretation['finding'], '', interpretation['qualification'], '',
             '## Independent native qualification', '',
             'The original frozen solver fails six of twelve newly added native tests. The corrected solver passes all twelve. Constant fields, sloping lake-at-rest, wet/dry face positivity, compatible affine fields on a rotated irregular TIN, beginning-stage wall pressure, reconstructed wall states, thread parity, vertex velocity bounds and a closed bank-release energy counterexample are tested without using measured UK curves.', '',
             'Velocity bounds use all wet incident cells at a vertex. An arbitrary affine velocity can violate a reflecting wall; the affine interior test therefore excludes stencils touching wall vertices, and a separate wall-compatible tangential affine test checks surface and velocity derivatives. Scalar surface/depth face-stencil admissibility is unchanged. The gradient tolerance remains 2e-11, wall impulse tolerance 2e-12. The bank counterexample must reach 0.5 s within 5,000 steps with no more than 2% energy increase; no UK measurements enter that criterion.', '',
             'The native bank fixture crops 234 triangles and 141 vertices from the actual upstream bank corner, retaining exact coordinates and elevations and closing its exterior with reflective walls. A simpler structured-bank test did not expose the unstable candidate, so both fixtures remain. The cropped fixture is a numerical regression, not a reproduction of the entire laboratory experiment.', '',
             '| Native check | Original | Corrected |', '|---|---|---|']
    original = {x['name']: x for x in qualification['original']['rows']}
    for test in qualification['corrected']['rows']:
        lines.append(f"| {test['name'].split('.')[-1]} | {'FAIL' if original[test['name']]['failed'] else 'PASS'} | PASS |")
    lines += ['', 'Both frozen-source and current-working-source builds pass all 16 existing analytical jump/reflection cases with unchanged criteria. Their broader marcher runs introduce no new failures relative to the original: the original porewater donor failure remains visible, and one OpenMP-specific coupled case is skipped by the standalone test driver. The focused one/four-thread reconstruction test runs in both builds. Current-source CPU correctness checks also pass. This does not claim a clean result for the entire engine test suite.', '',
              '## Numerical changes and rejected candidates', '',
              '1. Replace arithmetic Green–Gauss gradients with a conditioned inverse-distance least-squares fit on hydraulically connected wet neighbors. Retain the existing stencil-conditioning threshold, thin-cell fallback, dry-sill exclusions, face bounds and joint surface/depth positivity scaling.',
              '2. Bound velocity at every cell vertex using incident wet-cell extrema, in addition to face-midpoint bounds. Revert velocity slopes at shoreline and geometrically dry vertices. This prevents the demonstrated bank-corner runaway while retaining admissible affine reconstruction.',
              '3. Evaluate reflective-wall pressure and mirrored velocity from the beginning of the same Euler stage as interior fluxes. At second order, reconstruct the wall face and apply the same hydrostatic bed correction as the interior kernel. Bottom friction still uses the updated depth.',
              '4. Reject unrepresentable pressure/kinetic flux before any face booking, so a deliberately overflowing coupled source trial can roll back atomically.', '',
              'An initial least-squares candidate passed the analytical jumps but became unstable at upstream bank-toe cell 123 around 0.116 s. Reducing CFL from 0.4 to 0.2 and 0.1 did not resolve it. Fixed midpoint bed, an alternate surface-gradient pressure source, common velocity limiting, and conserved-momentum reconstruction also failed the cropped-bank control. Zero velocity slopes were stable but discarded as the final method because they remove second-order velocity reconstruction. Those rejected runs are retained locally and are not treated as completed physical comparisons.', '',
              'Building vertex lookup data during the first advance initially changed the checkpoint mesh fingerprint and broke restart checks. The final method builds the derived lookup during initialization, before checkpoint identity is established. Restart/rollback tests then return to the original failure set. The final production patch contains none of the experimental switches or rejected flux formulas.', '',
              'The wall-only change failed one of the sixteen analytical cases and was not advanced to a UK comparison. The gradient-only UK run is an ablation retaining the known original wall-state inconsistency; passing its analytical cases does not qualify it as a production alternative.', '',
              'The original diagnostic-switch replay is bit-identical to the archived original solution. The cleaned source and current-source integration are separately checked against the prototype over a completed one-second full-domain run; [source-equivalence results](source-equivalence.json) give exact field differences. A short equivalence check establishes implementation identity over that window, not convergence or long-duration physical validation.', '',
              '## Test 6A comparisons', '',
              'The coarse drawing-constrained TIN has 61,642 cells. The broader 0.05 m mesh has 91,420 cells and refines the reservoir, constriction, gate and building together through x=8 m with a graded transition. The full corrected coarse simulation completes 120 s; gradient-only and refined controls complete 30 s. They retain the original dimensioned banks: the central flat bed is 2.92 m wide within vertical walls 3.6 m apart, with 0.34 m banks rising 0.155 m. The throat itself is rectangular and 1 m wide. No trapezoidal 1D channel cross-section is substituted for this terrain.', '',
              f"All 1,200 full-duration frames are finite and nonnegative. Independent saved-field diagnostics give maximum relative water-volume drift {fields['maximum_relative_volume_error']:.3g}, maximum speed {fields['maximum_speed_mps']:.4g} m/s and maximum discrete energy {fields['maximum_discrete_energy_ratio']:.6g} of the initial value. The complete first 30 seconds of depth and both velocity components are bit-identical to the shorter corrected run. These are numerical checks, not proof of laboratory agreement. The [field diagnostics](full-field-diagnostics.json) and [duration equivalence](duration-equivalence.json) retain their scope.", '',
              'Plots reproduce the panels and axis limits of UK report Figures 4.25 and 4.26, with full-range views so clipping is explicit. Comparison is only with the recovered UCL measurement markers, never with another hydraulic model. Original complete measured records and independent second-person digitization review remain unavailable. Time-weighted RMSE uses the same recovered subset and segmented weighting, excludes gaps over 1 s, and does not quantify digitization uncertainty. Measurements do not extend across the full 120-second numerical run.', '',
              '| Configuration | G2 level (m) | G2 speed (m/s) | G4 level (m) | G4 speed (m/s) | G5 level (m) | G6 level (m) |',
              '|---|---:|---:|---:|---:|---:|---:|']
    for name, record in records.items():
        values = {(x['probe'], x['quantity']): x['rmse'] for x in record['metrics']['observed']['metrics']}
        keys = [('G2', 'level_m'), ('G2', 'speed_mps'), ('G4', 'level_m'), ('G4', 'speed_mps'), ('G5', 'level_m'), ('G6', 'level_m')]
        lines.append('| ' + record['label'] + ' | ' + ' | '.join(f'{values[k]:.6g}' if k in values else 'Unavailable' for k in keys) + ' |')
    for name in figures:
        lines += ['', f'![Reconstruction reassessment: {name}]({name})']
    lines += ['', 'The spatial panels show computed depths and cell-face Fr=1 transitions at 20 s. The sampled transition along y=-0.6 m is a cell-constant diagnostic, not a tracked shock-normal trajectory. Measured spatial jump maps are unavailable. Gauge and spatial evidence must be read together; neither a single instant nor one crossing proves the secondary slowdown has been resolved.', '',
              '## Executed inputs and evidence', '']
    for name, record in records.items():
        lines.append(f"- {record['label']}: [input]({name}/model.inp), [history]({name}/probes.csv), [metrics]({name}/metrics.json), [identity]({name}/manifest.json).")
    lines += ['', '[Native and analytical qualification](qualification.json). [Case summary](summary.json). [G2 at 20 s](G2-state-20s.json). [Front samples](front-positions.csv). [Numerical source patch](solver-clean.patch). [Native tests](native-test-source.cpp). [Fixture provenance](bank_corner.json). [Exact fixture audit](fixture-audit.json). [Execution identities](execution-identities.json). [Report identity](report-provenance.json).', '',
              'Raw HDF5 fields, executable libraries, all intermediate source copies and rejected runs remain in the local verification/results directories. The website publishes the thin, hash-sealed evidence package. Canonical benchmark inputs and reviewed anchors are not changed. Runtime measurements share a busy host and are not a performance comparison.', '',
              '## Next work', '', *interpretation['next_steps'], '',
              'Source comparison layout: [Environment Agency SC120002/R, Figures 4.25–4.26](https://assets.publishing.service.gov.uk/media/6033a943d3bf7f721f4b0d49/_SC120002_Benchmarking_2D_hydraulic_models_Report.pdf). The preceding [geometry and momentum audit](../g2-geometry-momentum/report.html) records drawing/DEM distinctions and the gate/initial-condition/output audit.']
    (O / 'report.html').write_text(render.render('\n'.join(lines) + '\n'))
    save(O / 'report-provenance.json', dict(created_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
         figures=figures, figure_sha256={n: sha(O / n) for n in figures},
         cases={name: sha(O / name / 'model.inp') for name in CASES},
         qualification_sha256=sha(O / 'qualification.json'), script_sha256=sha(__file__),
         report_sha256=sha(O / 'report.html')))
    print(json.dumps(states, indent=2))


if __name__ == '__main__':
    main()
