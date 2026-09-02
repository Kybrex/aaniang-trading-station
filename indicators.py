from __future__ import annotations
import pandas as pd

def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["EMA20"] = out["Close"].ewm(span=20, adjust=False).mean()
    out["EMA50"] = out["Close"].ewm(span=50, adjust=False).mean()
    out["SMA200"] = out["Close"].rolling(200).mean()
    out["ATR14"] = pd.concat([out["High"] - out["Low"], (out["High"] - out["Close"].shift()).abs(), (out["Low"] - out["Close"].shift()).abs()], axis=1).max(axis=1).rolling(14).mean()
    out["VolAvg20"] = out["Volume"].rolling(20).mean()
    out["Mom20"] = (out["Close"] / out["Close"].shift(20) - 1) * 100
    out["Mom60"] = (out["Close"] / out["Close"].shift(60) - 1) * 100
    delta = out["Close"].diff()
    gains = delta.clip(lower=0).rolling(14).mean()
    losses = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gains / losses.replace(0, float("nan"))
    out["RSI14"] = (100 - 100 / (1 + rs)).fillna(50)
    return out
