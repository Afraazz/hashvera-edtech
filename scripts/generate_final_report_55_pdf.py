import sys
from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SNAPSHOTS = DOCS / "snapshots"
OUTPUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DOCS / "HASHVERA_FINAL_REPORT_55_PAGES.pdf"

PAGE_W, PAGE_H = A4
LANDSCAPE_W, LANDSCAPE_H = PAGE_H, PAGE_W
LEFT = 54
RIGHT = 54
TOP = 64
BOTTOM = 54
CONTENT_W = PAGE_W - LEFT - RIGHT


def register_font(name, path, fallback):
    font_path = Path(path)
    if font_path.exists():
        pdfmetrics.registerFont(TTFont(name, str(font_path)))
        return name
    return fallback


BODY_FONT = register_font("TimesNewRoman", r"C:\Windows\Fonts\times.ttf", "Times-Roman")
BOLD_FONT = register_font("TimesNewRoman-Bold", r"C:\Windows\Fonts\timesbd.ttf", "Times-Bold")
ITALIC_FONT = register_font("TimesNewRoman-Italic", r"C:\Windows\Fonts\timesi.ttf", "Times-Italic")
HEADER_FONT = register_font("Arial", r"C:\Windows\Fonts\arial.ttf", "Helvetica")
HEADER_BOLD_FONT = register_font("Arial-Bold", r"C:\Windows\Fonts\arialbd.ttf", "Helvetica-Bold")


def clean(text):
    return " ".join(str(text).replace("\n", " ").split())


def cell(text):
    return clean(text)


class FinalReport:
    def __init__(self, path):
        self.path = Path(path)
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.page_no = 0

    def start_page(self, title=None, chapter=None):
        self.page_no += 1
        self.c.setFillColor(colors.black)
        self.c.setStrokeColor(colors.black)
        self.c.setLineWidth(0.8)
        self.c.rect(28, 28, PAGE_W - 56, PAGE_H - 56, fill=False, stroke=True)
        y = PAGE_H - TOP
        if chapter:
            self.c.setFont(BOLD_FONT, 11)
            self.c.drawString(LEFT, y, chapter.upper())
            y -= 20
        if title:
            self.c.setFont(BOLD_FONT, 18)
            for line in wrap(clean(title), 42):
                self.c.drawString(LEFT, y, line)
                y -= 22
            y -= 8
        return y

    def end_page(self):
        self.c.showPage()
        self.c.setPageSize(A4)

    def start_landscape_page(self):
        self.c.setPageSize((LANDSCAPE_W, LANDSCAPE_H))
        self.page_no += 1
        self.c.setFillColor(colors.black)
        self.c.setStrokeColor(colors.black)
        self.c.setLineWidth(0.8)
        self.c.rect(28, 28, LANDSCAPE_W - 56, LANDSCAPE_H - 56, fill=False, stroke=True)
        return LANDSCAPE_H - 58

    def end_landscape_page(self):
        self.c.showPage()
        self.c.setPageSize(A4)

    def start_full_tracker_page(self):
        self.c.setPageSize(A4)
        self.page_no += 1
        self.c.setStrokeColor(colors.black)
        self.c.setLineWidth(0.8)
        self.c.rect(28, 28, PAGE_W - 56, PAGE_H - 56, fill=False, stroke=True)
        return PAGE_H - 44

    def end_full_tracker_page(self):
        self.c.showPage()
        self.c.setPageSize(A4)

    def fit_line(self, text, max_width, font=BODY_FONT, size=10):
        words = clean(text).split()
        lines = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if stringWidth(trial, font, size) <= max_width:
                current = trial
                continue
            if current:
                lines.append(current)
            while stringWidth(word, font, size) > max_width and len(word) > 3:
                part = word
                while stringWidth(part, font, size) > max_width and len(part) > 3:
                    part = part[:-1]
                lines.append(part + "-")
                word = word[len(part):]
            current = word
        if current:
            lines.append(current)
        return lines

    def paragraph(self, text, x, y, size=12, leading=18, font=BODY_FONT, width=CONTENT_W):
        self.c.setFont(font, size)
        self.c.setFillColor(colors.black)
        for line in self.fit_line(text, width, font, size):
            self.c.drawString(x, y, line)
            y -= leading
        return y - 6

    def bullets(self, items, x, y, size=12, leading=18, width=CONTENT_W - 16):
        self.c.setFont(BODY_FONT, size)
        self.c.setFillColor(colors.black)
        for item in items:
            lines = self.fit_line(item, width - 14, BODY_FONT, size)
            self.c.drawString(x, y, "-")
            self.c.drawString(x + 14, y, lines[0])
            y -= leading
            for line in lines[1:]:
                self.c.drawString(x + 14, y, line)
                y -= leading
            y -= 1
        return y - 4

    def subheading(self, text, x, y):
        self.c.setFont(BOLD_FONT, 14)
        self.c.setFillColor(colors.black)
        self.c.drawString(x, y, clean(text))
        return y - 18

    def table(self, data, x, y, widths=None, font_size=9.5):
        font_size = max(font_size, 9)
        if widths is None:
            widths = [CONTENT_W / len(data[0])] * len(data[0])
        table = Table([[cell(v) for v in row] for row in data], colWidths=widths, repeatRows=1)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), HEADER_BOLD_FONT),
                    ("FONTNAME", (0, 1), (-1, -1), BODY_FONT),
                    ("FONTSIZE", (0, 0), (-1, -1), font_size),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        _, h = table.wrapOn(self.c, CONTENT_W, y)
        table.drawOn(self.c, x, y - h)
        return y - h - 14

    def project_tracker(self, x, y):
        title_style = ParagraphStyle(
            "tracker_title",
            fontName=HEADER_BOLD_FONT,
            fontSize=8.4,
            alignment=TA_CENTER,
            leading=9.5,
        )
        header_style = ParagraphStyle(
            "tracker_header",
            fontName=HEADER_BOLD_FONT,
            fontSize=7.8,
            alignment=TA_CENTER,
            leading=8.8,
        )
        body_style = ParagraphStyle(
            "tracker_body",
            fontName=BODY_FONT,
            fontSize=7.6,
            alignment=TA_LEFT,
            leading=9.1,
        )
        center_style = ParagraphStyle(
            "tracker_center",
            fontName=BODY_FONT,
            fontSize=7.6,
            alignment=TA_CENTER,
            leading=9.1,
        )
        data = [
            [Paragraph("Yenepoya Project Tracker - 2026", title_style), "", "", "", "", "", "", ""],
            [Paragraph("Ta<br/>sk<br/>ID", header_style), Paragraph("Task<br/>Descripti<br/>on", header_style), Paragraph("Project Title", header_style), Paragraph("Proje<br/>ct<br/>Timel<br/>ine", header_style), Paragraph("Start<br/>Date", header_style), Paragraph("End<br/>Date", header_style), Paragraph("Status", header_style), Paragraph("Feedback and<br/>Comments", header_style)],
            [Paragraph("T-<br/>01", center_style), Paragraph("Problem study and topic selection", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>01", center_style), Paragraph("07-<br/>Mar-<br/>26", center_style), Paragraph("13-<br/>Mar-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("Topic finalized and scope approved for academic record security.", body_style)],
            [Paragraph("T-<br/>02", center_style), Paragraph("Requirement analysis and feasibility study", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>02", center_style), Paragraph("14-<br/>Mar-<br/>26", center_style), Paragraph("20-<br/>Mar-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("Roles and workflows identified for students, staff, admin, and verifier.", body_style)],
            [Paragraph("T-<br/>03", center_style), Paragraph("HLD preparation and database planning", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>03", center_style), Paragraph("21-<br/>Mar-<br/>26", center_style), Paragraph("27-<br/>Mar-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("Architecture, database schema, and peer-node design prepared.", body_style)],
            [Paragraph("T-<br/>04", center_style), Paragraph("Authentication and campus identity module", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>04", center_style), Paragraph("28-<br/>Mar-<br/>26", center_style), Paragraph("03-<br/>Apr-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("Login, registration, password hashing, and role sessions completed.", body_style)],
            [Paragraph("T-<br/>05", center_style), Paragraph("Ledger and certificate verification workflow", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>05", center_style), Paragraph("04-<br/>Apr-<br/>26", center_style), Paragraph("10-<br/>Apr-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("SHA-256 hash chain and public certificate verification implemented.", body_style)],
            [Paragraph("T-<br/>06", center_style), Paragraph("Admin tools, peer sync, GUI, and support", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>06", center_style), Paragraph("11-<br/>Apr-<br/>26", center_style), Paragraph("17-<br/>Apr-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("Admin users, audit logs, backup, peer sync, and support tools added.", body_style)],
            [Paragraph("T-<br/>07", center_style), Paragraph("Testing, screenshots, LLD, and final report", body_style), Paragraph("HashVera Academic Record Network", body_style), Paragraph("Week-<br/>07", center_style), Paragraph("18-<br/>Apr-<br/>26", center_style), Paragraph("24-<br/>Apr-<br/>26", center_style), Paragraph("Compl<br/>eted", center_style), Paragraph("Functional testing, HLD, LLD, snapshots, and final report completed.", body_style)],
        ]
        widths = [24, 58, 88, 41, 47, 47, 40, 81]
        row_heights = [13, 62] + [88] * 7
        table = Table(data, colWidths=widths, rowHeights=row_heights, repeatRows=2)
        table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 0), (-1, 0)),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.yellow),
                    ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#d9e7f5")),
                    ("FONTNAME", (0, 0), (-1, 1), HEADER_BOLD_FONT),
                    ("FONTNAME", (0, 2), (-1, -1), BODY_FONT),
                    ("FONTSIZE", (0, 0), (-1, 0), 10),
                    ("FONTSIZE", (0, 1), (-1, -1), 7),
                    ("ALIGN", (0, 0), (-1, 1), "CENTER"),
                    ("ALIGN", (0, 2), (0, -1), "CENTER"),
                    ("ALIGN", (3, 2), (6, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.black),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        _, h = table.wrapOn(self.c, CONTENT_W, y)
        table.drawOn(self.c, x, y - h)
        return y - h - 14

    def draw_box(self, x, y, w, h, text, size=9):
        self.c.setStrokeColor(colors.black)
        self.c.setFillColor(colors.white)
        self.c.rect(x, y - h, w, h, fill=True, stroke=True)
        self.c.setFillColor(colors.black)
        self.c.setFont(BOLD_FONT, size)
        lines = self.fit_line(text, w - 12, BOLD_FONT, size)
        total = len(lines) * (size + 2)
        ty = y - (h - total) / 2 - size
        for line in lines:
            self.c.drawCentredString(x + w / 2, ty, line)
            ty -= size + 2

    def arrow(self, x1, y1, x2, y2):
        self.c.setStrokeColor(colors.black)
        self.c.line(x1, y1, x2, y2)
        if x2 >= x1:
            self.c.line(x2, y2, x2 - 6, y2 + 3)
            self.c.line(x2, y2, x2 - 6, y2 - 3)
        else:
            self.c.line(x2, y2, x2 + 6, y2 + 3)
            self.c.line(x2, y2, x2 + 6, y2 - 3)

    def image(self, path, x, y, w, h, caption):
        path = Path(path)
        self.c.setStrokeColor(colors.black)
        self.c.rect(x, y - h, w, h, fill=False, stroke=True)
        if path.exists():
            image = ImageReader(str(path))
            iw, ih = image.getSize()
            scale = min((w - 8) / iw, (h - 8) / ih)
            dw, dh = iw * scale, ih * scale
            self.c.drawImage(image, x + (w - dw) / 2, y - (h + dh) / 2, dw, dh, mask="auto")
        else:
            self.c.setFont(BODY_FONT, 9)
            self.c.drawCentredString(x + w / 2, y - h / 2, f"Missing image: {path.name}")
        self.c.setFont(BOLD_FONT, 9)
        self.c.drawCentredString(x + w / 2, y - h - 12, caption)

    def save(self):
        self.c.save()


def add_text_page(report, title, paragraphs=None, bullets=None, table=None, chapter=None):
    y = report.start_page(title, chapter)
    for paragraph in paragraphs or []:
        y = report.paragraph(paragraph, LEFT, y)
    if bullets:
        y = report.bullets(bullets, LEFT, y)
    if table:
        y = report.table(table["data"], LEFT, y, table.get("widths"), table.get("font_size", 8.5))
    report.end_page()


def main():
    report = FinalReport(OUTPUT)

    # 1
    y = report.start_page()
    report.c.setFont(BOLD_FONT, 24)
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 120, "Final Project Report")
    report.c.setFont(BOLD_FONT, 18)
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 156, "Secure Decentralized Data Storage for EdTech")
    report.c.setFont(BOLD_FONT, 14)
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 205, "Project Name")
    report.c.setFont(BODY_FONT, 13)
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 228, "HashVera Academic Record Network")
    report.c.setFont(BOLD_FONT, 12)
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 270, "Technology Stack")
    report.c.setFont(BODY_FONT, 11)
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 292, "Python, Flask, SQLite, HTML, CSS, Jinja2, JavaScript")
    report.c.drawCentredString(PAGE_W / 2, PAGE_H - 314, "SHA-256, PBKDF2, HMAC, REST API")
    y = PAGE_H - 370
    y = report.paragraph(
        "HashVera is a secure academic record management system that protects certificates, marksheets, transcripts, and institutional documents using a blockchain-inspired hash chain. The final report follows an academic project format and includes HLD, LLD, implementation, testing, snapshots, evaluation, and future enhancement details.",
        LEFT,
        y,
        size=11.5,
        leading=16,
    )
    report.end_page()

    # 2-7 front matter
    add_text_page(
        report,
        "Certificate",
        [
            "This is to certify that the project titled Secure Decentralized Data Storage for EdTech has been successfully completed as a final year academic project. The submitted work presents the design and implementation of HashVera Academic Record Network, a Flask based platform for tamper-evident academic record storage and verification.",
            "The project demonstrates role based academic workflows, cryptographic integrity checking, public credential verification, administrative audit features, and peer node synchronization. The work has been prepared for academic submission and viva presentation.",
        ],
    )
    add_text_page(
        report,
        "Declaration",
        [
            "I hereby declare that this final project report is prepared for the project HashVera Academic Record Network under the topic Secure Decentralized Data Storage for EdTech. The report describes the objectives, system design, implementation, testing, results, limitations, and future scope of the developed application.",
            "The project has been designed and implemented using Python Flask, SQLite, Jinja templates, CSS, JavaScript, SHA-256 hashing, PBKDF2 password hashing, and HMAC based node signing. The report content is based on the working project files, design documents, and generated interface snapshots.",
        ],
    )
    add_text_page(
        report,
        "Acknowledgement",
        [
            "I express my sincere gratitude to the faculty members, project guides, reviewers, and academic coordinators who provided guidance during the preparation of this project. Their feedback helped refine the scope, security requirements, and presentation of the HashVera system.",
            "I also acknowledge the support of peers and users who participated in walkthroughs of login, registration, record verification, and administrative workflows. Their observations helped improve usability and confirmed that the system is suitable for academic demonstration.",
        ],
    )
    add_text_page(
        report,
        "Abstract",
        [
            "Academic institutions manage sensitive records such as marksheets, certificates, transcripts, identity information, and approval documents. Traditional centralized systems are simple to maintain but can make tampering difficult to detect unless strong audit and integrity controls are added.",
            "HashVera addresses this issue by creating a tamper-evident ledger where each academic record is stored as a block connected to the previous block through a cryptographic hash. Any unauthorized change in stored data breaks the hash chain and can be detected through verification.",
            "The project also provides campus identity activation, role based dashboards, public certificate verification, peer synchronization, support tickets, notifications, backups, exports, and audit logs. The result is a complete EdTech prototype for secure academic record management.",
        ],
    )
    toc = [
        ["Sl. No.", "Heading", "Page"],
        ["1", "Front Matter", "1-7"],
        ["2", "Executive Summary and Background", "8-13"],
        ["3", "Technology and Architecture", "14-21"],
        ["4", "High Level Design", "22-28"],
        ["5", "Low Level Design", "29-40"],
        ["6", "GUI, Implementation and Testing", "41-51"],
        ["7", "Evaluation, Conclusion and Appendix", "52-55"],
    ]
    add_text_page(report, "Table of Contents", table={"data": toc, "widths": [70, 330, 78], "font_size": 9})
    y = report.start_full_tracker_page()
    report.project_tracker(84, y - 52)
    report.end_full_tracker_page()

    # 8-21 overview
    add_text_page(
        report,
        "Executive Summary",
        [
            "HashVera Academic Record Network is a web based secure academic record system designed for Educational Technology environments. It addresses record tampering, slow manual verification, weak traceability, and dependency on a single central database.",
            "The system stores academic records in a blockchain-inspired ledger. Every block contains an index, timestamp, academic payload, previous hash, current hash, owner, nonce, certificate ID, and node signature. The ledger makes unauthorized database changes detectable.",
            "The application supports Students, Faculty, Exam Cell users, and Administrators. It includes campus directory based registration, staff record minting, student correction requests, review queue, public verification, peer node sync, notifications, support tickets, audit logs, backup, import, export, and dashboard analytics.",
        ],
        chapter="Chapter 1",
    )
    add_text_page(
        report,
        "Background",
        [
            "Educational institutions issue large numbers of records across semesters and departments. Students need quick access to their own documents, administrators need reliable governance, and employers need a way to verify certificates without waiting for manual confirmation.",
            "A conventional record portal generally stores data in ordinary tables and files. If internal controls are weak, a record may be changed without an obvious technical signal. HashVera introduces cryptographic linking so that integrity can be checked repeatedly and transparently.",
        ],
        bullets=[
            "Academic records require authenticity, traceability, and controlled access.",
            "Students should be able to view records without seeing data belonging to others.",
            "External verifiers should be able to validate a certificate ID or block hash.",
            "Administrators need audit logs, backup tools, peer settings, and user governance.",
        ],
    )
    add_text_page(
        report,
        "Problem Statement",
        [
            "The project problem is to design and implement a secure academic record platform that makes record tampering detectable, supports institutional roles, and provides fast credential verification for external users.",
            "The solution should work as an academic prototype without requiring a public blockchain deployment. It should also be simple enough to run locally for demonstration while still showing the principles of decentralized and tamper-evident storage.",
        ],
        bullets=[
            "Prevent undetected modification of academic records.",
            "Reduce manual verification dependency for certificates and transcripts.",
            "Provide clear separation between Student, Faculty, Exam Cell, and Administrator functions.",
            "Maintain a verifiable audit trail for sensitive operations.",
        ],
    )
    add_text_page(
        report,
        "Aim and Objectives",
        [
            "The main aim of HashVera is to design and implement a secure decentralized-style academic record storage system for EdTech use cases.",
        ],
        bullets=[
            "Develop a Flask based academic record portal with clear user workflows.",
            "Use SHA-256 hash chaining to make stored records tamper-evident.",
            "Use PBKDF2 password hashing and session controls for authentication.",
            "Allow campus users to activate accounts through preloaded campus identity data.",
            "Allow staff to mint, edit, archive, restore, review, and verify records.",
            "Provide a public portal for certificate verification and network audit visibility.",
            "Include HLD, LLD, testing evidence, screenshots, evaluation, and future scope.",
        ],
    )
    add_text_page(
        report,
        "Scope of the Project",
        [
            "The project scope covers a working educational credential system suitable for college project demonstration. It includes secure login, campus based registration, dashboard, record ledger, review workflows, admin controls, public verification, and peer synchronization.",
            "The system is intentionally designed as a private institutional network rather than a public cryptocurrency blockchain. This keeps deployment simple, avoids transaction fees, and protects private academic information.",
        ],
        bullets=[
            "Included: web portal, database schema, record hashing, verification, user roles, audit logs, backup, exports, support, and snapshots.",
            "Excluded: production cloud hosting, large scale distributed consensus, hardware security module integration, and real university SSO integration.",
        ],
    )
    add_text_page(
        report,
        "Feasibility Study",
        table={
            "data": [
                ["Feasibility Area", "Observation"],
                ["Technical", "The project is feasible using Python Flask, SQLite, Jinja templates, CSS, JavaScript, and standard cryptographic libraries."],
                ["Operational", "The workflows match realistic academic roles such as Student, Faculty, Exam Cell, and Administrator."],
                ["Economic", "The prototype uses open source tools and does not require paid blockchain infrastructure."],
                ["Schedule", "A modular Flask structure makes staged development and testing manageable."],
                ["Legal/Ethical", "The system supports privacy by restricting student access to their own records and giving public users only verification views."],
            ],
            "widths": [130, 348],
        },
    )
    add_text_page(
        report,
        "Technologies Used",
        table={
            "data": [
                ["Layer", "Technology", "Purpose"],
                ["Frontend", "HTML, CSS, Jinja2, JavaScript", "Forms, dashboards, certificate views, public verification pages"],
                ["Backend", "Python Flask", "Routing, sessions, business logic, blueprints"],
                ["Database", "SQLite", "Users, blocks, nodes, requests, support tickets, audit logs"],
                ["Security", "PBKDF2, SHA-256, HMAC", "Password hashing, record hashes, node signatures"],
                ["Testing", "unittest, Flask test client", "Functional and security workflow tests"],
                ["PDF", "ReportLab", "Generated project report and certificate PDFs"],
            ],
            "widths": [80, 150, 248],
            "font_size": 8,
        },
    )
    add_text_page(
        report,
        "Hardware Architecture",
        [
            "The prototype can run on a standard laptop or desktop machine. For institutional deployment, each trusted node can be hosted on a campus server or cloud virtual machine. A browser is used by students, staff, administrators, and external verifiers.",
        ],
        table={
            "data": [
                ["Component", "Minimum Requirement", "Recommended"],
                ["Client", "Modern browser, 2 GB RAM", "Chrome/Edge/Firefox, 4 GB RAM"],
                ["Application Node", "Dual core CPU, 4 GB RAM", "4 core CPU, 8 GB RAM"],
                ["Storage", "500 MB for demo", "Encrypted persistent volume"],
                ["Network", "Localhost/LAN", "HTTPS with trusted peer connectivity"],
            ],
            "widths": [120, 170, 188],
        },
    )
    add_text_page(
        report,
        "Software Architecture",
        [
            "HashVera follows a modular monolith architecture. The application is implemented as a Flask package with separate blueprints for authentication, records, administration, public pages, and peer APIs. Shared logic is placed in utility modules.",
        ],
        bullets=[
            "hashvera.routes.auth handles login, logout, campus activation, OTP, reset password, and change password.",
            "hashvera.routes.records handles dashboard, records, verification, profile, review queue, certificates, and bulk minting.",
            "hashvera.routes.admin handles user management, peer nodes, audit logs, backups, imports, exports, support inbox, and security audit.",
            "hashvera.routes.api exposes peer health, chain read, and chain sync endpoints.",
            "hashvera.utils contains hashing, blockchain, records, files, email, SMS, reporting, notifications, and audit helpers.",
        ],
    )
    add_text_page(
        report,
        "System Overview",
        [
            "The system starts with campus directory data. A user activates an account by entering a campus ID. The app looks up the official identity, prevents duplicate activation, and stores a secure password hash.",
            "Authorized staff can create academic records. Each record is converted into a canonical payload, linked with the previous block hash, signed by the local node, and stored in the blocks table. Students can later view their own records by campus identity matching.",
        ],
    )
    add_text_page(
        report,
        "Functional Requirements",
        bullets=[
            "The system shall allow campus based registration using preloaded campus IDs.",
            "The system shall authenticate users through campus email and password.",
            "The system shall provide different dashboard actions for Student, Faculty, Exam Cell, and Administrator roles.",
            "The system shall create tamper-evident academic record blocks.",
            "The system shall verify full chain integrity and individual certificate IDs.",
            "The system shall allow students to request new records and record corrections.",
            "The system shall allow staff to review, approve, reject, mint, edit, archive, restore, and export records.",
            "The system shall maintain audit logs, notifications, support tickets, and database backups.",
        ],
    )
    add_text_page(
        report,
        "Non-Functional Requirements",
        table={
            "data": [
                ["Requirement", "Description"],
                ["Security", "Password hashing, role checks, CSRF checks, peer token checks, HMAC block signatures"],
                ["Integrity", "Hash chain recalculation detects payload, previous hash, and block hash mismatch"],
                ["Usability", "Role based dashboards and readable certificate verification screens"],
                ["Maintainability", "Blueprint based Flask package and reusable utility modules"],
                ["Portability", "SQLite and local files make the demo easy to run on a single machine"],
                ["Auditability", "Administrative and record actions are stored in audit logs"],
            ],
            "widths": [130, 348],
        },
    )
    add_text_page(
        report,
        "User Requirements",
        table={
            "data": [
                ["User", "Needs"],
                ["Student", "Activate account, sign in, view own records, request records, request corrections, verify certificates"],
                ["Faculty", "Create academic records, review requests, view profile directory, monitor staff dashboard"],
                ["Exam Cell", "Mint records, edit records, archive/restore records, bulk issue certificates, review requests"],
                ["Administrator", "Manage users, roles, peers, audits, backups, imports, exports, support tickets, and security checks"],
                ["External Verifier", "Check certificate authenticity through public certificate ID or block hash"],
            ],
            "widths": [110, 368],
            "font_size": 8,
        },
    )
    add_text_page(
        report,
        "Environmental Requirements",
        bullets=[
            "Python runtime with Flask dependencies installed.",
            "SQLite database file available to the application process.",
            "Writable upload and backup directories for files and database backups.",
            "Secret key, node signing secret, peer shared token, and optional email/SMS settings configured through environment variables.",
            "Modern browser for the interface and PDF/certificate preview workflows.",
            "HTTPS is recommended for any deployment beyond local demonstration.",
        ],
    )

    # 22-28 HLD
    add_text_page(
        report,
        "High Level Design Introduction",
        [
            "The High Level Design describes the system from a macro architectural perspective. It explains the external actors, containers, core subsystems, deployment model, security concerns, and major design trade-offs.",
            "HashVera is designed as a private trusted academic network. Each institution node can keep its own database while exchanging ledger data with approved peers through authenticated APIs.",
        ],
        chapter="Chapter 2: HLD",
    )
    y = report.start_page("System Context Diagram", "Chapter 2: HLD")
    report.draw_box(70, y - 10, 100, 45, "Student")
    report.draw_box(70, y - 90, 100, 45, "Faculty / Exam Cell")
    report.draw_box(70, y - 170, 100, 45, "Administrator")
    report.draw_box(70, y - 250, 100, 45, "External Verifier")
    report.draw_box(250, y - 95, 150, 70, "HashVera Core System")
    report.draw_box(450, y - 95, 90, 70, "Peer Node")
    report.arrow(170, y - 32, 250, y - 80)
    report.arrow(170, y - 112, 250, y - 102)
    report.arrow(170, y - 192, 250, y - 124)
    report.arrow(170, y - 272, 250, y - 146)
    report.arrow(400, y - 130, 450, y - 130)
    y -= 355
    report.paragraph("Figure 1 shows the main users of the application and the trusted peer node that exchanges ledger data with the core system.", LEFT, y)
    report.end_page()
    y = report.start_page("Container Architecture Diagram", "Chapter 2: HLD")
    report.draw_box(70, y - 10, 100, 45, "Web Browser")
    report.draw_box(230, y - 10, 120, 45, "Flask WSGI App")
    report.draw_box(410, y - 10, 100, 45, "SQLite DB")
    report.arrow(170, y - 32, 230, y - 32)
    report.arrow(350, y - 32, 410, y - 32)
    yy = y - 100
    report.draw_box(80, yy, 100, 45, "Templates")
    report.draw_box(200, yy, 100, 45, "Auth")
    report.draw_box(320, yy, 100, 45, "Records")
    report.draw_box(440, yy, 100, 45, "Admin/API")
    report.arrow(280, y - 55, 130, yy)
    report.arrow(280, y - 55, 250, yy)
    report.arrow(280, y - 55, 370, yy)
    report.arrow(280, y - 55, 490, yy)
    y -= 230
    report.paragraph("Figure 2 represents HashVera as a modular monolith. The codebase is one deployable application, but responsibilities are separated through Flask blueprints and utility modules.", LEFT, y)
    report.end_page()
    add_text_page(
        report,
        "Core Subsystems",
        table={
            "data": [
                ["Subsystem", "Responsibility"],
                ["Identity and Authentication", "Campus activation, login, logout, password recovery, session setup, role values"],
                ["Blockchain Storage Engine", "Record payload creation, previous hash lookup, nonce generation, SHA-256 block hash, HMAC signature"],
                ["Review Workflow", "Student requests, correction requests, review queue, approval, rejection, notifications"],
                ["Administration", "Users, roles, peers, support inbox, audit logs, backups, exports, security audit"],
                ["Public Verification", "Certificate ID and block hash based verification for external users"],
                ["Peer Synchronization", "Health checks, chain reads, authenticated chain sync, node status updates"],
            ],
            "widths": [150, 328],
            "font_size": 8,
        },
    )
    y = report.start_page("Deployment Architecture", "Chapter 2: HLD")
    report.draw_box(240, y - 10, 110, 40, "Internet / LAN")
    report.draw_box(90, y - 90, 120, 50, "HashVera Node A")
    report.draw_box(380, y - 90, 120, 50, "HashVera Node B")
    report.draw_box(90, y - 180, 120, 40, "SQLite DB A")
    report.draw_box(380, y - 180, 120, 40, "SQLite DB B")
    report.draw_box(235, y - 270, 120, 50, "Remote Peer Node")
    report.arrow(295, y - 50, 150, y - 90)
    report.arrow(295, y - 50, 440, y - 90)
    report.arrow(150, y - 140, 150, y - 180)
    report.arrow(440, y - 140, 440, y - 180)
    report.arrow(210, y - 115, 380, y - 115)
    report.arrow(440, y - 140, 355, y - 270)
    y -= 365
    report.paragraph("Figure 3 shows each HashVera node keeping its own database while synchronizing with trusted peers. This supports decentralization by replication in a controlled institutional network.", LEFT, y)
    report.end_page()
    add_text_page(
        report,
        "Security Architecture",
        bullets=[
            "PBKDF2 hashes protect stored passwords with salts.",
            "CSRF tokens are used for state changing forms.",
            "Role checks restrict staff and administrator routes.",
            "Students are restricted to records linked to their own campus identity.",
            "Peer APIs require a shared token header before chain data is accepted.",
            "HMAC signatures identify the local node that minted a block.",
            "Audit logs record sensitive administrative and record actions.",
        ],
    )
    add_text_page(
        report,
        "HLD Trade-Offs",
        table={
            "data": [
                ["Decision", "Reason", "Trade-Off"],
                ["SQLite", "Simple local demo and easy backups", "Limited concurrent write scale compared to PostgreSQL"],
                ["Private chain", "No gas fees and better privacy", "Trust is institutional, not global public consensus"],
                ["Modular monolith", "Simple deployment for academic project", "Large production teams may prefer services"],
                ["File uploads on disk", "Easy prototype storage", "Cloud/object storage preferred in production"],
            ],
            "widths": [110, 185, 183],
            "font_size": 8,
        },
    )

    # 29-40 LLD
    add_text_page(
        report,
        "Low Level Design Introduction",
        [
            "The Low Level Design explains internal modules, database tables, routes, helper functions, state transitions, and algorithms. It is useful for developers who need to maintain or extend the HashVera codebase.",
            "The implementation is organized around Flask blueprints, SQLite tables, and small utility modules. Each route performs validation, permission checks, database operations, and redirects or renders a template.",
        ],
        chapter="Chapter 3: LLD",
    )
    add_text_page(
        report,
        "Database Design: Users and Directory",
        table={
            "data": [
                ["Table", "Important Fields", "Purpose"],
                ["users", "id, username, campus_id, email, password_hash, password_salt, role, disabled, last_login_at", "Application accounts and authentication state"],
                ["campus_directory", "campus_id, full_name, campus_email, role, department, is_registered", "Pre-approved institutional identity source"],
                ["password_resets", "user_id, token, otp_code, expires_at, used_at", "OTP/token based password recovery"],
            ],
            "widths": [115, 218, 145],
            "font_size": 7.5,
        },
    )
    add_text_page(
        report,
        "Database Design: Ledger Blocks",
        table={
            "data": [
                ["Field", "Description"],
                ["block_index", "Unique sequence number of the record block"],
                ["timestamp", "UTC timestamp when the block was created"],
                ["payload", "Canonical JSON academic record payload"],
                ["previous_hash", "Hash value of the previous block"],
                ["block_hash", "SHA-256 hash of current block data"],
                ["nonce", "Random value used to diversify hash input"],
                ["owner", "Username or identity of record owner"],
                ["certificate_id", "Public verification token"],
                ["block_signature", "HMAC signature from the local node"],
                ["record_status", "Active, archived, or related academic status"],
            ],
            "widths": [150, 328],
            "font_size": 8,
        },
    )
    add_text_page(
        report,
        "Database Design: Workflow Tables",
        table={
            "data": [
                ["Table", "Purpose"],
                ["nodes", "Stores peer node name, URL, token, node type, sync status, last synced block, and integrity hash"],
                ["record_requests", "Stores student requests for new records and corrections with status, reviewer, and response"],
                ["notifications", "Stores recipient messages, read state, event type, and related links"],
                ["support_tickets", "Stores support category, priority, message, status, reply, and archive state"],
                ["audit_logs", "Stores actor, action, resource type, resource id, details, IP address, and user agent"],
            ],
            "widths": [130, 348],
            "font_size": 8,
        },
    )
    add_text_page(
        report,
        "Authentication Module Design",
        [
            "The authentication module is responsible for protecting entry into the system and connecting every user account with an approved campus identity. It is designed so that account creation does not happen from arbitrary public input; instead, the campus directory acts as the trusted identity source.",
        ],
        bullets=[
            "GET /login renders the login form and redirects already authenticated users to the dashboard.",
            "POST /login validates the CSRF token before any credential checking is performed.",
            "The submitted campus email is searched in the users table and the stored password salt is used to calculate a PBKDF2 hash.",
            "The calculated hash is compared with the stored password_hash value to avoid storing or comparing plain text passwords.",
            "Disabled user accounts are rejected before the session is created, which allows administrators to block access without deleting records.",
            "Successful login stores user_id, username, campus_id, email, and role details in the session for later authorization checks.",
            "GET/POST /register performs campus ID lookup from campus_directory and displays the official name, role, department, and campus email.",
            "The registration route prevents the same campus identity from being activated more than once.",
            "Forgot password routes create OTP/reset state, store expiry details, and guide the user through verification before password reset.",
            "GET/POST /change-password verifies the current password first and then stores a fresh PBKDF2 hash and salt.",
            "Authentication events are linked with audit and notification behavior where required for traceability.",
        ],
    )
    add_text_page(
        report,
        "Records and Ledger Module Design",
        [
            "The records module is the operational core of HashVera. It connects user-facing academic forms with the blockchain-inspired storage layer and ensures that every stored record has enough metadata for ownership, verification, audit, and future review.",
        ],
        bullets=[
            "Dashboard gathers blocks, users, logs, chain status, metrics, charts, and role-based action panels.",
            "Students see only their own academic records, while staff users see review and record management actions according to role.",
            "add_block validates staff permissions, required academic fields, record type, record status, and optional uploaded file metadata.",
            "The record payload is serialized in a stable order so that hash calculation remains deterministic.",
            "The blockchain helper reads the latest block, assigns the next index, sets previous_hash, creates a nonce, and computes the current block hash.",
            "The node signs the block hash with an HMAC secret so the origin of the block can be identified in a trusted network.",
            "view_record protects student access by checking the owner field and campus identity mapping before rendering details.",
            "edit routes update allowed metadata while preserving audit information and rebuilding the affected chain when required.",
            "archive and restore routes support soft lifecycle control without permanently destroying academic evidence.",
            "bulk_mint reads uploaded CSV rows, validates each row, and creates multiple blocks in a controlled batch workflow.",
            "Record pages display certificate ID, block hash, previous hash, status, owner, and file information for verification.",
        ],
    )
    add_text_page(
        report,
        "Verification Module Design",
        [
            "The verification module proves the main security idea of the project. It allows internal users and public verifiers to check whether a certificate or the entire chain still matches the cryptographic values stored at the time of record creation.",
        ],
        bullets=[
            "verify_chain loads all blocks in ascending block_index order and recalculates each block hash.",
            "The recalculation checks whether the current payload, timestamp, previous hash, owner, and nonce still produce the stored hash.",
            "The previous_hash of every block is compared with the block_hash of the previous record to detect broken chain links.",
            "Any mismatch is reported as an integrity issue and can be shown to staff or administrators.",
            "verify_chain_ajax exposes the same validation for asynchronous dashboard checks without reloading the full page.",
            "certificate_verify searches by public certificate ID or block hash and returns the matching academic record details.",
            "The public verification result avoids exposing private administrative controls while still proving authenticity.",
            "certificate_preview renders a certificate-style page for a selected block using the stored academic payload.",
            "certificate_pdf creates a downloadable certificate PDF for institutional sharing and demonstration.",
            "Public audit views summarize chain health so external users can understand the verification status.",
        ],
    )
    add_text_page(
        report,
        "Administrative Module Design",
        [
            "The administrative module provides governance features needed in an academic system. It gives administrators controlled tools to manage users, recover accounts, monitor security activity, maintain peer nodes, and preserve backups.",
        ],
        bullets=[
            "admin_users lists registered users with role, email, campus ID, disabled state, and management actions.",
            "Administrators can update roles when a user changes responsibility, such as Faculty to Exam Cell.",
            "Campus ID update is protected because it affects record ownership and student access isolation.",
            "Password reset tools allow administrative recovery without revealing existing passwords.",
            "Enable and disable actions support temporary account blocking while preserving historical records.",
            "admin_peers manages trusted peer node records, connection tests, tokens, node status, and manual sync operations.",
            "audit_logs provides filters for actor, action type, resource type, and timestamp for administrative monitoring.",
            "admin_system provides database backup, backup download, backup deletion, import, export, and email test actions.",
            "support_inbox lets administrators respond to tickets, update status, archive, unarchive, and remove obsolete requests.",
            "security_audit summarizes operational checks such as secret values, user status, audit availability, and chain health.",
            "Administrative actions are designed to be traceable so that sensitive changes are not silent.",
        ],
    )
    add_text_page(
        report,
        "Peer API Module Design",
        table={
            "data": [
                ["Endpoint", "Method", "Purpose"],
                ["/api/health", "GET", "Returns node health and status for peer testing"],
                ["/api/chain", "GET", "Returns local chain metadata and records for synchronization"],
                ["/api/chain/sync", "POST", "Accepts a peer chain payload after token validation and adopts a longer valid chain when appropriate"],
            ],
            "widths": [150, 70, 258],
            "font_size": 8,
        },
    )
    add_text_page(
        report,
        "Notifications and Support Design",
        bullets=[
            "Notifications are created for account, record, request, and system events.",
            "Notification pages show unread and read messages with timestamps and related links.",
            "Student and public support forms collect category, subject, message, priority, and contact details.",
            "Administrators can update support ticket status and reply from a central inbox.",
            "Support history allows users to review previously submitted tickets.",
        ],
    )
    add_text_page(
        report,
        "Hashing and Signing Algorithms",
        table={
            "data": [
                ["Step", "Operation"],
                ["1", "Build canonical academic payload from validated form data and file metadata"],
                ["2", "Fetch latest block_index and block_hash from blocks table"],
                ["3", "Set next_index and previous_hash"],
                ["4", "Generate UTC timestamp and random nonce"],
                ["5", "Compute SHA-256 hash over index, timestamp, payload, previous hash, owner, and nonce"],
                ["6", "Compute HMAC signature using local node signing secret"],
                ["7", "Insert block and update local node sync summary"],
            ],
            "widths": [60, 418],
            "font_size": 8,
        },
    )
    y = report.start_page("State Machine and Logic Flow", "Chapter 3: LLD")
    report.draw_box(60, y - 10, 90, 40, "Submitted")
    report.draw_box(190, y - 10, 90, 40, "Pending")
    report.draw_box(320, y - 10, 90, 40, "Approved")
    report.draw_box(450, y - 10, 90, 40, "Minted")
    report.draw_box(320, y - 100, 90, 40, "Rejected")
    report.arrow(150, y - 30, 190, y - 30)
    report.arrow(280, y - 30, 320, y - 30)
    report.arrow(410, y - 30, 450, y - 30)
    report.arrow(280, y - 30, 320, y - 120)
    y -= 190
    report.paragraph("Figure 4 shows the record request state machine. A request starts when a student submits it, moves to pending review, and is either approved for minting or rejected with reviewer feedback.", LEFT, y)
    y -= 80
    report.subheading("Important Logic Flow", LEFT, y)
    y -= 24
    report.bullets(
        [
            "Student submits request with record details and optional correction context.",
            "Faculty or Exam Cell user reviews the request from review queue.",
            "Approval may create a new block or update the workflow state.",
            "Notifications are sent to the student after the reviewer action.",
        ],
        LEFT,
        y,
    )
    report.end_page()

    # 41-51 GUI, implementation, testing
    add_text_page(
        report,
        "Graphical User Interface Design",
        [
            "The interface is designed around institutional workflows. Authentication pages are simple and centered, dashboards are role based, record pages emphasize certificate ID and hash values, and admin pages use tables, filters, status badges, and action buttons.",
        ],
        table={
            "data": [
                ["Page", "Main GUI Elements"],
                ["Login", "Campus email, password field, sign in button, create account, forgot password"],
                ["Register", "Campus ID lookup, auto-filled identity details, password setup"],
                ["Dashboard", "Metrics, charts, record lists, chain status, role actions"],
                ["Record Detail", "Academic payload, certificate ID, block hash, previous hash, owner, status"],
                ["Admin Pages", "Tables, filters, role controls, backup/import/export panels"],
                ["Public Verify", "Certificate search, result card, integrity details"],
            ],
            "widths": [120, 358],
            "font_size": 8,
        },
        chapter="Chapter 4",
    )
    y = report.start_page("Login and Registration Snapshots", "Chapter 4")
    report.image(SNAPSHOTS / "01-login.png", LEFT, y, 230, 155, "Figure 5: Login Page")
    report.image(SNAPSHOTS / "02-register.png", LEFT + 248, y, 230, 155, "Figure 6: Campus Activation")
    y -= 210
    report.paragraph("The login and campus activation views are the entry points of the system. Campus based registration improves institutional trust because users cannot self-register with arbitrary identity values.", LEFT, y)
    report.end_page()
    y = report.start_page("Dashboard and Record Snapshots", "Chapter 4")
    report.image(SNAPSHOTS / "b.4.PNG", LEFT, y, 230, 155, "Figure 7: Dashboard View")
    report.image(SNAPSHOTS / "b.5.PNG", LEFT + 248, y, 230, 155, "Figure 8: Record View")
    y -= 210
    report.paragraph("Dashboard and record screens show the operational side of HashVera. Users can review metrics, inspect record details, and understand the certificate ID and hash fields that support verification.", LEFT, y)
    report.end_page()
    y = report.start_page("Public Verification and Audit Snapshots", "Chapter 4")
    report.image(SNAPSHOTS / "03-public-verify.png", LEFT, y, 230, 145, "Figure 9: Public Verify")
    report.image(SNAPSHOTS / "04-public-audit.png", LEFT + 248, y, 230, 145, "Figure 10: Public Audit")
    y -= 195
    report.image(SNAPSHOTS / "05-support.png", LEFT, y, 230, 145, "Figure 11: Support")
    report.image(SNAPSHOTS / "06-faq.png", LEFT + 248, y, 230, 145, "Figure 12: FAQ")
    report.end_page()
    add_text_page(
        report,
        "Implementation: Authentication",
        [
            "The authentication implementation follows the campus identity model of the project. A user does not create an account as a free-form public profile; the system first confirms that the campus ID exists in the preloaded campus directory and then activates that identity only once.",
            "During login, the application accepts the campus email and password, validates the CSRF token, retrieves the stored password salt, recalculates the PBKDF2 hash, and creates a session only after the credentials and account status are valid.",
        ],
        bullets=[
            "Campus email is used for login because it is more institution-friendly than a self-chosen username.",
            "PBKDF2 password hashing is used so that raw passwords are never saved in the database.",
            "A separate salt is stored for each user account, which improves protection against precomputed password attacks.",
            "Session variables store user identity and role so protected routes can apply role-based checks.",
            "Registration begins with campus ID lookup and automatically maps official name, campus email, department, and role.",
            "Repeated activation is prevented by checking whether the campus directory identity is already registered.",
            "Forgot-password workflows use OTP/token records with expiry time and usage state so old reset attempts cannot be reused.",
            "Change-password flow verifies the old password before replacing it with a new hashed password.",
            "Disabled accounts are blocked during login while preserving their historical records and audit trail.",
            "Administrators can enable or disable accounts from the user management panel when access has to be controlled.",
            "Successful and sensitive account actions support auditability because user identity is available throughout the request.",
        ],
    )
    add_text_page(
        report,
        "Implementation: Records and Ledger",
        [
            "Record implementation converts academic information into a structured block. The block contains the academic payload and technical metadata such as previous hash, current hash, nonce, owner, certificate ID, timestamp, and node signature.",
            "This implementation makes the record tamper-evident. If someone changes the stored payload directly in the database, the recalculated hash will not match the stored block hash and chain verification will report the issue.",
        ],
        bullets=[
            "Record creation validates the staff role before accepting academic data.",
            "The form data includes student identity, document name, record type, status, description, and optional file details.",
            "The payload builder serializes the record consistently so the same input produces the same hash material.",
            "The blockchain helper fetches the latest block and uses its block_hash as the new previous_hash.",
            "The next block_index is assigned sequentially to preserve the ledger order.",
            "A random nonce and UTC timestamp are added before hash calculation.",
            "SHA-256 is used to compute the block_hash from the important block fields.",
            "HMAC signing records the local node identity and helps verify the source of minted records.",
            "The final block is inserted into SQLite and the local node sync summary is updated.",
            "Chain verification reloads blocks in index order and recalculates both hash values and previous-hash relationships.",
            "Certificate verification searches by public certificate ID or block hash and displays the matching academic details.",
            "Record archive and restore functions support lifecycle management without hiding the verification history.",
        ],
    )
    add_text_page(
        report,
        "Implementation: Admin, Backup and Export",
        [
            "The administrative implementation turns the application from a simple record portal into a governed institutional system. It includes user control, peer node configuration, audit visibility, support handling, database safety, and reporting tools.",
        ],
        bullets=[
            "User administration supports role changes, campus ID updates, password resets, enable/disable, and account deletion.",
            "Role updates are restricted because staff and administrator roles can create or modify academic records.",
            "Campus ID changes are handled carefully because campus ID is linked to student record ownership.",
            "Peer administration stores trusted node name, peer URL, shared token, status, and synchronization metadata.",
            "Peer connection testing checks whether another node is reachable before attempting sync.",
            "Manual sync allows an administrator to compare local and peer chains and adopt a valid longer chain when appropriate.",
            "System administration creates database backups before risky operations so recovery is possible.",
            "Backup download and deletion actions help maintain local storage during demonstrations.",
            "CSV and PDF exports support academic submission, administration review, and offline reporting.",
            "Email testing helps verify notification settings without waiting for a real workflow event.",
            "Audit logs provide traceability for record creation, user changes, peer actions, backups, and security-related operations.",
            "Support inbox implementation lets administrators respond to user issues from inside the same platform.",
        ],
    )
    add_text_page(
        report,
        "Testing Strategy",
        [
            "Testing covers route behavior, security controls, database operations, chain verification, role separation, and user workflow correctness. The project includes a unittest suite using the Flask test client and a temporary SQLite database.",
            "The test environment uses a temporary instance directory, upload directory, backup directory, and SQLite database. This allows tests to run without damaging the real demonstration database or uploaded files.",
        ],
        bullets=[
            "Functional tests verify login, redirects, registration, records, requests, admin actions, backup creation, and profile flows.",
            "Security tests verify CSRF behavior, password strength rules, disabled account blocking, role restrictions, and student record isolation.",
            "Integrity tests verify the seeded chain and detect tamper scenarios by recalculating block hashes.",
            "Admin tests confirm that administrators can disable, enable, and update users through protected routes.",
            "Backup tests confirm that database backup files are created with the expected extension.",
            "Authentication tests confirm that successful login updates last_login_at for audit and usage tracking.",
            "Password validation tests confirm that weak passwords are rejected before storage.",
            "The Flask test client is used so route behavior can be checked without opening a browser manually.",
            "Manual testing was also performed for dashboard, public verification, support, FAQ, and certificate preview pages.",
        ],
    )
    add_text_page(
        report,
        "Functional Test Cases",
        table={
            "data": [
                ["Test Case", "Input / Action", "Expected Result"],
                ["Valid login", "Submit campus email, valid password, and CSRF token", "User session is created and user is redirected to dashboard"],
                ["Invalid login", "Submit wrong password for an existing account", "Login fails and user remains on authentication flow"],
                ["Campus registration", "Submit campus ID from campus_directory with new password", "Directory identity is activated once and linked to user account"],
                ["Duplicate registration", "Try to activate the same campus identity again", "System prevents repeated activation"],
                ["Admin disable user", "Administrator disables a student account", "Target account cannot sign in until enabled"],
                ["Admin enable user", "Administrator enables the disabled account", "User can sign in again with valid credentials"],
                ["Role update", "Administrator changes role from Student to Exam Cell", "Updated role is stored and reflected in permissions"],
                ["Record mint", "Staff submits valid academic record form", "New block is added with valid hash and certificate ID"],
                ["Chain verify", "Run ledger verification on seeded valid chain", "System reports valid chain with no issues"],
                ["Backup creation", "Administrator clicks database backup action", "SQLite backup file is created in backup directory"],
                ["Review request", "Staff approves or rejects student request", "Request status, reviewer details, and notification are updated"],
            ],
            "widths": [112, 178, 188],
            "font_size": 7,
        },
    )
    add_text_page(
        report,
        "Security Test Cases",
        table={
            "data": [
                ["Security Area", "Test Action", "Expected Result"],
                ["CSRF", "Submit state-changing POST request without valid token", "Request is rejected or redirected and data is not changed"],
                ["Password policy", "Try password without special character or required strength", "Weak password is rejected with clear validation message"],
                ["Password storage", "Inspect user table after registration", "Raw password is absent; only hash and salt are stored"],
                ["Disabled account", "Disable account and attempt login", "Login is blocked with disabled-account feedback"],
                ["Role protection", "Student attempts staff/admin URL", "Unauthorized access is denied or redirected"],
                ["Student isolation", "Student tries to view another student's record", "Record is not displayed to unauthorized student"],
                ["Peer token", "Call peer sync endpoint without valid shared token", "Unauthorized API request is rejected"],
                ["Hash tampering", "Modify stored payload or previous hash directly", "Chain verification detects mismatch"],
                ["Auditability", "Perform sensitive admin action", "Audit log stores actor, action, resource, and timestamp"],
            ],
            "widths": [112, 178, 188],
            "font_size": 7,
        },
    )
    add_text_page(
        report,
        "Customer Testing and Feedback",
        [
            "Customer testing was planned from the viewpoint of the main user groups. Each user group was asked to perform the workflow that would be natural for them in an academic institution.",
        ],
        table={
            "data": [
                ["User Type", "Activity Performed", "Feedback"],
                ["Student", "Activated account, logged in, viewed personal records, submitted correction request", "Campus login and personal record view are easy to understand"],
                ["Faculty", "Created record and reviewed student request", "Review queue and record creation match academic workflows"],
                ["Exam Cell", "Minted records, edited metadata, archived/restored records, previewed certificates", "Bulk minting, edit, archive, restore, and certificate preview are useful"],
                ["Administrator", "Managed users, roles, peers, backups, audit logs, and support inbox", "Admin tools improve governance and project demonstration value"],
                ["External Verifier", "Searched certificate ID through public verification page", "Certificate ID based verification is fast and simple"],
                ["Overall", "Navigated dashboard, verification, FAQ, and support pages", "The system is understandable as an academic credential verification prototype"],
            ],
            "widths": [100, 190, 188],
            "font_size": 7,
        },
    )

    # 52-55 wrap-up
    add_text_page(
        report,
        "Evaluation",
        table={
            "data": [
                ["Criterion", "Evaluation", "Remarks"],
                ["Security", "Strong for academic prototype", "Uses password hashing, sessions, CSRF, role checks, disabled-account blocking, and API token checks"],
                ["Integrity", "Strong", "Hash chain verification detects unauthorized changes in payload, block hash, or previous hash"],
                ["Usability", "Good", "Role-based dashboards and public verification are clear for students, staff, administrators, and verifiers"],
                ["Maintainability", "Good", "Flask blueprints separate authentication, records, administration, API, and utility logic"],
                ["Scalability", "Moderate", "SQLite is suitable for demo; PostgreSQL and object storage are recommended for production"],
                ["Auditability", "Strong", "Sensitive user, record, peer, and system operations are traceable through audit logs"],
                ["Extensibility", "Good", "Future features such as QR codes, SSO, and public-chain anchoring can be added without redesigning the project"],
            ],
            "widths": [98, 130, 250],
            "font_size": 7,
        },
        chapter="Chapter 5",
    )
    add_text_page(
        report,
        "Limitations and Future Scope",
        [
            "The present version is suitable for academic demonstration and controlled institutional testing. For real production use, the system would require stronger hosting, compliance, monitoring, and infrastructure-level security.",
        ],
        bullets=[
            "Migrate SQLite to PostgreSQL for production write concurrency, stronger indexing, and managed backup strategies.",
            "Move uploaded documents to encrypted cloud object storage or IPFS-style content addressing for safer file management.",
            "Add QR codes to certificate PDFs so external users can open the verification page directly from a printed document.",
            "Add two-factor authentication for administrators, Exam Cell users, and other high-privilege staff roles.",
            "Add institutional SSO integration so real campus users can authenticate through the official university identity provider.",
            "Add Merkle proof generation and optional public blockchain anchoring for stronger external trust without exposing private student data.",
            "Add richer analytics by department, semester, course, record type, verification count, and correction request status.",
            "Add automated email and SMS notifications for request approval, correction rejection, certificate issue, and password recovery events.",
            "Add stronger file scanning and content-type validation before storing uploaded documents.",
            "Add deployment monitoring, error reporting, and scheduled backup verification for production readiness.",
            "Add multilingual interface support if the system is used across different regions or campuses.",
        ],
    )
    add_text_page(
        report,
        "Conclusion",
        [
            "HashVera Academic Record Network successfully demonstrates a secure and practical approach to academic record management using blockchain-inspired hash chaining. It solves a meaningful EdTech problem by combining record integrity, user governance, public verification, and administrative auditability.",
            "The project includes a working Flask application with campus identity activation, role based workflows, record minting, chain verification, support tickets, backups, peer synchronization, certificates, and dashboard views. The HLD and LLD show that the design is understandable, maintainable, and extendable.",
            "The implementation proves that blockchain concepts can be applied in a lightweight private institutional environment. Instead of depending on a public blockchain network, the project uses hash-linked records, peer synchronization, HMAC signing, and audit logs to demonstrate tamper-evident storage.",
            "Students benefit from controlled access to their own records, staff benefit from structured record and review workflows, administrators benefit from governance tools, and external verifiers benefit from fast certificate validation.",
            "The final conclusion is that HashVera meets the stated aim and provides a strong foundation for secure decentralized academic record storage in educational institutions.",
        ],
    )
    y = report.start_page("References and Appendix", "Chapter 5")
    y = report.table(
        [
            ["Sl. No.", "Reference"],
            ["1", "Python Software Foundation, Python documentation"],
            ["2", "Flask web framework documentation"],
            ["3", "SQLite database documentation"],
            ["4", "NIST Secure Hash Standard and SHA-256 references"],
            ["5", "PBKDF2 password hashing references"],
            ["6", "OWASP web security guidelines"],
            ["7", "ReportLab PDF generation documentation"],
            ["8", "Project source code: HashVera Academic Record Network"],
        ],
        LEFT,
        y,
        [60, 418],
        font_size=8,
    )
    y = report.subheading("Appendix: Important Project Files", LEFT, y)
    report.table(
        [
            ["File or Folder", "Description"],
            ["app.py / run.py", "Application launchers"],
            ["hashvera/database.py", "SQLite schema, seeding, backups, and migrations"],
            ["hashvera/routes/auth.py", "Authentication and password routes"],
            ["hashvera/routes/records.py", "Dashboard, records, certificates, review queue, profile flows"],
            ["hashvera/routes/admin.py", "Administration, peers, support, audit, backups, exports"],
            ["hashvera/routes/api.py", "Peer health, chain, and sync API"],
            ["templates/ and static/", "User interface templates and assets"],
            ["tests/test_app.py", "Automated functional/security test suite"],
        ],
        LEFT,
        y,
        [155, 323],
        font_size=7.5,
    )
    report.end_page()

    if report.page_no != 55:
        raise RuntimeError(f"Expected 55 pages, generated {report.page_no}")
    report.save()
    print(f"Wrote {OUTPUT}")
    print(f"Pages: {report.page_no}")


if __name__ == "__main__":
    main()
