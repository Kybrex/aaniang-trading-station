"""Streamlit UI for the nine AANIANG V4 automation modules."""
from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import streamlit as st

from v3_features import load_notes, load_snapshot
from v4_features import (
    copilot_answer, earnings_calendar, evaluate_alert, export_vault, load_trades,
    monte_carlo, optimize_portfolio, options_snapshot, paper_positions, save_trade,
    sec_filings,
)


MODULES = [
    ("1 · AI Stock Copilot", ":material/smart_toy:"),
    ("2 · SEC Filing Analyzer", ":material/article:"),
    ("3 · Smart Alerts", ":material/notifications_active:"),
    ("4 · Paper Trading", ":material/candlestick_chart:"),
    ("5 · Portfolio Optimizer", ":material/auto_graph:"),
    ("6 · Monte Carlo", ":material/query_stats:"),
    ("7 · Earnings Calendar", ":material/calendar_month:"),
    ("8 · Options Analytics", ":material/functions:"),
    ("9 · Account & Cloud Sync", ":material/cloud_sync:"),
]


def _universe() -> pd.DataFrame:
    return st.session_state.get("v3_universe_data", pd.DataFrame())


def _symbols(frame: pd.DataFrame) -> list[str]:
    return frame.Symbol.astype(str).tolist() if not frame.empty and "Symbol" in frame else []


def render() -> None:
    st.divider()
    st.header("AANIANG V4 Automation & Intelligence")
    st.caption("Nine connected modules for explainable research, monitoring, simulation, execution practice, and portable account data.")
    universe = _universe()
    if universe.empty:
        st.info("Load the V3 research universe above to activate company-aware V4 tools. SEC, calendar, options, and account tools can also run independently.")

    st.markdown("**Quick access — all nine modules**")
    for start in range(0, 9, 3):
        cols = st.columns(3)
        for col, (label, icon) in zip(cols, MODULES[start:start + 3]):
            with col:
                if st.button(label, icon=icon, width="stretch", key=f"v4_quick_{label[0]}"):
                    st.session_state.v4_section = label
    section = st.selectbox("V4 module", [label for label, _ in MODULES], key="v4_section")
    symbols = _symbols(universe)

    if section.startswith("1"):
        st.subheader("AI Stock Copilot")
        st.caption("Explainable answers grounded in the metrics already loaded by the app. It does not invent live facts or issue buy/sell instructions.")
        if symbols:
            symbol = st.selectbox("Company", symbols, key="v4_copilot_symbol")
        else:
            symbol = st.text_input("Company symbol", "AAPL", key="v4_copilot_ticker").strip().upper()
            st.caption("V3 is not loaded, so Copilot will retrieve this company when you ask a question.")
        prompts = ["Give me an overview", "What are the principal risks?", "Is the valuation attractive?", "How is momentum?"]
        question = st.text_input("Ask about this company", prompts[0], key="v4_question")
        if st.button("Ask Copilot", type="primary", key="v4_ask"):
            if symbols and symbol in symbols:
                row = universe.loc[universe.Symbol == symbol].iloc[0].to_dict()
            else:
                try:
                    fmp_key = str(st.secrets.get("FMP_API_KEY", ""))
                except Exception:
                    fmp_key = ""
                with st.spinner(f"Loading {symbol} research metrics..."):
                    row = load_snapshot(symbol, fmp_key)
            if row:
                st.session_state.v4_answer = copilot_answer(question, row)
            else:
                st.session_state.v4_answer = "No usable company data was returned. Check the ticker or try again after a temporary data-provider delay."
        if st.session_state.get("v4_answer"):
            with st.chat_message("assistant"): st.write(st.session_state.v4_answer)
        st.caption("Try: " + " · ".join(prompts[1:]))

    elif section.startswith("2"):
        st.subheader("SEC Filing Analyzer")
        st.caption("Recent 10-K, 10-Q, 8-K, 20-F, and 6-K filing metadata from the official SEC EDGAR API.")
        symbol = st.text_input("US-listed symbol", symbols[0] if symbols else "AAPL", key="v4_sec_symbol").upper()
        agent = st.text_input("SEC contact email", "research@example.com", help="SEC asks automated clients to identify themselves with contact information.")
        if st.button("Analyze SEC filings", type="primary", key="v4_sec_run"):
            try:
                with st.spinner("Loading official EDGAR filing history..."):
                    st.session_state.v4_sec = sec_filings(symbol, f"AANIANG-Trading-Station {agent}")
            except Exception as error: st.error(str(error))
        result = st.session_state.get("v4_sec")
        if result:
            st.success(f"{result['company']} · CIK {result['cik']}")
            filings = result["filings"]
            if filings.empty: st.warning("No recent supported filings were found.")
            else:
                for _, filing in filings.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{filing['form']} · {filing['filingDate']}**")
                        st.caption(str(filing.get("primaryDocDescription") or filing.get("primaryDocument")))
                        st.link_button("Open official filing", filing["url"])

    elif section.startswith("3"):
        st.subheader("Smart Alerts")
        st.caption("Alerts are evaluated whenever you refresh this module. Background push notifications require an external notification service.")
        if not symbols: return
        alerts = st.session_state.setdefault("v4_alerts", [])
        with st.form("v4_alert_form", border=True):
            symbol = st.selectbox("Symbol", symbols)
            field = st.selectbox("Metric", ["Price", "Quality", "Value gap", "1M return", "6M return"])
            operator = st.selectbox("Condition", [">=", "<="])
            threshold = st.number_input("Threshold", value=0.0)
            if st.form_submit_button("Add alert", type="primary"):
                alerts.append({"Symbol": symbol, "Metric": field, "Condition": operator, "Threshold": threshold})
        rows = []
        for alert in alerts:
            row = universe.loc[universe.Symbol == alert["Symbol"]]
            if row.empty: continue
            triggered, value = evaluate_alert(row.iloc[0].to_dict(), alert["Metric"], alert["Condition"], alert["Threshold"])
            rows.append({**alert, "Current": value, "Status": "TRIGGERED" if triggered else "Watching"})
        if rows:
            table = pd.DataFrame(rows); st.dataframe(table, hide_index=True, width="stretch")
            st.metric("Triggered now", int(table.Status.eq("TRIGGERED").sum()), border=True)
            if st.button("Clear all alerts"): st.session_state.v4_alerts = []; st.rerun()

    elif section.startswith("4"):
        st.subheader("Paper-Trading Portfolio")
        st.caption("Practice ledger only. No order is sent to a broker.")
        if not symbols: return
        with st.form("v4_trade", border=True):
            symbol = st.selectbox("Symbol", symbols, key="v4_trade_symbol")
            side = st.segmented_control("Side", ["BUY", "SELL"], default="BUY")
            shares = st.number_input("Shares", min_value=0.01, value=1.0)
            market_price = float(universe.loc[universe.Symbol == symbol, "Price"].iloc[0])
            price = st.number_input("Execution price", min_value=0.01, value=max(market_price, 0.01))
            if st.form_submit_button("Record simulated order", type="primary"):
                save_trade({"Time": datetime.now(timezone.utc).isoformat(), "Symbol": symbol, "Side": side, "Shares": shares, "Price": price}); st.success("Simulated order recorded.")
        prices = dict(zip(universe.Symbol, universe.Price))
        trades = load_trades(); positions = paper_positions(trades, prices)
        if trades: st.dataframe(pd.DataFrame(trades), hide_index=True, width="stretch")
        if not positions.empty:
            st.markdown("**Open positions and performance**"); st.dataframe(positions, hide_index=True, width="stretch")

    elif section.startswith("5"):
        st.subheader("Portfolio Optimizer")
        st.caption("Inverse-volatility allocation: lower-volatility assets receive more weight, subject to a concentration cap.")
        choices = st.multiselect("Select 2–15 assets", symbols or ["AAPL", "MSFT", "NVDA"], default=(symbols or ["AAPL", "MSFT", "NVDA"])[:3], max_selections=15)
        max_weight = st.slider("Maximum weight per asset", 10, 100, 35) / 100
        if st.button("Optimize allocation", type="primary", key="v4_optimize"):
            if len(choices) < 2: st.warning("Select at least two assets.")
            else:
                try:
                    with st.spinner("Calculating correlations and volatility..."):
                        allocation, metrics = optimize_portfolio(choices, max_weight)
                    st.session_state.v4_optimization = (allocation, metrics)
                except Exception as error: st.error(str(error))
        if st.session_state.get("v4_optimization"):
            allocation, metrics = st.session_state.v4_optimization
            cols = st.columns(3)
            cols[0].metric("Expected annual return", f"{metrics['Expected return']:.1f}%")
            cols[1].metric("Annual volatility", f"{metrics['Volatility']:.1f}%")
            cols[2].metric("Historical Sharpe", f"{metrics['Sharpe']:.2f}")
            st.bar_chart(allocation.set_index("Symbol")["Suggested weight"]); st.dataframe(allocation, hide_index=True, width="stretch")

    elif section.startswith("6"):
        st.subheader("Monte Carlo Portfolio Simulator")
        choices = st.multiselect("Portfolio symbols", symbols or ["AAPL", "MSFT"], default=(symbols or ["AAPL", "MSFT"])[:2], max_selections=10, key="v4_mc_symbols")
        weights_text = st.text_input("Weights (%) in the same order", ", ".join([str(round(100 / len(choices), 1))] * len(choices)) if choices else "")
        cols = st.columns(2); initial = cols[0].number_input("Starting portfolio value", min_value=100.0, value=10000.0); years = cols[1].slider("Years", 1, 20, 5)
        if st.button("Run 1,000 simulations", type="primary", key="v4_mc_run"):
            try:
                weights = [float(value.strip()) for value in weights_text.split(",")]
                if len(weights) != len(choices) or not choices: raise ValueError("Provide one weight for every selected symbol.")
                with st.spinner("Simulating potential paths..."):
                    chart, metrics = monte_carlo(choices, weights, initial, years)
                st.session_state.v4_mc = (chart, metrics)
            except Exception as error: st.error(str(error))
        if st.session_state.get("v4_mc"):
            chart, metrics = st.session_state.v4_mc; st.line_chart(chart)
            cols = st.columns(4)
            cols[0].metric("10th percentile", f"${metrics['P10']:,.0f}"); cols[1].metric("Median", f"${metrics['Median']:,.0f}")
            cols[2].metric("90th percentile", f"${metrics['P90']:,.0f}"); cols[3].metric("Loss probability", f"{metrics['Loss probability']:.1f}%")

    elif section.startswith("7"):
        st.subheader("Earnings & Economic Calendar")
        calendar_symbols = st.text_input("Symbols (maximum 20)", ", ".join((symbols or ["AAPL", "MSFT", "NVDA"])[:10]))
        if st.button("Load company calendar", type="primary", key="v4_calendar"):
            selected = [s.strip().upper() for s in calendar_symbols.split(",") if s.strip()][:20]
            with st.spinner("Loading company events..."): st.session_state.v4_calendar_data = earnings_calendar(selected)
        if st.session_state.get("v4_calendar_data") is not None:
            st.dataframe(st.session_state.v4_calendar_data, hide_index=True, width="stretch")
        st.markdown("**Official macro calendars**")
        cols = st.columns(3)
        cols[0].link_button("Federal Reserve calendar", "https://www.federalreserve.gov/newsevents/calendar.htm")
        cols[1].link_button("US economic releases", "https://www.bls.gov/schedule/")
        cols[2].link_button("SEC filing search", "https://www.sec.gov/search-filings")

    elif section.startswith("8"):
        st.subheader("Options Analytics")
        symbol = st.text_input("Option symbol", symbols[0] if symbols else "AAPL", key="v4_option_symbol").upper()
        if st.button("Load option chain", type="primary", key="v4_options"):
            try:
                with st.spinner("Loading available expirations..."):
                    calls, puts, expiries = options_snapshot(symbol)
                st.session_state.v4_options_data = (calls, puts, expiries)
            except Exception as error: st.error(str(error))
        if st.session_state.get("v4_options_data"):
            calls, puts, expiries = st.session_state.v4_options_data
            if not expiries: st.warning("No listed option chain was returned.")
            else:
                st.caption(f"Nearest expiration: {expiries[0]} · {len(expiries)} expirations available")
                call_tab, put_tab, payoff_tab = st.tabs(["Calls", "Puts", "Covered-call payoff"])
                columns = ["strike", "lastPrice", "bid", "ask", "volume", "openInterest", "impliedVolatility", "Volume/OI"]
                with call_tab: st.dataframe(calls[columns].sort_values("Volume/OI", ascending=False), hide_index=True, width="stretch")
                with put_tab: st.dataframe(puts[columns].sort_values("Volume/OI", ascending=False), hide_index=True, width="stretch")
                with payoff_tab:
                    strike = st.number_input("Call strike", min_value=0.01, value=float(calls.strike.median()))
                    premium = st.number_input("Premium received per share", min_value=0.0, value=1.0)
                    stock_cost = st.number_input("Stock cost per share", min_value=0.01, value=max(strike * 0.9, 0.01))
                    prices = np.linspace(stock_cost * 0.5, stock_cost * 1.5, 100)
                    payoff = (prices - stock_cost) + premium - np.maximum(prices - strike, 0)
                    st.line_chart(pd.DataFrame({"Stock price": prices, "Profit per share": payoff}).set_index("Stock price"))

    else:
        st.subheader("Account & Cloud Sync Vault")
        st.caption("Portable backup works now across devices. A hosted database and authentication provider are still required for automatic cloud synchronization.")
        profile_name = st.text_input("Profile name", st.session_state.get("v4_profile_name", "My portfolio"))
        st.session_state.v4_profile_name = profile_name
        payload = export_vault({"name": profile_name}, load_notes(), st.session_state.get("v4_alerts", []), load_trades())
        st.download_button("Download account backup", payload, "aaniang-account-backup.json", "application/json", icon=":material/download:")
        upload = st.file_uploader("Restore account backup", type="json", key="v4_vault_upload")
        if upload and st.button("Restore backup", type="primary"):
            try:
                restored = json.loads(upload.getvalue().decode("utf-8"))
                st.session_state.v4_profile_name = restored.get("profile", {}).get("name", "My portfolio")
                st.session_state.v4_alerts = restored.get("alerts", [])
                st.success("Profile and alerts restored into this session. Notes and trade history remain available in the downloaded vault.")
            except Exception as error: st.error(f"Invalid backup: {error}")
        with st.container(border=True):
            st.markdown("**Cloud connection status**")
            st.write("Local/session profile: Active")
            st.write("Portable backup: Active")
            st.write("Automatic multi-device database sync: Not connected")

