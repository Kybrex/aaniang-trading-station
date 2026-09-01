"""Swing Setup Screener - run with: streamlit run app.py"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from charts import build_chart
from research import add_relative_strength, annotate_earnings, backtest, market_regime
from scanner import ScanSettings, scan_market
from storage import add_journal, add_watch, journal, watchlist
from universe import load_universe
from value_screener import scan_value

st.set_page_config(page_title="AANIANG Tranding Station", page_icon="S", layout="wide")
logo_col, title_col = st.columns([1, 14], vertical_alignment="center")
with logo_col:
    st.image("senegal_flag.svg", width=48)
with title_col:
    st.title("AANIANG Tranding Station")
st.caption("US equities via Yahoo Finance | educational research tool, not investment advice")
with st.sidebar:
    st.header("Scan settings")
    direction = st.selectbox("Direction", ["Both", "Long", "Short"])
    min_score = st.slider("Minimum score", 0, 100, 55, 5)
    max_results = st.slider("Maximum results", 10, 100, 30, 5)
    min_price = st.number_input("Minimum price ($)", min_value=1.0, value=10.0, step=1.0)
    min_volume = st.number_input("Minimum average volume", min_value=10_000, value=500_000, step=50_000)
    equity = st.number_input("Account equity ($)", min_value=100.0, value=25_000.0, step=500.0)
    risk_pct = st.number_input("Risk per trade (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    max_position_pct = st.number_input("Maximum position value (%)", 1.0, 100.0, 20.0, 1.0)
    max_portfolio_risk = st.number_input("Maximum portfolio heat (%)", 1.0, 25.0, 5.0, .5)
    earnings_days = st.slider("Avoid earnings within (days)", 0, 21, 7)
    earnings_filter = st.checkbox("Exclude candidates with near earnings", value=True)
    st.divider()
    universe_choice = st.radio("Universe", ["Broad US listed stocks", "S&P 500 / liquid fallback"], index=0)
    batch_size = st.slider("Download batch size", 25, 200, 100, 25)

@st.cache_data(ttl=3600, show_spinner=False)
def get_universe(choice: str) -> list[str]:
    return load_universe(broad=choice.startswith("Broad"))

if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()
if "value_results" not in st.session_state:
    st.session_state.value_results = pd.DataFrame()
if st.button("Scan market", type="primary", use_container_width=True):
    symbols = get_universe(universe_choice)
    settings = ScanSettings(direction, min_score, max_results, min_price, int(min_volume), equity, risk_pct, batch_size)
    progress = st.progress(0, text="Starting Yahoo Finance scan...")
    status = st.empty()
    def update(done: int, total: int, message: str) -> None:
        progress.progress(min(done / max(total, 1), 1.0), text=message); status.caption(message)
    with st.spinner(f"Scanning {len(symbols):,} symbols in batches..."):
        results, skipped = scan_market(symbols, settings, update)
    if not results.empty:
        results = annotate_earnings(add_relative_strength(results), earnings_days)
        if earnings_filter: results = results[results["Earnings safe"]].reset_index(drop=True)
    progress.empty(); st.session_state.results = results
    status.success(f"Finished. {len(results)} candidates found; {skipped} symbols skipped/unavailable.")

results = st.session_state.results
if results.empty:
    st.info("Set filters and click Scan market. The first broad scan can take several minutes.")
else:
    cols = st.columns(3)
    for column, (name, status) in zip(cols, market_regime().items()): column.metric(name, status)
    st.subheader(f"Ranked opportunities ({len(results)})")
    display = results[["Symbol", "Score", "Signal", "Setup", "Entry", "Stop", "Risk/Share", "20D Momentum", "60D Momentum", "RS vs SPY", "Earnings", "Shares", "Trade plan"]]
    st.dataframe(display, use_container_width=True, hide_index=True, column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"), "Entry": st.column_config.NumberColumn(format="$%.2f"), "Stop": st.column_config.NumberColumn(format="$%.2f"), "Risk/Share": st.column_config.NumberColumn(format="$%.2f"), "20D Momentum": st.column_config.NumberColumn(format="%.1f%%"), "60D Momentum": st.column_config.NumberColumn(format="%.1f%%"), "RS vs SPY": st.column_config.NumberColumn(format="%.1f%%")})
    symbol = st.selectbox("Open candidate chart", results["Symbol"].tolist())
    selected = results.loc[results.Symbol == symbol].iloc[0]
    capped_shares = min(int(selected.Shares), int((equity * max_position_pct / 100) / selected.Entry))
    st.markdown(f"**{selected.Signal} {selected.Setup}** | {selected['Trade plan']}")
    a, b, c = st.columns(3)
    a.metric("Risk budget", f"${equity * risk_pct / 100:,.0f}"); b.metric("Capped position", f"{capped_shares:,} shares"); c.metric("Portfolio heat limit", f"${equity * max_portfolio_risk / 100:,.0f}")
    with st.expander("Enlarged interactive chart", expanded=True):
        fig, message = build_chart(symbol, selected)
        if fig: st.plotly_chart(fig, use_container_width=True, config={"displaylogo": False})
        else: st.warning(message)
    action_col, backtest_col = st.columns(2)
    with action_col:
        alert = st.selectbox("Alert condition", ["Entry reached", "Stop reached", "Target 1 reached", "Target 2 reached"])
        if st.button("Add selected setup to watchlist"):
            add_watch({key: selected[key] for key in ["Symbol", "Signal", "Entry", "Stop", "Target 1", "Target 2"]} | {"Alert": alert})
            st.success("Saved locally. Alerts are evaluated when this app is open and refreshed.")
    with backtest_col:
        if st.button("Run selected setup backtest"):
            trades = backtest(symbol, selected.Signal)
            if trades.empty: st.warning("Not enough usable history for this test.")
            else:
                st.metric("Backtest expectancy", f"{trades['R multiple'].mean():.2f}R", f"Win rate {(trades['R multiple'] > 0).mean():.0%}")
                st.dataframe(trades.tail(30), hide_index=True, use_container_width=True)

st.divider()
watch_tab, journal_tab = st.tabs(["Watchlist and alerts", "Trade journal"])
with watch_tab:
    st.caption("Local alerts are reference markers. The app cannot send background notifications while closed.")
    st.dataframe(watchlist(), use_container_width=True, hide_index=True)
with journal_tab:
    with st.form("journal_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        j_symbol = c1.text_input("Symbol").upper(); j_side = c2.selectbox("Side", ["LONG", "SHORT"]); j_date = c3.date_input("Date")
        j_entry = st.number_input("Entry", min_value=0.0); j_exit = st.number_input("Exit", min_value=0.0); j_shares = st.number_input("Shares", min_value=0, step=1); notes = st.text_input("Notes")
        if st.form_submit_button("Save trade") and j_symbol:
            add_journal({"Date": j_date.isoformat(), "Symbol": j_symbol, "Side": j_side, "Entry": j_entry, "Exit": j_exit, "Shares": j_shares, "Notes": notes}); st.success("Trade saved locally.")
    st.dataframe(journal(), use_container_width=True, hide_index=True)

st.divider()
st.header("Value and economic-moat screener")
st.caption("Uses Yahoo analyst mean target price as a fair-value proxy. Moat ratings below are estimates from profitability, operating margin, leverage, and company scale; they are not Morningstar ratings.")
value_a, value_b, value_c = st.columns(3)
with value_a:
    value_min = st.number_input("Minimum analyst upside (%)", min_value=0, max_value=100, value=25, key="value_min")
with value_b:
    value_max = st.number_input("Maximum analyst upside (%)", min_value=1, max_value=200, value=50, key="value_max")
with value_c:
    moat_filter = st.selectbox("Moat estimate", ["Any estimate", "Wide estimate", "Narrow estimate"])
value_limit = st.slider("Fundamental scan universe size", 25, 200, 75, 25, help="A smaller scan is faster and avoids Yahoo request limits.")
if st.button("Find 25-50% undervalued moat candidates", type="primary"):
    value_progress = st.progress(0, text="Reading Yahoo fundamental data...")
    def value_update(done: int, total: int) -> None:
        value_progress.progress(done / max(total, 1), text=f"Checked {done} of {total} companies")
    symbols = get_universe("S&P 500 / liquid fallback")[:value_limit]
    value_results, value_skipped = scan_value(symbols, int(value_min), int(value_max), moat_filter, value_update)
    value_progress.empty(); st.session_state.value_results = value_results
    st.success(f"Finished. Found {len(value_results)} candidates; {value_skipped} unavailable symbols skipped.")
value_results = st.session_state.value_results
if not value_results.empty:
    st.dataframe(value_results, use_container_width=True, hide_index=True, column_config={"Price": st.column_config.NumberColumn(format="$%.2f"), "Analyst fair value": st.column_config.NumberColumn(format="$%.2f"), "Upside": st.column_config.NumberColumn(format="%.1f%%"), "ROE": st.column_config.NumberColumn(format="%.1f%%"), "Operating margin": st.column_config.NumberColumn(format="%.1f%%")})
