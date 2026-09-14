import unittest
from unittest.mock import patch
import pandas as pd

from scan_dashboard import position_size, market_snapshot, signal_reasons
from scanner import candidate, ScanSettings


class SizingTests(unittest.TestCase):
    def test_long_and_short_amount_and_caps(self):
        for side, stop in [("LONG", 95), ("SHORT", 105)]:
            result = position_size(100, stop, 10000, 25000, 1, 20, side)
            self.assertEqual(result["shares"], 100)
            self.assertEqual(result["loss"], 500)
            self.assertEqual(result["limited_shares"], 50)
            self.assertEqual(result["limited_loss"], 250)

    def test_whole_shares_and_decimal_boundary(self):
        result = position_size(0.10, 0.09, 0.30, 100, 1, 20, "LONG")
        self.assertEqual(result["shares"], 3)
        self.assertAlmostEqual(result["loss"], 0.03)
        self.assertEqual(position_size(100, 95, 99, 25000, 1, 20, "LONG")["shares"], 0)
        self.assertEqual(position_size(100, 95, 0, 25000, 1, 20, "LONG")["loss"], 0)

    def test_risk_and_position_caps_are_independent(self):
        self.assertEqual(position_size(100, 90, 10000, 25000, 1, 100, "LONG")["limited_shares"], 25)
        self.assertEqual(position_size(100, 99, 10000, 25000, 5, 4, "LONG")["limited_shares"], 10)

    def test_invalid_values_and_stops(self):
        for entry, stop, amount, side in [(0, 95, 10, "LONG"), (100, 100, 100, "LONG"),
                                         (100, 101, 100, "LONG"), (100, 99, 100, "SHORT"),
                                         (100, -1, 100, "LONG"), (100, 95, -1, "LONG"),
                                         (float("nan"), 95, 100, "LONG"), (100, 95, float("inf"), "LONG"),
                                         (100, 95, 100, "WATCH")]:
            with self.subTest(entry=entry, stop=stop, side=side):
                with self.assertRaises(ValueError):
                    position_size(entry, stop, amount, 25000, 1, 20, side)


def fixture_frame():
    return pd.DataFrame({"Open": 100., "High": 105., "Low": 95., "Close": 100., "Volume": 1000000.},
                        index=pd.date_range("2025-01-01", periods=205))


class SignalTests(unittest.TestCase):
    def test_four_setup_variants_explain_same_score(self):
        for side in ("LONG", "SHORT"):
            for setup in ("Breakout", "EMA pullback"):
                with self.subTest(side=side, setup=setup):
                    long = side == "LONG"
                    frame = fixture_frame()
                    indicators = frame.copy()
                    indicators["EMA20"] = 97. if long else 103.
                    indicators["EMA50"] = 95. if long else 105.
                    indicators["SMA200"] = 90. if long else 110.
                    indicators["ATR14"] = 2.
                    indicators["VolAvg20"] = 1000000.
                    indicators["Mom20"] = 10. if long else -10.
                    indicators["Mom60"] = 20. if long else -20.
                    indicators.iloc[-11, indicators.columns.get_loc("EMA20")] = 96. if long else 104.
                    close = (106. if long else 94.) if setup == "Breakout" else 100.
                    indicators.iloc[-1, indicators.columns.get_loc("Close")] = close
                    indicators.iloc[-1, indicators.columns.get_loc("Open")] = close - 1 if long else close + 1
                    with patch("scanner.add_indicators", return_value=indicators):
                        row = candidate("TEST", frame, ScanSettings("Both", 0, 30, 1, 100, 25000, 1, 25))
                    self.assertIsNotNone(row)
                    self.assertEqual(row["Signal"], side)
                    self.assertEqual(row["Setup"], setup)
                    score = sum(row[k] for k in ["Trend points", "Momentum points", "Volume points", "Setup points"]) - row["Extension penalty"]
                    self.assertEqual(row["Score"], min(100, round(score)))
                    self.assertEqual(len(signal_reasons(row)), 4)
                    self.assertIn("above" if long else "below", signal_reasons(row)[0])
                    self.assertAlmostEqual(row["Risk/Share"], 3)

    def test_old_scan_requests_rescan(self):
        self.assertIn("Scan market again", signal_reasons({"Signal": "LONG"})[0])

    def test_market_boundaries_missing_data_and_dates(self):
        frames = {"SPY": fixture_frame(), "QQQ": fixture_frame(), "^VIX": fixture_frame()}
        frames["SPY"].iloc[-1, frames["SPY"].columns.get_loc("Close")] = 101
        frames["^VIX"]["Close"] = 22.
        with patch("data.download_batch", return_value=pd.DataFrame()), patch("data.symbol_frame", side_effect=lambda raw, symbol: frames[symbol]):
            snapshot = market_snapshot()
        self.assertEqual([c["state"] for c in snapshot["cards"]], ["Risk-on", "Risk-off", "Elevated"])
        self.assertEqual(snapshot["cards"][0]["data_date"], str(frames["SPY"].index[-1].date()))
        with patch("data.download_batch", return_value=pd.DataFrame()):
            self.assertTrue(all(c["state"] == "Unavailable" for c in market_snapshot()["cards"]))


class DashboardTests(unittest.TestCase):
    def test_calculator_reacts_and_comparison_survives_rescan(self):
        from streamlit.testing.v1 import AppTest
        code = '''
import pandas as pd
import streamlit as st
from scan_dashboard import render_comparison, render_candidate, render_market
row = {"Symbol":"AAA","Data date":"2026-09-11","Score":80,"Signal":"LONG","Setup":"EMA pullback",
       "Entry":100.0,"Stop":95.0,"Risk/Share":5.0,"20D Momentum":5.0,"60D Momentum":10.0,
       "RS vs SPY":None,"Earnings":"Unknown"}
rows = pd.DataFrame([row, dict(row, Symbol="BBB"), dict(row, Symbol="CCC")])
if st.checkbox("New scan"):
    rows = pd.DataFrame([dict(row, Symbol="DDD")])
render_market({"checked":"2026-09-14 12:00:00 UTC","cards":[
    {"label":"S&P 500","symbol":"SPY","value":100.0,"state":"Risk-on","data_date":"2026-09-11","reason":"Above average."},
    {"label":"Nasdaq 100","symbol":"QQQ","value":None,"state":"Unavailable","data_date":"Unavailable","reason":"No data."},
    {"label":"VIX","symbol":"^VIX","value":22.0,"state":"Elevated","data_date":"2026-09-11","reason":"At threshold."}]})
render_comparison(rows)
render_candidate(rows.iloc[0], 25000.0, 1.0, 20.0)
'''
        app = AppTest.from_string(code).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.multiselect[0].value, ["AAA", "BBB", "CCC"])
        app.number_input[0].set_value(1000.0).run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual([m.value for m in app.metric], ["10", "$50.00"])
        app.checkbox[0].check().run()
        self.assertEqual(len(app.exception), 0)
        self.assertEqual(app.multiselect[0].value, [])
        self.assertTrue(any("one candidate" in info.value for info in app.info))


if __name__ == "__main__":
    unittest.main()
