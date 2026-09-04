"""Streamlit UI for the nine AANIANG V3 expansion modules."""
from __future__ import annotations

import io
import pandas as pd
import plotly.express as px
import streamlit as st

from v3_features import PRESETS, apply_screen, comparison_performance, load_notes, load_snapshot, peer_rank, portfolio_health, research_brief, save_note, scan_symbols
from v3_pdf import research_pdf


DEFAULT_SYMBOLS = "AAPL, MSFT, NVDA, AMZN, GOOGL, META, AVGO, JPM, V, MA, COST, WMT, KO, PEP, UNH, LLY, XOM, CVX, CAT, GE, PLTR, NFLX, AMD, CRM, ORCL, HD, NKE, DIS, BA, TSLA"


def _secret(name: str) -> str:
    try: return str(st.secrets.get(name, ""))
    except Exception: return ""


@st.cache_data(ttl=1800, max_entries=12, show_spinner=False)
def _scan(symbols: tuple[str, ...], fmp_key: str) -> pd.DataFrame:
    return scan_symbols(list(symbols), fmp_key)


@st.cache_data(ttl=900, max_entries=50, show_spinner=False)
def _single(symbol: str, fmp_key: str) -> dict | None:
    return load_snapshot(symbol, fmp_key)


@st.cache_data(ttl=900, max_entries=20, show_spinner=False)
def _comparison_history(symbols: tuple[str, ...]) -> pd.DataFrame:
    return comparison_performance(list(symbols))


def _symbols(text: str) -> list[str]:
    return list(dict.fromkeys(value.strip().upper() for value in text.replace("\n", ",").split(",") if value.strip()))[:100]


def _table(frame: pd.DataFrame) -> None:
    display = frame[[column for column in ["Symbol", "Company", "Sector", "Quality", "Price", "Value gap", "Revenue growth", "Operating margin", "Debt/Equity", "Forward P/E", "1M return", "6M return"] if column in frame]]
    st.dataframe(display, hide_index=True, width="stretch", column_config={
        "Quality": st.column_config.ProgressColumn(min_value=0, max_value=100),
        "Price": st.column_config.NumberColumn(format="$%.2f"),
        "Value gap": st.column_config.NumberColumn(format="%.1f%%"),
        "Revenue growth": st.column_config.NumberColumn(format="%.1f%%"),
        "Operating margin": st.column_config.NumberColumn(format="%.1f%%"),
        "1M return": st.column_config.NumberColumn(format="%.1f%%"),
        "6M return": st.column_config.NumberColumn(format="%.1f%%"),
    })


def render() -> None:
    st.divider()
    st.header("AANIANG V3 Discovery Center")
    st.caption("Nine connected modules for discovery, comparison, research, portfolio monitoring, notes, and data quality.")
    fmp_key = _secret("FMP_API_KEY")
    with st.form("v3_universe", border=True):
        universe_text = st.text_area("Research universe (comma separated, maximum 100)", value=DEFAULT_SYMBOLS, height=90)
        load_universe = st.form_submit_button("Load V3 research universe", type="primary", icon=":material/database:")
    if load_universe:
        symbols = tuple(_symbols(universe_text))
        with st.spinner(f"Loading comparable data for {len(symbols)} companies..."):
            st.session_state.v3_universe_data = _scan(symbols, fmp_key)
    universe = st.session_state.get("v3_universe_data", pd.DataFrame())
    if universe.empty:
        st.info("Load the research universe once, then use all nine modules without downloading the same data again.")

    st.markdown("**Quick access — all nine modules**")
    quick_modules = [
        ("1 · Value Radar", ":material/radar:"),
        ("2 · Stock comparison", ":material/compare_arrows:"),
        ("3 · Advanced screener", ":material/filter_alt:"),
        ("4 · Screening strategies", ":material/strategy:"),
        ("5 · AI research report", ":material/description:"),
        ("6 · Industry peers", ":material/groups:"),
        ("7 · Notes and checklist", ":material/checklist:"),
        ("8 · Portfolio health", ":material/monitoring:"),
        ("9 · Professional data", ":material/database:"),
    ]
    for row_start in range(0, len(quick_modules), 3):
        columns = st.columns(3)
        for column, (label, icon) in zip(columns, quick_modules[row_start:row_start + 3]):
            with column:
                if st.button(label, icon=icon, width="stretch", key=f"quick_{label[0]}"):
                    st.session_state.v3_section = label

    section = st.selectbox("V3 module", [
        "1 · Value Radar", "2 · Stock comparison", "3 · Advanced screener", "4 · Screening strategies",
        "5 · AI research report", "6 · Industry peers", "7 · Notes and checklist",
        "8 · Portfolio health", "9 · Professional data",
    ], key="v3_section")

    if section.startswith("1"):
        st.subheader("Value Radar and market heatmap")
        if universe.empty: return
        color_metric = st.selectbox("Color tiles by", ["Value gap", "Quality", "1M return", "6M return", "1Y return"])
        radar = universe.dropna(subset=["Market cap", color_metric]).copy()
        if radar.empty: st.warning("No usable radar data is available for this selection."); return
        radar["Tile size"] = radar["Market cap"].clip(lower=1)
        figure = px.treemap(radar, path=[px.Constant("Market"), "Sector", "Symbol"], values="Tile size", color=color_metric, hover_data=["Company", "Price", "Quality", "Value gap"], color_continuous_scale="RdYlGn", color_continuous_midpoint=0 if color_metric != "Quality" else 50)
        figure.update_layout(margin=dict(t=30, l=5, r=5, b=5), height=650)
        st.plotly_chart(figure, width="stretch", config={"displaylogo": False})
        _table(universe.sort_values(color_metric, ascending=False, na_position="last"))

    elif section.startswith("2"):
        st.subheader("Multi-stock comparison")
        st.caption("Enter stock symbols directly. Loading the V3 research universe first is optional.")
        default_compare = ", ".join(universe.Symbol.head(5).tolist()) if not universe.empty else "AAPL, MSFT, NVDA"
        with st.form("direct_stock_comparison", border=True):
            compare_text = st.text_input("Stock symbols to compare", default_compare, help="Comma separated; maximum 30 stocks")
            bench_a, bench_b = st.columns(2)
            include_sp500 = bench_a.checkbox("Compare with S&P 500 (SPY)", value=True)
            include_nasdaq = bench_b.checkbox("Compare with Nasdaq-100 (QQQ)", value=True)
            run_compare = st.form_submit_button("Load comparison", type="primary", icon=":material/compare_arrows:")
        if run_compare:
            stocks = _symbols(compare_text)[:30]
            benchmarks = (["SPY"] if include_sp500 else []) + (["QQQ"] if include_nasdaq else [])
            all_symbols = tuple(dict.fromkeys(stocks + benchmarks))
            if not stocks: st.warning("Enter at least one stock symbol.")
            else:
                with st.spinner(f"Loading {len(all_symbols)} comparison symbols..."):
                    st.session_state.v3_compare_data = _scan(all_symbols, fmp_key)
                    st.session_state.v3_compare_history = _comparison_history(all_symbols)
                    st.session_state.v3_compare_stocks = stocks
                    st.session_state.v3_compare_benchmarks = benchmarks
        compared = st.session_state.get("v3_compare_data", pd.DataFrame())
        performance = st.session_state.get("v3_compare_history", pd.DataFrame())
        if compared.empty and performance.empty:
            st.info("Enter symbols and tap Load comparison. You do not need to load the research universe above.")
        else:
            if not performance.empty:
                labels = {"SPY":"S&P 500 (SPY)", "QQQ":"Nasdaq-100 (QQQ)"}
                chart = performance.rename(columns=labels)
                st.subheader("One-year relative performance")
                st.caption("Every series starts at 100, making stocks and indexes directly comparable.")
                st.line_chart(chart, height=430)
                returns = (performance.iloc[-1] - 100).sort_values(ascending=False).rename("1Y return %").reset_index(names="Symbol")
                returns["Name"] = returns.Symbol.map(labels).fillna(returns.Symbol)
                st.dataframe(returns[["Name", "1Y return %"]], hide_index=True, width="stretch", column_config={"1Y return %":st.column_config.NumberColumn(format="%.1f%%")})
            if not compared.empty:
                st.subheader("Fundamental comparison")
                score_columns = [column for column in ["Quality", "ROE", "Operating margin", "Revenue growth", "Earnings growth", "Value gap"] if column in compared]
                score_data = compared.set_index("Symbol")[score_columns].dropna(how="all")
                if not score_data.empty: st.bar_chart(score_data, height=420)
                _table(compared)

    elif section.startswith("3"):
        st.subheader("Advanced fundamental screener")
        if universe.empty: return
        with st.form("advanced_screen", border=True):
            min_quality = st.slider("Minimum quality", 0, 100, 55)
            min_growth = st.slider("Minimum revenue growth (%)", -50, 100, 0)
            min_margin = st.slider("Minimum operating margin (%)", -50, 60, 0)
            max_debt = st.slider("Maximum debt/equity (%)", 0, 500, 200)
            min_gap = st.slider("Minimum value gap (%)", -100, 100, -100)
            max_pe = st.slider("Maximum forward P/E", 5, 100, 50)
            run_filter = st.form_submit_button("Apply filters", type="primary")
        if run_filter:
            rules = {"min_quality": min_quality, "min_growth": min_growth, "min_margin": min_margin, "max_debt": max_debt, "min_value_gap": min_gap, "max_forward_pe": max_pe}
            st.session_state.v3_screen = apply_screen(universe, rules)
        screened = st.session_state.get("v3_screen", universe)
        st.metric("Matching companies", len(screened), border=True); _table(screened)
        st.download_button("Download screen", screened.to_csv(index=False), "aaniang-v3-screen.csv", "text/csv")

    elif section.startswith("4"):
        st.subheader("One-click screening strategies")
        if universe.empty: return
        preset = st.selectbox("Strategy", list(PRESETS))
        selected = apply_screen(universe, PRESETS[preset])
        st.caption("Transparent preset rules: " + (", ".join(f"{key}={value}" for key, value in PRESETS[preset].items()) or "No filters"))
        st.metric("Candidates", len(selected), border=True); _table(selected)

    elif section.startswith("5"):
        st.subheader("AI-ready research report")
        if universe.empty: return
        symbol = st.selectbox("Company", universe.Symbol.tolist(), key="v3_report_symbol")
        row = universe.loc[universe.Symbol == symbol].iloc[0].to_dict(); brief = research_brief(row)
        st.caption("Evidence-based first draft. It separates facts from inference and provides questions for deeper research.")
        for heading, points in brief.items():
            with st.container(border=True):
                st.markdown(f"**{heading}**")
                for point in points: st.write(f"• {point}")
        company = str(row.get("Company") or symbol)
        report_pdf = research_pdf(symbol, company, brief)
        st.download_button(
            "Download research report (PDF)",
            report_pdf,
            f"{symbol}-research-report.pdf",
            "application/pdf",
            icon=":material/picture_as_pdf:",
        )

    elif section.startswith("6"):
        st.subheader("Industry peer discovery")
        if universe.empty: return
        symbol = st.selectbox("Find peers for", universe.Symbol.tolist(), key="v3_peer_symbol")
        peers = peer_rank(universe, symbol)
        if len(peers) < 2: st.warning("Add more companies from the same sector or industry to the research universe.")
        else:
            st.caption(f"Ranks companies sharing the selected company’s industry or sector. {len(peers)} peers found.")
            _table(peers)

    elif section.startswith("7"):
        st.subheader("Personal notes and investment checklist")
        available = universe.Symbol.tolist() if not universe.empty else ["AAPL"]
        symbol = st.selectbox("Ticker", available, key="v3_note_symbol")
        saved = load_notes().get(symbol, {})
        with st.form("v3_note", border=True):
            thesis = st.text_area("Investment thesis", value=saved.get("thesis", ""))
            risks = st.text_area("Principal risks", value=saved.get("risks", ""))
            buy_price = st.number_input("Desired purchase price", min_value=0.0, value=float(saved.get("buy_price", 0)))
            sell_reason = st.text_area("Reasons to sell", value=saved.get("sell_reason", ""))
            conviction = st.slider("Conviction", 1, 5, int(saved.get("conviction", 3)))
            checklist = st.multiselect("Checklist completed", ["Understand the business", "Review five-year financials", "Check debt", "Test valuation scenarios", "Read risks", "Compare peers"], default=saved.get("checklist", []))
            if st.form_submit_button("Save notes", type="primary"):
                save_note(symbol, {"thesis": thesis, "risks": risks, "buy_price": buy_price, "sell_reason": sell_reason, "conviction": conviction, "checklist": checklist}); st.success("Notes saved.")

    elif section.startswith("8"):
        st.subheader("Portfolio health monitor")
        st.caption("Upload CSV columns: Symbol, Shares, Cost. Cost means average cost per share.")
        template = pd.DataFrame({"Symbol": ["AAPL", "MSFT"], "Shares": [10, 5], "Cost": [200, 350]})
        st.download_button("Download portfolio template", template.to_csv(index=False), "portfolio-template.csv", "text/csv")
        upload = st.file_uploader("Portfolio CSV", type="csv", key="v3_portfolio")
        if upload:
            try:
                holdings = pd.read_csv(io.BytesIO(upload.getvalue())); symbols = tuple(holdings.Symbol.astype(str).str.upper().unique())
                snapshots = _scan(symbols, fmp_key); portfolio, metrics = portfolio_health(holdings, snapshots)
                with st.container(horizontal=True):
                    st.metric("Portfolio value", f"${metrics['Value']:,.0f}", border=True)
                    st.metric("Gain/loss", f"${metrics['Gain/Loss']:,.0f}", border=True)
                    st.metric("Largest position", f"{metrics['Largest position']:.1f}%", border=True)
                    st.metric("Largest sector", f"{metrics['Largest sector']:.1f}%", border=True)
                    st.metric("Weighted beta", f"{metrics['Weighted beta']:.2f}", border=True)
                warnings = []
                if metrics["Largest position"] > 20: warnings.append("One position exceeds 20% of the portfolio.")
                if metrics["Largest sector"] > 35: warnings.append("One sector exceeds 35% of the portfolio.")
                if metrics["Weighted beta"] > 1.3: warnings.append("Portfolio beta indicates elevated market sensitivity.")
                for warning in warnings: st.warning(warning)
                st.dataframe(portfolio, hide_index=True, width="stretch")
                st.bar_chart(portfolio.groupby("Sector")["Market value"].sum().sort_values(), horizontal=True)
            except Exception as error: st.error(str(error))

    else:
        st.subheader("Professional data center")
        with st.container(horizontal=True):
            st.metric("Yahoo Finance", "Active", border=True)
            st.metric("Financial Modeling Prep", "Configured" if fmp_key else "Optional", border=True)
            st.metric("Cache duration", "15–30 min", border=True)
        st.write("Add `FMP_API_KEY` to Streamlit Secrets to enrich company identity, sector, market-cap, beta, and profile data. Yahoo remains the fallback for price history and ratios.")
        test_symbol = st.text_input("Provider test symbol", "AAPL", key="v3_provider_symbol").upper()
        if st.button("Test data providers", key="v3_provider_test"):
            with st.spinner("Checking data availability..."):
                result = _single(test_symbol, fmp_key)
            if result: st.success(f"Loaded {test_symbol} from {result.get('Source', 'available provider')} at ${result.get('Price', 0):,.2f}.")
            else: st.error("No provider returned usable data. Check the symbol, API key, or temporary rate limits.")

