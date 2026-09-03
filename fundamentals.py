"""Explainable company-quality and valuation research built on Yahoo Finance data."""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import pandas as pd
import yfinance as yf


def number(value: object) -> float | None:
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def _statement_series(frame: pd.DataFrame, names: Iterable[str]) -> pd.Series:
    if frame is None or frame.empty:
        return pd.Series(dtype=float)
    for name in names:
        if name in frame.index:
            series = pd.to_numeric(frame.loc[name], errors="coerce").dropna().sort_index()
            if not series.empty:
                return series
    return pd.Series(dtype=float)


def _growth(series: pd.Series) -> float | None:
    positive = series[series > 0]
    if len(positive) < 2:
        return None
    start, end = float(positive.iloc[0]), float(positive.iloc[-1])
    years = max(len(positive) - 1, 1)
    return (end / start) ** (1 / years) - 1 if start > 0 and end > 0 else None


def _consistency(series: pd.Series) -> float | None:
    if len(series) < 3:
        return None
    changes = series.pct_change(fill_method=None).replace([math.inf, -math.inf], pd.NA).dropna()
    if changes.empty:
        return None
    return float((changes > 0).mean())


def load_company(symbol: str) -> dict:
    """Fetch one reusable research bundle. Network failures surface as ValueError."""
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("Enter a stock symbol.")
    ticker = yf.Ticker(symbol)
    try:
        info = ticker.get_info() or {}
        history = ticker.history(period="5y", auto_adjust=True)
        income = ticker.financials
        cashflow = ticker.cashflow
        balance = ticker.balance_sheet
    except Exception as error:
        raise ValueError(f"Yahoo Finance could not load {symbol}: {error}") from error
    if not info and history.empty:
        raise ValueError(f"No usable data was returned for {symbol}.")
    return {"symbol": symbol, "info": info, "history": history, "income": income, "cashflow": cashflow, "balance": balance}


def financial_history(bundle: dict) -> pd.DataFrame:
    income, cashflow = bundle["income"], bundle["cashflow"]
    revenue = _statement_series(income, ["Total Revenue", "Operating Revenue"])
    earnings = _statement_series(income, ["Net Income", "Net Income Common Stockholders"])
    operating = _statement_series(income, ["Operating Income"])
    ocf = _statement_series(cashflow, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    capex = _statement_series(cashflow, ["Capital Expenditure", "Capital Expenditures"])
    index = revenue.index.union(earnings.index).union(operating.index).union(ocf.index).union(capex.index)
    table = pd.DataFrame(index=index)
    table["Revenue"] = revenue
    table["Net income"] = earnings
    table["Operating income"] = operating
    table["Operating cash flow"] = ocf
    table["Capital expenditure"] = capex.abs()
    table["Free cash flow"] = table["Operating cash flow"] - table["Capital expenditure"]
    table.index = pd.to_datetime(table.index).year.astype(str)
    return table.sort_index()


def quality_score(bundle: dict) -> tuple[int, pd.DataFrame]:
    """Return a transparent 0-100 quality score and its component evidence."""
    info = bundle["info"]
    history = financial_history(bundle)
    revenue, earnings, fcf = history.get("Revenue", pd.Series(dtype=float)).dropna(), history.get("Net income", pd.Series(dtype=float)).dropna(), history.get("Free cash flow", pd.Series(dtype=float)).dropna()
    roe = number(info.get("returnOnEquity")); margin = number(info.get("operatingMargins"))
    roic = number(info.get("returnOnAssets")); debt_equity = number(info.get("debtToEquity"))
    current_ratio = number(info.get("currentRatio")); revenue_growth = _growth(revenue)
    earnings_growth = _growth(earnings); fcf_consistency = _consistency(fcf)
    earnings_consistency = _consistency(earnings)

    rows: list[dict] = []
    def add(category: str, metric: str, value: float | None, maximum: int, points: int, display: str) -> None:
        rows.append({"Category": category, "Metric": metric, "Value": display if value is not None else "Unavailable", "Points": points if value is not None else 0, "Maximum": maximum})

    add("Profitability", "Return on equity", roe, 10, 10 if roe is not None and roe >= .20 else 6 if roe is not None and roe >= .12 else 2 if roe is not None and roe > 0 else 0, f"{roe:.1%}" if roe is not None else "")
    add("Profitability", "Operating margin", margin, 10, 10 if margin is not None and margin >= .20 else 6 if margin is not None and margin >= .10 else 2 if margin is not None and margin > 0 else 0, f"{margin:.1%}" if margin is not None else "")
    add("Profitability", "Return on assets proxy", roic, 5, 5 if roic is not None and roic >= .10 else 3 if roic is not None and roic >= .05 else 1 if roic is not None and roic > 0 else 0, f"{roic:.1%}" if roic is not None else "")
    add("Growth", "Annualized revenue growth", revenue_growth, 10, 10 if revenue_growth is not None and revenue_growth >= .12 else 6 if revenue_growth is not None and revenue_growth >= .05 else 2 if revenue_growth is not None and revenue_growth > 0 else 0, f"{revenue_growth:.1%}" if revenue_growth is not None else "")
    add("Growth", "Annualized earnings growth", earnings_growth, 10, 10 if earnings_growth is not None and earnings_growth >= .12 else 6 if earnings_growth is not None and earnings_growth >= .05 else 2 if earnings_growth is not None and earnings_growth > 0 else 0, f"{earnings_growth:.1%}" if earnings_growth is not None else "")
    add("Cash flow", "Positive latest free cash flow", number(fcf.iloc[-1]) if not fcf.empty else None, 10, 10 if not fcf.empty and fcf.iloc[-1] > 0 else 0, f"${fcf.iloc[-1]/1e9:.2f}B" if not fcf.empty else "")
    add("Cash flow", "Free-cash-flow consistency", fcf_consistency, 10, round(10 * fcf_consistency) if fcf_consistency is not None else 0, f"{fcf_consistency:.0%} positive years" if fcf_consistency is not None else "")
    add("Balance sheet", "Debt to equity", debt_equity, 10, 10 if debt_equity is not None and debt_equity <= 50 else 6 if debt_equity is not None and debt_equity <= 100 else 2 if debt_equity is not None and debt_equity <= 200 else 0, f"{debt_equity:.1f}%" if debt_equity is not None else "")
    add("Balance sheet", "Current ratio", current_ratio, 10, 10 if current_ratio is not None and current_ratio >= 1.5 else 6 if current_ratio is not None and current_ratio >= 1 else 1 if current_ratio is not None and current_ratio > 0 else 0, f"{current_ratio:.2f}" if current_ratio is not None else "")
    add("Predictability", "Earnings consistency", earnings_consistency, 15, round(15 * earnings_consistency) if earnings_consistency is not None else 0, f"{earnings_consistency:.0%} positive years" if earnings_consistency is not None else "")
    evidence = pd.DataFrame(rows)
    return int(evidence["Points"].sum()), evidence


@dataclass(frozen=True)
class ValuationAssumptions:
    growth: float
    discount: float
    terminal_growth: float
    earnings_multiple: float


def intrinsic_value(bundle: dict, assumptions: ValuationAssumptions) -> dict:
    info = bundle["info"]
    history = financial_history(bundle)
    shares = number(info.get("sharesOutstanding"))
    price = number(info.get("currentPrice")) or number(info.get("regularMarketPrice"))
    fcf_series = history.get("Free cash flow", pd.Series(dtype=float)).dropna()
    earnings_series = history.get("Net income", pd.Series(dtype=float)).dropna()
    values: dict[str, float] = {}
    if shares and shares > 0 and not fcf_series.empty and fcf_series.iloc[-1] > 0 and assumptions.discount > assumptions.terminal_growth:
        base_fcf = float(fcf_series.tail(3).median())
        projected = [base_fcf * (1 + assumptions.growth) ** year for year in range(1, 6)]
        terminal = projected[-1] * (1 + assumptions.terminal_growth) / (assumptions.discount - assumptions.terminal_growth)
        enterprise = sum(value / (1 + assumptions.discount) ** year for year, value in enumerate(projected, 1)) + terminal / (1 + assumptions.discount) ** 5
        cash = number(info.get("totalCash")) or 0; debt = number(info.get("totalDebt")) or 0
        values["DCF / FCF"] = max(0, (enterprise + cash - debt) / shares)
    eps = number(info.get("trailingEps"))
    if eps and eps > 0:
        values["Earnings multiple"] = eps * (1 + assumptions.growth) ** 3 * assumptions.earnings_multiple / (1 + assumptions.discount) ** 3
    book = number(info.get("bookValue")); pb = number(info.get("priceToBook"))
    if book and book > 0 and pb and pb > 0:
        values["Book-value normalization"] = book * min(max(pb, .8), 4.0)
    analyst = number(info.get("targetMeanPrice"))
    if analyst and analyst > 0:
        values["Analyst consensus"] = analyst
    fair = sum(values.values()) / len(values) if values else None
    return {"price": price, "methods": values, "fair_value": fair, "margin_of_safety": ((fair / price - 1) * 100 if fair and price else None), "earnings_history": earnings_series}


def default_growth(bundle: dict) -> float:
    history = financial_history(bundle)
    estimates = [_growth(history[column].dropna()) for column in ["Revenue", "Net income", "Free cash flow"] if column in history]
    usable = [value for value in estimates if value is not None]
    return min(max(float(pd.Series(usable).median()), 0), .25) if usable else .08


