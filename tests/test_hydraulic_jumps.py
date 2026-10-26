"""Independent jump identities, complete output and suite discovery contracts."""
import numpy as np
import h5py
import pytest
from harness import suites
from suites.analytical.hydraulic_jumps import references as ref
from suites.analytical.hydraulic_jumps import suite


@pytest.mark.parametrize('kind',['stationary','moving-upstream','oblique','wall'])
def test_compressive_reference_conserves_mass_and_momentum(kind):
    h2,u2,s,vt=ref.reference(kind)
    u1=ref.U1+(s if kind!='wall' else 0)
    assert h2>ref.H1
    assert ref.H1*(u1-s)==pytest.approx(h2*(u2-s),abs=1e-14)
    left=ref.H1*(u1-s)**2+.5*ref.G*ref.H1**2
    right=h2*(u2-s)**2+.5*ref.G*h2**2
    assert left==pytest.approx(right,abs=1e-13)
    assert (u1-s)/np.sqrt(ref.G*ref.H1)>1
    assert (u2-s)/np.sqrt(ref.G*h2)<1
    if kind=='wall':assert u2==0 and s<0


def test_incomplete_schedule_is_rejected_before_scoring(tmp_path):
    path=tmp_path/'surface.h5'
    with h5py.File(path,'w') as f:f['time']=[46023+.1/86400]
    with pytest.raises(ValueError,match='Incomplete'):
        # The schedule guard runs before reading fields or referencing a state.
        suite.assess(path,{},np.array([]))


def test_closed_domain_fixture_and_registered_suite():
    text,case,cx=ref.make('oblique',2,64)
    boundaries=text.split('[2D_BOUNDARY_CONDITIONS]')[1].splitlines()
    assert all(row.split()[2]=='WALL' for row in boundaries if row.strip())
    assert 'ROUTING_STEP 0.1' in text and 'REPORT_STEP 0:00:00.1' in text
    assert case['angle']==64 and len(cx)==case['nx']*ref.NY*2
    assert suite.SUITE in suites.list_suites()
