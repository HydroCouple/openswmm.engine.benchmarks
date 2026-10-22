"""Observed goodness of fit, with explicit coverage and gap handling."""
from __future__ import annotations
import csv
import json
import numpy as np
from .sources import digest


def compare(reference_dir, case, times, values, probes):
    """Opt-in long-format CSV; absent or invalid observations never imply fit."""
    manifest_path=reference_dir/'observations.json'
    if not manifest_path.exists():return dict(status='unavailable',reason='Original measured series not supplied',metrics=[])
    manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
    required=['source','citation','quantity_definitions','datum','time_origin','csv_sha256','max_gap_s']
    if any(not manifest.get(k) for k in required):raise ValueError('Incomplete observation provenance')
    if manifest.get('kind') not in ('observed','digitized_observed'):raise ValueError('Invalid observed reference kind')
    data=(reference_dir/'observations.csv').read_bytes()
    if digest(data)!=manifest['csv_sha256']:raise ValueError('Observation hash mismatch')
    if manifest['max_gap_s']<=0:raise ValueError('Observation gap limit must be positive')
    rows=list(csv.DictReader(data.decode().splitlines()))
    result=[]
    for j,p in enumerate(probes):
        for k,quantity in [(1,'level_m'),(2,'speed_mps')]:
            selected=[r for r in rows if r['probe']==p['id'] and r['quantity']==quantity and r.get('value','').strip()]
            if not selected:continue
            obs=np.array([[float(r['time_s']),float(r['value'])] for r in selected])
            if not np.isfinite(obs).all() or np.any(np.diff(obs[:,0])<=0):raise ValueError('Invalid observation records')
            valid=(obs[:,0]>=times[0])&(obs[:,0]<=times[-1]);obs=obs[valid]
            if len(obs)<2:continue
            segments=np.split(np.arange(len(obs)),np.flatnonzero(np.diff(obs[:,0])>manifest['max_gap_s'])+1)
            weights=np.zeros(len(obs))
            for seg in segments:
                if len(seg)<2:continue
                d=np.diff(obs[seg,0]);weights[seg[:-1]]+=d/2;weights[seg[1:]]+=d/2
            if weights.sum()==0:continue
            residual=np.interp(obs[:,0],times,values[:,3*j+k])-obs[:,1]
            result.append(dict(probe=p['id'],quantity=quantity,n=len(obs),covered_duration_s=float(weights.sum()),
                               bias=float(np.average(residual,weights=weights)),mae=float(np.average(abs(residual),weights=weights)),
                               rmse=float(np.sqrt(np.average(residual**2,weights=weights))),
                               max_absolute_residual=float(abs(residual).max()),gate='report'))
    if not result:raise ValueError('No usable measured comparison intervals')
    return dict(status='compared',kind=manifest['kind'],source=manifest['source'],metrics=result)
