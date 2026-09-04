"""AANIANG V3 discovery, comparison, research, notes, portfolio, and data tools."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import math
from pathlib import Path
from typing import Callable

import pandas as pd
import requests
import yfinance as yf


DATA_COLUMNS = [
    "Symbol", "Company", "Sector", "Industry", "Price", "Market cap", "Quality",
    "ROE", "Operating margin", "Revenue growth", "Earnings growth", "Debt/Equity",
    "Current ratio", "Trailing P/E", "Forward P/E", "Price/Sales", "Dividend yield",
    "Beta", "Analyst target", "Value gap", "1M return", "6M return", "1Y return",
]

PRESETS = {
    "Quality compounders": {"min_quality": 70, "min_growth": 5, "max_debt": 120, "min_margin": 12},
    "Undervalued growth": {"min_quality": 55, "min_growth": 10, "min_value_gap": 15},
    "Fallen angels": {"min_quality": 65, "max_1y": -10, "min_1m": -20},
    "Defensive stocks": {"min_quality": 60, "max_beta": .85, "min_margin": 8},
    "Dividend cash cows": {"min_quality": 55, "min_dividend": 2, "max_debt": 150},
    "Momentum leaders": {"min_quality": 50, "min_1m": 5, "min_6m": 15},
    "Potential shorts": {"max_quality": 40, "max_1m": -5, "max_6m": -10},
    "Earnings quality": {"min_quality": 65, "min_growth": 8, "min_margin": 15},
    "GARP": {"min_quality": 65, "min_growth": 8, "max_forward_pe": 30},
    "All companies": {},
}


def num(value: object) -> float | None:
    try:
        answer = float(value)
        return answer if math.isfinite(answer) else None
    except (TypeError, ValueError):
        return None


def _pct(info: dict, key: str) -> float | None:
    value = num(info.get(key))
    return value * 100 if value is not None else None


def _return(history: pd.DataFrame, sessions: int) -> float | None:
    if history is None or history.empty or "Close" not in history or len(history) <= sessions:
        return None
    old, latest = num(history["Close"].iloc[-sessions - 1]), num(history["Close"].iloc[-1])
    return (latest / old - 1) * 100 if old and latest else None


def quality_from_info(info: dict) -> int:
    roe = _pct(info, "returnOnEquity"); margin = _pct(info, "operatingMargins")
    revenue = _pct(info, "revenueGrowth"); earnings = _pct(info, "earningsGrowth")
    debt = num(info.get("debtToEquity")); current = num(info.get("currentRatio"))
    fcf = num(info.get("freeCashflow")); operating = num(info.get("operatingCashflow"))
    score = 0
    score += 18 if roe is not None and roe >= 20 else 11 if roe is not None and roe >= 12 else 4 if roe is not None and roe > 0 else 0
    score += 16 if margin is not None and margin >= 20 else 10 if margin is not None and margin >= 10 else 3 if margin is not None and margin > 0 else 0
    score += 13 if revenue is not None and revenue >= 12 else 8 if revenue is not None and revenue >= 5 else 3 if revenue is not None and revenue > 0 else 0
    score += 13 if earnings is not None and earnings >= 12 else 8 if earnings is not None and earnings >= 5 else 3 if earnings is not None and earnings > 0 else 0
    score += 14 if debt is not None and debt <= 50 else 9 if debt is not None and debt <= 100 else 3 if debt is not None and debt <= 200 else 0
    score += 10 if current is not None and current >= 1.5 else 6 if current is not None and current >= 1 else 1 if current is not None and current > 0 else 0
    score += 16 if fcf is not None and fcf > 0 and operating is not None and operating > 0 else 8 if operating is not None and operating > 0 else 0
    return min(score, 100)


def yahoo_snapshot(symbol: str) -> dict | None:
    symbol = symbol.strip().upper()
    if not symbol:
        return None
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info() or {}
        history = ticker.history(period="1y", auto_adjust=True)
        price = num(info.get("currentPrice")) or num(info.get("regularMarketPrice"))
        if price is None and not history.empty:
            price = num(history["Close"].iloc[-1])
        if not price:
            return None
        target = num(info.get("targetMeanPrice"))
        fundamental_fields = ["returnOnEquity", "operatingMargins", "revenueGrowth", "earningsGrowth", "debtToEquity", "currentRatio", "freeCashflow"]
        fundamentals_available = sum(info.get(key) is not None for key in fundamental_fields) >= 3
        return {
            "Symbol": symbol, "Company": info.get("shortName") or info.get("longName") or symbol,
            "Sector": info.get("sector") or "Unknown", "Industry": info.get("industry") or "Unknown",
            "Price": price, "Market cap": num(info.get("marketCap")), "Quality": quality_from_info(info) if fundamentals_available else None,
            "ROE": _pct(info, "returnOnEquity"), "Operating margin": _pct(info, "operatingMargins"),
            "Revenue growth": _pct(info, "revenueGrowth"), "Earnings growth": _pct(info, "earningsGrowth"),
            "Debt/Equity": num(info.get("debtToEquity")), "Current ratio": num(info.get("currentRatio")),
            "Trailing P/E": num(info.get("trailingPE")), "Forward P/E": num(info.get("forwardPE")),
            "Price/Sales": num(info.get("priceToSalesTrailing12Months")), "Dividend yield": _pct(info, "dividendYield"),
            "Beta": num(info.get("beta")), "Analyst target": target,
            "Value gap": ((target / price - 1) * 100 if target else None),
            "1M return": _return(history, 21), "6M return": _return(history, 126), "1Y return": _return(history, 250),
            "Description": info.get("longBusinessSummary") or "", "Website": info.get("website") or "",
            "Currency": info.get("currency") or "USD", "Source": "Yahoo Finance",
            "Fundamentals available": fundamentals_available,
        }
    except Exception:
        return None


def fmp_profile(symbol: str, api_key: str) -> dict | None:
    if not api_key:
        return None
    try:
        response = requests.get("https://financialmodelingprep.com/stable/profile", params={"symbol": symbol.upper(), "apikey": api_key}, timeout=12)
        response.raise_for_status(); rows = response.json()
        if not rows:
            return None
        row = rows[0]
        return {"Symbol": symbol.upper(), "Company": row.get("companyName") or symbol.upper(), "Price": num(row.get("price")), "Market cap": num(row.get("marketCap")), "Sector": row.get("sector") or "Unknown", "Industry": row.get("industry") or "Unknown", "Beta": num(row.get("beta")), "Description": row.get("description") or "", "Website": row.get("website") or "", "Currency": row.get("currency") or "USD", "Source": "Financial Modeling Prep"}
    except Exception:
        return None


def load_snapshot(symbol: str, fmp_key: str = "") -> dict | None:
    yahoo = yahoo_snapshot(symbol)
    fmp = fmp_profile(symbol, fmp_key)
    if yahoo and fmp:
        merged = yahoo | {key: value for key, value in fmp.items() if value not in (None, "", "Unknown")}
        merged["Source"] = "FMP + Yahoo Finance"
        return merged
    return fmp or yahoo


def scan_symbols(symbols: list[str], fmp_key: str = "", progress: Callable[[int, int], None] | None = None, workers: int = 6) -> pd.DataFrame:
    clean = list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=max(1, min(workers, 8))) as pool:
        futures = {pool.submit(load_snapshot, symbol, fmp_key): symbol for symbol in clean}
        for done, future in enumerate(as_completed(futures), 1):
            try: row = future.result()
            except Exception: row = None
            if row: rows.append(row)
            if progress: progress(done, len(clean))
    frame = pd.DataFrame(rows)
    for column in DATA_COLUMNS:
        if column not in frame: frame[column] = None
    return frame.sort_values(["Quality", "Market cap"], ascending=False, na_position="last").reset_index(drop=True) if not frame.empty else frame


def apply_screen(frame: pd.DataFrame, rules: dict) -> pd.DataFrame:
    if frame.empty: return frame
    result = frame.copy()
    checks = [
        ("min_quality", "Quality", ">="), ("max_quality", "Quality", "<="),
        ("min_growth", "Revenue growth", ">="), ("min_margin", "Operating margin", ">="),
        ("max_debt", "Debt/Equity", "<="), ("max_beta", "Beta", "<="),
        ("min_dividend", "Dividend yield", ">="), ("min_value_gap", "Value gap", ">="),
        ("min_1m", "1M return", ">="), ("max_1m", "1M return", "<="),
        ("min_6m", "6M return", ">="), ("max_6m", "6M return", "<="),
        ("max_1y", "1Y return", "<="), ("max_forward_pe", "Forward P/E", "<="),
    ]
    for key, column, operation in checks:
        if key not in rules: continue
        values = pd.to_numeric(result[column], errors="coerce")
        result = result[(values >= rules[key]) if operation == ">=" else (values <= rules[key])]
    return result.reset_index(drop=True)


def peer_rank(frame: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if frame.empty: return frame
    selected = frame[frame.Symbol == symbol]
    if selected.empty: return pd.DataFrame()
    industry, sector = selected.iloc[0].Industry, selected.iloc[0].Sector
    peers = frame[(frame.Industry == industry) | (frame.Sector == sector)].copy()
    peers["Peer rank"] = peers["Quality"].rank(method="min", ascending=False).astype(int)
    return peers.sort_values(["Peer rank", "Value gap"], ascending=[True, False], na_position="last")


def research_brief(row: dict) -> dict[str, list[str]]:
    measured_quality = num(row.get("Quality")); quality = measured_quality or 0; growth = num(row.get("Revenue growth")); earnings = num(row.get("Earnings growth")); margin = num(row.get("Operating margin")); debt = num(row.get("Debt/Equity")); gap = num(row.get("Value gap")); beta = num(row.get("Beta"))
    bull, bear, moat, questions = [], [], [], []
    if quality >= 70: bull.append(f"Strong explainable quality score of {quality:.0f}/100.")
    if growth is not None and growth >= 10: bull.append(f"Revenue growth is {growth:.1f}%.")
    if earnings is not None and earnings >= 10: bull.append(f"Earnings growth is {earnings:.1f}%.")
    if gap is not None and gap >= 15: bull.append(f"Analyst consensus implies {gap:.1f}% upside, subject to estimate risk.")
    if margin is not None and margin >= 15: moat.append(f"Operating margin of {margin:.1f}% may indicate pricing power or scale advantages.")
    if measured_quality is not None and quality < 50: bear.append(f"Quality score is only {quality:.0f}/100.")
    if growth is not None and growth < 0: bear.append(f"Revenue is contracting by {abs(growth):.1f}%.")
    if earnings is not None and earnings < 0: bear.append(f"Earnings are contracting by {abs(earnings):.1f}%.")
    if debt is not None and debt > 150: bear.append(f"Debt/equity is elevated at {debt:.1f}%.")
    if gap is not None and gap < -10: bear.append(f"Price is {abs(gap):.1f}% above analyst consensus target.")
    if beta is not None and beta > 1.5: bear.append(f"Beta of {beta:.2f} indicates above-market volatility.")
    questions.extend(["Is growth organic and supported by free cash flow?", "Could margins survive a recession or stronger competition?", "What would invalidate the investment thesis?", "Are analyst estimates unusually optimistic or stale?"])
    return {"Bull case": bull or ["No strong quantitative bull flag was detected."], "Bear case": bear or ["No severe quantitative red flag was detected."], "Moat evidence": moat or ["Quantitative data alone does not establish a durable moat."], "Due-diligence questions": questions}


def notes_path(root: str | Path = "user_data") -> Path:
    return Path(root) / "v3_notes.json"


def load_notes(root: str | Path = "user_data") -> dict:
    path = notes_path(root)
    try: return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (OSError, json.JSONDecodeError): return {}


def save_note(symbol: str, note: dict, root: str | Path = "user_data") -> None:
    path = notes_path(root); path.parent.mkdir(parents=True, exist_ok=True)
    notes = load_notes(root); note["updated_at"] = datetime.now(timezone.utc).isoformat(); notes[symbol.upper()] = note
    path.write_text(json.dumps(notes, indent=2), encoding="utf-8")


def portfolio_health(holdings: pd.DataFrame, snapshots: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    required = {"Symbol", "Shares", "Cost"}
    if not required.issubset(holdings.columns): raise ValueError("Portfolio file needs Symbol, Shares, and Cost columns.")
    data = holdings.copy(); data["Symbol"] = data.Symbol.astype(str).str.upper().str.strip()
    data["Shares"] = pd.to_numeric(data.Shares, errors="coerce"); data["Cost"] = pd.to_numeric(data.Cost, errors="coerce")
    merged = data.merge(snapshots, on="Symbol", how="left")
    merged["Market value"] = merged.Shares * merged.Price; merged["Cost basis"] = merged.Shares * merged.Cost
    merged["Gain/Loss"] = merged["Market value"] - merged["Cost basis"]
    total = float(merged["Market value"].sum())
    merged["Weight"] = merged["Market value"] / total * 100 if total else 0
    sector_weights = merged.groupby("Sector", dropna=False)["Market value"].sum() / total * 100 if total else pd.Series(dtype=float)
    weighted_beta = float((merged.Beta.fillna(1) * merged.Weight / 100).sum()) if total else 0
    metrics = {"Value": total, "Gain/Loss": float(merged["Gain/Loss"].sum()), "Largest position": float(merged.Weight.max()) if not merged.empty else 0, "Largest sector": float(sector_weights.max()) if not sector_weights.empty else 0, "Weighted beta": weighted_beta, "Holdings": len(merged)}
    return merged, metrics

