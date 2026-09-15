import unittest
from datetime import datetime, timezone
import pandas as pd
from decision_report import assumptions, valuation, dcf_per_share, financial_checks, portfolio_fit, build_decision_report, peer_view


def fixture():
    trends=pd.DataFrame([dict(Year=2021+i,Revenue=1000*(1.1**i),**{"Net income":100*(1.1**i),"Operating cash flow":120*(1.1**i),"Free cash flow":90*(1.1**i),"Total debt":200,"Diluted shares":100,"Share repurchases":-10,"Stock compensation":20,"Receivables":100*(1.1**i),"Operating income":150*(1.1**i),"Operating margin %":15}) for i in range(5)])
    snapshot={"Symbol":"TEST","Company":"Example Research Company","Sector":"Technology","Industry":"Software","Price":30.,"Trailing EPS":1.5,"ROE":18.,"Operating margin":15.,"Revenue growth":10.,"Earnings growth":10.,"Debt/Equity":40.,"Currency":"USD","Financial currency":"USD","Source":"Synthetic test fixture","Description":"Fictional business for layout and calculation testing. This is not a stock recommendation."}
    report=dict(symbol="TEST",snapshot=snapshot,financial_trends=trends,generated_at=datetime.now(timezone.utc),calendar=pd.DataFrame(),technical_history=pd.DataFrame(),levels=pd.DataFrame(),technical_checks=[],technical_score=0,errors={})
    return report


class DecisionTests(unittest.TestCase):
    def test_dcf_closed_form(self):
        # Flat perpetual cash flow, first payment next year: cash / discount.
        self.assertAlmostEqual(dcf_per_share(10,0,10,0,5),100)

    def test_reverse_model_reconstructs_price(self):
        r=fixture(); v=valuation(r["snapshot"],r["financial_trends"],None)
        cash=r["financial_trends"].iloc[-1]["Free cash flow"]/100
        self.assertAlmostEqual(dcf_per_share(cash,v["reverse_growth"],10,2.5,5),30)
        self.assertLess(v["scenarios"].iloc[0]["Fair value today"],v["fair_value"])
        self.assertAlmostEqual(v["buy_price"],v["fair_value"]*.75)

    def test_missing_data_never_means_safe(self):
        r=fixture(); r["snapshot"]={"Symbol":"TEST"}; r["financial_trends"]=pd.DataFrame()
        d=build_decision_report(r)
        self.assertIsNone(d["valuation"]["fair_value"])
        self.assertEqual(d["confidence"],"Limited")
        self.assertTrue(d["checks"].Status.eq("Insufficient evidence").all())

    def test_sector_models(self):
        r=fixture()
        for sector in ("Banks - Regional","Insurance - Property & Casualty"):
            r["snapshot"]["Industry"]=sector
            v=valuation(r["snapshot"],r["financial_trends"],{"book_per_share":10})
            self.assertEqual(v["model"],"Earnings multiple")
            self.assertNotIn("Cash-flow sensitivity",v["models"].Method.tolist())
            c=financial_checks(r["snapshot"],r["financial_trends"])
            self.assertEqual(c.iloc[0].Status,"Insufficient evidence")
        r["snapshot"]["Industry"]="REIT - Retail"
        self.assertIsNone(valuation(r["snapshot"],r["financial_trends"],None)["fair_value"])
        self.assertGreater(valuation(r["snapshot"],r["financial_trends"],{"ffo_per_share":3})["fair_value"],0)

    def test_currency_mismatch_disables_cash_model(self):
        r=fixture(); r["snapshot"]["Financial currency"]="EUR"
        self.assertEqual(valuation(r["snapshot"],r["financial_trends"],None)["model"],"Earnings multiple")

    def test_negative_eps_and_fcf_no_invented_value(self):
        r=fixture(); r["snapshot"]["Trailing EPS"]=-1
        r["financial_trends"]["Free cash flow"]=-1
        self.assertIsNone(valuation(r["snapshot"],r["financial_trends"],None)["fair_value"])

    def test_assumption_validation(self):
        for args in ({"discount":2,"terminal_growth":3},{"years":1.5},{"growth":float("nan")},{"portfolio_value":-1},{"exit_multiple":0}):
            with self.assertRaises(ValueError): assumptions(args)

    def test_portfolio_existing_exposure_and_limits(self):
        r=fixture(); v=valuation(r["snapshot"],r["financial_trends"],None)
        h=pd.DataFrame([{"Symbol":"TEST","Sector":"Technology","Value":4000}])
        result=portfolio_fit(r["snapshot"],v,{"portfolio_value":100000,"planned_amount":2000},h).set_index("Measure")
        self.assertEqual(result.loc["After purchase company exposure %","Result"],"6.00")
        self.assertEqual(result.loc["Position limit","Result"],"Exceeded")
        with self.assertRaises(ValueError): portfolio_fit(r["snapshot"],v,{"portfolio_value":5000,"planned_amount":2000},h)

    def test_thesis_baseline_and_wrong_symbol(self):
        r=fixture(); first=build_decision_report(r)
        r["snapshot"]["Operating margin"]=10
        second=build_decision_report(r,previous=first)
        self.assertEqual(second["tracker"].set_index("Metric").loc["Operating margin %","Status"],"Review triggered")
        first["symbol"]="OTHER"
        second=build_decision_report(r,previous=first)
        self.assertTrue(second["tracker"].Previous.isna().all())

    def test_peer_selection_same_industry_and_no_self_duplicates(self):
        r=fixture(); s=r["snapshot"]
        peers=pd.DataFrame([s,{**s,"Symbol":"PEER"},{**s,"Symbol":"OTHER","Industry":"Banks"}])
        p,note=peer_view(s,peers)
        self.assertEqual(p.Symbol.tolist(),["TEST","PEER"])

    def test_pdf_all_sections(self):
        from v7_pdf import complete_research_pdf
        r=fixture(); r["decision"]=build_decision_report(r)
        pdf=complete_research_pdf(r)
        self.assertTrue(pdf.startswith(b"%PDF")); self.assertGreater(len(pdf),10000)

if __name__=="__main__": unittest.main()
