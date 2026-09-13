import unittest
from unittest.mock import patch,Mock
import pandas as pd
from investment_research import filing_passages,earnings_changes,sensitivity,allocation,thesis_warning,sec_get
from investment_cloud import config,load_cloud,save_cloud,CloudError


class ResearchTests(unittest.TestCase):
    def test_hidden_text_excluded_and_sources_preserved(self):
        text='<script>competitive advantage '+('fake '*100)+'</script><div style="display:none"><br>brand hidden</div><p>'+('Our brand and distribution network support our competitive advantage, while competition may weaken pricing power. '*2)+'</p>'
        rows=filing_passages(text,'https://www.sec.gov/example')
        self.assertFalse(rows.empty)
        self.assertTrue(rows.Source.eq('https://www.sec.gov/example').all())
        self.assertFalse(rows.Passage.str.contains('fake|hidden').any())

    def test_sec_url_and_contact_fail_closed(self):
        with self.assertRaises(ValueError): sec_get('https://example.org/','a@b.com')
        with self.assertRaises(ValueError): sec_get('https://www.sec.gov/','invalid')

    def test_earnings_match_year_and_preserve_missing(self):
        dates=pd.to_datetime(['2026-06-30','2026-03-31','2025-06-30'])
        income=pd.DataFrame([[120,110,100],[24,10,10]],index=['Total Revenue','Operating Income'],columns=dates)
        changes=earnings_changes(income,pd.DataFrame(),pd.DataFrame()).set_index('Metric')
        self.assertAlmostEqual(changes.loc['Revenue','Change %'],20)
        self.assertAlmostEqual(changes.loc['Operating margin %','Change'],10)
        self.assertTrue(pd.isna(changes.loc['Total debt','Current']))

    def test_sensitivity_direction_and_invalid_rates(self):
        frame=sensitivity(5,.05,.10,.02)
        self.assertGreater(frame.iloc[2,1],frame.iloc[0,1])
        self.assertGreater(frame.iloc[1,0],frame.iloc[1,2])
        with self.assertRaises(ValueError): sensitivity(5,.05,.02,.02)

    def test_allocation_preserves_cash_signs_and_missing(self):
        dates=pd.to_datetime(['2025-12-31','2024-12-31'])
        cash=pd.DataFrame([[100,90],[-20,-10],[-30,-20],[-60,-20],[-15,5]],index=['Operating Cash Flow','Capital Expenditure','Cash Dividends Paid','Repurchase Of Capital Stock','Net Business Purchase And Sale'],columns=dates)
        result=allocation(pd.DataFrame(),cash,pd.DataFrame())
        self.assertEqual(result.iloc[-1]['Free cash flow'],80)
        self.assertEqual(result.iloc[-1]['Net acquisition cash flow (signed)'],-15)
        self.assertEqual(result.iloc[-1]['Dividends + buybacks / FCF %'],112.5)
        self.assertTrue(pd.isna(result.iloc[-1]['Debt repaid']))

    def test_warning_missing_is_not_pass(self):
        r=thesis_warning('KO',{'period':None,'revenue_growth':None,'margin':None,'fcf':None},{'thesis_updated':'today','min_growth':5,'min_margin':10,'positive_fcf':True})
        self.assertEqual(r['Status'],'Incomplete data')


class CloudTests(unittest.TestCase):
    def test_reject_elevated_key_and_unapproved_host(self):
        with self.assertRaises(CloudError): config('https://x.supabase.co','sb_secret_example')
        with self.assertRaises(CloudError): config('http://x.supabase.co','sb_publishable_test')
        with self.assertRaises(CloudError): config('https://evil.test','sb_publishable_test')

    def test_cloud_load_filters_owner_and_checks_response(self):
        user='12345678-1234-1234-1234-123456789012'
        with patch('investment_cloud.api',return_value=[{'user_id':user,'payload':{'version':1,'companies':{}},'version':3}]) as api:
            self.assertEqual(load_cloud('url','key',{'user_id':user,'access_token':'token'}),({},3))
            self.assertIn('user_id=eq.'+user,api.call_args.args[2])
        with patch('investment_cloud.api',return_value=[{'user_id':'other','payload':{},'version':1}]):
            with self.assertRaises(CloudError): load_cloud('url','key',{'user_id':user,'access_token':'token'})

    def test_conflict_does_not_silently_overwrite(self):
        response=Mock(status_code=400,text='notebook_conflict')
        with patch('investment_cloud.requests.request',return_value=response):
            with self.assertRaisesRegex(CloudError,'Another device'):
                save_cloud('https://x.supabase.co','sb_publishable_test',{'access_token':'token'},{},3)


if __name__=='__main__': unittest.main()
