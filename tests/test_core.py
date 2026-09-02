from __future__ import annotations

from datetime import date
from unittest import TestCase, mock

import pandas as pd

import research
import scanner
import charts
from data import cached_frame, clear_frame_cache, remember_frame, symbol_frame


def price_frame(rising: bool = True, rows: int = 260) -> pd.DataFrame:
    values=[50+i*.4 for i in range(rows)]
    if not rising: values=list(reversed(values))
    index=pd.bdate_range("2025-01-02",periods=rows)
    return pd.DataFrame({
        "Open":[v-.2 for v in values],"High":[v+1 for v in values],"Low":[v-1 for v in values],
        "Close":values,"Volume":[2_000_000]*rows,
    },index=index)


def breakout_frame(rising: bool = True) -> pd.DataFrame:
    frame=price_frame(rising)
    if rising:
        frame.iloc[-1]=[154.0,156.0,153.0,155.0,3_000_000]
    else:
        frame.iloc[-1]=[49.5,50.0,48.0,48.8,3_000_000]
    return frame


class ScannerTests(TestCase):
    def settings(self, direction="Both", batch_size=25):
        return scanner.ScanSettings(direction,0,20,1,1,25_000,1,batch_size,pause_seconds=0)

    def test_long_candidate(self):
        result=scanner.candidate("LONG",breakout_frame(True),self.settings("Long"))
        self.assertIsNotNone(result); self.assertEqual(result["Signal"],"LONG"); self.assertGreaterEqual(result["Score"],80)
        self.assertEqual(result["Setup"],"Breakout")
        self.assertLess(result["Stop"],result["Entry"]); self.assertGreater(result["Target 1"],result["Entry"])

    def test_short_candidate(self):
        result=scanner.candidate("SHORT",breakout_frame(False),self.settings("Short"))
        self.assertIsNotNone(result); self.assertEqual(result["Signal"],"SHORT"); self.assertGreaterEqual(result["Score"],80)
        self.assertEqual(result["Setup"],"Breakout")
        self.assertGreater(result["Stop"],result["Entry"]); self.assertLess(result["Target 1"],result["Entry"])

    def test_plain_trend_is_not_mislabeled_as_pullback(self):
        self.assertIsNone(scanner.candidate("TREND",price_frame(True),self.settings("Long")))

    def test_two_empty_batches_stop_the_scan(self):
        symbols=[f"T{i}" for i in range(100)]; messages=[]
        with mock.patch.object(scanner,"download_batch",return_value=pd.DataFrame()) as download:
            results,skipped=scanner.scan_market(symbols,self.settings(batch_size=25),lambda *args:messages.append(args[2]))
        self.assertTrue(results.empty); self.assertEqual(skipped,100); self.assertEqual(download.call_count,2)
        self.assertIn("stopped safely",messages[-1])


class DataShapeTests(TestCase):
    def test_multiindex_symbol_normalization(self):
        base=price_frame().tail(5); raw=pd.concat({"AAPL":base},axis=1)
        normalized=symbol_frame(raw,"AAPL")
        self.assertEqual(list(normalized.columns),["Open","High","Low","Close","Volume"]); self.assertEqual(len(normalized),5)

    def test_frame_cache_keeps_longest_history(self):
        clear_frame_cache(); remember_frame("AAPL",price_frame(rows=240)); remember_frame("AAPL",price_frame(rows=5))
        self.assertEqual(len(cached_frame("AAPL",minimum_rows=200)),240)

    def test_chart_reuses_scanner_history(self):
        clear_frame_cache(); remember_frame("AAPL",price_frame(rows=260))
        setup={"Entry":150,"Stop":140,"Target 1":170,"Target 2":180,"Support":135,"Resistance":155}
        with mock.patch.object(charts,"download_batch",side_effect=AssertionError("unexpected Yahoo request")):
            figure,message=charts.build_chart("AAPL",setup)
        self.assertIsNotNone(figure); self.assertEqual(message,"")


class ResearchTests(TestCase):
    def test_dictionary_earnings_calendar(self):
        ticker=mock.Mock(); ticker.calendar={"Earnings Date":[pd.Timestamp("2026-10-15")]}
        with mock.patch.object(research.yf,"Ticker",return_value=ticker): self.assertEqual(research.next_earnings("AAPL"),date(2026,10,15))

    def test_watchlist_alert_evaluation(self):
        latest=price_frame().tail(5); saved=pd.DataFrame([{"Symbol":"AAPL","Signal":"LONG","Entry":100.0,"Stop":90.0,"Target 1":110.0,"Target 2":120.0,"Alert":"Entry reached"}])
        with mock.patch.object(research,"download_batch",return_value=latest): result=research.evaluate_alerts(saved)
        self.assertEqual(result.iloc[0].Status,"TRIGGERED"); self.assertGreater(result.iloc[0]["Last price"],100)

    def test_relative_strength_reuses_cached_histories(self):
        clear_frame_cache(); remember_frame("SPY",price_frame(rows=80)); remember_frame("AAPL",price_frame(rows=80))
        candidates=pd.DataFrame([{"Symbol":"AAPL"}])
        with mock.patch.object(research,"download_batch",side_effect=AssertionError("unexpected Yahoo request")):
            result=research.add_relative_strength(candidates)
        self.assertEqual(result.iloc[0]["RS vs SPY"],0)


if __name__ == "__main__":
    import unittest
    unittest.main()
