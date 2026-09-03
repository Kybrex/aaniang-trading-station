"""Streamlit UI for AANIANG V5 Institutional Research."""
from __future__ import annotations

import io
import pandas as pd
import streamlit as st

from v5_features import (
    catalysts, dividend_intelligence, fifo_tax_lots, insider_activity,
    management_score, ownership, scenario_table, sector_rotation,
    transcript_analysis,
)


MODULES = [
    ("1 · Earnings Call Analyzer", ":material/record_voice_over:"),
    ("2 · Insider Trading", ":material/badge:"),
    ("3 · Institutional Ownership", ":material/account_balance:"),
    ("4 · Dividend Intelligence", ":material/payments:"),
    ("5 · Catalyst Tracker", ":material/event_upcoming:"),
    ("6 · Sector Rotation", ":material/cycle:"),
    ("7 · Stock Scenario Lab", ":material/science:"),
    ("8 · Portfolio Tax Center", ":material/receipt_long:"),
    ("9 · Management Quality", ":material/leaderboard:"),
]


def _universe() -> pd.DataFrame:
    return st.session_state.get("v3_universe_data", pd.DataFrame())


def _symbol_input(label: str, universe: pd.DataFrame, key: str) -> str:
    symbols = universe.Symbol.tolist() if not universe.empty and "Symbol" in universe else []
    return st.selectbox(label, symbols, key=key) if symbols else st.text_input(label, "AAPL", key=key).strip().upper()


def render() -> None:
    st.divider(); st.header("AANIANG V5 Institutional Research Suite")
    st.caption("Nine professional research modules for management analysis, ownership, income, catalysts, scenarios, sectors, and taxes.")
    universe = _universe()
    st.markdown("**Quick access — all nine modules**")
    for start in range(0, 9, 3):
        cols = st.columns(3)
        for col, (label, icon) in zip(cols, MODULES[start:start + 3]):
            with col:
                if st.button(label, icon=icon, width="stretch", key=f"v5_quick_{label[0]}"):
                    st.session_state.v5_section = label
    section = st.selectbox("V5 module", [label for label, _ in MODULES], key="v5_section")

    if section.startswith("1"):
        st.subheader("Earnings Call Analyzer")
        st.caption("Paste or upload a transcript you are authorized to use. The analyzer extracts tone, guidance, risks, and decision-relevant sentences.")
        upload = st.file_uploader("Transcript file", type="txt", key="v5_transcript_file")
        initial = upload.getvalue().decode("utf-8", errors="replace") if upload else ""
        text = st.text_area("Transcript text", value=initial, height=260, placeholder="Paste the earnings-call transcript here...")
        if st.button("Analyze earnings call", type="primary"):
            if len(text.strip()) < 100: st.warning("Add at least a short transcript passage.")
            else: st.session_state.v5_transcript = transcript_analysis(text)
        result = st.session_state.get("v5_transcript")
        if result:
            cols = st.columns(3); cols[0].metric("Management tone", result["Tone"]); cols[1].metric("Positive signals", result["Positive signals"]); cols[2].metric("Risk signals", result["Risk signals"])
            for heading in ("Highlights", "Guidance", "Risks"):
                with st.expander(heading, expanded=heading == "Highlights"):
                    for sentence in result[heading] or ["No matching statements detected."]: st.write(f"• {sentence}")

    elif section.startswith("2"):
        st.subheader("Insider Trading Tracker")
        symbol = _symbol_input("Company symbol", universe, "v5_insider_symbol")
        if st.button("Load insider activity", type="primary"):
            try:
                with st.spinner("Loading reported insider transactions..."): st.session_state.v5_insiders = insider_activity(symbol)
            except Exception as error: st.error(str(error))
        data = st.session_state.get("v5_insiders")
        if isinstance(data, pd.DataFrame):
            if data.empty: st.warning("No insider transactions were returned.")
            else:
                st.dataframe(data, hide_index=True, width="stretch")
                st.download_button("Download insider data", data.to_csv(index=False), f"{symbol}-insiders.csv", "text/csv")

    elif section.startswith("3"):
        st.subheader("Institutional Ownership")
        symbol = _symbol_input("Company symbol", universe, "v5_owner_symbol")
        if st.button("Load ownership", type="primary"):
            try:
                with st.spinner("Loading major holders..."): st.session_state.v5_ownership = ownership(symbol)
            except Exception as error: st.error(str(error))
        if st.session_state.get("v5_ownership"):
            institutions, funds, major = st.session_state.v5_ownership
            tabs = st.tabs(["Institutions", "Mutual funds", "Major-holder summary"])
            for tab, frame in zip(tabs, (institutions, funds, major)):
                with tab:
                    if frame.empty: st.info("No data returned for this category.")
                    else: st.dataframe(frame, hide_index=True, width="stretch")

    elif section.startswith("4"):
        st.subheader("Dividend Intelligence")
        symbol = _symbol_input("Dividend symbol", universe, "v5_dividend_symbol")
        shares = st.number_input("Shares owned", min_value=0.0, value=100.0)
        if st.button("Analyze dividend", type="primary"):
            try:
                with st.spinner("Loading dividend history..."): st.session_state.v5_dividend = dividend_intelligence(symbol)
            except Exception as error: st.error(str(error))
        if st.session_state.get("v5_dividend"):
            history, metrics = st.session_state.v5_dividend
            cols = st.columns(5)
            cols[0].metric("Safety", f"{metrics['Safety score']}/100"); cols[1].metric("Yield", f"{metrics['Yield']:.2f}%")
            cols[2].metric("Payout", f"{metrics['Payout ratio']:.1f}%"); cols[3].metric("5Y growth", f"{metrics['5Y average growth']:.1f}%")
            cols[4].metric("Estimated annual income", f"${shares * metrics['Annual income/share']:,.2f}")
            if history.empty: st.warning("No dividend history was returned.")
            else: st.bar_chart(history.set_index("Year")["Dividend/share"]); st.dataframe(history, hide_index=True, width="stretch")

    elif section.startswith("5"):
        st.subheader("Catalyst Tracker")
        symbol = _symbol_input("Company symbol", universe, "v5_catalyst_symbol")
        if st.button("Load catalysts", type="primary"):
            try:
                with st.spinner("Loading company calendar and headlines..."): st.session_state.v5_catalysts = catalysts(symbol)
            except Exception as error: st.error(str(error))
        if st.session_state.get("v5_catalysts"):
            calendar, news = st.session_state.v5_catalysts
            st.markdown("**Scheduled company events**"); st.dataframe(calendar, hide_index=True, width="stretch") if not calendar.empty else st.info("No scheduled events returned.")
            st.markdown("**Recent potential catalysts**")
            if news.empty: st.info("No recent headlines returned.")
            else:
                for row in news.itertuples(index=False):
                    with st.container(border=True):
                        st.markdown(f"**{row.Title}**"); st.caption(f"{row.Publisher} · {row.Published}")
                        if row.URL: st.link_button("Open source", row.URL)

    elif section.startswith("6"):
        st.subheader("Sector Rotation Dashboard")
        period = st.selectbox("Lookback", ["3mo", "6mo", "1y"], index=1)
        if st.button("Analyze sector rotation", type="primary"):
            try:
                with st.spinner("Comparing US sector ETFs..."): st.session_state.v5_sectors = sector_rotation(period)
            except Exception as error: st.error(str(error))
        sectors = st.session_state.get("v5_sectors")
        if isinstance(sectors, pd.DataFrame):
            if sectors.empty: st.warning("No sector price history was returned.")
            else:
                st.bar_chart(sectors.set_index("Sector")[["1M return", "3M return", "6M return"]]); st.dataframe(sectors, hide_index=True, width="stretch")

    elif section.startswith("7"):
        st.subheader("Stock Scenario Lab")
        st.caption("Stress revenue growth, margins, and valuation multiples. Results are scenarios, not forecasts.")
        symbol = _symbol_input("Company symbol", universe, "v5_scenario_symbol")
        if not universe.empty and symbol in universe.Symbol.values:
            row = universe.loc[universe.Symbol == symbol].iloc[0]
            price = float(row.get("Price", 100)); base_growth = float(row.get("Revenue growth", 5)); margin = float(row.get("Operating margin", 15)); pe = float(row.get("Forward P/E", 20) or 20)
        else: price, base_growth, margin, pe = 100.0, 5.0, 15.0, 20.0
        cols = st.columns(3); price = cols[0].number_input("Current price", min_value=0.01, value=max(price, 0.01)); years = cols[1].slider("Years", 1, 10, 3); pe = cols[2].number_input("Current forward P/E", min_value=1.0, value=max(pe, 1.0))
        assumptions = {}
        for name, offsets in (("Bear", (-8, -5, -5)), ("Base", (0, 0, 0)), ("Bull", (8, 5, 5))):
            with st.expander(f"{name} assumptions", expanded=name == "Base"):
                c = st.columns(3); growth = c[0].number_input("Revenue growth %", value=base_growth + offsets[0], key=f"v5_{name}_growth"); scenario_margin = c[1].number_input("Operating margin %", value=margin + offsets[1], key=f"v5_{name}_margin"); exit_pe = c[2].number_input("Exit P/E", min_value=1.0, value=max(pe + offsets[2], 1.0), key=f"v5_{name}_pe")
                assumptions[name] = (growth, scenario_margin, exit_pe)
        scenarios = scenario_table(price, base_growth, margin, pe, years, assumptions)
        st.bar_chart(scenarios.set_index("Scenario")["Estimated price"]); st.dataframe(scenarios, hide_index=True, width="stretch")

    elif section.startswith("8"):
        st.subheader("Portfolio Tax Center")
        st.caption("FIFO estimate for education and planning. Confirm tax treatment with a qualified professional.")
        template = pd.DataFrame({"Date": ["2025-01-10", "2026-02-15"], "Symbol": ["AAPL", "AAPL"], "Side": ["BUY", "SELL"], "Shares": [10, 5], "Price": [190, 230]})
        st.download_button("Download trade template", template.to_csv(index=False), "tax-trades-template.csv", "text/csv")
        upload = st.file_uploader("Trade-history CSV", type="csv", key="v5_tax_upload")
        if upload:
            try:
                trades = pd.read_csv(io.BytesIO(upload.getvalue())); realized, metrics = fifo_tax_lots(trades)
                cols = st.columns(3); cols[0].metric("Realized gain/loss", f"${metrics['Realized gain/loss']:,.2f}"); cols[1].metric("Short-term", f"${metrics['Short-term']:,.2f}"); cols[2].metric("Long-term", f"${metrics['Long-term']:,.2f}")
                st.dataframe(realized, hide_index=True, width="stretch")
                st.download_button("Download tax-lot estimate", realized.to_csv(index=False), "tax-lot-estimate.csv", "text/csv")
            except Exception as error: st.error(str(error))

    else:
        st.subheader("Management Quality Score")
        st.caption("Transparent proxy based on profitability, growth, leverage, and the app’s quality model. It does not measure character or private board information.")
        if universe.empty:
            st.info("Load the V3 research universe to score management quality from comparable company metrics."); return
        symbol = st.selectbox("Company", universe.Symbol.tolist(), key="v5_management_symbol")
        row = universe.loc[universe.Symbol == symbol].iloc[0].to_dict(); score, reasons = management_score(row)
        st.metric("Management quality proxy", f"{score}/100", border=True)
        st.progress(score)
        for reason in reasons: st.write(f"• {reason}")

