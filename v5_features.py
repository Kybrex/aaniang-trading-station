"""Institutional-style research helpers for AANIANG V5."""
from __future__ import annotations

import re
from collections import deque
from typing import Any

import numpy as np
import pandas as pd
import yfinance as yf


SECTOR_ETFS = {
    "Technology": "XLK", "Financials": "XLF", "Healthcare": "XLV",
    "Consumer Discretionary": "XLY", "Consumer Defensive": "XLP",
    "Industrials": "XLI", "Energy": "XLE", "Utilities": "XLU",
    "Real Estate": "XLRE", "Materials": "XLB", "Communication": "XLC",
}


def number(value: Any, default: float = 0.0) -> float:
    try:
        value = float(value)
        return value if np.isfinite(value) else default
    except (TypeError, ValueError): return default


def transcript_analysis(text: str) -> dict:
    cleaned = re.sub(r"\s+", " ", text).strip()
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", cleaned) if len(s.strip()) > 30]
    positive = ("strong", "growth", "improved", "record", "accelerat", "confident", "opportunity", "raised")
    negative = ("weak", "decline", "pressure", "risk", "uncertain", "slowed", "lowered", "headwind")
    guidance_words = ("guidance", "outlook", "expect", "forecast", "anticipate")
    pos = sum(any(word in s.lower() for word in positive) for s in sentences)
    neg = sum(any(word in s.lower() for word in negative) for s in sentences)
    tone = "Constructive" if pos > neg * 1.25 else "Cautious" if neg > pos * 1.25 else "Balanced"
    guidance = [s for s in sentences if any(word in s.lower() for word in guidance_words)][:8]
    risks = [s for s in sentences if any(word in s.lower() for word in negative)][:8]
    highlights = sorted(sentences, key=lambda s: sum(word in s.lower() for word in positive + negative + guidance_words), reverse=True)[:8]
    return {"Tone": tone, "Positive signals": pos, "Risk signals": neg, "Highlights": highlights, "Guidance": guidance, "Risks": risks}


def insider_activity(symbol: str) -> pd.DataFrame:
    data = yf.Ticker(symbol).insider_transactions
    return data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame()


def ownership(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    ticker = yf.Ticker(symbol)
    institutions = ticker.institutional_holders
    funds = ticker.mutualfund_holders
    major = ticker.major_holders
    frames = [frame.copy() if isinstance(frame, pd.DataFrame) else pd.DataFrame() for frame in (institutions, funds, major)]
    return frames[0], frames[1], frames[2]


def dividend_intelligence(symbol: str) -> tuple[pd.DataFrame, dict]:
    ticker = yf.Ticker(symbol); info = ticker.info or {}; dividends = ticker.dividends
    annual = dividends.groupby(dividends.index.year).sum() if not dividends.empty else pd.Series(dtype=float)
    growth = annual.pct_change() * 100
    frame = pd.DataFrame({"Dividend/share": annual, "Growth %": growth}).reset_index(names="Year") if not annual.empty else pd.DataFrame()
    payout = number(info.get("payoutRatio")) * 100; debt = number(info.get("debtToEquity")); fcf = number(info.get("freeCashflow")); net_income = number(info.get("netIncomeToCommon"))
    safety = 50 + (15 if 0 < payout < 65 else -15 if payout > 90 else 0) + (15 if fcf > 0 else -15) + (10 if debt < 100 else -10) + (10 if len(annual) >= 5 and (growth.tail(5).fillna(0) >= 0).sum() >= 4 else 0)
    metrics = {"Yield": number(info.get("dividendYield")) * 100, "Payout ratio": payout, "5Y average growth": growth.tail(5).mean() if not growth.empty else 0, "Annual income/share": annual.iloc[-1] if not annual.empty else 0, "Safety score": int(np.clip(safety, 0, 100))}
    return frame, metrics


def catalysts(symbol: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    ticker = yf.Ticker(symbol); calendar = ticker.calendar; news = ticker.news or []
    cal_rows = []
    if isinstance(calendar, dict):
        for key, value in calendar.items(): cal_rows.append({"Event": key, "Date/value": str(value)})
    news_rows = []
    for item in news[:15]:
        content = item.get("content", item)
        news_rows.append({"Published": content.get("pubDate", ""), "Title": content.get("title", ""), "Publisher": content.get("provider", {}).get("displayName", content.get("publisher", "")), "URL": content.get("canonicalUrl", {}).get("url", content.get("link", ""))})
    return pd.DataFrame(cal_rows), pd.DataFrame(news_rows)


def sector_rotation(period: str = "6mo") -> pd.DataFrame:
    tickers = list(SECTOR_ETFS.values()); data = yf.download(tickers, period=period, auto_adjust=True, progress=False, threads=True)
    close = data["Close"]
    rows = []
    reverse = {ticker: sector for sector, ticker in SECTOR_ETFS.items()}
    for ticker in tickers:
        series = close[ticker].dropna() if ticker in close else pd.Series(dtype=float)
        if len(series) < 2: continue
        rows.append({"Sector": reverse[ticker], "ETF": ticker, "1M return": (series.iloc[-1] / series.iloc[-min(22, len(series))] - 1) * 100, "3M return": (series.iloc[-1] / series.iloc[-min(64, len(series))] - 1) * 100, "6M return": (series.iloc[-1] / series.iloc[0] - 1) * 100})
    frame = pd.DataFrame(rows)
    if not frame.empty: frame["Rotation score"] = frame[["1M return", "3M return", "6M return"]].rank(pct=True).mean(axis=1) * 100
    return frame.sort_values("Rotation score", ascending=False) if not frame.empty else frame


def scenario_table(price: float, base_growth: float, base_margin: float, base_pe: float, years: int, assumptions: dict[str, tuple[float, float, float]]) -> pd.DataFrame:
    rows = []
    for name, (growth, margin, exit_pe) in assumptions.items():
        growth_factor = (1 + growth / 100) ** years
        margin_factor = margin / max(base_margin, 1)
        multiple_factor = exit_pe / max(base_pe, 1)
        estimated = price * growth_factor * margin_factor * multiple_factor
        rows.append({"Scenario": name, "Revenue growth %": growth, "Operating margin %": margin, "Exit P/E": exit_pe, "Estimated price": estimated, "Return %": (estimated / price - 1) * 100})
    return pd.DataFrame(rows)


def fifo_tax_lots(trades: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {"Date", "Symbol", "Side", "Shares", "Price"}
    if not required.issubset(trades.columns): raise ValueError("CSV requires Date, Symbol, Side, Shares, and Price columns.")
    frame = trades.copy(); frame["Date"] = pd.to_datetime(frame["Date"]); frame = frame.sort_values("Date")
    lots: dict[str, deque] = {}; realized = []
    for row in frame.itertuples(index=False):
        symbol = str(row.Symbol).upper(); side = str(row.Side).upper(); shares = float(row.Shares); price = float(row.Price)
        lots.setdefault(symbol, deque())
        if side == "BUY": lots[symbol].append([shares, price, row.Date])
        elif side == "SELL":
            remaining = shares
            while remaining > 0 and lots[symbol]:
                lot = lots[symbol][0]; used = min(remaining, lot[0]); gain = used * (price - lot[1]); days = (row.Date - lot[2]).days
                realized.append({"Symbol": symbol, "Shares": used, "Proceeds": used * price, "Cost basis": used * lot[1], "Gain/loss": gain, "Term": "Long" if days > 365 else "Short"})
                lot[0] -= used; remaining -= used
                if lot[0] <= 1e-9: lots[symbol].popleft()
    result = pd.DataFrame(realized)
    metrics = {"Realized gain/loss": result["Gain/loss"].sum() if not result.empty else 0, "Short-term": result.loc[result.Term.eq("Short"), "Gain/loss"].sum() if not result.empty else 0, "Long-term": result.loc[result.Term.eq("Long"), "Gain/loss"].sum() if not result.empty else 0}
    return result, metrics


def management_score(row: dict) -> tuple[int, list[str]]:
    score = 0; reasons = []
    checks = [
        (number(row.get("ROE")) >= 15, 20, "Return on equity is at least 15%."),
        (number(row.get("Operating margin")) >= 15, 20, "Operating margin is at least 15%."),
        (number(row.get("Revenue growth")) > 0, 15, "Revenue is growing."),
        (number(row.get("Earnings growth")) > 0, 15, "Earnings are growing."),
        (number(row.get("Debt/Equity")) < 100, 15, "Debt/equity is below 100%."),
        (number(row.get("Quality")) >= 70, 15, "Overall quality score is at least 70."),
    ]
    for passed, points, explanation in checks:
        if passed: score += points; reasons.append(f"+{points}: {explanation}")
        else: reasons.append(f"+0: Did not pass - {explanation}")
    return score, reasons

