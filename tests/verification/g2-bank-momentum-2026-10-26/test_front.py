"""Known synthetic fronts qualify the orientation detector, not solver hydraulics."""
import unittest
import numpy as np
from front import locate
class Front(unittest.TestCase):
 def setUp(self):self.x=np.arange(2.,3.65001,.005);self.y=np.arange(-.8,-.3999,.01);self.xx,self.yy=np.meshgrid(self.x,self.y)
 def field(self,x0,slope):return .03+.04*(1+np.tanh((self.xx-(x0+slope*(self.yy+.6)))/.02))
 def test_oblique_front_position_and_normal(self):
  slope,x0,rms,_,_=locate(self.x,self.y,self.field(2.9,.2));self.assertAlmostEqual(x0,2.9,delta=.003);self.assertAlmostEqual(slope,.2,delta=.01);self.assertLess(rms,.003)
 def test_translation_is_tracked(self):
  a=locate(self.x,self.y,self.field(2.8,-.3));b=locate(self.x,self.y,self.field(3.0,-.3));self.assertAlmostEqual(b[1]-a[1],.2,delta=.003)
 def test_uniform_lake_has_no_front(self):self.assertIsNone(locate(self.x,self.y,np.full_like(self.xx,.1)))
 def test_outside_search_window_is_rejected(self):self.assertIsNone(locate(self.x,self.y,self.field(3.64,.0)))
if __name__=='__main__':unittest.main()
