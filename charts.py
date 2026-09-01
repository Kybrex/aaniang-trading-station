from __future__ import annotations
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from data import download_batch, symbol_frame
from indicators import add_indicators

def build_chart(symbol: str, setup: object) -> tuple[go.Figure | None, str]:
    frame = symbol_frame(download_batch([symbol], period="1y", timeout=25), symbol)
    if frame.empty: return None, "Yahoo Finance did not return chart data for this symbol."
    df = add_indicators(frame).tail(180)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[.76, .24], vertical_spacing=.03)
    fig.add_trace(go.Candlestick(x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name=symbol), row=1, col=1)
    for name, color in [("EMA20", "#1f77b4"), ("EMA50", "#ff7f0e"), ("SMA200", "#9467bd")]:
        fig.add_trace(go.Scatter(x=df.index, y=df[name], name=name, line=dict(color=color, width=1.5)), row=1, col=1)
    for key, color in [("Entry", "#00cc96"), ("Stop", "#ef553b"), ("Target 1", "#00cc96"), ("Target 2", "#00cc96")]:
        fig.add_hline(y=float(setup[key]), line_dash="dash", line_color=color, annotation_text=f"{key} ${float(setup[key]):.2f}", row=1, col=1)
    for key, color in [("Support", "#636efa"), ("Resistance", "#ab63fa")]:
        if key in setup:
            fig.add_hline(y=float(setup[key]), line_dash="dot", line_color=color, annotation_text=key, row=1, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df.Volume, name="Volume", marker_color="#9aa5b5"), row=2, col=1)
    fig.update_layout(height=760, xaxis_rangeslider_visible=False, template="plotly_white", legend_orientation="h", margin=dict(l=20,r=20,t=35,b=20))
    return fig, ""
