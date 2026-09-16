import unittest
from unittest.mock import patch
import pandas as pd
from insider_transactions import transaction_type, normalize_insiders
from streamlit.testing.v1 import AppTest


class InsiderTests(unittest.TestCase):
    def test_provider_descriptions(self):
        examples={'Sale at price 190.00 per share.':'Sell','Purchase at price 80.00 per share.':'Buy',
                  'Stock Gift':'Gift','Conversion of Exercise of derivative security':'Exercise / Conversion',
                  'Stock Award (Grant)':'Grant / Award','Shares withheld for tax liability':'Tax / Exercise payment',
                  'Acquisition (Non Open Market)':'Other acquisition / disposition','Disposition (Non Open Market)':'Other acquisition / disposition',
                  'Purchase and sale':'Unknown','':'Unknown'}
        for text,expected in examples.items():
            with self.subTest(text=text): self.assertEqual(transaction_type({'Text':text,'Transaction':''}),expected)

    def test_codes_and_no_inference_from_values_or_ownership(self):
        for code,label in [('P','Buy'),('S','Sell'),('A','Grant / Award'),('G','Gift'),('M','Exercise / Conversion'),('F','Tax / Exercise payment'),('D','Disposition to issuer')]:
            self.assertEqual(transaction_type({'Transaction Code':code}),label)
        for shares,value in [(100,1000),(-100,-1000),(0,0)]:
            self.assertEqual(transaction_type({'Shares':shares,'Value':value,'Ownership':'D','Text':None}),'Unknown')
        self.assertEqual(transaction_type({'Text':pd.NA,'Transaction':float('nan')}),'Unknown')

    def test_normalization_preserves_source_and_exports_type(self):
        source=pd.DataFrame([{'Insider':'Example','Shares':100,'Text':'Sale at price 10','Transaction':''}])
        result=normalize_insiders(source)
        self.assertEqual(result.columns[0],'Transaction type')
        self.assertEqual(result.iloc[0]['Transaction type'],'Sell')
        self.assertEqual(result.iloc[0]['Text'],source.iloc[0]['Text'])
        self.assertNotIn('Transaction type',source)
        self.assertIn('Sell',result.to_csv(index=False))
        pd.testing.assert_frame_equal(normalize_insiders(result),result)
        self.assertTrue(normalize_insiders(None).empty)
        self.assertTrue(normalize_insiders(pd.DataFrame()).empty)

    def test_live_helper_and_ui_company_change(self):
        source=pd.DataFrame([{'Text':'Sale at price 10','Shares':100}])
        with patch('v5_features.yf.Ticker') as ticker:
            ticker.return_value.insider_transactions=source
            from v5_features import insider_activity
            self.assertEqual(insider_activity('TEST').iloc[0]['Transaction type'],'Sell')
        with patch('v5_ui.insider_activity',return_value=normalize_insiders(source)):
            app=AppTest.from_string('import v5_ui\nv5_ui.render()',default_timeout=30)
            app.session_state['v5_section']='2 · Insider Trading'
            app.run()
            next(b for b in app.button if b.label=='Load insider activity').click().run()
            self.assertFalse(app.exception,str(app.exception))
            self.assertEqual(app.dataframe[-1].value.iloc[0]['Transaction type'],'Sell')
            app.text_input(key='v5_insider_symbol').set_value('MSFT').run()
            self.assertEqual(len(app.dataframe),0)
            self.assertTrue(any('retrieve transactions' in x.value for x in app.info))


if __name__=='__main__': unittest.main()
