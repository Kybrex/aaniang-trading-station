"""AANIANG V2 decision-center interface."""
from __future__ import annotations

import os
from pathlib import Path
import pandas as pd
import streamlit as st

from advanced import backtest_metrics,bracket_plan,detect_setups,multi_timeframe
from data import best_symbol_frame,cached_frame
from investor import company_events,compare_companies,dcf_valuation,fundamental_history,fundamental_snapshot,search_symbols
from notifications import send_email,send_telegram
from portfolio import correlation_matrix,journal_analytics,portfolio_snapshot
from reporting import excel_workbook,table_pdf
from research import backtest,evaluate_alerts
from storage import add_event,add_position,events,journal,newly_triggered,positions,save_positions,watchlist


def _secret(name: str) -> str:
    try:return str(st.secrets.get(name,""))
    except Exception:return os.getenv(name,"")


def _metric_row(metrics: dict[str,float], keys: list[str]) -> None:
    columns=st.columns(len(keys))
    for column,key in zip(columns,keys):
        value=metrics.get(key,0);column.metric(key,f"{value:,.2f}" if isinstance(value,(int,float)) else str(value))


def render(results: pd.DataFrame, equity: float) -> None:
    st.divider();st.header("AANIANG V2 Decision Center")
    st.caption("12 modules: resilient data, professional backtests, multi-timeframe analysis, validated setups, portfolio risk, trade plans, notifications, journal analytics, fundamentals, valuation, investment portfolio, and research/exports.")
    market_tab,strategy_tab,risk_tab,investor_tab,alerts_tab,research_tab=st.tabs(["Market & timeframes","Strategies & backtest","Portfolio risk","Investor","Alerts & journal","Research & exports"])
    alpha_key=_secret("ALPHAVANTAGE_API_KEY")

    with market_tab:
        symbol=st.text_input("Symbol for multi-timeframe analysis",value=(str(results.iloc[0].Symbol) if not results.empty else "AAPL"),key="mtf_symbol").upper().strip()
        if st.button("Analyze weekly / daily / 4-hour",key="mtf_run") and symbol:
            with st.spinner("Loading three timeframes..."):
                summary,alignment=multi_timeframe(symbol,alpha_key);frame,source=best_symbol_frame(symbol,period="2y",minimum_rows=200,api_key=alpha_key);spy=cached_frame("SPY",21);setups=detect_setups(frame,spy)
            st.session_state.mtf_summary=summary;st.session_state.mtf_alignment=alignment;st.session_state.setup_lab=setups
        if "mtf_summary" in st.session_state:
            st.info(st.session_state.mtf_alignment);st.dataframe(st.session_state.mtf_summary,hide_index=True,width="stretch")
            ready=st.session_state.setup_lab;st.subheader("Validated setup laboratory");st.dataframe(ready,hide_index=True,width="stretch")
        st.caption("Alpha Vantage daily fallback: configured" if alpha_key else "Optional fallback inactive: add ALPHAVANTAGE_API_KEY to Streamlit Secrets.")

    with strategy_tab:
        candidates=results.Symbol.astype(str).tolist() if not results.empty else ["AAPL"]
        symbol=st.selectbox("Candidate",candidates,key="strategy_symbol");setup=st.selectbox("Strategy",["Breakout","EMA pullback"],key="strategy_setup");side=st.selectbox("Direction",["LONG","SHORT"],key="strategy_side")
        if st.button("Run professional backtest",key="advanced_backtest"):
            trades=backtest(symbol,side,setup=setup);metrics,curve=backtest_metrics(trades);st.session_state.advanced_trades=trades;st.session_state.advanced_metrics=metrics;st.session_state.advanced_curve=curve
        metrics=st.session_state.get("advanced_metrics",{})
        if metrics:
            _metric_row(metrics,["Trades","Win rate","Expectancy R","Profit factor","Max drawdown %"]);curve=st.session_state.advanced_curve;st.line_chart(curve.set_index("Date")["Equity"]);st.dataframe(st.session_state.advanced_trades.tail(50),hide_index=True,width="stretch")
            st.caption("Includes a 0.05R cost/slippage allowance and a 70/30 in-sample/out-of-sample label. Historical results do not guarantee future performance.")
        st.subheader("Bracket / OCO order planner")
        if not results.empty:
            selected=results.loc[results.Symbol==symbol].iloc[0];shares=int(selected.Shares);plan=bracket_plan(symbol,str(selected.Signal),float(selected.Entry),float(selected.Stop),float(selected["Target 1"]),float(selected["Target 2"]),shares);st.dataframe(plan,hide_index=True,width="stretch");st.download_button("Download order plan CSV",plan.to_csv(index=False).encode(),f"{symbol}_bracket.csv","text/csv")
        else:st.info("Run the market scanner first to prepare a bracket plan.")

    with risk_tab:
        st.subheader("Add or update a position")
        with st.form("position_form",clear_on_submit=True):
            c1,c2,c3,c4=st.columns(4);p_symbol=c1.text_input("Symbol").upper();p_shares=c2.number_input("Shares",min_value=0.0);p_cost=c3.number_input("Average cost",min_value=0.0);p_stop=c4.number_input("Protective stop",min_value=0.0)
            c5,c6,c7,c8=st.columns(4);p_sector=c5.text_input("Sector",value="Unknown");p_country=c6.text_input("Country",value="USA");p_currency=c7.text_input("Currency",value="USD");p_purpose=c8.selectbox("Purpose",["Swing","Investment"])
            c9,c10=st.columns(2);p_dividend=c9.number_input("Dividend yield %",min_value=0.0);p_target=c10.number_input("Target portfolio weight %",min_value=0.0,max_value=100.0)
            if st.form_submit_button("Save position") and p_symbol:add_position({"Symbol":p_symbol,"Shares":p_shares,"Cost":p_cost,"Stop":p_stop,"Sector":p_sector,"Country":p_country,"Currency":p_currency,"Purpose":p_purpose,"Dividend Yield":p_dividend,"Target Weight":p_target});st.success("Position saved.")
        upload=st.file_uploader("Import positions CSV",type=["csv"],key="positions_upload")
        if upload is not None and st.button("Replace positions with uploaded CSV"):
            imported=pd.read_csv(upload);required={"Symbol","Shares","Cost","Stop","Sector","Country","Currency","Purpose","Dividend Yield","Target Weight"}
            if required.issubset(imported.columns):save_positions(imported);st.success("Positions imported.")
            else:st.error("CSV columns required: "+", ".join(sorted(required)))
        saved=positions();st.dataframe(saved,hide_index=True,width="stretch")
        if not saved.empty and st.button("Calculate portfolio exposure and risk"):
            detail,metrics,sector,purpose,corr=portfolio_snapshot(saved,equity);st.session_state.portfolio_analysis=(detail,metrics,sector,purpose,corr)
        if "portfolio_analysis" in st.session_state:
            detail,metrics,sector,purpose,corr=st.session_state.portfolio_analysis;_metric_row(metrics,["Market value","Unrealized P/L","Portfolio heat %","Largest position %","Annual dividends"]);st.dataframe(detail,hide_index=True,width="stretch");c1,c2=st.columns(2);c1.bar_chart(sector.set_index("Sector")["Weight %"]);c2.bar_chart(purpose.set_index("Purpose")["Weight %"])
            if metrics["Portfolio heat %"]>5:st.warning("Portfolio heat exceeds 5%. Consider reducing position risk.")
            if not sector.empty and sector["Weight %"].max()>35:st.warning("Sector concentration exceeds 35%.")
            if not corr.empty:
                st.subheader("Position correlation");st.dataframe(corr,width="stretch")
                pairs=[f"{a}/{b}" for i,a in enumerate(corr.columns) for b in corr.columns[i+1:] if corr.loc[a,b]>=.80]
                if pairs:st.warning("Highly correlated positions: "+", ".join(pairs))
        st.download_button("Download positions backup",saved.to_csv(index=False).encode(),"aaniang_positions.csv","text/csv",disabled=saved.empty)

    with investor_tab:
        symbol=st.text_input("Company symbol",value="AAPL",key="fund_symbol").upper().strip()
        if st.button("Analyze fundamentals",key="fund_run") and symbol:
            with st.spinner("Reading company fundamentals..."):st.session_state.fundamental=fundamental_snapshot(symbol);st.session_state.fundamental_history=fundamental_history(symbol)
        snapshot=st.session_state.get("fundamental")
        if snapshot:
            if snapshot.get("Status")=="Unavailable":st.warning("Fundamental data unavailable.")
            else:
                st.subheader(str(snapshot.get("Company",symbol)));st.info("Research classification: "+str(snapshot.get("Research classification"))+" — analytical label, not investment advice.");_metric_row(snapshot,["Quality score","Growth score","Valuation score","ROE %","FCF yield %"]);st.dataframe(pd.DataFrame([snapshot]),hide_index=True,width="stretch")
                history=st.session_state.get("fundamental_history",pd.DataFrame())
                if not history.empty:st.subheader("Available annual history");st.dataframe(history,hide_index=True,width="stretch")
                st.subheader("DCF scenarios")
                fcf=float(snapshot.get("Free cash flow") or 0);shares=float(snapshot.get("Shares") or 0);net_debt=float(snapshot.get("Net debt") or 0)
                dcf_rows=[]
                for name,growth,discount in [("Bear",.03,.11),("Base",.08,.10),("Bull",.13,.09)]:
                    row=dcf_valuation(fcf,shares,net_debt,growth,.025,discount);row["Scenario"]=name;dcf_rows.append(row)
                dcf=pd.DataFrame(dcf_rows);st.dataframe(dcf,hide_index=True,width="stretch")
        compare_text=st.text_input("Compare symbols (comma-separated)",value="AAPL,MSFT,GOOGL")
        if st.button("Compare companies"):
            symbols=[item.strip().upper() for item in compare_text.split(",") if item.strip()][:6]
            with st.spinner("Comparing companies..."):st.session_state.company_comparison=compare_companies(symbols)
        if "company_comparison" in st.session_state:st.dataframe(st.session_state.company_comparison,hide_index=True,width="stretch")

    with alerts_tab:
        saved_watch=watchlist();st.dataframe(saved_watch,hide_index=True,width="stretch")
        if st.button("Evaluate and notify triggered alerts",disabled=saved_watch.empty):
            evaluated=evaluate_alerts(saved_watch);triggered=newly_triggered(evaluated);st.dataframe(evaluated,hide_index=True,width="stretch")
            if triggered.empty:st.info("No new alert transition is triggered.")
            else:
                message="AANIANG alerts\n"+"\n".join(f"{row.Symbol}: {row.Alert} at {row['Last price']}" for _,row in triggered.iterrows())
                telegram=send_telegram(message,_secret("TELEGRAM_BOT_TOKEN"),_secret("TELEGRAM_CHAT_ID"));email=send_email(message,"AANIANG Trading Alert",_secret("SMTP_HOST"),int(_secret("SMTP_PORT") or 587),_secret("SMTP_USER"),_secret("SMTP_PASSWORD"),_secret("ALERT_EMAIL"));st.info(telegram[1]);st.info(email[1])
        st.caption("For alerts while Streamlit is closed, run `python alert_worker.py` periodically with Windows Task Scheduler or cron. Credentials remain in environment variables or Streamlit Secrets.")
        enriched,metrics,by_setup=journal_analytics(journal());st.subheader("Journal analytics")
        if metrics:_metric_row(metrics,["Trades","Net P/L","Win rate %","Average R","Profit factor"]);st.dataframe(by_setup,hide_index=True,width="stretch");st.dataframe(enriched,hide_index=True,width="stretch")
        else:st.info("Record completed trades in the journal to unlock analytics.")

    with research_tab:
        query=st.text_input("Search a ticker or company",key="company_search")
        if st.button("Search",key="search_button"):
            with st.spinner("Searching..."):st.session_state.search_results=search_symbols(query,alpha_key)
        if "search_results" in st.session_state:st.dataframe(st.session_state.search_results,hide_index=True,width="stretch")
        event_symbol=st.text_input("Company calendar symbol",value="AAPL",key="event_symbol").upper()
        if st.button("Load company calendar"):
            with st.spinner("Loading calendar..."):st.session_state.company_events=company_events(event_symbol)
        if "company_events" in st.session_state:st.dataframe(st.session_state.company_events,hide_index=True,width="stretch")
        with st.form("manual_event",clear_on_submit=True):
            e1,e2,e3=st.columns(3);event_date=e1.date_input("Date");event_type=e2.selectbox("Type",["Earnings","Dividend","Economic","Company","Other"]);event_symbol=e3.text_input("Symbol (optional)").upper();event_name=st.text_input("Event");event_notes=st.text_input("Notes")
            if st.form_submit_button("Add calendar event") and event_name:add_event({"Date":event_date.isoformat(),"Type":event_type,"Symbol":event_symbol,"Event":event_name,"Notes":event_notes});st.success("Event added.")
        saved_events=events();st.dataframe(saved_events.sort_values("Date") if not saved_events.empty else saved_events,hide_index=True,width="stretch")
        sheets={"Scanner":results,"Positions":positions(),"Journal":journal(),"Calendar":saved_events}
        if "company_comparison" in st.session_state:sheets["Company comparison"]=st.session_state.company_comparison
        st.subheader("Printable reports")
        st.download_button("Download complete Excel workbook",excel_workbook(sheets),"aaniang_trading_station.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        pdf_columns=[column for column in ["Symbol","Data date","Score","Signal","Setup","Entry","Stop","Risk/Share","20D Momentum","Earnings","Shares"] if column in results]
        printable=results[pdf_columns].head(50)
        pdf_bytes=table_pdf("AANIANG Trading Station — Ranked Opportunities",printable,"Daily adjusted research data. Verify prices before trading.") if not printable.empty else b""
        st.download_button("Download scanner PDF",pdf_bytes,"aaniang_scanner.pdf","application/pdf",disabled=printable.empty)
