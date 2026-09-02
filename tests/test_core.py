from __future__ import annotations

from datetime import date
from unittest import TestCase, mock

import pandas as pd

import research
import scanner
from data import symbol_frame


def price_frame(rising: bool = True, rows: int = 260) -> pd.DataFrame:
    values=[50+i*.4 for i in range(rows)]
    if not rising: values=list(reversed(values))
    index=pd.bdate_range("2025-01-02",periods=rows)
    return pd.DataFrame({
        "Open":[v-.2 for v in values],"High":[v+1 for v in values],"Low":[v-1 for v in values],
        "Close":values,"Volume":[2_000_000]*rows,
    },index=index)


class ScannerTests(TestCase):
    def settings(self, direction="Both", batch_size=25):
        return scanner.ScanSettings(direction,0,20,1,1,25_000,1,batch_size,pause_seconds=0)

    def test_long_candidate(self):
        result=scanner.candidate("LONG",price_frame(True),self.settings("Long"))
        self.assertIsNotNone(result); self.assertEqual(result["Signal"],"LONG"); self.assertGreaterEqual(result["Score"],80)
        self.assertLess(result["Stop"],result["Entry"]); self.assertGreater(result["Target 1"],result["Entry"])

    def test_short_candidate(self):
        result=scanner.candidate("SHORT",price_frame(False),self.settings("Short"))
        self.assertIsNotNone(result); self.assertEqual(result["Signal"],"SHORT"); self.assertGreaterEqual(result["Score"],80)
        self.assertGreater(result["Stop"],result["Entry"]); self.assertLess(result["Target 1"],result["Entry"])

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


class ResearchTests(TestCase):
    def test_dictionary_earnings_calendar(self):
        ticker=mock.Mock(); ticker.calendar={"Earnings Date":[pd.Timestamp("2026-10-15")]}
        with mock.patch.object(research.yf,"Ticker",return_value=ticker): self.assertEqual(research.next_earnings("AAPL"),date(2026,10,15))

    def test_watchlist_alert_evaluation(self):
        latest=price_frame().tail(5); saved=pd.DataFrame([{"Symbol":"AAPL","Signal":"LONG","Entry":100.0,"Stop":90.0,"Target 1":110.0,"Target 2":120.0,"Alert":"Entry reached"}])
        with mock.patch.object(research,"download_batch",return_value=latest): result=research.evaluate_alerts(saved)
        self.assertEqual(result.iloc[0].Status,"TRIGGERED"); self.assertGreater(result.iloc[0]["Last price"],100)


if __name__ == "__main__":
    import unittest
    unittest.main()
