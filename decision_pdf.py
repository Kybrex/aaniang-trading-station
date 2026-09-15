"""Readable decision report with one topic per page and explicit evidence."""
import io
from xml.sax.saxutils import escape
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
from decision_report import fmt


def decision_pdf(report):
    d=report["decision"]; s=report["snapshot"]; v=d["valuation"]; a=d["assumptions"]
    out=io.BytesIO(); styles=getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Small",fontName="Helvetica",fontSize=8,leading=11,textColor=colors.HexColor("#334155")))
    styles.add(ParagraphStyle(name="HeadCell",parent=styles["Small"],fontName="Helvetica-Bold",textColor=colors.white))
    styles["Title"].textColor=colors.HexColor("#12324b")
    styles["Heading1"].textColor=colors.HexColor("#126b70")
    styles["Heading2"].textColor=colors.HexColor("#12324b")
    styles["BodyText"].spaceAfter=7
    story=[]; width=A4[0]-80
    def p(text,style="BodyText"):
        return Paragraph(escape(str(text)),styles[style])
    def table(frame):
        if frame is None or frame.empty:
            story.append(p("Insufficient evidence: no data returned.")); return
        # Split wide tables horizontally, retaining the identifying first column.
        cols=list(frame.columns)
        chunks=[cols] if len(cols)<=5 else [[cols[0]]+cols[i:i+4] for i in range(1,len(cols),4)]
        for chunk in chunks:
            rows=[[p(c,"HeadCell") for c in chunk]]
            for _,row in frame.iterrows():
                rows.append([p(str(int(row[c])) if c=="Year" and pd.notna(row[c]) else fmt(row[c]) if isinstance(row[c],(int,float)) else ("Unavailable" if pd.isna(row[c]) else row[c]),"Small") for c in chunk])
            t=Table(rows,colWidths=[width/len(chunk)]*len(chunk),repeatRows=1,hAlign="LEFT")
            t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#12324b")),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.HexColor("#f0f5f8"),colors.white]),("VALIGN",(0,0),(-1,-1),"TOP"),("GRID",(0,0),(-1,-1),.3,colors.HexColor("#d7e1e8")),("TOPPADDING",(0,0),(-1,-1),5),("BOTTOMPADDING",(0,0),(-1,-1),5)]))
            story.extend([t,Spacer(1,10)])
    def section(title,note=None):
        if story: story.append(PageBreak())
        story.append(p(title,"Heading1"))
        if note: story.append(p(note))
    def bullets(title,items):
        story.append(p(title,"Heading2"))
        for item in items: story.append(p("- "+str(item)))
    section("AANIANG Investment Decision Report")
    story.append(p(f"{s.get('Company',d['symbol'])} | {d['symbol']}","Title"))
    story.append(p(f"{d['generated']} | Trading currency: {d['currency']}","Small"))
    story.append(p(d["summary"],"Heading2"))
    table(pd.DataFrame([
        ("Market price",fmt(s.get("Price"))),("Base fair value / margin-of-safety price",fmt(v["fair_value"])+" / "+fmt(v["buy_price"])),
        ("Business quality", "Evidence in sections 2-3; no combined buy/sell score"),
        ("Financial checks requiring review",str(sum(d["checks"].Status.eq("Review")))),
        ("Data confidence",d["confidence"]+"; qualitative moat and model assumptions need review"),
        ("Technical timing",fmt(report.get("technical_score"),"/100") if not report.get("technical_history",pd.DataFrame()).empty else "Unavailable")],columns=["Decision lens","Assessment"]))
    bullets("Reasons to investigate",d["strengths"])
    bullets("Principal concerns",d["concerns"])
    story.append(p("Independent AANIANG analysis. No Morningstar, CFRA, Argus or StockOracle rating is reproduced or implied. Revisit after the next earnings release or a thesis trigger.","Small"))

    section("2 | Business quality and competitive advantage",d["specialist"])
    story.append(p(s.get("Description") or "Business description unavailable."))
    table(d["moat"])
    story.append(p("Profitability alone does not establish a durable moat. Sourced observations are user research and require verification. Unassessed factors are not scored as weak or strong.","Small"))

    section("3 | Financial health through time",d["history_note"])
    from v7_pdf import _financial_trend_chart
    trends=report.get("financial_trends",pd.DataFrame())
    story.append(_financial_trend_chart(trends)); story.append(Spacer(1,12))
    story.append(p("Annual periods are shown as returned, without filling missing years. Revenue and profit are in statement currency; diluted shares are share counts. Review the filings for acquisitions, restatements and changes in fiscal year.","Small"))
    table(trends)

    section("4 | Fair value and a price with room for error",f"Primary model: {v['model']}. Sector treatment: {v['sector']}.")
    table(v["models"])
    table(pd.DataFrame([(k,fmt(a[k])) for k in ["growth","discount","terminal_growth","exit_multiple","margin_safety","years"]],columns=["Editable assumption","Value (% except years and multiple)"]))
    story.append(p(f"Base fair value: {fmt(v['fair_value'])}. Price with {fmt(a['margin_safety'])}% margin of safety: {fmt(v['buy_price'])}."))
    story.append(p("The analyst target is a separate opinion, not intrinsic value: "+fmt(s.get("Analyst target"))))
    story.append(p(v["note"],"Small"))
    story.append(p("Multiple valuation discounts future EPS or FFO times the assumed exit multiple. Financial-company book valuation assumes stable ROE and retention compatible with growth. Models are displayed separately; they are not averaged into false precision.","Small"))

    section("5 | Expectations embedded in the current price")
    table(pd.DataFrame([("Required annual growth under selected model",fmt(v["reverse_growth"],"%")),("Your base growth assumption",fmt(a["growth"],"%")),("Reported revenue growth (different measure)",fmt(s.get("Revenue growth"),"%")),("Reported earnings growth (different period)",fmt(s.get("Earnings growth"),"%"))],columns=["Expectation","Value"]))
    story.append(p("The reverse calculation solves for the growth rate that makes the selected model equal today's price, holding other assumptions fixed. Cash-flow growth, EPS growth and revenue growth are different measures; compare them only after assessing margins, reinvestment and dilution."))
    story.append(p("For a multiple model: implied growth = (price x (1 + discount rate)^years / (base EPS or FFO x exit multiple))^(1/years) - 1. Cash-flow growth is solved numerically. Unavailable means inputs are missing or the solution lies outside the tested range.","Small"))

    section("6 | Bear, base and bull outcomes",f"Horizon: {a['years']} years. Scenarios are sensitivities, not assigned probabilities.")
    table(v["scenarios"])
    bullets("What changes across scenarios",["Bear: base growth minus 5 percentage points; exit multiple 25% lower for multiple models.","Base: your entered growth and exit multiple.","Bull: base growth plus 5 percentage points; exit multiple 25% higher for multiple models.","Cash-flow scenarios use the same discount and terminal-growth rates; the terminal value determines the horizon price."])
    story.append(p("Fair value today includes the discounting appropriate to each model. Horizon price is a future value. Annual price return excludes interim distributions, dividends, taxes and fees. Neither the bear outcome nor a stop price is a guaranteed loss limit.","Small"))

    section("7 | Earnings quality and warning signs")
    table(d["checks"])
    story.append(p("Thresholds flag questions for investigation; they do not diagnose fraud. Missing information remains insufficient evidence. Compare cash flow and earnings for the same reporting period.","Small"))

    section("8 | Peer comparison",d["peer_note"])
    table(d["peers"])
    story.append(p("Compare growth, profitability and valuation together. A lower multiple may reflect slower growth, weaker funding or business mix. No peer ranking is produced from incomplete observations.","Small"))

    section("9 | Catalysts, milestones and thesis changes",f"Previous baseline: {d['prior_date']}")
    table(d["tracker"])
    table(report.get("calendar",pd.DataFrame()).head(8))
    story.append(p("Review conditions above are editable-policy candidates, not automatic trading orders. Download the research notebook to preserve the baseline across sessions; import it before the next update. Financial changes may reflect a new annual period or a provider revision.","Small"))

    section("10 | Portfolio fit and downside exposure")
    table(d["portfolio"])
    story.append(p(f"Entered position cap: {fmt(a['position_cap'])}%. Entered scenario loss budget: {fmt(a['loss_budget'])}%. Holdings and planned amount use one portfolio currency; all purchases are assumed funded from existing cash.","Small"))

    for title,frame,note in d.get("extensions",[]):
        section(title,note)
        table(frame)
        if title.startswith("12.") and d.get("valuation_history"):
            table(pd.DataFrame(d["valuation_history"]).tail(30))
            story.append(p("Last 30 saved observations shown; summary uses all saved observations before the current date.","Small"))

    section("Technical timing | separate from investment value")
    from v7_pdf import _technical_chart
    story.append(_technical_chart(report.get("technical_history",pd.DataFrame()),report.get("levels",pd.DataFrame())))
    table(pd.DataFrame(report.get("technical_checks",[])))
    story.append(p("Trend and price levels describe market behavior. They do not establish business quality or intrinsic value.","Small"))

    for title,key in [("Appendix | Analyst estimates and revisions","estimate_revisions"),("Appendix | Earnings surprise history","earnings_surprises"),("Appendix | Recent SEC filings","sec_filings"),("Appendix | Dividend history","dividend_history"),("Appendix | Insider transactions","insiders"),("Appendix | Institutional ownership","institutions"),("Appendix | Recent company news","news")]:
        frame=report.get(key,pd.DataFrame())
        if isinstance(frame,pd.DataFrame) and not frame.empty:
            section(title,f"First {min(len(frame),10)} of {len(frame)} returned records. Source: SEC EDGAR for filings; Yahoo Finance for other provider data.")
            if key=="sec_filings": frame=frame[[c for c in ["form","filingDate","reportDate","primaryDocument"] if c in frame]]
            table(frame.head(10))
    section("Sources, assumptions and data limitations")
    table(d["sources"])
    if report.get("errors"): table(pd.DataFrame(report["errors"].items(),columns=["Feed","Limitation"]))
    story.append(p("Confidence describes data coverage, not the probability of a profitable investment. Scenario assumptions and research thresholds are AANIANG/user inputs. Specialist metrics are not invented. Data and model outputs are research aids and can be incomplete.","Small"))
    def footer(canvas,doc):
        canvas.setFont("Helvetica",8); canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(40,24,f"AANIANG | {d['symbol']} | {d['generated']}")
        canvas.drawRightString(A4[0]-40,24,f"{doc.page}")
    SimpleDocTemplate(out,pagesize=A4,leftMargin=40,rightMargin=40,topMargin=38,bottomMargin=40,title=f"{d['symbol']} Investment Decision Report").build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()
