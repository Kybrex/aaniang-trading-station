from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import math
import time
import pandas as pd
from data import download_batch, last_number, symbol_frame
from indicators import add_indicators

@dataclass(frozen=True)
class ScanSettings:
    direction: str; min_score: int; max_results: int; min_price: float; min_volume: int; equity: float; risk_pct: float; batch_size: int; pause_seconds: float = .5

def candidate(symbol: str, frame: pd.DataFrame, s: ScanSettings) -> dict | None:
    if len(frame) < 205:
        return None
    indicators = add_indicators(frame)
    d = indicators.iloc[-1]
    close, ema20, ema50, sma200, atr = (last_number(d[x]) for x in ["Close", "EMA20", "EMA50", "SMA200", "ATR14"])
    avg_vol, mom20, mom60 = (last_number(d[x]) for x in ["VolAvg20", "Mom20", "Mom60"])
    if any(x is None or x <= 0 for x in [close, ema20, ema50, sma200, atr, avg_vol]) or mom20 is None or mom60 is None:
        return None
    if close < s.min_price or avg_vol < s.min_volume:
        return None
    current_open = last_number(d["Open"]); current_high = last_number(d["High"]); current_low = last_number(d["Low"]); current_volume = last_number(d["Volume"])
    ema20_past = last_number(indicators["EMA20"].iloc[-11])
    if any(x is None for x in [current_open, current_high, current_low, current_volume, ema20_past]):
        return None
    previous = frame.iloc[:-1].tail(20)
    support = last_number(previous["Low"].min())
    resistance = last_number(previous["High"].max())
    if support is None or resistance is None:
        return None

    long_trend = close > sma200 and ema20 > ema50 and ema20 > ema20_past
    short_trend = close < sma200 and ema20 < ema50 and ema20 < ema20_past
    volume_ratio = current_volume / avg_vol
    long_breakout = long_trend and close > resistance and close <= resistance + .75 * atr and volume_ratio >= .8
    short_breakout = short_trend and close < support and close >= support - .75 * atr and volume_ratio >= .8
    long_pullback = long_trend and current_low <= ema20 and close > ema20 and close > current_open
    short_pullback = short_trend and current_high >= ema20 and close < ema20 and close < current_open
    long_valid = long_breakout or long_pullback
    short_valid = short_breakout or short_pullback
    if not long_valid and not short_valid:
        return None
    side = "LONG" if long_valid and not short_valid else "SHORT" if short_valid and not long_valid else ("LONG" if mom20 >= 0 else "SHORT")

    aligned_mom20 = mom20 if side == "LONG" else -mom20
    aligned_mom60 = mom60 if side == "LONG" else -mom60
    trend_points = 55
    momentum_points = min(15, max(0, aligned_mom20) * .75) + min(10, max(0, aligned_mom60) * .25)
    volume_points = min(10, max(0, (volume_ratio - .5) * 10))
    setup_points = 15
    extension_penalty = min(12, max(0, aligned_mom20 - 20) * .5)
    score = min(100, int(round(trend_points + momentum_points + volume_points + setup_points - extension_penalty)))
    if s.direction != "Both" and side != s.direction.upper():
        return None
    if score < s.min_score:
        return None
    entry = close
    stop = entry - 1.5 * atr if side == "LONG" else entry + 1.5 * atr
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    target1 = entry + 2 * risk if side == "LONG" else entry - 2 * risk
    target2 = entry + 3 * risk if side == "LONG" else entry - 3 * risk
    shares = max(0, math.floor((s.equity * (s.risk_pct / 100)) / risk))
    setup_type = "Breakout" if (long_breakout if side == "LONG" else short_breakout) else "EMA pullback"
    plan = f"{side} {setup_type}: enter near ${entry:.2f}; stop ${stop:.2f}; targets ${target1:.2f}/${target2:.2f}."
    data_date = pd.Timestamp(frame.index[-1]).date().isoformat()
    return {"Symbol": symbol, "Data date": data_date, "Score": score, "Signal": side, "Entry": entry, "Stop": stop, "Risk/Share": risk,
            "20D Momentum": mom20, "60D Momentum": mom60, "Shares": shares, "Target 1": target1, "Target 2": target2,
            "Support": support, "Resistance": resistance, "Setup": setup_type, "Trade plan": plan}

def scan_market(symbols: list[str], s: ScanSettings, progress: Callable[[int, int, str], None]) -> tuple[pd.DataFrame, int]:
    rows: list[dict] = []; skipped = 0; total = len(symbols); consecutive_empty_batches = 0
    for start in range(0, total, s.batch_size):
        batch = symbols[start:start + s.batch_size]
        raw = download_batch(batch)
        consecutive_empty_batches = consecutive_empty_batches + 1 if raw.empty else 0
        for symbol in batch:
            frame = symbol_frame(raw, symbol)
            row = candidate(symbol, frame, s) if not frame.empty else None
            if row: rows.append(row)
            elif frame.empty: skipped += 1
        done = min(start + len(batch), total)
        progress(done, total, f"Processed {done:,} of {total:,} symbols ({len(rows)} setups)")
        if consecutive_empty_batches >= 2:
            skipped += total - done
            progress(total, total, "Yahoo Finance is unavailable or rate-limited; scan stopped safely.")
            break
        if done < total and s.pause_seconds > 0:
            time.sleep(s.pause_seconds if not raw.empty else max(2.0, s.pause_seconds))
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["Score", "20D Momentum"], ascending=[False, False], key=lambda col: col.abs() if col.name == "20D Momentum" else col).head(s.max_results).reset_index(drop=True)
    return result, skipped
