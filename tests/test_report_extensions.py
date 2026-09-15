import unittest
import pandas as pd
from test_decision_report import fixture
from decision_report import build_decision_report, assumptions
from report_extensions import extra_inputs, history_rows, return_breakdown, stress_tests, valuation_history

class ExtensionTests(unittest.TestCase):
    def test_six_sections_and_baseline_changes(self):
        r=fixture(); first=build_decision_report(r)
        self.assertEqual(len(first['extensions']),6)
        baseline={'symbol':'TEST','generated':first['generated'],'observations':first['observations'],'inputs':first['assumptions']}
        r['snapshot']['Trailing EPS']=2.
        second=build_decision_report(r,{'growth':9},previous=baseline)
        changes=second['extensions'][0][1].set_index('Metric')
        self.assertAlmostEqual(changes.loc['Trailing EPS','Change'],.5)
        self.assertEqual(changes.loc['Assumption: growth','Interpretation'],'Assumption change')

    def test_history_deduplicates_excludes_current_and_future(self):
        r=fixture(); r['snapshot']['Trailing P/E']=25
        rows=[{'Date':f'202{i}-01-01','Trailing P/E':10.+i,'Source':'Annual report'} for i in range(1,4)]
        rows.append({'Date':'2099-01-01','Trailing P/E':999.,'Source':'invalid future'})
        frame,stats,_=valuation_history(r,{'valuation_history':rows},rows)
        self.assertEqual(len(frame),4)
        self.assertEqual(stats.set_index('Measure').loc['Historical high','Value'],'13.00')
        self.assertEqual(stats.set_index('Measure').loc['Prior observations below current (%)','Value'],'100.00')

    def test_return_contributions_reconcile_without_double_counting(self):
        r=fixture(); r['snapshot']['Price']=30.; r['snapshot']['Trailing EPS']=1.5
        a=assumptions({'years':1,'exit_multiple':20}); a.update(extra_inputs({'profit_growth':10,'share_change':10,'annual_dividend':1.5}))
        frame,note=return_breakdown(r,a)
        contributions=frame['Contribution to total return (pp)'].astype(float)
        self.assertAlmostEqual(contributions.sum(),5.)
        self.assertIn('total return 5.00%',note)
        a['annual_dividend']=None
        frame,note=return_breakdown(r,a)
        self.assertEqual(frame.iloc[-1,1],'Unavailable')
        self.assertIn('total return Unavailable',note)

    def test_stress_math_and_sector_exclusions(self):
        r=fixture(); r['financial_trends']=pd.DataFrame([{'Year':2025,'Revenue':1000.,'Operating income':200.,'Total debt':100.}])
        a=extra_inputs({'sales_shock':10,'margin_shock':3,'rate_shock':2,'refinance_pct':50})
        frame,_=stress_tests(r,a)
        combined=frame.set_index('Scenario').loc['Combined stress']
        self.assertAlmostEqual(combined['Operating profit'],153.)
        self.assertAlmostEqual(combined['Profit less extra interest'],152.)
        r['snapshot']['Industry']='Banks - Regional'
        frame,_=stress_tests(r,a)
        self.assertIn('Coverage',frame)

    def test_missing_data_and_invalid_inputs(self):
        r=fixture(); r['snapshot']={'Symbol':'TEST'}; r['financial_trends']=pd.DataFrame()
        d=build_decision_report(r)
        self.assertEqual(len(d['extensions']),6)
        self.assertIn('Unavailable',str(d['extensions'][2][1]))
        for value in ({'share_change':-100},{'refinance_pct':101},{'annual_dividend':-1},{'rate_shock':float('nan')}):
            with self.assertRaises(ValueError): extra_inputs(value)
        with self.assertRaises(ValueError): history_rows([{'Date':'2025-01-01','Trailing P/E':-5,'Source':'x'}])

if __name__=='__main__': unittest.main()
