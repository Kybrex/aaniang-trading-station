"""Streamlit UI for the AANIANG one-click complete research report."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from v7_features import complete_stock_research
from v7_pdf import complete_research_pdf


def _secret(name: str) -> str:
    try: return str(st.secrets.get(name, ""))
    except Exception: return ""


def render() -> None:
    st.divider(); st.header("AANIANG V7 Complete Stock Research")
    st.caption("Select one ticker, run the stock-specific research modules together, and download a consolidated PDF.")
    universe = st.session_state.get("v3_universe_data", pd.DataFrame())
    symbols = universe.Symbol.tolist() if not universe.empty and "Symbol" in universe else []
    symbol = st.selectbox("Stock symbol", symbols, key="v7_symbol") if symbols else st.text_input("Stock symbol", "AAPL", key="v7_symbol").strip().upper()
    if st.button("Run complete research", type="primary", icon=":material/manage_search:", width="stretch"):
        try:
            with st.spinner("Running fundamentals, valuation, technicals, management, ownership, dividends, catalysts, and risk checks..."):
                report = complete_stock_research(symbol, _secret("FMP_API_KEY"), universe)
                st.session_state.v7_report = report
                st.session_state.v7_pdf = complete_research_pdf(report)
        except Exception as exc:
            st.error(f"Research could not be completed: {exc}")
    report = st.session_state.get("v7_report")
    if report:
        snap = report["snapshot"]; cols = st.columns(4)
        cols[0].metric("Price", f"${snap.get('Price', 0):,.2f}", border=True)
        cols[1].metric("Quality", f"{snap['Quality']}/100" if snap.get("Quality") is not None else "Unavailable", border=True)
        cols[2].metric("Technical", f"{report['technical_score']}/100", border=True)
        cols[3].metric("Management", f"{report['management_score']}/100" if report["management_score"] is not None else "Unavailable", border=True)
        score_cols = st.columns(2)
        score_cols[0].metric("Professional score", f"{report['overall_score']}/100", border=True)
        score_cols[1].metric("Research classification", report["classification"], border=True)
        st.success(f"Complete report ready for {report['symbol']}. Included all ticker-only modules; {len(report['errors'])} data feeds reported limitations.")
        with st.expander("AI Research Summary", expanded=True):
            for heading, narrative in report.get("ai_summary", {}).items():
                st.markdown(f"**{heading}**")
                st.write(narrative)
        with st.expander("Professional report additions"):
            st.write("Overall score · Bull/Base/Bear valuation · Financial trends · Risk dashboard · Peer comparison · Catalyst timeline · Analyst estimates · Trade plan · Investment checklist")
            st.dataframe(report["checklist"], hide_index=True, width="stretch")
        with st.expander("Due-Diligence Pack — 12 additional sections"):
            dd_cols=st.columns(3)
            dd_cols[0].metric("Moat score",f"{report['moat_score']}/100",border=True)
            dd_cols[1].metric("Recession resilience",f"{report['recession_score']}/100",border=True)
            dd_cols[2].metric("Red flags",len(report["red_flags"]),border=True)
            st.caption("SEC filings · estimate revisions · moat · recession resilience · cash-flow quality · dilution/buybacks · valuation range · earnings surprises · red flags · competitors · probability outlook · sources")
        st.download_button("Download complete stock research (PDF)", st.session_state.v7_pdf,
            f"{report['symbol']}-complete-research.pdf", "application/pdf", icon=":material/picture_as_pdf:", type="primary")

