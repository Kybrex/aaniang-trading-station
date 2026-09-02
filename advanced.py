"""Multi-timeframe, setup research, and professional backtest summaries."""
from __future__ import annotations

import math
import pandas as pd

from data import best_symbol_frame, download_batch, last_number, symbol_frame
from indicators import add_indicators


def _trend(frame: pd.DataFrame, fast: int = 20, slow: int = 50) -> tuple[str, float | None]:
    if frame.empty or len(frame) < slow + 5:
        return "Unavailable", None
    close = frame["Close"]
    fast_ma = close.ewm(span=fast, adjust=False).mean()
    slow_ma = close.ewm(span=slow, adjust=False).mean()
    price = last_number(close.iloc[-1])
    if price is None:
        return "Unavailable", None
    direction = "Bullish" if price > fast_ma.iloc[-1] > slow_ma.iloc[-1] else "Bearish" if price < fast_ma.iloc[-1] < slow_ma.iloc[-1] else "Mixed"
    return direction, price


def multi_timeframe(symbol: str, api_key: str | None = None) -> tuple[pd.DataFrame, str]:
    daily, source = best_symbol_frame(symbol, period="2y", minimum_rows=200, api_key=api_key)
    weekly_raw = download_batch([symbol], period="5y", interval="1wk", timeout=25)
    hourly_raw = download_batch([symbol], period="6mo", interval="1h", timeout=25)
    weekly = symbol_frame(weekly_raw, symbol)
    hourly = symbol_frame(hourly_raw, symbol)
    four_hour = pd.DataFrame()
    if not hourly.empty:
        four_hour = hourly.resample("4h").agg({"Open":"first","High":"max","Low":"min","Close":"last","Volume":"sum"}).dropna()
    rows=[]
    for timeframe, frame, fast, slow in [("Weekly",weekly,10,30),("Daily",daily,20,50),("4-hour",four_hour,20,50)]:
        trend, price = _trend(frame,fast,slow)
        rows.append({"Timeframe":timeframe,"Trend":trend,"Last":price,"Bars":len(frame)})
    available=[row["Trend"] for row in rows if row["Trend"]!="Unavailable"]
    alignment = available[0] if available and len(set(available)) == 1 else "Mixed"
    return pd.DataFrame(rows), f"{alignment} alignment | daily source: {source}"


def detect_setups(frame: pd.DataFrame, spy_frame: pd.DataFrame | None = None) -> pd.DataFrame:
    if frame.empty or len(frame) < 205:
        return pd.DataFrame(columns=["Setup","Direction","Status","Evidence"])
    df=add_indicators(frame); row=df.iloc[-1]; previous=df.iloc[-21:-1]
    close=float(row.Close); atr=float(row.ATR14); ema20=float(row.EMA20); ema50=float(row.EMA50); sma200=float(row.SMA200)
    resistance=float(previous.High.max()); support=float(previous.Low.min()); volume_ratio=float(row.Volume / row.VolAvg20)
    range_recent=float((previous.tail(10).High.max()-previous.tail(10).Low.min())/close)
    range_prior=float((previous.head(10).High.max()-previous.head(10).Low.min())/close)
    gap=float((row.Open/df.iloc[-2].Close-1)*100)
    long_trend=close>sma200 and ema20>ema50; short_trend=close<sma200 and ema20<ema50
    setups=[]
    def add(name,direction,status,evidence): setups.append({"Setup":name,"Direction":direction,"Status":"READY" if status else "No","Evidence":evidence})
    add("Base breakout","LONG",long_trend and close>resistance and volume_ratio>=1.0,f"close {close:.2f} vs 20D high {resistance:.2f}; volume {volume_ratio:.1f}x")
    add("Breakdown","SHORT",short_trend and close<support and volume_ratio>=1.0,f"close {close:.2f} vs 20D low {support:.2f}; volume {volume_ratio:.1f}x")
    add("EMA20 pullback","LONG" if long_trend else "SHORT",(long_trend and row.Low<=ema20<close) or (short_trend and row.High>=ema20>close),f"EMA20 {ema20:.2f}; ATR {atr:.2f}")
    add("Volatility contraction","LONG",long_trend and range_prior>0 and range_recent/range_prior<.7 and close>=resistance*.97,f"10D range contraction {(range_recent/range_prior if range_prior else math.nan):.2f}x")
    spy_note="SPY comparison unavailable"
    rs_ready=False
    if spy_frame is not None and len(spy_frame)>=21:
        stock_return=close/frame.Close.iloc[-21]-1; spy_return=spy_frame.Close.iloc[-1]/spy_frame.Close.iloc[-21]-1
        rs=(stock_return-spy_return)*100; rs_ready=long_trend and rs>=5 and close>=resistance*.98; spy_note=f"20D RS vs SPY {rs:.1f}%"
    add("Relative-strength breakout","LONG",rs_ready,spy_note)
    add("Post-event gap","LONG" if gap>0 else "SHORT",abs(gap)>=3 and volume_ratio>=1.5,f"gap {gap:.1f}%; volume {volume_ratio:.1f}x")
    reversal_long=close<sma200 and float(row.RSI14)<35 and close>row.Open
    reversal_short=close>sma200 and float(row.RSI14)>65 and close<row.Open
    add("Reversal","LONG" if reversal_long else "SHORT",reversal_long or reversal_short,f"RSI14 {float(row.RSI14):.1f}")
    return pd.DataFrame(setups)


def backtest_metrics(trades: pd.DataFrame, risk_fraction: float = .01) -> tuple[dict[str, float], pd.DataFrame]:
    if trades.empty or "R multiple" not in trades:
        return {}, pd.DataFrame()
    r=pd.to_numeric(trades["R multiple"],errors="coerce").dropna()-0.05
    wins=r[r>0].sum(); losses=abs(r[r<0].sum())
    equity=(1+r*risk_fraction).cumprod()*10_000
    drawdown=(equity/equity.cummax()-1)*100
    metrics={"Trades":float(len(r)),"Win rate":float((r>0).mean()*100),"Expectancy R":float(r.mean()),"Profit factor":float(wins/losses) if losses else math.inf,"Total R":float(r.sum()),"Max drawdown %":float(drawdown.min())}
    curve=pd.DataFrame({"Date":trades.loc[r.index,"Date"].values,"Equity":equity.values,"Drawdown %":drawdown.values,"Sample":["In sample" if i<int(len(r)*.7) else "Out of sample" for i in range(len(r))]})
    return metrics,curve


def bracket_plan(symbol: str, side: str, entry: float, stop: float, target1: float, target2: float, shares: int) -> pd.DataFrame:
    first=max(1,shares//2); second=max(0,shares-first); exit_side="SELL" if side.upper()=="LONG" else "BUY"
    return pd.DataFrame([
        {"Order":"ENTRY","Action":"BUY" if side.upper()=="LONG" else "SELL","Quantity":shares,"Type":"STOP LIMIT","Price":entry,"OCO group":"Entry"},
        {"Order":"STOP","Action":exit_side,"Quantity":shares,"Type":"STOP","Price":stop,"OCO group":"Bracket"},
        {"Order":"TARGET 1","Action":exit_side,"Quantity":first,"Type":"LIMIT","Price":target1,"OCO group":"Bracket"},
        {"Order":"TARGET 2","Action":exit_side,"Quantity":second,"Type":"LIMIT","Price":target2,"OCO group":"Bracket"},
    ])
