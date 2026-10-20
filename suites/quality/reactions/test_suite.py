"""Falsify the benchmark scorers with absent engines and incorrect results."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('reaction_suite',Path(__file__).with_name('suite.py'))
suite=importlib.util.module_from_spec(spec)
spec.loader.exec_module(suite)

class ZeroOutput:
    err_code=0
    n_periods=2
    def series(self,*args):
        return [1000.,1000.] if args[-1]==3 else [0.,0.]
    node_series=series
    subcatch_series=series

class ScorerControls(unittest.TestCase):
    def test_zero_chemistry_cannot_pass_any_extended_profile(self):
        for case,names in [('wall_geometry',['A','W']),('dry_buildup',['A','B','tracer']),('setpoint',['A']),('lid_layers',['A','B','tracer'])]:
            with self.subTest(case=case):
                output=ZeroOutput();output.pollut_ids=names
                result=suite.check_extended(case,output,'Remaining Buildup ........ 0.000 0.000 0.000\n')
                self.assertEqual(result['verdict'],'FAIL')

    def test_missing_species_is_an_error(self):
        output=ZeroOutput();output.pollut_ids=['wrong']
        for case in ('wall_geometry','lid_layers','setpoint'):
            with self.subTest(case=case):
                with self.assertRaises(ValueError):suite.check_extended(case,output,'')

    def test_missing_executable_reports_all_cells_unavailable(self):
        original=suite.RESULTS
        with tempfile.TemporaryDirectory(prefix='reactions-negative-') as path:
            try:
                suite.RESULTS=Path(path)
                result=suite.run(['--exe',str(Path(path)/'missing-engine')])
                self.assertEqual(len(result['cells']),38)
                self.assertTrue(all(c['verdict']=='UNAVAILABLE' for c in result['cells']))
            finally:suite.RESULTS=original

if __name__=='__main__':unittest.main()
