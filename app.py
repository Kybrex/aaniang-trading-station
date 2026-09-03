"""Swing Setup Screener - run with: streamlit run app.py"""
from __future__ import annotations
import pandas as pd
import streamlit as st
from charts import build_chart
from technical_chart import build_company_technical_chart, technical_data, technical_snapshot
from fundamentals import ValuationAssumptions, default_growth, financial_history, intrinsic_value, load_company, quality_score
from research import add_relative_strength, annotate_earnings, backtest, evaluate_alerts, market_regime
from scanner import ScanSettings, scan_market
from storage import add_journal, add_watch, journal, save_attachment, save_watchlist, watchlist
from universe import load_universe
from value_screener import scan_value
import v2_ui
import v3_ui
import v4_ui
import v5_ui
from ui_theme import apply_theme

st.set_page_config(page_title="AANIANG Trading Station", page_icon="S", layout="wide")
apply_theme()
logo_col, title_col = st.columns([1, 14], vertical_alignment="center")
with logo_col:
    st.image("senegal_flag.svg", width=48)
with title_col:
    st.title("AANIANG Trading Station")
st.caption("Yahoo Finance adjusted daily data—not a guaranteed live quote | educational research tool, not investment advice")
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
    universe_limit = st.slider("Maximum symbols per scan", 50, 5000, 250, 50, help="Start with 250. Larger scans take longer and are more likely to be limited by Yahoo Finance.")
    batch_size = st.slider("Download batch size", 10, 100, 25, 5)

@st.cache_data(ttl=3600, show_spinner=False)
def get_universe(choice: str) -> list[str]:
    return load_universe(broad=choice.startswith("Broad"))

@st.cache_data(ttl=900, show_spinner=False)
def cached_market_regime() -> dict[str, str]:
    return market_regime()

if "results" not in st.session_state:
    st.session_state.results = pd.DataFrame()
if "value_results" not in st.session_state:
    st.session_state.value_results = pd.DataFrame()
if st.button("Scan market", type="primary", width="stretch"):
    symbols = get_universe(universe_choice)[:int(universe_limit)]
    # Fetch the three small benchmark histories before the large market scan.
    st.session_state.market_regime = cached_market_regime()
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
    if skipped >= len(symbols): status.error("Yahoo Finance returned no usable data. Wait a few minutes, then retry with the liquid fallback and 50–250 symbols.")
    else: status.success(f"Finished. {len(results)} candidates found; {skipped} symbols skipped/unavailable.")

results = st.session_state.results
if results.empty:
    st.info("Set filters and click Scan market. The first broad scan can take several minutes.")
else:
    cols = st.columns(3)
    regime = st.session_state.get("market_regime") or cached_market_regime()
    for column, (name, status) in zip(cols, regime.items()): column.metric(name, status)
    if any(status == "Unavailable" for status in regime.values()):
        if st.button("Retry unavailable market context"):
            cached_market_regime.clear()
            st.session_state.market_regime = cached_market_regime()
            st.rerun()
    st.subheader(f"Ranked opportunities ({len(results)})")
    display = results[["Symbol", "Data date", "Score", "Signal", "Setup", "Entry", "Stop", "Risk/Share", "20D Momentum", "60D Momentum", "RS vs SPY", "Earnings", "Shares", "Trade plan"]]
    st.dataframe(display, width="stretch", hide_index=True, column_config={"Score": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%d"), "Entry": st.column_config.NumberColumn(format="$%.2f"), "Stop": st.column_config.NumberColumn(format="$%.2f"), "Risk/Share": st.column_config.NumberColumn(format="$%.2f"), "20D Momentum": st.column_config.NumberColumn(format="%.1f%%"), "60D Momentum": st.column_config.NumberColumn(format="%.1f%%"), "RS vs SPY": st.column_config.NumberColumn(format="%.1f%%")})
    symbol = st.selectbox("Open candidate chart", results["Symbol"].tolist())
    selected = results.loc[results.Symbol == symbol].iloc[0]
    capped_shares = min(int(selected.Shares), int((equity * max_position_pct / 100) / selected.Entry))
    st.markdown(f"**{selected.Signal} {selected.Setup}** | {selected['Trade plan']}")
    a, b, c = st.columns(3)
    a.metric("Risk budget", f"${equity * risk_pct / 100:,.0f}"); b.metric("Capped position", f"{capped_shares:,} shares"); c.metric("Portfolio heat limit", f"${equity * max_portfolio_risk / 100:,.0f}")
    with st.expander("Enlarged interactive chart", expanded=True):
        fig, message = build_chart(symbol, selected)
        if fig: st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        else: st.warning(message)
    action_col, backtest_col = st.columns(2)
    with action_col:
        alert = st.selectbox("Alert condition", ["Entry reached", "Stop reached", "Target 1 reached", "Target 2 reached"])
        if st.button("Add selected setup to watchlist"):
            add_watch({key: selected[key] for key in ["Symbol", "Signal", "Entry", "Stop", "Target 1", "Target 2"]} | {"Alert": alert})
            st.success("Saved locally. Alerts are evaluated when this app is open and refreshed.")
    with backtest_col:
        if st.button("Run selected setup backtest"):
            trades = backtest(symbol, selected.Signal, setup=selected.Setup)
            if trades.empty: st.warning("Not enough usable history for this test.")
            else:
                st.metric("Backtest expectancy", f"{trades['R multiple'].mean():.2f}R", f"Win rate {(trades['R multiple'] > 0).mean():.0%}")
                st.dataframe(trades.tail(30), hide_index=True, width="stretch")

st.divider()
watch_tab, journal_tab = st.tabs(["Watchlist and alerts", "Trade journal"])
with watch_tab:
    st.caption("Local alerts are reference markers. The app cannot send background notifications while closed.")
    saved_watchlist = watchlist()
    watchlist_notice = st.session_state.pop("watchlist_notice", "")
    if watchlist_notice: st.success(watchlist_notice)
    action_col, edit_col = st.columns([1, 1])
    with action_col:
        if st.button("Refresh watchlist prices and alerts", disabled=saved_watchlist.empty):
            st.session_state.evaluated_watchlist = evaluate_alerts(saved_watchlist)
    with edit_col:
        edit_watchlist = st.toggle("Edit watchlist", value=False, key="edit_watchlist_toggle")
    if edit_watchlist:
        st.caption("Edit cells directly, add rows, or use the mobile-friendly delete control below.")
        edited_watchlist = st.data_editor(
            saved_watchlist,
            width="stretch",
            hide_index=True,
            num_rows="dynamic",
            key="watchlist_editor",
            column_config={
                "Symbol": st.column_config.TextColumn("Symbol", required=True, help="Ticker symbol"),
                "Signal": st.column_config.SelectboxColumn("Signal", options=["LONG", "SHORT", "WATCH"], required=True),
                "Entry": st.column_config.NumberColumn("Entry", min_value=0.0, format="$%.2f"),
                "Stop": st.column_config.NumberColumn("Stop", min_value=0.0, format="$%.2f"),
                "Target 1": st.column_config.NumberColumn("Target 1", min_value=0.0, format="$%.2f"),
                "Target 2": st.column_config.NumberColumn("Target 2", min_value=0.0, format="$%.2f"),
                "Alert": st.column_config.TextColumn("Alert", help="Example: Entry reached"),
            },
        )
        delete_options = sorted(
            symbol for symbol in edited_watchlist.get("Symbol", pd.Series(dtype=str)).fillna("").astype(str).str.strip().str.upper().unique()
            if symbol
        )
        save_col, symbol_col, delete_col = st.columns([1.5, 1.15, 0.65], vertical_alignment="bottom")
        with save_col:
            if st.button("Save watchlist changes", type="primary", icon=":material/save:", width="stretch"):
                save_watchlist(edited_watchlist)
                st.session_state.pop("evaluated_watchlist", None)
                st.session_state.watchlist_notice = "Watchlist changes saved."
                st.rerun()
        with symbol_col:
            delete_symbol = st.selectbox(
                "Delete row",
                delete_options,
                index=None,
                placeholder="Ticker",
                disabled=not delete_options,
                key="watchlist_delete_symbol",
                label_visibility="collapsed",
            )
        with delete_col:
            if st.button(
                "Delete",
                icon=":material/delete:",
                disabled=not delete_symbol,
                key="watchlist_delete_button",
                width="stretch",
            ):
                remaining = edited_watchlist[
                    edited_watchlist["Symbol"].fillna("").astype(str).str.strip().str.upper() != delete_symbol
                ]
                save_watchlist(remaining)
                st.session_state.pop("evaluated_watchlist", None)
                st.session_state.watchlist_notice = f"{delete_symbol} was deleted from the watchlist."
                st.rerun()
        st.caption(f"{len(edited_watchlist)} rows · Choose a ticker beside Save, then tap Delete.")
    else:
        st.dataframe(st.session_state.get("evaluated_watchlist", saved_watchlist), width="stretch", hide_index=True)
with journal_tab:
    with st.form("journal_form", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        j_symbol = c1.text_input("Symbol").upper(); j_side = c2.selectbox("Side", ["LONG", "SHORT"]); j_date = c3.date_input("Date")
        c4,c5,c6=st.columns(3);j_setup=c4.selectbox("Setup",["Breakout","EMA pullback","VCP","RS breakout","Post-event gap","Reversal","Other"]);j_stop=c5.number_input("Initial Stop",min_value=0.0);j_target=c6.number_input("Initial Target",min_value=0.0)
        j_entry = st.number_input("Entry", min_value=0.0); j_exit = st.number_input("Exit", min_value=0.0); j_shares = st.number_input("Shares", min_value=0, step=1); notes = st.text_input("Notes");screenshot=st.file_uploader("Chart screenshot (optional)",type=["png","jpg","jpeg"],key="journal_screenshot")
        if st.form_submit_button("Save trade") and j_symbol:
            attachment=save_attachment(screenshot.name,screenshot.getvalue()) if screenshot else ""
            add_journal({"Date": j_date.isoformat(), "Symbol": j_symbol, "Side": j_side,"Setup":j_setup,"Initial Stop":j_stop,"Initial Target":j_target,"Entry": j_entry, "Exit": j_exit, "Shares": j_shares,"Screenshot":attachment,"Notes": notes}); st.success("Trade saved locally.")
    st.dataframe(journal(), width="stretch", hide_index=True)

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
    st.dataframe(value_results, width="stretch", hide_index=True, column_config={"Price": st.column_config.NumberColumn(format="$%.2f"), "Analyst fair value": st.column_config.NumberColumn(format="$%.2f"), "Upside": st.column_config.NumberColumn(format="%.1f%%"), "ROE": st.column_config.NumberColumn(format="%.1f%%"), "Operating margin": st.column_config.NumberColumn(format="%.1f%%")})

st.divider()
st.header("AANIANG company intelligence", anchor="company-intelligence")
st.caption("Explainable quality and valuation research using Yahoo Finance. Missing fields receive no points; estimates are not investment advice.")

@st.cache_data(ttl=1800, max_entries=25, show_spinner=False)
def get_company_bundle(symbol: str) -> dict:
    return load_company(symbol)

with st.form("company_lookup"):
    research_symbol = st.text_input("Company symbol", value="AAPL", placeholder="AAPL").strip().upper()
    analyze_company = st.form_submit_button("Analyze company", type="primary", icon=":material/analytics:")
if analyze_company:
    with st.spinner(f"Loading financial statements for {research_symbol}..."):
        try:
            st.session_state.company_bundle = get_company_bundle(research_symbol)
            st.session_state.company_error = ""
        except ValueError as error:
            st.session_state.company_error = str(error)
if st.session_state.get("company_error"):
    st.error(st.session_state.company_error)

bundle = st.session_state.get("company_bundle")
if bundle:
    info = bundle["info"]; symbol = bundle["symbol"]
    score, evidence = quality_score(bundle)
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    company_name = info.get("longName") or info.get("shortName") or symbol
    st.subheader(f"{company_name} ({symbol})")
    with st.container(horizontal=True):
        st.metric("Quality score", f"{score}/100", border=True)
        st.metric("Price", f"${float(current_price):,.2f}" if current_price else "Unavailable", border=True)
        st.metric("Market cap", f"${float(info.get('marketCap'))/1e9:,.1f}B" if info.get("marketCap") else "Unavailable", border=True)
        st.metric("Sector", info.get("sector", "Unavailable"), border=True)

    intelligence_view = st.segmented_control("Research section", ["Overview", "Technical", "Quality", "Financials", "Valuation"], default="Overview", key="intelligence_view")
    if intelligence_view == "Overview":
        with st.container(border=True):
            st.markdown("**Business overview**")
            st.write(info.get("longBusinessSummary") or "Business description is unavailable from Yahoo Finance.")
        overview = pd.DataFrame([
            {"Metric": "Industry", "Value": info.get("industry", "Unavailable")},
            {"Metric": "Employees", "Value": f"{int(info['fullTimeEmployees']):,}" if info.get("fullTimeEmployees") else "Unavailable"},
            {"Metric": "Trailing P/E", "Value": f"{float(info['trailingPE']):.2f}" if info.get("trailingPE") else "Unavailable"},
            {"Metric": "Forward P/E", "Value": f"{float(info['forwardPE']):.2f}" if info.get("forwardPE") else "Unavailable"},
            {"Metric": "Dividend yield", "Value": f"{float(info['dividendYield']):.2%}" if info.get("dividendYield") else "Unavailable"},
            {"Metric": "Analyst target", "Value": f"${float(info['targetMeanPrice']):.2f}" if info.get("targetMeanPrice") else "Unavailable"},
        ])
        st.dataframe(overview, hide_index=True, width="stretch")
        history = bundle["history"]
        if not history.empty:
            st.line_chart(history[["Close"]].rename(columns={"Close": symbol}), height=360)
    elif intelligence_view == "Technical":
        history = bundle["history"]
        if history.empty or not {"Open", "High", "Low", "Close", "Volume"}.issubset(history.columns):
            st.warning("OHLCV price history is unavailable for this symbol.")
        else:
            st.caption("Interactive candlesticks with moving averages, volume, momentum, volatility, zoom, pan, and unified hover data.")
            setting_a, setting_b, setting_c = st.columns([1, 1.5, 1])
            with setting_a:
                chart_period = st.selectbox("Chart period", ["3 months", "6 months", "1 year", "2 years", "5 years"], index=2, key="company_chart_period")
            with setting_b:
                overlays = st.multiselect("Moving averages", ["EMA 21", "SMA 20", "SMA 50", "SMA 200"], default=["EMA 21", "SMA 50", "SMA 200"], key="company_chart_mas")
            with setting_c:
                oscillator = st.selectbox("Lower indicator", ["RSI 14", "MACD", "None"], key="company_chart_oscillator")
            sessions = {"3 months": 66, "6 months": 132, "1 year": 252, "2 years": 504, "5 years": 1260}
            indicators = technical_data(history)
            visible = indicators.tail(sessions[chart_period])
            snapshot = technical_snapshot(indicators)
            metric_cols = st.columns(5)
            metric_cols[0].metric("Trend", snapshot["Trend"], border=True)
            metric_cols[1].metric("RSI 14", f"{snapshot['RSI']:.1f}", snapshot["Momentum"], border=True)
            metric_cols[2].metric("MACD signal", snapshot["MACD"], border=True)
            metric_cols[3].metric("ATR 14", f"${snapshot['ATR']:.2f}", border=True)
            metric_cols[4].metric("Last close", f"${snapshot['Price']:.2f}", border=True)
            technical_figure = build_company_technical_chart(visible, symbol, overlays, oscillator)
            st.plotly_chart(
                technical_figure,
                width="stretch",
                config={"displaylogo": False, "scrollZoom": True, "modeBarButtonsToRemove": ["lasso2d", "select2d"]},
                key=f"company_technical_{symbol}_{chart_period}_{oscillator}",
            )
            with st.expander("Latest technical indicator data"):
                technical_columns = ["Close", "Volume", "EMA 21", "SMA 20", "SMA 50", "SMA 200", "RSI 14", "MACD", "MACD signal", "ATR 14"]
                latest_technical = indicators[technical_columns].tail(20).reset_index()
                st.dataframe(latest_technical, hide_index=True, width="stretch")
                st.download_button("Download technical data", indicators[technical_columns].to_csv(), f"{symbol}-technical-analysis.csv", "text/csv")
    elif intelligence_view == "Quality":
        st.progress(score / 100, text=f"AANIANG Quality Score: {score}/100")
        st.dataframe(evidence, hide_index=True, width="stretch", column_config={"Points": st.column_config.ProgressColumn("Points earned", min_value=0, max_value=15), "Maximum": st.column_config.NumberColumn("Maximum")})
        st.caption("Profitability 25 points · Growth 20 · Cash flow 20 · Balance sheet 20 · Predictability 15")
    elif intelligence_view == "Financials":
        statements = financial_history(bundle)
        if statements.empty:
            st.warning("Annual financial statements are unavailable for this symbol.")
        else:
            chart_metric = st.selectbox("Chart metric", statements.columns.tolist(), key="financial_metric")
            st.line_chart(statements[[chart_metric]], height=340)
            st.dataframe(statements.reset_index(names="Year"), hide_index=True, width="stretch", column_config={column: st.column_config.NumberColumn(column, format="$%.0f") for column in statements.columns})
    else:
        estimated_growth = default_growth(bundle)
        st.caption("Adjust the assumptions to test uncertainty. Growth and terminal growth are capped to keep the model conservative.")
        scenario = st.segmented_control("Scenario", ["Bear", "Base", "Bull"], default="Base", key="valuation_scenario")
        presets = {
            "Bear": (max(0.0, estimated_growth - .04), .11, .02, 15.0),
            "Base": (estimated_growth, .09, .025, 20.0),
            "Bull": (min(.25, estimated_growth + .04), .08, .03, 25.0),
        }
        preset = presets[scenario]
        with st.form("valuation_assumptions"):
            growth = st.number_input("Annual growth (%)", 0.0, 25.0, preset[0] * 100, .5) / 100
            discount = st.number_input("Required return / discount rate (%)", 6.0, 20.0, preset[1] * 100, .5) / 100
            terminal = st.number_input("Terminal growth (%)", 0.0, 4.0, preset[2] * 100, .25) / 100
            multiple = st.number_input("Future earnings multiple", 5.0, 40.0, preset[3], 1.0)
            calculate = st.form_submit_button("Calculate intrinsic value", type="primary", icon=":material/calculate:")
        if calculate or "valuation_result" not in st.session_state or st.session_state.get("valuation_symbol") != symbol:
            st.session_state.valuation_result = intrinsic_value(bundle, ValuationAssumptions(growth, discount, terminal, multiple))
            st.session_state.valuation_symbol = symbol
        valuation = st.session_state.valuation_result
        fair, upside = valuation["fair_value"], valuation["margin_of_safety"]
        with st.container(horizontal=True):
            st.metric("Current price", f"${valuation['price']:,.2f}" if valuation["price"] else "Unavailable", border=True)
            st.metric("Blended fair value", f"${fair:,.2f}" if fair else "Unavailable", border=True)
            st.metric("Margin of safety", f"{upside:,.1f}%" if upside is not None else "Unavailable", border=True)
        methods = pd.DataFrame([{"Method": method, "Estimated value": value} for method, value in valuation["methods"].items()])
        if methods.empty:
            st.warning("Yahoo Finance did not provide enough positive cash-flow, earnings, or analyst data for this valuation.")
        else:
            st.dataframe(methods, hide_index=True, width="stretch", column_config={"Estimated value": st.column_config.NumberColumn(format="$%.2f")})
            st.bar_chart(methods.set_index("Method"), horizontal=True)
        st.info("Valuation is a range-building aid, not a price prediction. Review filings and test several scenarios before making a decision.", icon=":material/info:")

v2_ui.render(results, equity)

v3_ui.render()

v4_ui.render()

v5_ui.render()
