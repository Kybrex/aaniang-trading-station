from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
import math
import pandas as pd
from data import download_batch, last_number, symbol_frame
from indicators import add_indicators

@dataclass(frozen=True)
class ScanSettings:
    direction: str; min_score: int; max_results: int; min_price: float; min_volume: int; equity: float; risk_pct: float; batch_size: int

def candidate(symbol: str, frame: pd.DataFrame, s: ScanSettings) -> dict | None:
    if len(frame) < 205:
        return None
    d = add_indicators(frame).iloc[-1]
    close, ema20, ema50, sma200, atr = (last_number(d[x]) for x in ["Close", "EMA20", "EMA50", "SMA200", "ATR14"])
    avg_vol, mom20, mom60 = (last_number(d[x]) for x in ["VolAvg20", "Mom20", "Mom60"])
    if any(x is None or x <= 0 for x in [close, ema20, ema50, sma200, atr, avg_vol]) or mom20 is None or mom60 is None:
        return None
    if close < s.min_price or avg_vol < s.min_volume:
        return None
    long_score = (25 if close > sma200 else 0) + (20 if ema20 > ema50 else 0) + (20 if close > ema20 else 0) + (20 if mom20 > 0 else 0) + (15 if mom60 > 0 else 0)
    short_score = (25 if close < sma200 else 0) + (20 if ema20 < ema50 else 0) + (20 if close < ema20 else 0) + (20 if mom20 < 0 else 0) + (15 if mom60 < 0 else 0)
    side, score = ("LONG", long_score) if long_score >= short_score else ("SHORT", short_score)
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
    support = last_number(frame["Low"].tail(20).min())
    resistance = last_number(frame["High"].tail(20).max())
    setup_type = "Breakout" if (side == "LONG" and entry >= resistance * .985) or (side == "SHORT" and entry <= support * 1.015) else "EMA pullback"
    plan = f"{side} {setup_type}: enter near ${entry:.2f}; stop ${stop:.2f}; targets ${target1:.2f}/${target2:.2f}."
    return {"Symbol": symbol, "Score": score, "Signal": side, "Entry": entry, "Stop": stop, "Risk/Share": risk,
            "20D Momentum": mom20, "60D Momentum": mom60, "Shares": shares, "Target 1": target1, "Target 2": target2,
            "Support": support, "Resistance": resistance, "Setup": setup_type, "Trade plan": plan}

def scan_market(symbols: list[str], s: ScanSettings, progress: Callable[[int, int, str], None]) -> tuple[pd.DataFrame, int]:
    rows: list[dict] = []; skipped = 0; total = len(symbols)
    for start in range(0, total, s.batch_size):
        batch = symbols[start:start + s.batch_size]
        raw = download_batch(batch)
        for symbol in batch:
            frame = symbol_frame(raw, symbol)
            row = candidate(symbol, frame, s) if not frame.empty else None
            if row: rows.append(row)
            elif frame.empty: skipped += 1
        done = min(start + len(batch), total)
        progress(done, total, f"Processed {done:,} of {total:,} symbols ({len(rows)} setups)")
    result = pd.DataFrame(rows)
    if not result.empty:
        result = result.sort_values(["Score", "20D Momentum"], ascending=[False, False], key=lambda col: col.abs() if col.name == "20D Momentum" else col).head(s.max_results).reset_index(drop=True)
    return result, skipped
