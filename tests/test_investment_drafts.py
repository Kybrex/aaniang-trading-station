import unittest
from unittest.mock import patch
import pandas as pd
from investment_drafts import research_draft
from investment_workspace import validate_record, load_notebook, export_notebook
from streamlit.testing.v1 import AppTest


def fixture(ticker='TEST'):
    dates=pd.to_datetime(['2025-12-31'])
    return dict(symbol=ticker,info={'longName':ticker+' Company','longBusinessSummary':ticker+' operates a subscription software platform.',
                'operatingMargins':.25,'revenueGrowth':-.03,'debtToEquity':0.,'currency':'USD','financialCurrency':'USD','currentPrice':40.},
                income=pd.DataFrame(),balance=pd.DataFrame(),cashflow=pd.DataFrame([[20.],[-5.]],index=['Operating Cash Flow','Capital Expenditure'],columns=dates),
                retrieved='2026-09-16T00:00:00Z')


class DraftTests(unittest.TestCase):
    def test_facts_keep_units_periods_missing_and_negative_values(self):
        draft=research_draft(fixture())
        facts=draft['facts'].set_index('Measure').Observation
        self.assertEqual(facts['Operating margin'],'25.00%')
        self.assertEqual(facts['Revenue growth (provider period)'],'-3.00%')
        self.assertEqual(facts['Debt / equity'],'0.00%')
        self.assertEqual(facts['Gross margin'],'Unavailable')
        self.assertIn('15.00 USD (annual 2025)',facts['Free cash flow'])
        self.assertIn('TEST Company',draft['thesis'])
        self.assertTrue(all(not row['Reviewed'] for row in draft['moat']))
        validate_record({'moat':draft['moat'],'thesis':draft['thesis']})

    def test_missing_data_does_not_invent_a_case_or_moat(self):
        draft=research_draft({'symbol':'EMPTY','info':{}})
        self.assertFalse(draft['has_data'])
        self.assertTrue(draft['facts'].Observation.eq('Unavailable').all())
        self.assertIn('no investment case can be established',draft['thesis'])
        self.assertTrue(all('No direct qualitative evidence' in r['Evidence'] for r in draft['moat']))
        self.assertTrue(all(not r['Source'] for r in draft['moat']))

    def app(self):
        return AppTest.from_string('import investment_ui\ninvestment_ui.render()',default_timeout=30)

    def click(self,app,label):
        next(b for b in app.button if b.label==label).click().run()
        self.assertFalse(app.exception,str(app.exception))

    def test_initial_drafts_save_and_company_isolation(self):
        with patch('investment_ui.company',side_effect=fixture), patch('cloud_ui.render'):
            app=self.app().run()
            app.text_input(key='iw_ticker').set_value('TEST')
            self.click(app,'Load investment overview')
            self.assertIn('TEST Company',app.text_area(key='iw_edit_thesis_TEST').value)
            self.assertNotIn('thesis_updated',app.session_state['investment_book']['TEST'])
            self.click(app,'Save moat evidence')
            self.assertTrue(app.session_state['investment_book']['TEST']['moat'][0]['Evidence'])
            app.text_area(key='iw_edit_thesis_TEST').set_value('My own investment case')
            self.click(app,'Save investment thesis')
            book=app.session_state['investment_book']
            self.assertEqual(load_notebook(export_notebook(book))['companies']['TEST']['thesis'],'My own investment case')
            app.text_input(key='iw_ticker').set_value('OTHER')
            self.click(app,'Load investment overview')
            self.assertIn('OTHER Company',app.text_area(key='iw_edit_thesis_OTHER').value)
            app.text_input(key='iw_ticker').set_value('TEST')
            self.click(app,'Load investment overview')
            self.assertEqual(app.text_area(key='iw_edit_thesis_TEST').value,'My own investment case')

    def test_existing_notes_and_filing_import_refresh(self):
        with patch('investment_ui.company',side_effect=fixture), patch('cloud_ui.render'):
            app=self.app()
            app.session_state['investment_book']={'TEST':{'thesis':'Saved original','moat':[{'Advantage':'Brand','Evidence':'Saved evidence','Source':'https://example.com/report','Threat':'','Reviewed':''}]}}
            app.run()
            app.text_input(key='iw_ticker').set_value('TEST')
            self.click(app,'Load investment overview')
            self.assertEqual(app.text_area(key='iw_edit_thesis_TEST').value,'Saved original')
            filing={'Form':'10-K','Filed':'2026-01-01','Period':'2025-12-31','URL':'https://www.sec.gov/Archives/example.htm'}
            passages=pd.DataFrame([{'Topic':'Moat and competition','Passage':'Example annual filing excerpt','Source':filing['URL']}])
            app.session_state['research_evidence_TEST']=(filing,passages,[filing])
            app.run()
            self.click(app,'Add passages to my moat research notes')
            rows=app.session_state['investment_book']['TEST']['moat']
            self.assertEqual(len(rows),2)
            editors=[frame.value for frame in app.dataframe if 'Advantage' in frame.value.columns]
            self.assertTrue(any('Example annual filing excerpt' in frame['Evidence'].tolist() for frame in editors))
            self.click(app,'Save moat evidence')
            self.assertEqual(len(app.session_state['investment_book']['TEST']['moat']),2)
            self.assertEqual(app.text_area(key='iw_edit_thesis_TEST').value,'Saved original')


if __name__=='__main__': unittest.main()

