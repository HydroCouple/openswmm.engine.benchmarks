"""Independent integration controls; no UK observations enter these tests."""
import unittest
import numpy as np
from geometry import moments,mean_depth

def clipped(z,eta):
    p=[np.array([0.,0.,z[0]]),np.array([1.,0.,z[1]]),np.array([0.,1.,z[2]])];q=[]
    for a,b in zip(p,p[1:]+p[:1]):
        if a[2]<eta:q.append(a)
        if (a[2]<eta)!=(b[2]<eta):q.append(a+(b-a)*(eta-a[2])/(b[2]-a[2]))
    volume=0
    for i in range(1,len(q)-1):
        a,b,c=q[0],q[i],q[i+1]
        area=abs((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]))/2
        volume+=area*(3*eta-a[2]-b[2]-c[2])/3
    return volume/.5

class Geometry(unittest.TestCase):
    def test_storage_against_independent_polygon_clipping(self):
        rng=np.random.default_rng(20261026);z=rng.uniform(-.2,.5,(600,3));eta=rng.uniform(-.3,.6,600)
        expected=np.array([clipped(v,h) for v,h in zip(z,eta)])
        np.testing.assert_allclose(mean_depth(eta,z),expected,rtol=0,atol=2e-14)
    def test_storage_repeated_vertices_and_dry_limit(self):
        z=np.array([[0,0,.155],[0,.155,.155],[.155,.155,.155]]*30)
        eta=np.tile(np.linspace(-.1,.4,30),3).reshape(3,30).T.ravel()
        np.testing.assert_allclose(mean_depth(eta,z),[clipped(v,h) for v,h in zip(z,eta)],rtol=0,atol=2e-14)
    def test_edge_pressure_against_clipped_gaussian_quadrature(self):
        nodes,weights=np.polynomial.legendre.leggauss(3)
        for a,b in [(0,.155),(.155,0),(.1,.1),(-.1,.2)]:
            lo,hi=sorted((a,b))
            for eta in [-.2,0,.02,.1,.155,.2,.4]:
                wet=1. if hi==lo and eta>lo else 0. if hi==lo else min(1,max(0,(eta-lo)/(hi-lo)))
                points=(nodes+1)*wet/2
                for k in [1,2]:
                    expected=wet/2*np.sum(weights*np.maximum(eta-(lo+(hi-lo)*points),0)**k)
                    self.assertAlmostEqual(float(moments(np.array(eta),np.array(a),np.array(b),k)),expected,places=14)
    def test_partial_edge_can_be_wet_with_dry_midpoint(self):
        self.assertEqual(max(.04-.1/2,0),0)
        self.assertAlmostEqual(float(moments(np.array(.04),np.array(0.),np.array(.1),2)),.04**3/(3*.1),places=14)
    def test_full_wet_midpoint_pressure_error(self):
        exact=float(moments(np.array(.2),np.array(0.),np.array(.1),2))
        self.assertAlmostEqual(exact-(.2-.05)**2,.1**2/12,places=14)
if __name__=='__main__':unittest.main()
