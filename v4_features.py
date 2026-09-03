"""Core calculations and persistence for AANIANG V4."""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import yfinance as yf


DATA_DIR = Path("user_data")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
        return number if math.isfinite(number) else default
    except (TypeError, ValueError):
        return default


def copilot_answer(question: str, row: dict) -> str:
    """Return an explainable answer from the selected company's measured fields."""
    q = question.lower()
    symbol = row.get("Symbol", "This company")
    quality = _number(row.get("Quality"))
    gap = _number(row.get("Value gap"))
    growth = _number(row.get("Revenue growth"))
    margin = _number(row.get("Operating margin"))
    debt = _number(row.get("Debt/Equity"))
    momentum = _number(row.get("6M return"))
    if any(word in q for word in ("risk", "bear", "danger", "weak")):
        risks = []
        if debt > 150: risks.append(f"debt/equity is elevated at {debt:.0f}%")
        if growth < 0: risks.append(f"revenue growth is negative at {growth:.1f}%")
        if margin < 5: risks.append(f"operating margin is thin at {margin:.1f}%")
        if gap < 0: risks.append(f"the valuation gap is {gap:.1f}%, suggesting limited modeled upside")
        return f"{symbol}: " + ("; ".join(risks) if risks else "no major rule-based red flags were detected in the loaded metrics") + "."
    if any(word in q for word in ("buy", "attractive", "value", "cheap")):
        return f"{symbol} has a quality score of {quality:.0f}/100 and a modeled value gap of {gap:.1f}%. Revenue growth is {growth:.1f}% and operating margin is {margin:.1f}%. Treat this as a research signal, not a buy recommendation."
    if any(word in q for word in ("momentum", "trend", "technical")):
        direction = "positive" if momentum > 0 else "negative"
        return f"{symbol}'s six-month return is {momentum:.1f}%, so measured medium-term momentum is {direction}. Confirm with the multi-timeframe chart before acting."
    return f"{symbol} scores {quality:.0f}/100 for quality, with {growth:.1f}% revenue growth, {margin:.1f}% operating margin, {debt:.0f}% debt/equity, and a {gap:.1f}% modeled value gap. Ask about risk, valuation, momentum, or attractiveness for a focused explanation."


def sec_filings(symbol: str, user_agent: str) -> dict:
    """Load recent filing metadata from the official SEC submissions API."""
    headers = {"User-Agent": user_agent or "AANIANG-Trading-Station research@example.com", "Accept-Encoding": "gzip, deflate"}
    tickers = requests.get("https://www.sec.gov/files/company_tickers.json", headers=headers, timeout=15)
    tickers.raise_for_status()
    match = next((item for item in tickers.json().values() if item["ticker"].upper() == symbol.upper()), None)
    if not match:
        raise ValueError(f"SEC CIK not found for {symbol}.")
    cik = str(match["cik_str"]).zfill(10)
    response = requests.get(f"https://data.sec.gov/submissions/CIK{cik}.json", headers=headers, timeout=15)
    response.raise_for_status()
    data = response.json(); recent = data.get("filings", {}).get("recent", {})
    rows = pd.DataFrame(recent)
    if not rows.empty:
        rows = rows[rows["form"].isin(["10-K", "10-Q", "8-K", "20-F", "6-K"])].head(15).copy()
        rows["url"] = rows.apply(lambda r: f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{str(r['accessionNumber']).replace('-', '')}/{r['primaryDocument']}", axis=1)
    return {"company": data.get("name", match.get("title")), "cik": cik, "filings": rows}


def evaluate_alert(row: dict, field: str, operator: str, threshold: float) -> tuple[bool, float]:
    value = _number(row.get(field))
    triggered = value >= threshold if operator == ">=" else value <= threshold
    return triggered, value


def _ledger_path() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / "v4_paper_trades.json"


def load_trades() -> list[dict]:
    try: return json.loads(_ledger_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return []


def save_trade(trade: dict) -> None:
    trades = load_trades(); trades.append(trade)
    _ledger_path().write_text(json.dumps(trades, indent=2), encoding="utf-8")


def paper_positions(trades: list[dict], prices: dict[str, float]) -> pd.DataFrame:
    if not trades: return pd.DataFrame()
    frame = pd.DataFrame(trades); frame["signed_shares"] = np.where(frame.Side.eq("BUY"), frame.Shares, -frame.Shares)
    frame["signed_cash"] = np.where(frame.Side.eq("BUY"), -frame.Shares * frame.Price, frame.Shares * frame.Price)
    positions = frame.groupby("Symbol", as_index=False).agg(Shares=("signed_shares", "sum"), Cash_flow=("signed_cash", "sum"))
    positions["Current price"] = positions.Symbol.map(prices).fillna(0)
    positions["Market value"] = positions.Shares * positions["Current price"]
    positions["Total P/L"] = positions["Cash_flow"] + positions["Market value"]
    return positions


def history_matrix(symbols: list[str], period: str = "1y") -> pd.DataFrame:
    data = yf.download(symbols, period=period, auto_adjust=True, progress=False, threads=True)
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]].rename(columns={"Close": symbols[0]})
    if isinstance(close, pd.Series): close = close.to_frame(symbols[0])
    return close.dropna(how="all")


def optimize_portfolio(symbols: list[str], max_weight: float = 0.35) -> tuple[pd.DataFrame, dict]:
    prices = history_matrix(symbols)
    returns = prices.pct_change().dropna(how="all")
    vol = returns.std() * np.sqrt(252)
    raw = 1 / vol.replace(0, np.nan); weights = (raw / raw.sum()).fillna(0)
    for _ in range(10):
        weights = weights.clip(upper=max_weight)
        if weights.sum() > 0: weights /= weights.sum()
    portfolio_returns = returns.mul(weights, axis=1).sum(axis=1)
    metrics = {"Expected return": portfolio_returns.mean() * 252 * 100, "Volatility": portfolio_returns.std() * np.sqrt(252) * 100, "Sharpe": portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252) if portfolio_returns.std() else 0}
    result = pd.DataFrame({"Symbol": weights.index, "Suggested weight": weights.values * 100, "Annual volatility": vol.reindex(weights.index).values * 100})
    return result.sort_values("Suggested weight", ascending=False), metrics


def monte_carlo(symbols: list[str], weights: list[float], initial: float, years: int, simulations: int = 1000, seed: int = 42) -> tuple[pd.DataFrame, dict]:
    returns = history_matrix(symbols).pct_change().dropna()
    w = np.asarray(weights, dtype=float); w = w / w.sum()
    daily = returns.to_numpy() @ w
    mean, std = float(np.mean(daily)), float(np.std(daily))
    rng = np.random.default_rng(seed); days = 252 * years
    paths = initial * np.cumprod(1 + rng.normal(mean, std, size=(days, simulations)), axis=0)
    terminal = paths[-1]
    percentiles = np.percentile(paths, [10, 50, 90], axis=1)
    chart = pd.DataFrame({"P10": percentiles[0], "Median": percentiles[1], "P90": percentiles[2]})
    return chart, {"P10": np.percentile(terminal, 10), "Median": np.median(terminal), "P90": np.percentile(terminal, 90), "Loss probability": np.mean(terminal < initial) * 100}


def earnings_calendar(symbols: list[str]) -> pd.DataFrame:
    rows = []
    for symbol in symbols[:20]:
        try:
            calendar = yf.Ticker(symbol).calendar
            if isinstance(calendar, dict):
                earnings = calendar.get("Earnings Date", [])
                if not isinstance(earnings, (list, tuple)): earnings = [earnings]
                rows.append({"Symbol": symbol, "Next earnings": str(earnings[0])[:19] if earnings else "Unavailable", "Ex-dividend": str(calendar.get("Ex-Dividend Date", "Unavailable"))[:19]})
        except Exception: rows.append({"Symbol": symbol, "Next earnings": "Unavailable", "Ex-dividend": "Unavailable"})
    return pd.DataFrame(rows)


def options_snapshot(symbol: str, expiry: str = "") -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    ticker = yf.Ticker(symbol); expiries = list(ticker.options)
    if not expiries: return pd.DataFrame(), pd.DataFrame(), []
    selected = expiry if expiry in expiries else expiries[0]
    chain = ticker.option_chain(selected)
    calls, puts = chain.calls.copy(), chain.puts.copy()
    for frame in (calls, puts):
        frame["Volume/OI"] = frame["volume"].fillna(0) / frame["openInterest"].replace(0, np.nan)
    return calls, puts, expiries


def export_vault(profile: dict, notes: dict, alerts: list, trades: list) -> bytes:
    payload = {"version": 1, "exported_at": datetime.now(timezone.utc).isoformat(), "profile": profile, "notes": notes, "alerts": alerts, "trades": trades}
    return json.dumps(payload, indent=2).encode("utf-8")

