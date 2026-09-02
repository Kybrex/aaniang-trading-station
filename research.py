"""Market context, relative strength, earnings checks, and a transparent simple backtest."""
from __future__ import annotations

from datetime import date, timedelta
import pandas as pd
import yfinance as yf

from data import cached_frame, download_batch, last_number, symbol_frame
from indicators import add_indicators

def market_regime() -> dict[str, str]:
    raw = download_batch(["SPY", "QQQ", "^VIX"], period="1y", timeout=15)
    output: dict[str, str] = {}
    for symbol, label in [("SPY", "S&P 500"), ("QQQ", "Nasdaq 100"), ("^VIX", "VIX")]:
        frame = symbol_frame(raw, symbol)
        if frame.empty or (symbol != "^VIX" and len(frame) < 200):
            output[label] = "Unavailable"
            continue
        df = add_indicators(frame)
        close = last_number(df["Close"].iloc[-1])
        sma = last_number(df["SMA200"].iloc[-1]) if symbol != "^VIX" else None
        if close is None or (symbol != "^VIX" and sma is None):
            output[label] = "Unavailable"
        elif symbol == "^VIX":
            output[label] = f"{close:.1f} ({'elevated' if close >= 22 else 'calm'})"
        else:
            output[label] = f"{close:.2f} ({'risk-on' if close > sma else 'risk-off'})"
    return output

def add_relative_strength(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty: return results
    benchmark = cached_frame("SPY", minimum_rows=21)
    if benchmark.empty:
        benchmark = symbol_frame(download_batch(["SPY"], period="4mo", timeout=25), "SPY")
    if len(benchmark) < 21:
        results["RS vs SPY"] = None
        return results
    spy_return = benchmark["Close"].iloc[-1] / benchmark["Close"].iloc[-21] - 1
    values: list[float | None] = []
    for symbol in results["Symbol"]:
        frame = cached_frame(symbol, minimum_rows=21)
        values.append(round(((frame["Close"].iloc[-1] / frame["Close"].iloc[-21] - 1) - spy_return) * 100, 2) if len(frame) >= 21 else None)
    results = results.copy(); results["RS vs SPY"] = values
    return results

def next_earnings(symbol: str) -> date | None:
    """Best-effort yfinance calendar lookup; failures remain non-blocking."""
    try:
        calendar = yf.Ticker(symbol).calendar
        if calendar is None: return None
        value = None
        if isinstance(calendar, pd.DataFrame) and "Earnings Date" in calendar.index:
            value = calendar.loc["Earnings Date"].iloc[0]
        elif isinstance(calendar, dict):
            value = calendar.get("Earnings Date") or calendar.get("EarningsDate")
        elif isinstance(calendar, pd.Series):
            value = calendar.get("Earnings Date")
        if isinstance(value, (list, tuple, pd.Index)):
            value = value[0] if len(value) else None
        parsed = pd.to_datetime(value, errors="coerce")
        if isinstance(parsed, pd.DatetimeIndex): parsed = parsed[0] if len(parsed) else pd.NaT
        return parsed.date() if pd.notna(parsed) else None
    except Exception:
        return None

def annotate_earnings(results: pd.DataFrame, days: int) -> pd.DataFrame:
    out = results.copy(); dates = [next_earnings(s) for s in out["Symbol"]]
    out["Earnings"] = [d.isoformat() if d else "Unknown" for d in dates]
    cutoff = date.today() + timedelta(days=days)
    out["Earnings safe"] = [d is None or d > cutoff for d in dates]
    return out

def backtest(symbol: str, side: str, days: int = 20) -> pd.DataFrame:
    frame = symbol_frame(download_batch([symbol], period="5y", timeout=25), symbol)
    if len(frame) < 220:
        frame = cached_frame(symbol, minimum_rows=220)
    if len(frame) < 220: return pd.DataFrame()
    df = add_indicators(frame).dropna().copy(); trades: list[dict] = []
    for i in range(1, len(df) - days):
        row, previous = df.iloc[i], df.iloc[i - 1]
        long = row.Close > row.SMA200 and row.EMA20 > row.EMA50 and row.Mom20 > 0 and row.Close > row.EMA20 and previous.Close <= previous.EMA20
        short = row.Close < row.SMA200 and row.EMA20 < row.EMA50 and row.Mom20 < 0 and row.Close < row.EMA20 and previous.Close >= previous.EMA20
        if (side == "LONG" and not long) or (side == "SHORT" and not short): continue
        entry, risk = float(row.Close), float(row.ATR14 * 1.5)
        stop, target = (entry - risk, entry + 2 * risk) if side == "LONG" else (entry + risk, entry - 2 * risk)
        outcome = (float(df.iloc[i + days].Close) - entry) / risk if side == "LONG" else (entry - float(df.iloc[i + days].Close)) / risk
        for _, future in df.iloc[i + 1:i + days + 1].iterrows():
            if side == "LONG" and future.Low <= stop: outcome = -1; break
            if side == "SHORT" and future.High >= stop: outcome = -1; break
            if side == "LONG" and future.High >= target: outcome = 2; break
            if side == "SHORT" and future.Low <= target: outcome = 2; break
        trades.append({"Date": df.index[i].date(), "R multiple": round(outcome, 2)})
    return pd.DataFrame(trades)

def evaluate_alerts(saved: pd.DataFrame) -> pd.DataFrame:
    """Evaluate saved watchlist conditions against the latest available close."""
    if saved.empty: return saved
    raw = download_batch(saved["Symbol"].astype(str).tolist(), period="5d", timeout=20)
    rows=[]
    for _, item in saved.iterrows():
        frame=symbol_frame(raw,str(item.Symbol)); price=last_number(frame["Close"].iloc[-1]) if not frame.empty else None
        condition=str(item.Alert); side=str(item.Signal).upper(); reached=False
        if price is not None:
            if condition=="Entry reached": reached=price>=float(item.Entry) if side=="LONG" else price<=float(item.Entry)
            elif condition=="Stop reached": reached=price<=float(item.Stop) if side=="LONG" else price>=float(item.Stop)
            elif condition=="Target 1 reached": reached=price>=float(item["Target 1"]) if side=="LONG" else price<=float(item["Target 1"])
            elif condition=="Target 2 reached": reached=price>=float(item["Target 2"]) if side=="LONG" else price<=float(item["Target 2"])
        row=item.to_dict(); row["Last price"]=price; row["Status"]="TRIGGERED" if reached else ("Waiting" if price is not None else "Unavailable"); rows.append(row)
    return pd.DataFrame(rows)
