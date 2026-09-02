from __future__ import annotations

from unittest import TestCase,mock
from pathlib import Path
import tempfile
import pandas as pd

import advanced
import data
import investor
import notifications
import portfolio
import reporting
import storage
from indicators import add_indicators


def history(rows: int = 300, step: float = .25) -> pd.DataFrame:
    values=[50+i*step for i in range(rows)];index=pd.bdate_range("2025-01-02",periods=rows)
    return pd.DataFrame({"Open":[v-.1 for v in values],"High":[v+.5 for v in values],"Low":[v-.5 for v in values],"Close":values,"Volume":[2_000_000]*rows},index=index)


class AdvancedTests(TestCase):
    def test_rsi_and_setup_output(self):
        frame=history();frame.iloc[-1]=[126,128,125,127.5,3_000_000]
        self.assertIn("RSI14",add_indicators(frame).columns)
        setups=advanced.detect_setups(frame)
        self.assertIn("Base breakout",setups.Setup.tolist())

    def test_backtest_metrics_and_equity_curve(self):
        trades=pd.DataFrame({"Date":pd.date_range("2026-01-01",periods=4),"R multiple":[2,-1,2,-1]})
        metrics,curve=advanced.backtest_metrics(trades)
        self.assertEqual(metrics["Trades"],4);self.assertGreater(metrics["Profit factor"],1);self.assertEqual(len(curve),4)

    def test_bracket_quantities_equal_position(self):
        plan=advanced.bracket_plan("AAPL","LONG",100,95,110,115,11)
        targets=plan[plan.Order.str.startswith("TARGET")]
        self.assertEqual(int(targets.Quantity.sum()),11);self.assertEqual(plan.iloc[0].Action,"BUY")


class InvestorTests(TestCase):
    def test_dcf_three_core_outputs(self):
        result=investor.dcf_valuation(1_000_000,100_000,200_000,.08,.025,.10)
        self.assertGreater(result["Fair value/share"],0);self.assertLess(result["Terminal value share %"],100)

    def test_invalid_dcf_rates_are_rejected(self):
        self.assertEqual(investor.dcf_valuation(100,10,0,.05,.10,.08),{})


class PortfolioTests(TestCase):
    def test_risk_income_and_correlation(self):
        base=history();raw=pd.concat({"AAPL":base,"MSFT":base*1.02,"SPY":base*.9},axis=1)
        positions=pd.DataFrame([
            {"Symbol":"AAPL","Shares":10,"Cost":80,"Stop":100,"Sector":"Technology","Country":"USA","Currency":"USD","Purpose":"Investment","Dividend Yield":1,"Target Weight":50},
            {"Symbol":"MSFT","Shares":5,"Cost":90,"Stop":100,"Sector":"Technology","Country":"USA","Currency":"USD","Purpose":"Swing","Dividend Yield":1,"Target Weight":50},
        ])
        with mock.patch.object(portfolio,"download_batch",return_value=raw):detail,metrics,sector,purpose,corr=portfolio.portfolio_snapshot(positions,10_000)
        self.assertEqual(len(detail),2);self.assertGreater(metrics["Annual dividends"],0);self.assertFalse(corr.empty);self.assertAlmostEqual(float(sector["Weight %"].sum()),100)

    def test_journal_r_multiple(self):
        journal=pd.DataFrame([{"Symbol":"AAPL","Side":"LONG","Entry":100,"Exit":110,"Shares":10,"Initial Stop":95,"Setup":"Breakout"}])
        detail,metrics,by_setup=portfolio.journal_analytics(journal)
        self.assertEqual(detail.iloc[0]["R multiple"],2);self.assertEqual(metrics["Win rate %"],100);self.assertEqual(by_setup.iloc[0].Setup,"Breakout")


class ExportAndFallbackTests(TestCase):
    def test_pdf_and_excel_are_real_files(self):
        frame=pd.DataFrame([{"Symbol":"AAPL","Score":90}])
        self.assertTrue(reporting.table_pdf("Test",frame).startswith(b"%PDF"))
        self.assertTrue(reporting.excel_workbook({"Scanner":frame}).startswith(b"PK"))

    def test_alpha_vantage_daily_parsing(self):
        response=mock.Mock();response.raise_for_status.return_value=None;response.json.return_value={"Time Series (Daily)":{"2026-09-01":{"1. open":"100","2. high":"102","3. low":"99","4. close":"101","5. volume":"1000000"}}}
        data.clear_frame_cache()
        with mock.patch.object(data.requests,"get",return_value=response):frame=data.alpha_vantage_daily("AAPL","secret")
        self.assertEqual(float(frame.iloc[0].Close),101);self.assertEqual(data.frame_source("AAPL"),"Alpha Vantage")

    def test_telegram_payload(self):
        response=mock.Mock();response.raise_for_status.return_value=None
        with mock.patch.object(notifications.requests,"post",return_value=response) as post:success,_=notifications.send_telegram("hello","token","123")
        self.assertTrue(success);self.assertEqual(post.call_args.kwargs["json"]["chat_id"],"123")

    def test_alert_transition_is_sent_only_once(self):
        triggered=pd.DataFrame([{"Symbol":"AAPL","Alert":"Entry reached","Status":"TRIGGERED"}]);waiting=triggered.assign(Status="Waiting")
        with tempfile.TemporaryDirectory() as folder,mock.patch.object(storage,"ALERT_STATE",Path(folder)/"state.csv"):
            self.assertEqual(len(storage.newly_triggered(triggered)),1)
            self.assertTrue(storage.newly_triggered(triggered).empty)
            storage.newly_triggered(waiting)
            self.assertEqual(len(storage.newly_triggered(triggered)),1)
