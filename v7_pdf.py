"""PDF builder for the AANIANG complete stock research report."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.graphics.shapes import Drawing, Line, PolyLine, Rect, String
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _value(value, suffix="") -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)): return "N/A"
    if isinstance(value, float): return f"{value:,.2f}{suffix}"
    return f"{value}{suffix}"


def _table(frame: pd.DataFrame, styles, limit: int = 15):
    if frame is None or frame.empty: return Paragraph("No data returned.", styles["BodyText"])
    view = frame.head(limit).copy()
    if len(view.columns) > 6: view = view.iloc[:, :6]
    rows = [[Paragraph(f"<b>{escape(str(c))}</b>", styles["Tiny"]) for c in view.columns]]
    for values in view.itertuples(index=False, name=None):
        rows.append([Paragraph(escape(_value(v)), styles["Tiny"]) for v in values])
    table = Table(rows, repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), .25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6F8")]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3), ("RIGHTPADDING", (0, 0), (-1, -1), 3),
    ]))
    return table


def _technical_chart(history: pd.DataFrame, levels: pd.DataFrame) -> Drawing:
    """Build a sharp vector price chart with MVA and support/resistance."""
    width, height = 500, 245
    drawing = Drawing(width, height)
    drawing.add(Rect(0, 0, width, height, fillColor=colors.HexColor("#F8FAFC"), strokeColor=colors.HexColor("#CBD5E1")))
    left, right, bottom, top = 48, 12, 30, 28
    plot_width, plot_height = width-left-right, height-bottom-top
    if history is None or history.empty or "Close" not in history:
        drawing.add(String(width/2-55, height/2, "Price history unavailable", fontSize=10, fillColor=colors.HexColor("#64748B")))
        return drawing
    frame = history.tail(252).copy()
    series = {"Price": frame["Close"]}
    for column in ("SMA 20", "SMA 50", "SMA 200"):
        if column in frame: series[column] = frame[column]
    values = pd.concat([value for value in series.values()]).dropna()
    level_values = pd.to_numeric(levels.get("Level", pd.Series(dtype=float)), errors="coerce").dropna() if levels is not None else pd.Series(dtype=float)
    if not level_values.empty: values = pd.concat([values, level_values])
    minimum, maximum = float(values.min()), float(values.max())
    padding = max((maximum-minimum)*.08, maximum*.01); minimum -= padding; maximum += padding
    scale_y = lambda value: bottom + (float(value)-minimum) / max(maximum-minimum, .01) * plot_height
    scale_x = lambda index: left + index / max(len(frame)-1, 1) * plot_width
    for step in range(5):
        value = minimum + (maximum-minimum)*step/4; y = scale_y(value)
        drawing.add(Line(left, y, width-right, y, strokeColor=colors.HexColor("#E2E8F0"), strokeWidth=.5))
        drawing.add(String(3, y-3, f"{value:,.0f}", fontSize=7, fillColor=colors.HexColor("#64748B")))
    palette = {"Price":"#111827", "SMA 20":"#2563EB", "SMA 50":"#F59E0B", "SMA 200":"#7C3AED"}
    for name, data in series.items():
        points = [(scale_x(i), scale_y(value)) for i, value in enumerate(data.tolist()) if pd.notna(value)]
        if len(points) > 1: drawing.add(PolyLine(points, strokeColor=colors.HexColor(palette[name]), strokeWidth=1.5 if name=="Price" else 1.15))
    if levels is not None and not levels.empty:
        for row in levels.head(8).itertuples(index=False):
            y = scale_y(row.Level); support = str(row.Type).lower().startswith("support")
            color = colors.HexColor("#059669" if support else "#DC2626")
            drawing.add(Line(left, y, width-right, y, strokeColor=color, strokeWidth=.8, strokeDashArray=[4, 3]))
            drawing.add(String(width-right-82, y+2, f"{row.Type} {row.Level:.2f}", fontSize=6.5, fillColor=color))
    legend_x = left
    for name in series:
        drawing.add(Line(legend_x, height-12, legend_x+16, height-12, strokeColor=colors.HexColor(palette[name]), strokeWidth=2))
        drawing.add(String(legend_x+20, height-15, name, fontSize=7, fillColor=colors.HexColor("#334155")))
        legend_x += 82
    first_date, last_date = frame.index[0], frame.index[-1]
    drawing.add(String(left, 10, str(getattr(first_date, "date", lambda: first_date)()), fontSize=7, fillColor=colors.HexColor("#64748B")))
    drawing.add(String(width-right-58, 10, str(getattr(last_date, "date", lambda: last_date)()), fontSize=7, fillColor=colors.HexColor("#64748B")))
    return drawing


def complete_research_pdf(report: dict) -> bytes:
    output = io.BytesIO(); snapshot = report["snapshot"]; symbol = report["symbol"]
    doc = SimpleDocTemplate(output, pagesize=letter, rightMargin=.55*inch, leftMargin=.55*inch,
        topMargin=.62*inch, bottomMargin=.55*inch, title=f"{symbol} Complete Research Report", author="AANIANG Trading Station")
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], textColor=colors.HexColor("#0B6E75"), spaceBefore=12, spaceAfter=6, keepWithNext=True))
    styles.add(ParagraphStyle(name="Tiny", parent=styles["BodyText"], fontSize=7, leading=8.5))
    styles.add(ParagraphStyle(name="Meta", parent=styles["BodyText"], fontSize=9, textColor=colors.HexColor("#5B6573"), leading=12))
    story = [Paragraph("AANIANG Complete Stock Research", styles["Title"]),
        Paragraph(f"{escape(str(snapshot.get('Company', symbol)))} ({escape(symbol)})", styles["Heading1"]),
        Paragraph(f"Generated {report['generated_at'].strftime('%Y-%m-%d %H:%M UTC')} | Sources: {escape(str(snapshot.get('Source', 'Yahoo Finance')))}", styles["Meta"]), Spacer(1, 8)]

    key_metrics = [
        ["Price", _value(snapshot.get("Price")), "Quality", _value(snapshot.get("Quality"), "/100")],
        ["Market cap", _value(snapshot.get("Market cap")), "Technical", _value(report["technical_score"], "/100")],
        ["Forward P/E", _value(snapshot.get("Forward P/E")), "Management", _value(report["management_score"], "/100")],
        ["Analyst value gap", _value(snapshot.get("Value gap"), "%"), "1Y return", _value(snapshot.get("1Y return"), "%")],
    ]
    story.extend([Paragraph("Executive Dashboard", styles["Section"]), Table(key_metrics, colWidths=[1.25*inch, 1.5*inch, 1.35*inch, 1.5*inch], style=[("GRID",(0,0),(-1,-1),.3,colors.HexColor("#CBD5E1")),("BACKGROUND",(0,0),(0,-1),colors.HexColor("#E8F1F5")),("BACKGROUND",(2,0),(2,-1),colors.HexColor("#E8F1F5")),("PADDING",(0,0),(-1,-1),6)])])
    story.extend([Paragraph("Company and Fundamentals", styles["Section"]), Paragraph(escape(str(snapshot.get("Description") or "No business description returned.")), styles["BodyText"])])
    fundamentals = pd.DataFrame({"Metric":["Sector","Industry","ROE %","Operating margin %","Revenue growth %","Earnings growth %","Debt/Equity","Current ratio","Trailing P/E","Forward P/E","Dividend yield %","Beta","Analyst target"], "Value":[snapshot.get("Sector"),snapshot.get("Industry"),snapshot.get("ROE"),snapshot.get("Operating margin"),snapshot.get("Revenue growth"),snapshot.get("Earnings growth"),snapshot.get("Debt/Equity"),snapshot.get("Current ratio"),snapshot.get("Trailing P/E"),snapshot.get("Forward P/E"),snapshot.get("Dividend yield"),snapshot.get("Beta"),snapshot.get("Analyst target")]})
    story.append(_table(fundamentals, styles, 20))
    story.append(Paragraph("Investment Thesis", styles["Section"]))
    for heading, points in report["brief"].items():
        story.append(Paragraph(f"<b>{escape(heading)}</b>", styles["BodyText"]))
        for point in points: story.append(Paragraph(f"- {escape(str(point))}", styles["BodyText"]))

    story.extend([PageBreak(), Paragraph("Technical Analysis", styles["Section"]),
        Paragraph("One-year price chart with 20-, 50-, and 200-session moving averages plus detected support and resistance.", styles["Meta"]),
        _technical_chart(report.get("technical_history", pd.DataFrame()), report["levels"]), Spacer(1, 8),
        Paragraph(f"Composite technical score: <b>{report['technical_score']}/100</b>", styles["BodyText"]),
        _table(pd.DataFrame(report["technical_checks"]), styles), Paragraph("Support and Resistance", styles["Section"]), _table(report["levels"], styles)])
    pattern_frame = pd.DataFrame(report["patterns"])
    story.extend([Paragraph("Pattern Detection", styles["Section"]), _table(pattern_frame, styles), Paragraph("Active Technical Alerts", styles["Section"]), Paragraph(escape("; ".join(report["alerts"]) if report["alerts"] else "No configured technical alert is active."), styles["BodyText"])])
    story.extend([Paragraph("Management Quality", styles["Section"]), Paragraph(f"Score: <b>{report['management_score']}/100</b>", styles["BodyText"])])
    for reason in report["management_reasons"]: story.append(Paragraph(escape(reason), styles["BodyText"]))

    story.extend([PageBreak(), Paragraph("Dividend Intelligence", styles["Section"]), _table(pd.DataFrame([report["dividend_metrics"]]), styles), _table(report["dividend_history"], styles), Paragraph("Insider Activity", styles["Section"]), _table(report["insiders"], styles), Paragraph("Institutional Ownership", styles["Section"]), _table(report["institutions"], styles), Paragraph("Major Holders", styles["Section"]), _table(report["major_holders"], styles), Paragraph("Catalyst Calendar", styles["Section"]), _table(report["calendar"], styles), Paragraph("Recent News", styles["Section"]), _table(report["news"], styles)])
    story.append(Paragraph("Modules Requiring Additional Inputs", styles["Section"]))
    for item in report["input_required"]: story.append(Paragraph(f"- {escape(item)}", styles["BodyText"]))
    if report["errors"]:
        story.append(Paragraph("Data Availability Notes", styles["Section"]))
        for name, error in report["errors"].items(): story.append(Paragraph(f"- {escape(name)}: {escape(error)}", styles["Tiny"]))
    story.extend([Spacer(1, 12), Paragraph("Educational research only. Data may be delayed or incomplete. This report is not investment advice.", styles["Meta"])])

    def footer(canvas, document):
        canvas.saveState(); canvas.setFont("Helvetica", 8); canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawString(.55*inch, .28*inch, f"AANIANG | {symbol}"); canvas.drawRightString(letter[0]-.55*inch, .28*inch, f"Page {document.page}"); canvas.restoreState()
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return output.getvalue()

