"""Interactive company technical-analysis chart and indicator calculations."""
from __future__ import annotations

import math
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


MA_COLORS = {
    "EMA 21": "#d89b2b",
    "SMA 20": "#27a69a",
    "SMA 50": "#245a8d",
    "SMA 200": "#8b5cf6",
}


def technical_data(history: pd.DataFrame) -> pd.DataFrame:
    frame = history.copy().sort_index()
    close = pd.to_numeric(frame["Close"], errors="coerce")
    frame["EMA 21"] = close.ewm(span=21, adjust=False).mean()
    frame["SMA 20"] = close.rolling(20).mean()
    frame["SMA 50"] = close.rolling(50).mean()
    frame["SMA 200"] = close.rolling(200).mean()
    change = close.diff(); gains = change.clip(lower=0); losses = -change.clip(upper=0)
    rs = gains.ewm(alpha=1 / 14, adjust=False).mean() / losses.ewm(alpha=1 / 14, adjust=False).mean().replace(0, pd.NA)
    frame["RSI 14"] = 100 - (100 / (1 + rs))
    ema12 = close.ewm(span=12, adjust=False).mean(); ema26 = close.ewm(span=26, adjust=False).mean()
    frame["MACD"] = ema12 - ema26; frame["MACD signal"] = frame["MACD"].ewm(span=9, adjust=False).mean()
    frame["MACD histogram"] = frame["MACD"] - frame["MACD signal"]
    previous = close.shift(1)
    true_range = pd.concat([(frame["High"] - frame["Low"]).abs(), (frame["High"] - previous).abs(), (frame["Low"] - previous).abs()], axis=1).max(axis=1)
    frame["ATR 14"] = true_range.rolling(14).mean()
    return frame


def technical_snapshot(frame: pd.DataFrame) -> dict:
    latest = frame.dropna(subset=["Close"]).iloc[-1]
    price = float(latest["Close"]); rsi = float(latest.get("RSI 14", math.nan)); atr = float(latest.get("ATR 14", math.nan))
    sma50 = float(latest.get("SMA 50", math.nan)); sma200 = float(latest.get("SMA 200", math.nan))
    macd = float(latest.get("MACD", math.nan)); signal = float(latest.get("MACD signal", math.nan))
    trend = "Bullish" if price > sma50 and price > sma200 else "Bearish" if price < sma50 and price < sma200 else "Mixed"
    momentum = "Overbought" if rsi >= 70 else "Oversold" if rsi <= 30 else "Neutral"
    return {"Price": price, "Trend": trend, "RSI": rsi, "Momentum": momentum, "ATR": atr, "MACD": "Bullish" if macd > signal else "Bearish"}


def build_company_technical_chart(frame: pd.DataFrame, symbol: str, overlays: list[str], oscillator: str) -> go.Figure:
    rows = 3 if oscillator != "None" else 2
    heights = [0.62, 0.16, 0.22] if rows == 3 else [0.78, 0.22]
    figure = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.035, row_heights=heights)
    figure.add_trace(go.Candlestick(
        x=frame.index, open=frame["Open"], high=frame["High"], low=frame["Low"], close=frame["Close"],
        name=symbol, increasing_line_color="#17845c", decreasing_line_color="#c44343",
        increasing_fillcolor="#17845c", decreasing_fillcolor="#c44343",
    ), row=1, col=1)
    for overlay in overlays:
        if overlay in frame:
            figure.add_trace(go.Scatter(x=frame.index, y=frame[overlay], name=overlay, mode="lines", line={"width": 1.5, "color": MA_COLORS[overlay]}), row=1, col=1)
    volume_colors = ["#17845c" if close >= open_ else "#c44343" for close, open_ in zip(frame["Close"], frame["Open"])]
    figure.add_trace(go.Bar(x=frame.index, y=frame["Volume"], name="Volume", marker_color=volume_colors, opacity=.65), row=2, col=1)
    if oscillator == "RSI 14":
        figure.add_trace(go.Scatter(x=frame.index, y=frame["RSI 14"], name="RSI 14", line={"color": "#245a8d", "width": 1.6}), row=3, col=1)
        figure.add_hline(y=70, line_dash="dot", line_color="#c44343", row=3, col=1); figure.add_hline(y=30, line_dash="dot", line_color="#17845c", row=3, col=1)
        figure.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
    elif oscillator == "MACD":
        colors = ["#17845c" if value >= 0 else "#c44343" for value in frame["MACD histogram"].fillna(0)]
        figure.add_trace(go.Bar(x=frame.index, y=frame["MACD histogram"], name="Histogram", marker_color=colors, opacity=.6), row=3, col=1)
        figure.add_trace(go.Scatter(x=frame.index, y=frame["MACD"], name="MACD", line={"color": "#245a8d", "width": 1.5}), row=3, col=1)
        figure.add_trace(go.Scatter(x=frame.index, y=frame["MACD signal"], name="Signal", line={"color": "#d89b2b", "width": 1.3}), row=3, col=1)
        figure.update_yaxes(title_text="MACD", row=3, col=1)
    figure.update_layout(
        height=720 if rows == 3 else 610,
        margin={"l": 8, "r": 8, "t": 38, "b": 8},
        paper_bgcolor="#ffffff", plot_bgcolor="#f7f9fb",
        font={"color": "#17202a", "size": 11},
        hovermode="x unified", dragmode="pan",
        legend={"orientation": "h", "y": 1.02, "x": 0},
        xaxis_rangeslider_visible=False,
        transition={"duration": 350, "easing": "cubic-in-out"},
    )
    figure.update_xaxes(showgrid=True, gridcolor="#e2e7ec", rangeslider_visible=False)
    figure.update_yaxes(showgrid=True, gridcolor="#e2e7ec", zerolinecolor="#cbd4dc")
    figure.update_yaxes(title_text="Price", row=1, col=1); figure.update_yaxes(title_text="Volume", row=2, col=1)
    return figure

