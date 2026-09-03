"""PDF export helpers for AANIANG research reports."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def research_pdf(symbol: str, company: str, brief: dict[str, list[str]]) -> bytes:
    """Build a polished, printable research brief entirely in memory."""
    output = io.BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=0.7 * inch,
        leftMargin=0.7 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.65 * inch,
        title=f"{symbol} Research Brief",
        author="AANIANG Trading Station",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="ReportTitle", parent=styles["Title"], fontName="Helvetica-Bold",
        fontSize=22, leading=27, textColor=colors.HexColor("#123B5D"),
        alignment=TA_CENTER, spaceAfter=8,
    ))
    styles.add(ParagraphStyle(
        name="ReportMeta", parent=styles["Normal"], fontName="Helvetica",
        fontSize=9, leading=13, textColor=colors.HexColor("#5B6573"),
        alignment=TA_CENTER, spaceAfter=18,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", parent=styles["Heading2"], fontName="Helvetica-Bold",
        fontSize=13, leading=17, textColor=colors.HexColor("#0B6E75"),
        spaceBefore=12, spaceAfter=6, keepWithNext=True,
    ))
    styles.add(ParagraphStyle(
        name="ReportBullet", parent=styles["BodyText"], fontName="Helvetica",
        fontSize=10, leading=15, leftIndent=14, firstLineIndent=-8,
        textColor=colors.HexColor("#202833"), spaceAfter=5,
    ))
    story = [
        Paragraph("AANIANG Trading Station", styles["ReportMeta"]),
        Paragraph(f"{escape(company)} ({escape(symbol)})", styles["ReportTitle"]),
        Paragraph(
            f"AI-ready evidence research brief | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["ReportMeta"],
        ),
    ]
    for heading, points in brief.items():
        story.append(Paragraph(escape(str(heading)), styles["SectionTitle"]))
        for point in points:
            story.append(Paragraph(f"- {escape(str(point))}", styles["ReportBullet"]))
    story.extend([
        Spacer(1, 14),
        Paragraph(
            "Educational research only. This report is not investment advice and should be checked against current filings and reliable market data.",
            styles["ReportMeta"],
        ),
    ])

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawCentredString(letter[0] / 2, 0.35 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output.getvalue()

