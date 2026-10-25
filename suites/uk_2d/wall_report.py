"""Methods and audit tables for completed selective-wall experiments."""
from __future__ import annotations
import json


def wall_regions(record, output):
    """Show the actual constrained cells and selected exterior face groups."""
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from . import tin
    work, manifest, metric, rows = record
    sections = {}; section = None
    for raw in (work/'model.inp').read_text().splitlines():
        line = raw.split(';', 1)[0].strip()
        if line.startswith('['):
            section = line.strip('[]'); sections[section] = []
        elif section and line:
            sections[section].append(line.split())
    scale = 1 if manifest['uk_test'] == '6a' else 20
    vertices = np.array([[float(v) for v in row[:2]] for row in sections['2D_VERTICES']])/scale
    cells = np.array([[int(v) for v in row[:3]] for row in sections['2D_TRIANGLES']])
    triangles = vertices[cells]
    fig, axes = plt.subplots(1, 2, figsize=(9, 6))
    for ax, title, limits in zip(axes, ['Constriction throat', 'Obstruction'],
            [(-1.3, .5, -1.9, 1.9), (2.8, 4.8, -.8, 1.1)]):
        x0, x1, y0, y1 = limits
        mask = (triangles[:, :, 0].max(axis=1) >= x0) & (triangles[:, :, 0].min(axis=1) <= x1)
        mask &= (triangles[:, :, 1].max(axis=1) >= y0) & (triangles[:, :, 1].min(axis=1) <= y1)
        ax.add_collection(LineCollection(np.concatenate([triangles[mask][:, [0, 1]],
            triangles[mask][:, [1, 2]], triangles[mask][:, [2, 0]]]), colors='#bbbbbb', linewidths=.25))
        for group, color in [('OTHER_WALLS', '#555555'), ('THROAT', '#bd5700'), ('OBSTRUCTION', '#783ea6')]:
            segments = [vertices[cells[row['cell'], [(row['edge']+1)%3, (row['edge']+2)%3]]]
                for row in manifest['wall_groups'][group]]
            ax.add_collection(LineCollection(segments, colors=color, linewidths=2.3, label=group))
        for constraint in tin.geometry()['constraints']:
            if constraint['marker'] in (20, 30):
                points = np.array(constraint['points'])
                ax.plot(points[:, 0], points[:, 1], '--', color='#00818a', linewidth=1)
        ax.set(xlim=(x0, x1), ylim=(y0, y1), title=title, xlabel='x (m)', ylabel='y (m)')
        ax.set_aspect('equal'); ax.grid(alpha=.15)
    axes[1].legend(loc='upper left', fontsize=8)
    fig.suptitle('Test 6A mesh: wall-friction candidates\nDashed constraints are internal, not walls', fontsize=12)
    fig.tight_layout()
    name='6a-cs0-selected-wall-regions.png'
    fig.savefig(output/name, dpi=160, bbox_inches='tight'); plt.close(fig)
    return name


def methods(records, output):
    lines = ['## Experimental design', '',
        'The wall condition remains impermeable. Its optional tangential traction is '
        '`tau_t/rho = -Cw |u_t| u_t`, with no factor of one half in this coefficient '
        'definition. The force uses the selected edge length and wetted wall height. '
        'Resolved pressure forces around the obstruction already supply form drag; '
        'this experiment adds skin friction only. Cw=0 retains free slip. A roughness '
        'or smooth-wall function would need wall-material and near-wall-resolution '
        'evidence; the present prescribed coefficient does not establish either.', '',
        'All runs use CPU full shallow-water equations, second-order reconstruction, '
        'one timestep tier, CFL 0.4 and a 0.0001 m dry threshold. Smagorinsky uses '
        '`nu_t = (Cs sqrt(A))^2 |S|`; Cs=0 is the no-mixing control and Cs=0.1 is '
        'the mixing sensitivity. Neither coefficient was selected by minimizing '
        'measurement error. No fitted time shift is applied.', '',
        'The constrained TIN has 61,642 triangular cells. Geometry follows the '
        'dimensioned flume drawing, including the banks, dam abutments and rotated '
        'building; it is not a vertexwise reproduction of the pixelated DEM. '
        'Bank toes and the gate-release depth discontinuity are shared internal '
        'constraints, never solid walls. Test 6B scales both horizontal coordinates '
        'and elevations by 20 according to the written specification. The supplied '
        '6B DEM elevation conflict remains a documented interpretation.', '',
        '| Test | Duration (s) | Report interval (s) | Bed Manning n | Wettable area (m²) |',
        '|---|---:|---:|---:|---:|']
    seen = set()
    for work, manifest, metric, rows in records:
        key = manifest['uk_test']
        if key in seen:
            continue
        seen.add(key)
        case = json.loads((work/'canonical-case.json').read_text())
        lines.append(f"| {key.upper()} | {case['end']} | {case['step']} | {case['n']} | {case['area_m2']:g} |")
    provenance = output/'build-provenance.json'
    hardware = json.loads(provenance.read_text()).get('hardware') if provenance.exists() else None
    if hardware:
        lines += ['', f"Execution host: {hardware['cpu']} ({hardware['model']}), "
            f"{hardware['memory_bytes']/2**30:g} GiB RAM, {hardware['physical_cores']} physical cores. "
            'Each case uses one solver thread. A fixed CPU clock frequency and minimum '
            'hardware requirement are not established by this experiment.']
    lines += ['', '| Selected solid-wall region | Faces | Length in 6A (m) | Length in 6B (m) |',
        '|---|---:|---:|---:|']
    sample = records[0][1]
    scale = 1 if sample['uk_test'] == '6a' else 20
    for name in ['THROAT', 'OBSTRUCTION', 'OTHER_WALLS']:
        group = sample['wall_groups'][name]
        length = sum(row['length_m'] for row in group)/scale
        lines.append(f'| {name} | {len(group)} | {length:g} | {20*length:g} |')
    all_walls=any(set(record[1]['selected_groups'])==set(record[1]['wall_groups']) for record in records)
    coverage=('The all-walls control also applies the same Cw to OTHER_WALLS; regional cases retain free slip there.'
              if all_walls else 'OTHER_WALLS remain free slip in the configurations shown.')
    lines += ['', coverage+' Named assignments '
        'are retained in the executed inputs. In the GUI, select exterior edges, '
        'choose Wall, set the Wall friction Cw field, and use the boundary Group '
        'control to keep throat and obstruction selections separate. Undo/redo, '
        'the edge table and INP export use the same assignments.', '',
        f'![Actual constrained TIN and selected wall regions]({wall_regions(records[0], output)})', '',
        '## Reference and sampling limits', '',
        'Only isolated visible UCL measurement diamonds from the 2013 report '
        'are used. Continuous curves from other solvers are excluded. Occluded '
        'markers are missing, same-pixel time samples were averaged, and instrument '
        'uncertainty is unknown. This visibility-selected subset cannot establish '
        'fit to the complete experiment. The original complete measurement series '
        'and an independent second-person digitization remain unavailable.', '',
        'Model probes use the containing cell, with the lowest cell index on a '
        'shared-edge tie. Levels are cell bed plus depth and speeds are the '
        'accepted momentum divided by depth. Model histories are interpolated '
        'at recovered measurement times. Dry cells are masked in the plots; '
        'G6 has no recovered observations. Test 6B has no independent physical '
        'reference and is assessed only for numerical behavior.', '',
        '| Probe / quantity | Recovered samples | Weighted covered duration (s) |',
        '|---|---:|---:|']
    reference = next((r[2] for r in records if r[1]['uk_test'] == '6a'), None)
    if reference:
        for row in reference['observed']['metrics']:
            lines.append(f"| {row['probe']} / {row['quantity']} | {row['n']} | {row['covered_duration_s']:.6g} |")
    lines += ['', 'Residuals use trapezoidal time weights within recovered segments; '
        'gaps longer than 1 s are not bridged. Covered duration is the sum of '
        'those segment durations, not uninterrupted measurement coverage. '
        'The errors below are '
        'report-only diagnostics and are not regression pass/fail thresholds.', '',
        '## Numerical evidence and reproducibility', '',
        '| Case | Depth / continuity / volume checks | Elapsed time (s) | Input | Audit | Gauge histories |',
        '|---|---|---:|---|---|---|']
    for work, manifest, metric, rows in records:
        status = ' / '.join('PASS' if value else 'FAIL' for value in metric['checks'].values())
        lines.append(f"| {work.name} | {status} | {metric['wall_s']:.1f} | [INP]({work.name}/model.inp) | "
            f'[metrics]({work.name}/metrics.json), [identity]({work.name}/manifest.json) | '
            f'[CSV]({work.name}/probes.csv) |')
    lines += ['', 'The extractor requires every scheduled output through the full '
        'duration, finite saved fields, nonnegative depths, an accepted solver '
        'conservation ledger and an independently integrated volume balance. '
        'Native 0.1 s and 1 s report-clock preflights also check an analytical '
        'wall-channel velocity before expensive runs. Earlier attempts with '
        'ambiguous numeric report-step tokens had no output frames and were '
        'rejected; none of their data enter this assessment.', '',
        'The [build record](build-provenance.json) and per-case identity files '
        'retain exact CLI/library hashes, input hashes and analysis identity. '
        'Source inputs come from committed corpus revision 0e60707, preserving '
        'the separately edited working input. [Assessment plan](assessment-plan.json). '
        'Runs share machine resources, so their elapsed times are not controlled '
        'performance comparisons. Analytical and authoring tests qualify the '
        'implementation; mesh/timestep sensitivity and material roughness '
        'qualification remain necessary before adopting a closure.', '',
        '## Measured-subset errors and wall dissipation', '']
    interpretation = output/'interpretation.json'
    if interpretation.exists():
        finding = json.loads(interpretation.read_text())
        lines += [finding['finding'], '', finding['qualification'], '']
    return lines


def bias_table(records):
    lines = ['', '## Signed residuals against recovered measurements', '',
        'Bias is model minus measurement. Positive speed bias means overprediction; '
        'water-level bias retains the common flume-bed datum.', '',
        '| Case | Probe / quantity | Bias (m or m/s) | MAE (m or m/s) | Maximum absolute residual (m or m/s) |',
        '|---|---|---:|---:|---:|']
    for work, manifest, metric, rows in records:
        for row in metric['observed']['metrics']:
            lines.append(f"| {work.name} | {row['probe']} / {row['quantity']} | "
                f"{row['bias']:.6g} | {row['mae']:.6g} | {row['max_absolute_residual']:.6g} |")
    return lines
