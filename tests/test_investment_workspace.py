import unittest
import pandas as pd
from investment_workspace import scorecard, quarter_metrics, quarter_check, price_status, load_notebook, export_notebook, peer_row


class InvestmentTests(unittest.TestCase):
    def test_missing_values_never_favorable(self):
        b={'symbol':'TEST','info':{},'income':pd.DataFrame(),'cashflow':pd.DataFrame()}
        card=scorecard(b)
        self.assertTrue(card.Assessment.eq('Unavailable').all())
        self.assertEqual(peer_row(b)['Available checks'],0)

    def test_real_year_over_year_and_cash_date_alignment(self):
        dates=pd.to_datetime(['2026-06-30','2026-03-31','2025-06-30'])
        inc=pd.DataFrame([[120,110,100],[30,20,10]],index=['Total Revenue','Operating Income'],columns=dates)
        cash=pd.DataFrame([[50,40],[-10,-5]],index=['Operating Cash Flow','Capital Expenditure'],columns=dates[[1,2]])
        actual=quarter_metrics(inc,cash)
        self.assertAlmostEqual(actual['revenue_growth'],20)
        self.assertEqual(actual['margin'],25)
        self.assertIsNone(actual['fcf'])
        checks=quarter_check(actual,{'min_growth':21,'min_margin':20,'positive_fcf':True})
        self.assertEqual(checks.Result.tolist(),['Review thesis','Meets thesis','Unavailable'])

    def test_missing_prior_year_is_not_previous_quarter(self):
        inc=pd.DataFrame([[100,90]],index=['Total Revenue'],columns=pd.to_datetime(['2026-06-30','2026-03-31']))
        self.assertIsNone(quarter_metrics(inc,pd.DataFrame())['revenue_growth'])

    def test_watchlist_price_boundary(self):
        self.assertEqual(price_status(100,100),('At/below your buy price',0))
        self.assertEqual(price_status(None,100),('Unavailable',None))
        self.assertEqual(price_status(110,100)[0],'Waiting')

    def test_notebook_roundtrip_and_validation(self):
        book={'KO':{'buy_price':50,'fair_value':65,'thesis':'Cash generation','min_growth':3,'min_margin':15,'positive_fcf':True,'moat':[{'Advantage':'Brand','Evidence':'Annual report excerpt','Source':'https://www.sec.gov/example','Threat':'Competition','Reviewed':'2026-09-13'}]}}
        self.assertEqual(load_notebook(export_notebook(book))['companies'],book)
        for raw in ['{}','{"version":1,"companies":{"../../x":{}}}','{"version":1,"companies":{"KO":{"buy_price":-1}}}','{"version":1,"companies":{"KO":{"last_review":[]}}}']:
            with self.assertRaises(ValueError): load_notebook(raw)


if __name__=='__main__': unittest.main()
