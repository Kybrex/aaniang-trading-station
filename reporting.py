"""Printable PDF and Excel exports for scanner, portfolio, and research tables."""
from __future__ import annotations

from io import BytesIO
import pandas as pd
from openpyxl.styles import Font,PatternFill
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape,letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle


def excel_workbook(sheets: dict[str,pd.DataFrame]) -> bytes:
    output=BytesIO()
    with pd.ExcelWriter(output,engine="openpyxl") as writer:
        for name,frame in sheets.items():
            frame.to_excel(writer,sheet_name=name[:31],index=False)
            sheet=writer.sheets[name[:31]]; sheet.freeze_panes="A2"
            for cell in sheet[1]:cell.font=Font(bold=True,color="FFFFFF");cell.fill=PatternFill("solid",fgColor="1F4E78")
            for column in sheet.columns:
                width=min(40,max(10,max(len(str(cell.value or "")) for cell in column)+2));sheet.column_dimensions[column[0].column_letter].width=width
    return output.getvalue()


def table_pdf(title: str, frame: pd.DataFrame, subtitle: str = "") -> bytes:
    output=BytesIO();doc=SimpleDocTemplate(output,pagesize=landscape(letter),rightMargin=24,leftMargin=24,topMargin=24,bottomMargin=24);styles=getSampleStyleSheet();story=[Paragraph(title,styles["Title"])]
    if subtitle:story.extend([Paragraph(subtitle,styles["BodyText"]),Spacer(1,10)])
    display=frame.copy().fillna("")
    for column in display.columns:
        display[column]=display[column].map(lambda value:f"{value:.2f}" if isinstance(value,float) else str(value))
    data=[list(map(str,display.columns))]+display.astype(str).values.tolist();table=Table(data,repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#1F4E78")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),("FONTSIZE",(0,0),(-1,-1),7),("GRID",(0,0),(-1,-1),.25,colors.grey),("VALIGN",(0,0),(-1,-1),"TOP"),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#EEF3F8")])]))
    story.append(table);doc.build(story);return output.getvalue()
