import io
from flask import make_response, url_for
from datetime import datetime, timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

def generate_admin_ledger_report(blocks, metrics):
    """Generate a summary PDF report of the entire blockchain ledger."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
    )

    styles = getSampleStyleSheet()
    primary_color = HexColor("#0f766e")
    dark_color = HexColor("#0f172a")
    muted_color = HexColor("#64748b")
    line_color = HexColor("#e2e8f0")
    bg_color = HexColor("#f8fafc")

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontSize=24,
        leading=30,
        textColor=dark_color,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=muted_color,
        alignment=TA_CENTER,
        spaceAfter=10 * mm,
    )
    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontSize=14,
        leading=18,
        textColor=primary_color,
        spaceBefore=8 * mm,
        spaceAfter=4 * mm,
    )
    footer_style = ParagraphStyle(
        "ReportFooter",
        parent=styles["Normal"],
        fontSize=8,
        leading=12,
        textColor=muted_color,
        alignment=TA_CENTER,
    )

    elements = []

    # Header
    elements.append(Paragraph("HashVera Academic Record Network", subtitle_style))
    elements.append(Paragraph("Blockchain Ledger Summary Report", title_style))
    elements.append(Paragraph(
        f"Generated on: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        subtitle_style,
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=line_color, spaceAfter=8 * mm))

    # Network Metrics Table
    elements.append(Paragraph("Network Overview", heading_style))
    metric_data = [
        ["Total Blocks Secured", str(metrics.get("total_blocks", 0))],
        ["Active Academic Records", str(metrics.get("active_records", 0))],
        ["Registered Campus Users", str(metrics.get("registered_users", 0))],
        ["Decentralized Peer Nodes", str(metrics.get("active_nodes", 0))],
        ["Ledger Health Status", metrics.get("chain_status", "Unknown")],
    ]
    
    metric_table = Table(metric_data, colWidths=[80 * mm, 100 * mm])
    metric_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), dark_color),
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, line_color),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
    ]))
    elements.append(metric_table)
    elements.append(Spacer(1, 10 * mm))

    # Ledger Details Table
    elements.append(Paragraph("Ledger Entries (Recent 50)", heading_style))
    
    ledger_header = ["Index", "Student Name", "Campus ID", "Document", "Status", "Timestamp"]
    ledger_data = [ledger_header]
    
    # Take the last 50 blocks
    recent_blocks = blocks[-50:] if len(blocks) > 50 else blocks
    
    for b in reversed(recent_blocks):
        ledger_data.append([
            f"#{b.get('block_index', '0')}",
            (b.get("student_name")[:15] + "...") if b.get("student_name") and len(b.get("student_name")) > 15 else b.get("student_name", "N/A"),
            b.get("student_id", "N/A"),
            (b.get("document_name")[:15] + "...") if b.get("document_name") and len(b.get("document_name")) > 15 else b.get("document_name", "N/A"),
            b.get("record_status", "N/A"),
            b.get("timestamp", "")[:10] if b.get("timestamp") else "N/A"
        ])

    col_widths = [15 * mm, 40 * mm, 30 * mm, 40 * mm, 25 * mm, 30 * mm]
    ledger_table = Table(ledger_data, colWidths=col_widths, repeatRows=1)
    ledger_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), primary_color),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#ffffff")),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 0.5, line_color),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(ledger_table)

    # Footer
    elements.append(Spacer(1, 15 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=line_color, spaceAfter=3 * mm))
    elements.append(Paragraph(
        "Confidential Administrator Report - HashVera Academic Record Network",
        footer_style,
    ))
    elements.append(Paragraph(
        "Blockchain integrity verified using SHA-256 cryptographic linkage.",
        footer_style,
    ))

    doc.build(elements)
    buffer.seek(0)
    
    return buffer.getvalue()
