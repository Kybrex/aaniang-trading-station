"""Streamlit UI for AANIANG V6 advanced technical intelligence."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from technical_chart import build_company_technical_chart
from v6_features import (
    advanced_indicators, detect_patterns, load_history, market_breadth,
    relative_strength, support_resistance, technical_alerts, technical_score,
    trade_plan,
)


MODULES = [
    ("1 · Support & Resistance", ":material/horizontal_rule:"),
    ("2 · Pattern Detection", ":material/pattern:"),
    ("3 · Advanced Indicators", ":material/stacked_line_chart:"),
    ("4 · Technical Score", ":material/speed:"),
    ("5 · Relative Strength", ":material/leaderboard:"),
    ("6 · Market Breadth", ":material/monitoring:"),
    ("7 · Trade Planner", ":material/calculate:"),
    ("8 · Chart Replay", ":material/replay:"),
    ("9 · Technical Alerts", ":material/notifications_active:"),
]


@st.cache_data(ttl=900, max_entries=30, show_spinner=False)
def _history(symbol: str) -> pd.DataFrame:
    return load_history(symbol, "2y")


def _symbol(universe: pd.DataFrame, label: str, key: str) -> str:
    symbols = universe.Symbol.tolist() if not universe.empty and "Symbol" in universe else []
    return st.selectbox(label, symbols, key=key) if symbols else st.text_input(label, "AAPL", key=key).strip().upper()


def _load(symbol: str) -> pd.DataFrame:
    history = _history(symbol)
    if history.empty: st.warning("No price history was returned for this ticker.")
    return advanced_indicators(history) if not history.empty else history


def render() -> None:
    st.divider(); st.header("AANIANG V6 Advanced Technical Intelligence")
    st.caption("Nine chart, market-breadth, signal, replay, and trade-planning modules with transparent calculations.")
    universe = st.session_state.get("v3_universe_data", pd.DataFrame())
    st.markdown("**Quick access — all nine modules**")
    for start in range(0, 9, 3):
        cols = st.columns(3)
        for col, (label, icon) in zip(cols, MODULES[start:start + 3]):
            with col:
                if st.button(label, icon=icon, width="stretch", key=f"v6_quick_{label[0]}"): st.session_state.v6_section = label
    section = st.selectbox("V6 module", [label for label, _ in MODULES], key="v6_section")

    if section.startswith("1"):
        st.subheader("Automatic Support & Resistance")
        symbol = _symbol(universe, "Symbol", "v6_sr_symbol")
        if st.button("Find price levels", type="primary"):
            with st.spinner("Finding repeated pivot zones..."): st.session_state.v6_sr = (_load(symbol), symbol)
        if st.session_state.get("v6_sr"):
            frame, loaded_symbol = st.session_state.v6_sr; levels = support_resistance(frame)
            chart = go.Figure(go.Candlestick(x=frame.tail(252).index, open=frame.tail(252).Open, high=frame.tail(252).High, low=frame.tail(252).Low, close=frame.tail(252).Close, name=loaded_symbol))
            for row in levels.itertuples(index=False): chart.add_hline(y=row.Level, line_dash="dash", line_color="#17845c" if row.Type == "Support" else "#c44343", annotation_text=f"{row.Type} {row.Level:.2f} ({row.Touches})")
            chart.update_layout(height=580, xaxis_rangeslider_visible=False, hovermode="x unified", margin=dict(l=5, r=5, t=30, b=5))
            st.plotly_chart(chart, width="stretch", config={"displaylogo": False, "scrollZoom": True}); st.dataframe(levels, hide_index=True, width="stretch")

    elif section.startswith("2"):
        st.subheader("Chart Pattern Detection")
        symbol = _symbol(universe, "Symbol", "v6_pattern_symbol")
        if st.button("Detect patterns", type="primary"):
            with st.spinner("Analyzing recent pivots and volatility..."): st.session_state.v6_patterns = (detect_patterns(_load(symbol)), symbol)
        if st.session_state.get("v6_patterns"):
            patterns, loaded_symbol = st.session_state.v6_patterns
            st.caption(f"Heuristic candidates for {loaded_symbol}; confirm each pattern visually before using it.")
            for pattern in patterns:
                with st.container(border=True): st.markdown(f"**{pattern['Pattern']}**"); st.write(f"Bias: {pattern['Bias']} · Confidence: {pattern['Confidence']}%")

    elif section.startswith("3"):
        st.subheader("Advanced Indicators")
        symbol = _symbol(universe, "Symbol", "v6_indicator_symbol")
        choices = st.multiselect("Indicators", ["BB upper", "BB middle", "BB lower", "VWAP", "Ichimoku conversion", "Ichimoku base", "Ichimoku span A", "Ichimoku span B", "Supertrend"], default=["BB upper", "BB middle", "BB lower", "VWAP", "Supertrend"])
        if st.button("Build indicator chart", type="primary"):
            with st.spinner("Calculating indicators..."): st.session_state.v6_indicators = (_load(symbol), symbol, choices)
        if st.session_state.get("v6_indicators"):
            frame, loaded_symbol, selected = st.session_state.v6_indicators; visible = frame.tail(252)
            chart = go.Figure(go.Candlestick(x=visible.index, open=visible.Open, high=visible.High, low=visible.Low, close=visible.Close, name=loaded_symbol))
            palette = ["#245a8d", "#0f7b75", "#245a8d", "#d89b2b", "#14b8a6", "#f97316", "#60a5fa", "#8b5cf6", "#c44343"]
            for indicator, color in zip(selected, palette): chart.add_trace(go.Scatter(x=visible.index, y=visible[indicator], name=indicator, line=dict(width=1.35, color=color)))
            chart.update_layout(height=620, xaxis_rangeslider_visible=False, hovermode="x unified", transition=dict(duration=350), margin=dict(l=5, r=5, t=30, b=5))
            st.plotly_chart(chart, width="stretch", config={"displaylogo": False, "scrollZoom": True})
            latest = visible.iloc[-1]
            st.caption("Fibonacci reference levels from the visible one-year high/low")
            high, low = float(visible.High.max()), float(visible.Low.min())
            fib = pd.DataFrame({"Retracement": ["0%", "23.6%", "38.2%", "50%", "61.8%", "100%"], "Level": [high, high-(high-low)*.236, high-(high-low)*.382, (high+low)/2, high-(high-low)*.618, low]})
            st.dataframe(fib, hide_index=True, width="stretch")

    elif section.startswith("4"):
        st.subheader("Transparent Technical Signal Score")
        symbol = _symbol(universe, "Symbol", "v6_score_symbol")
        if st.button("Calculate technical score", type="primary"):
            with st.spinner("Scoring trend, momentum, and volume..."): st.session_state.v6_score = (technical_score(_load(symbol)), symbol)
        if st.session_state.get("v6_score"):
            (score, checks), loaded_symbol = st.session_state.v6_score
            st.metric(f"{loaded_symbol} technical score", f"{score}/100", border=True); st.progress(score)
            st.dataframe(pd.DataFrame(checks), hide_index=True, width="stretch", column_config={"Points": st.column_config.ProgressColumn(min_value=0, max_value=20)})

    elif section.startswith("5"):
        st.subheader("Relative Strength Leaderboard")
        if universe.empty: st.info("Load the V3 research universe first to compare multiple stocks.")
        else:
            ranked = relative_strength(universe); st.metric("Companies ranked", len(ranked), border=True)
            st.dataframe(ranked, hide_index=True, width="stretch", column_config={"RS score": st.column_config.ProgressColumn(min_value=0, max_value=100)})
            st.download_button("Download relative-strength ranking", ranked.to_csv(index=False), "relative-strength-ranking.csv", "text/csv")

    elif section.startswith("6"):
        st.subheader("Market Breadth Dashboard")
        defaults = universe.Symbol.head(50).tolist() if not universe.empty else ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "XOM", "UNH", "WMT"]
        text = st.text_area("Breadth universe (maximum 100 symbols)", ", ".join(defaults), height=90)
        if st.button("Calculate market breadth", type="primary"):
            symbols = [value.strip().upper() for value in text.replace("\n", ",").split(",") if value.strip()][:100]
            with st.spinner("Loading breadth history..."): st.session_state.v6_breadth = market_breadth(symbols)
        if st.session_state.get("v6_breadth"):
            breadth, metrics = st.session_state.v6_breadth; cols = st.columns(5)
            for col, (name, value) in zip(cols, metrics.items()): col.metric(name, f"{value:.1f}%" if "%" in name else str(value), border=True)
            st.dataframe(breadth.sort_values("1D change", ascending=False), hide_index=True, width="stretch")

    elif section.startswith("7"):
        st.subheader("Chart-Based Trade Planner")
        c1, c2, c3 = st.columns(3); entry = c1.number_input("Entry", min_value=0.01, value=100.0); stop = c2.number_input("Stop", min_value=0.0, value=95.0); target = c3.number_input("Target", min_value=0.01, value=115.0)
        c4, c5 = st.columns(2); equity = c4.number_input("Account equity", min_value=100.0, value=25000.0); risk = c5.number_input("Risk per trade (%)", min_value=.1, max_value=10.0, value=1.0)
        plan = trade_plan(entry, stop, target, equity, risk); cols = st.columns(5)
        labels = [("Risk budget", f"${plan['Risk budget']:,.0f}"), ("Risk/share", f"${plan['Risk/share']:,.2f}"), ("Shares", f"{plan['Shares']:,}"), ("Position value", f"${plan['Position value']:,.0f}"), ("Reward/risk", f"{plan['Reward/risk']:.2f}R")]
        for col, (name, value) in zip(cols, labels): col.metric(name, value, border=True)
        if plan["Reward/risk"] < 2: st.warning("Reward/risk is below 2R. Reconsider the entry, stop, or target.")

    elif section.startswith("8"):
        st.subheader("Historical Chart Replay")
        symbol = _symbol(universe, "Replay symbol", "v6_replay_symbol")
        frame = _load(symbol)
        if not frame.empty:
            maximum = len(frame) - 1; minimum = min(60, maximum)
            if st.session_state.get("v6_replay_symbol_loaded") != symbol:
                st.session_state.v6_replay_index = max(minimum, maximum - 60); st.session_state.v6_replay_symbol_loaded = symbol
            next_col, end_col = st.columns(2)
            with next_col:
                if st.button("Next candle", icon=":material/skip_next:", disabled=st.session_state.v6_replay_index >= maximum): st.session_state.v6_replay_index += 1; st.rerun()
            with end_col:
                if st.button("Jump to latest", disabled=st.session_state.v6_replay_index >= maximum): st.session_state.v6_replay_index = maximum; st.rerun()
            replay_index = st.slider("Replay position", minimum, maximum, key="v6_replay_index")
            replay = frame.iloc[:replay_index + 1]; st.caption(f"Visible through {replay.index[-1].date()} · Future candles are hidden")
            st.plotly_chart(build_company_technical_chart(replay.tail(252), symbol, ["EMA 21", "SMA 50", "SMA 200"], "RSI 14"), width="stretch", config={"displaylogo": False, "scrollZoom": True})

    else:
        st.subheader("Technical Alerts")
        st.caption("Signals are evaluated when you press Check. Background delivery still requires an external scheduler and notification service.")
        symbol = _symbol(universe, "Symbol", "v6_alert_symbol")
        if st.button("Check technical alerts", type="primary"):
            with st.spinner("Evaluating the latest completed candles..."): st.session_state.v6_alert_result = (technical_alerts(_load(symbol)), symbol)
        if st.session_state.get("v6_alert_result"):
            alerts, loaded_symbol = st.session_state.v6_alert_result
            if alerts:
                for alert in alerts: st.warning(f"{loaded_symbol}: {alert}")
            else: st.success(f"No configured technical conditions are active for {loaded_symbol}.")

