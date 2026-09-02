"""Fundamental value screen using Yahoo Finance consensus data and transparent moat proxies."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from typing import Callable
import math
import pandas as pd
import yfinance as yf

def number(value: object) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError, OverflowError):
        return None

def moat_estimate(info: dict) -> tuple[str, int]:
    """Return an explainable proxy, never a claim of a licensed moat rating."""
    roe = number(info.get("returnOnEquity")) or 0
    margin = number(info.get("operatingMargins")) or 0
    debt = number(info.get("debtToEquity"))
    cap = number(info.get("marketCap")) or 0
    score = (35 if roe >= .20 else 20 if roe >= .12 else 0) + (30 if margin >= .18 else 15 if margin >= .10 else 0) + (20 if debt is not None and debt <= 100 else 8 if debt is not None and debt <= 200 else 0) + (15 if cap >= 10_000_000_000 else 5 if cap >= 2_000_000_000 else 0)
    return ("Wide estimate" if score >= 75 else "Narrow estimate" if score >= 48 else "No estimate", score)

def analyze_symbol(symbol: str) -> dict | None:
    try:
        info = yf.Ticker(symbol).get_info()
        price = number(info.get("currentPrice")) or number(info.get("regularMarketPrice"))
        target = number(info.get("targetMeanPrice"))
        if not price or not target or price <= 0: return None
        discount = (target / price - 1) * 100
        moat, score = moat_estimate(info)
        return {"Symbol": symbol, "Price": price, "Analyst fair value": target, "Upside": round(discount, 1), "Moat estimate": moat, "Moat score": score,
                "ROE": round((number(info.get("returnOnEquity")) or 0) * 100, 1), "Operating margin": round((number(info.get("operatingMargins")) or 0) * 100, 1),
                "Debt/Equity": number(info.get("debtToEquity")), "Sector": info.get("sector", "Unknown")}
    except Exception:
        return None

def scan_value(symbols: list[str], minimum: int, maximum: int, moat_filter: str, progress: Callable[[int, int], None]) -> tuple[pd.DataFrame, int]:
    rows: list[dict] = []; skipped = 0; total = len(symbols)
    executor = ThreadPoolExecutor(max_workers=6)
    futures = {executor.submit(analyze_symbol, symbol): symbol for symbol in symbols}
    try:
        for done, future in enumerate(as_completed(futures, timeout=90), start=1):
            try: row = future.result()
            except Exception: row = None
            if row and minimum <= row["Upside"] <= maximum and (moat_filter == "Any estimate" or row["Moat estimate"] == moat_filter): rows.append(row)
            elif not row: skipped += 1
            progress(done, total)
    except TimeoutError:
        skipped += sum(not future.done() for future in futures)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    output = pd.DataFrame(rows)
    if not output.empty: output = output.sort_values(["Moat score", "Upside"], ascending=False).reset_index(drop=True)
    return output, skipped
