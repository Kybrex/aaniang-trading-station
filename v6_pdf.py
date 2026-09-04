"""PDF export helpers for AANIANG V6 technical intelligence."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def relative_strength_pdf(ranked: pd.DataFrame) -> bytes:
    """Create a printable PDF version of the relative-strength leaderboard."""
    output = io.BytesIO()
    page_size = landscape(letter)
    document = SimpleDocTemplate(
        output,
        pagesize=page_size,
        rightMargin=0.45 * inch,
        leftMargin=0.45 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch,
        title="Relative Strength Leaderboard",
        author="AANIANG Trading Station",
    )
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="RSSubtitle", parent=styles["Normal"], fontSize=9, leading=12,
        textColor=colors.HexColor("#5B6573"), spaceAfter=10,
    ))
    story = [
        Paragraph("AANIANG Relative Strength Leaderboard", styles["Title"]),
        Paragraph(
            f"{len(ranked)} companies ranked | Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            styles["RSSubtitle"],
        ),
    ]

    printable = ranked.copy().reset_index(drop=True)
    printable.insert(0, "Rank", range(1, len(printable) + 1))
    headers = [Paragraph(f"<b>{escape(str(column))}</b>", styles["BodyText"]) for column in printable.columns]
    rows = [headers]
    for values in printable.itertuples(index=False, name=None):
        row = []
        for value in values:
            if pd.isna(value):
                display = "—"
            elif isinstance(value, float):
                display = f"{value:,.2f}"
            else:
                display = str(value)
            row.append(Paragraph(escape(display), styles["BodyText"]))
        rows.append(row)

    usable_width = page_size[0] - 0.9 * inch
    column_width = usable_width / max(len(printable.columns), 1)
    table = Table(rows, colWidths=[column_width] * len(printable.columns), repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("LEADING", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F6F8")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.extend([
        table,
        Spacer(1, 10),
        Paragraph(
            "Relative strength is a comparative ranking, not a buy or sell recommendation. Educational research only.",
            styles["RSSubtitle"],
        ),
    ])

    def add_page_number(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#6B7280"))
        canvas.drawRightString(page_size[0] - 0.45 * inch, 0.28 * inch, f"Page {doc.page}")
        canvas.restoreState()

    document.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    return output.getvalue()

