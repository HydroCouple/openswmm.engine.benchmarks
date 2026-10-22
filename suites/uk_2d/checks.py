"""Numerical checks and explicit reviewed SWMM2D baseline comparisons."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from .sources import integral, digest


def numerical(case, data):
    ledger=data['ledger']
    continuity=ledger.get('continuity_error')
    if continuity is None or not np.isfinite(continuity):raise ValueError('Missing finite continuity_error')
    percent=100*float(continuity)
    checks=dict(nonnegative_depth=data['minimum_depth_m']>=case['numerical_limits']['min_depth_m'],
                continuity=abs(percent)<=case['numerical_limits']['continuity_pct'])
    final=data['final_volume_m3'];initial=case['initial_volume_m3']
    external=integral(np.asarray(case['forcing'])) if case.get('boundary_kind')=='flow' else 0.
    residual=None
    if case.get('boundary_kind')!='stage':
        residual=final-initial-external
        scale=max(initial,external,1e-9)
        checks['independent_volume']=abs(residual)/scale*100<=case['numerical_limits']['continuity_pct']
    return dict(checks=checks,continuity_err=percent,volume_residual_m3=residual,initial_volume_m3=initial,
                final_volume_m3=final,prescribed_inflow_m3=external)


def regression(reference_dir, case, times, values, analysis_hash):
    manifest_path=reference_dir/'baseline.json'
    if not manifest_path.exists():return dict(status='unavailable',reason='No reviewed baseline')
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    for field in ['reviewer','reason','engine_sha','binary_sha256','date']:
        if not manifest.get(field):raise ValueError('Baseline review metadata missing: '+field)
    for field,current in [('model_sha256',case['model_sha256']),('probes_sha256',case['probes_sha256']),('analysis_sha256',analysis_hash)]:
        if manifest.get(field)!=current:raise ValueError('Baseline incompatible: '+field)
    path=reference_dir/'baseline.npz'
    if digest(path.read_bytes())!=manifest.get('data_sha256'):raise ValueError('Baseline hash mismatch')
    with np.load(path) as base:
        if base['times'].shape!=times.shape or not np.allclose(base['times'],times,atol=1e-6,rtol=0):raise ValueError('Baseline times differ')
        if base['values'].shape!=values.shape:raise ValueError('Baseline quantities differ')
        tolerance=manifest['atol']+manifest['rtol']*abs(base['values'])
        difference=abs(base['values']-values)
        ok=bool(np.all(difference<=tolerance))
    return dict(status='checked',verdict='BASELINE-PASS' if ok else 'BASELINE-FAIL',max_absolute_change=float(difference.max()),review=manifest)
