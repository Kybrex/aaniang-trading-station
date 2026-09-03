"""Advanced technical and market-intelligence engines for AANIANG V6."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
import yfinance as yf

from technical_chart import technical_data


def load_history(symbol: str, period: str = "2y") -> pd.DataFrame:
    return yf.Ticker(symbol.strip().upper()).history(period=period, auto_adjust=True)


def advanced_indicators(history: pd.DataFrame) -> pd.DataFrame:
    frame = technical_data(history)
    close, high, low = frame["Close"], frame["High"], frame["Low"]
    middle = close.rolling(20).mean(); deviation = close.rolling(20).std()
    frame["BB middle"] = middle; frame["BB upper"] = middle + 2 * deviation; frame["BB lower"] = middle - 2 * deviation
    typical = (high + low + close) / 3
    frame["VWAP"] = (typical * frame["Volume"]).cumsum() / frame["Volume"].cumsum().replace(0, np.nan)
    conversion = (high.rolling(9).max() + low.rolling(9).min()) / 2
    base = (high.rolling(26).max() + low.rolling(26).min()) / 2
    frame["Ichimoku conversion"] = conversion; frame["Ichimoku base"] = base
    frame["Ichimoku span A"] = ((conversion + base) / 2).shift(26)
    frame["Ichimoku span B"] = ((high.rolling(52).max() + low.rolling(52).min()) / 2).shift(26)
    atr = frame["ATR 14"].fillna((high - low).rolling(14).mean())
    basic_upper = (high + low) / 2 + 3 * atr; basic_lower = (high + low) / 2 - 3 * atr
    direction = pd.Series(1, index=frame.index, dtype=int)
    for index in range(1, len(frame)):
        if close.iloc[index] > basic_upper.iloc[index - 1]: direction.iloc[index] = 1
        elif close.iloc[index] < basic_lower.iloc[index - 1]: direction.iloc[index] = -1
        else: direction.iloc[index] = direction.iloc[index - 1]
    frame["Supertrend"] = np.where(direction > 0, basic_lower, basic_upper); frame["Supertrend direction"] = direction
    return frame


def support_resistance(frame: pd.DataFrame, window: int = 5, tolerance: float = 0.018) -> pd.DataFrame:
    recent = frame.tail(300); high, low = recent["High"], recent["Low"]
    pivots = list(high[high.eq(high.rolling(window * 2 + 1, center=True).max())].dropna()) + list(low[low.eq(low.rolling(window * 2 + 1, center=True).min())].dropna())
    clusters: list[list[float]] = []
    for value in sorted(pivots):
        match = next((cluster for cluster in clusters if abs(value - np.mean(cluster)) / max(np.mean(cluster), 0.01) <= tolerance), None)
        (match if match is not None else clusters.append([value]))
        if match is not None: match.append(value)
    price = float(recent.Close.iloc[-1]); rows = []
    for cluster in clusters:
        level = float(np.mean(cluster))
        if len(cluster) >= 2: rows.append({"Type": "Resistance" if level > price else "Support", "Level": level, "Touches": len(cluster), "Distance %": (level / price - 1) * 100})
    return pd.DataFrame(rows).sort_values("Distance %", key=lambda values: values.abs()).head(10) if rows else pd.DataFrame(columns=["Type", "Level", "Touches", "Distance %"])


def detect_patterns(frame: pd.DataFrame) -> list[dict]:
    recent = frame.tail(80); close = recent.Close.dropna(); high = recent.High; low = recent.Low
    if len(close) < 30: return []
    results = []; price = float(close.iloc[-1])
    peak_values = high[high.eq(high.rolling(9, center=True).max())].dropna().tail(3)
    trough_values = low[low.eq(low.rolling(9, center=True).min())].dropna().tail(3)
    if len(peak_values) >= 2 and abs(peak_values.iloc[-1] / peak_values.iloc[-2] - 1) < .025: results.append({"Pattern": "Possible double top", "Bias": "Bearish", "Confidence": 70})
    if len(trough_values) >= 2 and abs(trough_values.iloc[-1] / trough_values.iloc[-2] - 1) < .025: results.append({"Pattern": "Possible double bottom", "Bias": "Bullish", "Confidence": 70})
    x = np.arange(len(close)); slope = np.polyfit(x, close.values, 1)[0]
    range_start = float((high - low).head(20).mean()); range_end = float((high - low).tail(20).mean())
    if range_end < range_start * .72: results.append({"Pattern": "Volatility contraction / triangle", "Bias": "Breakout watch", "Confidence": 65})
    results.append({"Pattern": "Rising channel" if slope > 0 else "Falling channel", "Bias": "Bullish" if slope > 0 else "Bearish", "Confidence": min(90, int(55 + abs(slope / max(price, .01)) * 1000))})
    return results


def technical_score(frame: pd.DataFrame) -> tuple[int, list[dict]]:
    latest = frame.dropna(subset=["Close"]).iloc[-1]; price = float(latest.Close); checks = []
    def add(name: str, passed: bool, points: int, detail: str): checks.append({"Factor": name, "Status": "Positive" if passed else "Negative", "Points": points if passed else 0, "Maximum": points, "Detail": detail})
    add("Price vs SMA 20", price > latest.get("SMA 20", price), 15, "Short-term trend")
    add("Price vs SMA 50", price > latest.get("SMA 50", price), 15, "Intermediate trend")
    add("Price vs SMA 200", price > latest.get("SMA 200", price), 20, "Long-term trend")
    add("SMA 50 vs SMA 200", latest.get("SMA 50", 0) > latest.get("SMA 200", 0), 15, "Trend structure")
    rsi = float(latest.get("RSI 14", 50)); add("RSI regime", 40 <= rsi <= 70, 10, f"RSI {rsi:.1f}")
    add("MACD", latest.get("MACD", 0) > latest.get("MACD signal", 0), 15, "Momentum crossover")
    volume_ratio = float(frame.Volume.tail(20).mean() / max(frame.Volume.tail(60).mean(), 1)); add("Volume confirmation", volume_ratio >= 1, 10, f"20D/60D volume {volume_ratio:.2f}x")
    return int(sum(row["Points"] for row in checks)), checks


def relative_strength(universe: pd.DataFrame) -> pd.DataFrame:
    columns = [column for column in ["Symbol", "Company", "Sector", "Quality", "1M return", "6M return", "1Y return"] if column in universe]
    frame = universe[columns].copy()
    for metric in ["1M return", "6M return", "1Y return"]:
        if metric in frame: frame[f"{metric} percentile"] = frame[metric].rank(pct=True) * 100
    rank_cols = [column for column in frame if column.endswith("percentile")]
    frame["RS score"] = frame[rank_cols].mean(axis=1) if rank_cols else 0
    if "Sector" in frame: frame["Sector rank"] = frame.groupby("Sector")["RS score"].rank(ascending=False, method="min")
    return frame.sort_values("RS score", ascending=False)


def market_breadth(symbols: list[str]) -> tuple[pd.DataFrame, dict]:
    data = yf.download(symbols[:100], period="1y", auto_adjust=True, progress=False, threads=True)
    close = data["Close"] if isinstance(data.columns, pd.MultiIndex) else data[["Close"]].rename(columns={"Close": symbols[0]})
    rows = []
    for symbol in close.columns:
        series = close[symbol].dropna()
        if len(series) < 50: continue
        last = series.iloc[-1]; rows.append({"Symbol": symbol, "1D change": (last / series.iloc[-2] - 1) * 100, "Above SMA50": last > series.tail(50).mean(), "Above SMA200": last > series.tail(200).mean() if len(series) >= 200 else False, "20D high": last >= series.tail(20).max(), "20D low": last <= series.tail(20).min()})
    frame = pd.DataFrame(rows)
    total = max(len(frame), 1); metrics = {"Advancing %": frame["1D change"].gt(0).sum() / total * 100, "Above SMA50 %": frame["Above SMA50"].sum() / total * 100, "Above SMA200 %": frame["Above SMA200"].sum() / total * 100, "New 20D highs": int(frame["20D high"].sum()), "New 20D lows": int(frame["20D low"].sum())}
    return frame, metrics


def trade_plan(entry: float, stop: float, target: float, equity: float, risk_pct: float) -> dict:
    risk_share = abs(entry - stop); risk_budget = equity * risk_pct / 100
    shares = math.floor(risk_budget / risk_share) if risk_share > 0 else 0
    reward = abs(target - entry); return {"Risk budget": risk_budget, "Risk/share": risk_share, "Shares": shares, "Position value": shares * entry, "Reward/risk": reward / risk_share if risk_share > 0 else 0, "Potential reward": shares * reward}


def technical_alerts(frame: pd.DataFrame) -> list[str]:
    latest, previous = frame.iloc[-1], frame.iloc[-2]; signals = []
    if previous.Close <= previous.get("SMA 50", previous.Close) and latest.Close > latest.get("SMA 50", latest.Close): signals.append("Price crossed above SMA 50")
    if previous.Close >= previous.get("SMA 50", previous.Close) and latest.Close < latest.get("SMA 50", latest.Close): signals.append("Price crossed below SMA 50")
    if latest.get("RSI 14", 50) >= 70: signals.append("RSI entered overbought territory")
    if latest.get("RSI 14", 50) <= 30: signals.append("RSI entered oversold territory")
    if latest.Volume > frame.Volume.tail(20).mean() * 1.8: signals.append("Unusual volume above 1.8x the 20-day average")
    if previous.get("MACD", 0) <= previous.get("MACD signal", 0) and latest.get("MACD", 0) > latest.get("MACD signal", 0): signals.append("Bullish MACD crossover")
    return signals

