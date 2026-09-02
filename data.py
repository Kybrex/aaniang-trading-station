"""Yahoo Finance download helpers that normalize yfinance's inconsistent shapes."""
from __future__ import annotations

import pandas as pd
import yfinance as yf

_FRAME_CACHE: dict[str, pd.DataFrame] = {}


def remember_frame(symbol: str, frame: pd.DataFrame) -> None:
    """Keep the best in-process history so Streamlit reruns do not re-query Yahoo."""
    if frame is None or frame.empty:
        return
    key = str(symbol).upper()
    saved = _FRAME_CACHE.get(key)
    if saved is None or len(frame) >= len(saved):
        _FRAME_CACHE[key] = frame.copy()


def cached_frame(symbol: str, minimum_rows: int = 1) -> pd.DataFrame:
    """Return a defensive copy of cached OHLCV history when it is sufficient."""
    frame = _FRAME_CACHE.get(str(symbol).upper())
    return frame.copy() if frame is not None and len(frame) >= minimum_rows else pd.DataFrame()


def clear_frame_cache() -> None:
    """Test/support helper; normal users never need to clear the session cache."""
    _FRAME_CACHE.clear()

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
