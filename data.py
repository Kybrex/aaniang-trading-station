"""Yahoo Finance download helpers that normalize yfinance's inconsistent shapes."""
from __future__ import annotations

import os
import pandas as pd
import requests
import yfinance as yf

_FRAME_CACHE: dict[str, pd.DataFrame] = {}
_SOURCE_CACHE: dict[str, str] = {}


def remember_frame(symbol: str, frame: pd.DataFrame, source: str = "Yahoo Finance") -> None:
    """Keep the best in-process history so Streamlit reruns do not re-query Yahoo."""
    if frame is None or frame.empty:
        return
    key = str(symbol).upper()
    saved = _FRAME_CACHE.get(key)
    if saved is None or len(frame) >= len(saved):
        _FRAME_CACHE[key] = frame.copy()
        _SOURCE_CACHE[key] = source


def cached_frame(symbol: str, minimum_rows: int = 1) -> pd.DataFrame:
    """Return a defensive copy of cached OHLCV history when it is sufficient."""
    frame = _FRAME_CACHE.get(str(symbol).upper())
    return frame.copy() if frame is not None and len(frame) >= minimum_rows else pd.DataFrame()


def clear_frame_cache() -> None:
    """Test/support helper; normal users never need to clear the session cache."""
    _FRAME_CACHE.clear()
    _SOURCE_CACHE.clear()


def frame_source(symbol: str) -> str:
    return _SOURCE_CACHE.get(str(symbol).upper(), "Unavailable")

def _download(symbols: list[str], period: str, interval: str, timeout: int) -> pd.DataFrame:
    return yf.download(symbols, period=period, interval=interval, group_by="ticker", auto_adjust=True,
                       threads=True, progress=False, timeout=timeout, actions=False)

def download_batch(symbols: list[str], period: str = "1y", interval: str = "1d", timeout: int = 35) -> pd.DataFrame:
    """Download one bounded Yahoo request; a failed batch returns empty and is skipped."""
    try:
        # yfinance passes this timeout to its HTTP layer.  Avoid a worker thread here:
        # shutting down a timed-out executor can itself wait indefinitely.
        raw = _download(symbols, period, interval, timeout)
        if interval == "1d" and raw is not None and not raw.empty:
            for symbol in symbols:
                remember_frame(symbol, symbol_frame(raw, symbol))
        return raw
    except Exception:
        return pd.DataFrame()


def alpha_vantage_daily(symbol: str, api_key: str | None = None, timeout: int = 25) -> pd.DataFrame:
    """Optional daily fallback. Alpha Vantage keys belong in secrets, never source code."""
    key = api_key or os.getenv("ALPHAVANTAGE_API_KEY", "")
    if not key:
        return pd.DataFrame()
    try:
        response = requests.get(
            "https://www.alphavantage.co/query",
            params={"function": "TIME_SERIES_DAILY", "symbol": symbol, "outputsize": "full", "apikey": key},
            timeout=timeout,
        )
        response.raise_for_status()
        series = response.json().get("Time Series (Daily)", {})
        if not series:
            return pd.DataFrame()
        frame = pd.DataFrame.from_dict(series, orient="index").rename(columns={
            "1. open": "Open", "2. high": "High", "3. low": "Low", "4. close": "Close", "5. volume": "Volume"
        })
        frame.index = pd.to_datetime(frame.index)
        frame = frame[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce").dropna().sort_index()
        remember_frame(symbol, frame, "Alpha Vantage")
        return frame
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return pd.DataFrame()


def best_symbol_frame(symbol: str, period: str = "1y", minimum_rows: int = 1, api_key: str | None = None) -> tuple[pd.DataFrame, str]:
    """Cached history, then Yahoo, then optional Alpha Vantage daily fallback."""
    saved = cached_frame(symbol, minimum_rows)
    if not saved.empty:
        return saved, frame_source(symbol)
    frame = symbol_frame(download_batch([symbol], period=period), symbol)
    if frame.empty:
        frame = alpha_vantage_daily(symbol, api_key=api_key)
    return frame, frame_source(symbol) if not frame.empty else "Unavailable"

def symbol_frame(raw: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Return one OHLCV frame regardless of MultiIndex, one-ticker, or empty response."""
    if raw is None or raw.empty:
        return pd.DataFrame()
    try:
        if isinstance(raw.columns, pd.MultiIndex):
            if symbol in raw.columns.get_level_values(0):
                frame = raw[symbol].copy()
            elif symbol in raw.columns.get_level_values(-1):
                frame = raw.xs(symbol, axis=1, level=-1).copy()
            else:
                return pd.DataFrame()
        else:
            frame = raw.copy()
        frame.columns = [str(c).title() for c in frame.columns]
        required = ["Open", "High", "Low", "Close", "Volume"]
        if not set(required).issubset(frame.columns):
            return pd.DataFrame()
        frame = frame[required].apply(pd.to_numeric, errors="coerce").dropna(subset=required)
        return frame[~frame.index.duplicated(keep="last")]
    except (KeyError, TypeError, ValueError):
        return pd.DataFrame()

def last_number(value: object) -> float | None:
    """Safely extract a scalar; prevents float(Series) errors from Yahoo responses."""
    if isinstance(value, pd.Series):
        value = value.dropna().iloc[-1] if not value.dropna().empty else None
    try:
        number = float(value) if value is not None else None
        return number if number is not None and pd.notna(number) else None
    except (TypeError, ValueError):
        return None
