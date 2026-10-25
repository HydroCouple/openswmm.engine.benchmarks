"""Opt-in end-to-end check that sub-30-second output contains fresh velocity."""
import os
import json
from pathlib import Path
import numpy as np
import pytest
from harness import engines,runner
from suites.uk_2d.sources import ROOT,digest


@pytest.mark.skipif(os.environ.get('UK_2D_ENGINE_TEST')!='1',reason='Explicit native engine integration run')
def test_velocity_is_refreshed_at_subsecond_output_times():
    import h5py
    exe=Path(os.environ.get('UK_2D_ENGINE_EXE',str(engines.REFACT_EXE))).resolve()
    assert engines.available(exe),'Requested native test engine is unavailable'
    from suites.uk_2d.suite import binary_manifest
    identity=digest(json.dumps(binary_manifest(exe),sort_keys=True).encode())[:12]
    work=ROOT/'results/uk_2d/output-freshness-test'/identity
    work.mkdir(parents=True,exist_ok=True)
    inp=work/'model.inp';h5=work/'surface.h5';h5.unlink(missing_ok=True)
    inp.write_text('''[OPTIONS]
FLOW_UNITS CMS
FLOW_ROUTING DYNWAVE
START_DATE 01/01/2026
START_TIME 00:00:00
END_DATE 01/01/2026
END_TIME 00:00:03
REPORT_STEP 0:00:00.1
WET_STEP 0:00:00.1
DRY_STEP 0:00:00.1
ROUTING_STEP 0.1
[JUNCTIONS]
J 0 10 0 0 0
[OUTFALLS]
O 0 FREE NO
[CONDUITS]
C J O 100 .01 0 0 0
[XSECTIONS]
C CIRCULAR 1 0 0 0 1
[2D_OPTIONS]
BACKEND CPU
INTEGRATOR EXPLICIT
MOMENTUM_EQUATION FULL_SWE
RECONSTRUCTION_ORDER 2
LTS_TIERS 1
CFL_NUMBER .4
REPORT_2D NO
REPORT_2D_VARIABLES DEPTH VELOCITY EDGE_FLUX
OUTPUT_PRECISION FLOAT64
OUTPUT_FILE surface.h5
[2D_VERTICES]
0 0 0
1 0 0
2 0 0
0 1 0
1 1 0
2 1 0
[2D_QUADS]
0 1 4 3 .03 1
1 2 5 4 .03 .1
''',encoding='utf-8')
    result=runner.run(exe,inp,work/'model.rpt',work/'model.out',cwd=work,timeout=60,
                      dylib_dirs=[str(exe.parent),str(exe.parent.parent/'engine')])
    (work/'process.log').write_text(result.get('stdout','')+'\n'+result['stderr'],encoding='utf-8')
    assert result['ok'],result
    with h5py.File(h5) as f:
        assert f['Mesh2_face_depth'].shape==(30,2)
        u=f['Mesh2_face_vx'][:];v=f['Mesh2_face_vy'][:]
        assert np.max(np.hypot(u[0],v[0]))>.01,'Moving water is reported with a stale zero velocity before the 30 s diagnostic refresh'
        # Independently reconstruct the documented RT0 velocity from each
        # report's outward edge flux, geometry and contemporaneous depth.
        normal=np.stack([f['Mesh2_edge_nx'][:],f['Mesh2_edge_ny'][:]],axis=-1)
        length=f['Mesh2_edge_length'][:]
        h=f['Mesh2_face_depth'][:];flux=f['Mesh2_edge_flux'][:]
        for t in range(30):
            for c in range(2):
                specific=np.linalg.lstsq(normal[c],flux[t,c]/length[c],rcond=None)[0]
                expected=specific/h[t,c]
                np.testing.assert_allclose([u[t,c],v[t,c]],expected,rtol=1e-9,atol=1e-10)


@pytest.mark.skipif(os.environ.get('UK_2D_ENGINE_TEST')!='1',reason='Explicit native engine integration run')
@pytest.mark.parametrize('step',[.1,1.])
def test_native_report_clock_preflight(step):
    from suites.uk_2d.suite import binary_manifest
    from suites.uk_2d.wall_sensitivity import verify_report_clock
    exe=Path(os.environ.get('UK_2D_ENGINE_EXE',str(engines.REFACT_EXE))).resolve()
    identity=binary_manifest(exe)
    key=digest(json.dumps(identity,sort_keys=True).encode())[:12]
    output=ROOT/'results/uk_2d/report-clock-test'/key
    output.mkdir(parents=True,exist_ok=True)
    verify_report_clock(exe,output,step,identity)
