"""Consolidated research with editable assumptions and a portable notebook."""
from __future__ import annotations
import json
import pandas as pd
import streamlit as st
from v7_features import complete_stock_research
from v7_pdf import complete_research_pdf
from decision_report import build_decision_report, DEFAULTS, fmt
from report_extensions import EXTRA_DEFAULTS, extra_inputs, history_rows

def validate_notebook(data):
    from decision_report import assumptions, num
    if not isinstance(data,dict) or data.get("version")!=1 or not isinstance(data.get("symbol"),str) or not data["symbol"].strip():
        raise ValueError("Unsupported notebook.")
    if not isinstance(data.get("inputs",{}),dict) or not isinstance(data.get("observations",{}),dict):
        raise ValueError("Invalid notebook inputs or observations.")
    result=dict(data, symbol=data["symbol"].strip().upper())
    result["inputs"]=assumptions(data.get("inputs",{}))
    result["inputs"].update(extra_inputs(result["inputs"]))
    result["valuation_history"]=history_rows(data.get("valuation_history",[]))
    result["inputs"]["valuation_history"]=history_rows(result["inputs"].get("valuation_history",[]))
    source=result["inputs"].get("specialist_source", "")
    if not isinstance(source,str): raise ValueError("Specialist source must be text.")
    if (result["inputs"]["ffo_per_share"] or result["inputs"]["book_per_share"]) and not source.strip():
        raise ValueError("Add a source for specialist per-share inputs.")
    for key,columns in [("holdings",["Symbol","Sector","Value"]),("evidence",["Factor","Assessment","Evidence","Source"])]:
        rows=data.get(key,[])
        if not isinstance(rows,list) or len(rows)>1000 or any(not isinstance(row,dict) or not set(columns).issubset(row) for row in rows):
            raise ValueError(f"Invalid {key} table.")
        for row in rows:
            for column in columns:
                value=row[column]
                if column=="Value":
                    if value is not None and (num(value) is None or num(value)<0): raise ValueError("Invalid holding value.")
                elif value is not None and not isinstance(value,str): raise ValueError(f"{column} must be text.")
        result[key]=rows
    return result

def _secret(name):
    try: return str(st.secrets.get(name,""))
    except Exception: return ""

def _notebook(report, inputs, holdings, evidence):
    d=report["decision"]
    return dict(version=1, symbol=report["symbol"], generated=d["generated"],
                observations=d["observations"], inputs=inputs, valuation_history=d["valuation_history"],
                holdings=holdings.astype(object).where(holdings.notna(),None).to_dict("records"), evidence=evidence.astype(object).where(evidence.notna(),None).to_dict("records"))

def render():
    st.divider(); st.header("AANIANG Complete Investment Decision Report")
    st.caption("Sixteen connected investment sections, technical context, and a sourced PDF. All valuations are editable model estimates.")
    symbol=st.text_input("Stock symbol","AAPL",key="v7_symbol").strip().upper()
    with st.expander("Valuation assumptions and portfolio inputs"):
        st.caption("Defaults are illustrative research assumptions, not analyst forecasts. Rates are percentages.")
        imported=st.file_uploader("Restore research notebook",type=["json"],key="decision_import")
        if st.button("Restore notebook",key="decision_restore"):
            try:
                if imported is None: raise ValueError("Choose a notebook first.")
                if imported.size>2_000_000: raise ValueError("Notebook must be smaller than 2 MB.")
                data=validate_notebook(json.loads(imported.getvalue()))
                st.session_state["decision_baselines"]={**st.session_state.get("decision_baselines",{}),data["symbol"]:data}
                st.session_state["decision_comparison_baseline"]=data
                for key,value in data.get("inputs",{}).items():
                    if key in DEFAULTS or key in EXTRA_DEFAULTS or key=="specialist_source": st.session_state["dr_"+key]=value
                st.session_state["decision_history_seed"]=data["inputs"].get("valuation_history",[])
                st.session_state.pop("decision_history_editor",None)
                st.session_state["decision_holdings_seed"]=data.get("holdings",[])
                st.session_state["decision_evidence_seed"]=data.get("evidence",[])
                st.session_state.pop("decision_holdings_editor",None)
                st.session_state.pop("decision_evidence_editor",None)
                st.success("Notebook restored. Enter its stock symbol above, then run or rebuild the report.")
            except Exception as exc: st.error(f"Notebook was not restored: {exc}")
        inputs={}
        fields=[("growth","Annual EPS / FCF / FFO growth (%)",-40.,40.,5.),
                ("discount","Required return / discount rate (%)",.1,40.,10.),
                ("terminal_growth","Long-run cash-flow growth (%)",-5.,15.,2.5),
                ("exit_multiple","Exit P/E or P/FFO multiple",.1,100.,18.),
                ("margin_safety","Margin of safety (%)",0.,90.,25.)]
        cols=st.columns(2)
        for i,(key,label,low,high,default) in enumerate(fields):
            inputs[key]=cols[i%2].number_input(label,min_value=low,max_value=high,value=default,key="dr_"+key)
        inputs["years"]=st.number_input("Investment horizon (years)",min_value=1,max_value=15,value=5,key="dr_years")
        st.caption("REITs require sourced FFO/share. Book value can supplement bank and insurer valuation. Enter per-share values in the stock's trading currency.")
        inputs["ffo_per_share"]=st.number_input("FFO per share (optional)",min_value=0.01,value=None,key="dr_ffo_per_share")
        inputs["book_per_share"]=st.number_input("Book value per share (optional)",min_value=0.01,value=None,key="dr_book_per_share")
        inputs["specialist_source"]=st.text_input("Specialist input source and reporting period",key="dr_specialist_source")
        st.caption("Portfolio values must use one currency. Total includes existing holdings and available cash.")
        for key,label,default in [("portfolio_value","Total portfolio value",0.),("planned_amount","Planned purchase amount",0.),("position_cap","Maximum company allocation (%)",5.),("loss_budget","Portfolio loss budget at bear value (%)",1.)]:
            inputs[key]=st.number_input(label,min_value=0. if key in ("portfolio_value","planned_amount") else .1,value=default,key="dr_"+key)
        holding_seed=pd.DataFrame(st.session_state.get("decision_holdings_seed",[]),columns=["Symbol","Sector","Value"]).astype({"Symbol":"string","Sector":"string","Value":"float64"})
        holdings=st.data_editor(holding_seed,num_rows="dynamic",hide_index=True,key="decision_holdings_editor",column_config={"Value":st.column_config.NumberColumn(min_value=0.)})
        st.caption("Add 3-5 peer tickers to retrieve comparable company snapshots. Leave blank to use the loaded V3 universe.")
        peer_symbols=st.text_input("Peer symbols (comma separated)",key="decision_peer_symbols")
    with st.expander("Competitive advantage evidence"):
        evidence=st.data_editor(pd.DataFrame(st.session_state.get("decision_evidence_seed",[
            {"Factor":factor,"Assessment":"Unassessed","Evidence":"","Source":""} for factor in ["Pricing power","Switching costs","Network effects","Cost advantage","Intangible assets"]]
        )),hide_index=True,key="decision_evidence_editor",
            column_config={"Factor":st.column_config.TextColumn(disabled=True),"Assessment":st.column_config.SelectboxColumn(options=["Unassessed","Strengthening","Stable","Weakening"])})
    with st.expander("Return breakdown, stress tests and earnings targets"):
        st.caption("These are editable research assumptions. Total-profit growth and share-count change drive a separate earnings return illustration; they do not change the primary valuation's per-share growth input.")
        labels={"profit_growth":"Total profit / FFO growth per year (%)","share_change":"Share-count change per year (%)","refinance_pct":"Debt repriced in stress test (%)","sales_shock":"Stress sales decline (%)","margin_shock":"Stress margin decline (percentage points)","rate_shock":"Stress borrowing rate increase (percentage points)","target_revenue_growth":"Next-quarter minimum revenue growth (%)","target_margin":"Next-quarter minimum operating margin (%)","target_fcf":"Next-quarter minimum FCF (statement currency)","target_debt_equity":"Maximum debt/equity (%)","target_dilution":"Maximum year-over-year share dilution (%)"}
        for key,label in labels.items():
            inputs[key]=st.number_input(label,value=EXTRA_DEFAULTS[key],key="dr_"+key)
        inputs["annual_dividend"]=st.number_input("Annual dividend per share (blank uses provider; enter 0 for none)",min_value=0.,value=None,key="dr_annual_dividend")
    with st.expander("Sourced historical valuation observations"):
        st.caption("Enter earlier trailing P/E observations with YYYY-MM-DD dates and source URLs. Saved notebooks also accumulate the current trailing P/E. At least three earlier observations are required for a range; this is not a complete daily history.")
        history_seed=pd.DataFrame(st.session_state.get("decision_history_seed",[]),columns=["Date","Trailing P/E","Source"]).astype({"Date":"string","Trailing P/E":"float64","Source":"string"})
        history=st.data_editor(history_seed,num_rows="dynamic",hide_index=True,key="decision_history_editor",column_config={"Trailing P/E":st.column_config.NumberColumn(min_value=.01)})
        inputs["valuation_history"]=history.astype(object).where(history.notna(),None).to_dict("records")
    run=st.button("Run complete research",type="primary",icon=":material/manage_search:",width="stretch")
    rebuild=st.button("Rebuild report with current assumptions",disabled=not bool(st.session_state.get("v7_report")))
    if run or rebuild:
        try:
            from decision_report import assumptions
            assumptions(inputs)
            extra_inputs(inputs)
            history_rows(inputs["valuation_history"])
            if (inputs["ffo_per_share"] or inputs["book_per_share"]) and not inputs["specialist_source"].strip():
                raise ValueError("Add the source and reporting period for specialist per-share inputs.")
            baselines=st.session_state.get("decision_baselines",{})
            prior=baselines.get(symbol)
            with st.spinner("Collecting evidence and building the investment decision report..."):
                if run:
                    universe=st.session_state.get("v3_universe_data",pd.DataFrame())
                    if peer_symbols.strip():
                        from v3_features import load_snapshot
                        selected=list(dict.fromkeys(x.strip().upper() for x in peer_symbols.split(",") if x.strip()))[:5]
                        universe=pd.DataFrame([row for ticker in selected if (row:=load_snapshot(ticker,_secret("FMP_API_KEY")))])
                    report=complete_stock_research(symbol,_secret("FMP_API_KEY"),universe)
                else:
                    report=dict(st.session_state.v7_report)
                    if report["symbol"]!=symbol: raise ValueError("Run research for the new symbol before rebuilding.")
                    prior=st.session_state.get("decision_comparison_baseline")
                report["decision"]=build_decision_report(report,inputs,holdings,evidence,prior)
                pdf=complete_research_pdf(report)
                notebook=_notebook(report,inputs,holdings,evidence)
                notebook_json=json.dumps(notebook,indent=2,allow_nan=False)
                st.session_state.v7_report=report
                st.session_state.v7_pdf=pdf
                st.session_state["decision_comparison_baseline"]=prior
                st.session_state["decision_notebook"]=notebook_json
                st.session_state["decision_baselines"]={**baselines,symbol:notebook}
        except Exception as exc: st.error(f"Report could not be updated: {exc}")
    report=st.session_state.get("v7_report")
    if not report or "decision" not in report: return
    d=report["decision"]; v=d["valuation"]
    st.subheader(f"{report['symbol']} | Investment decision summary")
    st.write(d["summary"])
    cols=st.columns(4)
    for col,label,value in zip(cols,["Market price","Base fair value","Margin-of-safety price","Data confidence"],[fmt(report["snapshot"].get("Price")),fmt(v["fair_value"]),fmt(v["buy_price"]),d["confidence"]]): col.metric(label,value,border=True)
    st.caption(f"Generated {d['generated']} | Currency: {d['currency']} | {v['model']}. Changing inputs requires Rebuild report.")
    for title,items in [("Reasons to investigate",d["strengths"]),("Principal concerns",d["concerns"])]:
        st.markdown("**"+title+"**")
        for item in items: st.write("- "+item)
    sections=[
        ("2. Business quality and moat",d["moat"],d["specialist"]),
        ("3. Financial health trends",report.get("financial_trends",pd.DataFrame()),d["history_note"]),
        ("4. Fair value models",v["models"],v["note"]),
        ("5. Expectations in today's price",pd.DataFrame([{"Required growth %":v["reverse_growth"],"Assumed growth %":d["assumptions"]["growth"]}]),"Growth required by the selected valuation model, holding other assumptions fixed."),
        ("6. Bear / base / bull scenarios",v["scenarios"],"Horizon prices and annual price returns exclude dividends and are not probabilities."),
        ("7. Earnings quality and warning signs",d["checks"],"Review means investigate the stated threshold; missing data is not a pass."),
        ("8. Peer comparison",d["peers"],d["peer_note"]),
        ("9. Catalysts and thesis tracker",d["tracker"],"Previous report: "+d["prior_date"]),
        ("10. Portfolio fit",d["portfolio"],"Based on entered direct holdings and cash-funded purchase."),
        *d.get("extensions",[]),
        ("Sources and confidence",d["sources"],"Provider data, model estimates and user research are identified separately.")]
    for title,frame,note in sections:
        with st.expander(title):
            st.write(note)
            if frame.empty: st.info("Insufficient evidence: no data returned.")
            else: st.dataframe(frame,hide_index=True,width="stretch")
            if title.startswith("12.") and d.get("valuation_history"):
                st.dataframe(pd.DataFrame(d["valuation_history"]),hide_index=True,width="stretch")
            if title.startswith("3.") and not frame.empty:
                chart=frame.set_index("Year")[[c for c in ["Revenue","Net income","Free cash flow"] if c in frame]]
                if not chart.empty: st.line_chart(chart)
            if title.startswith("9.") and not report.get("calendar",pd.DataFrame()).empty: st.dataframe(report["calendar"],hide_index=True)
    st.download_button("Download complete stock research (PDF)",st.session_state.v7_pdf,f"{report['symbol']}-investment-decision.pdf","application/pdf",type="primary")
    st.download_button("Download research notebook",st.session_state["decision_notebook"],f"{report['symbol']}-research-notebook.json","application/json")
