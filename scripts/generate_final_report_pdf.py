import sys
from pathlib import Path
from textwrap import wrap

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SNAPSHOTS = DOCS / "snapshots"
OUTPUT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DOCS / "FINAL_REPORT.pdf"

PAGE_W, PAGE_H = A4
LEFT = 54
RIGHT = 54
TOP = 64
BOTTOM = 54
CONTENT_W = PAGE_W - LEFT - RIGHT


def clean(text):
    return " ".join(str(text).replace("\n", " ").split())


class Report:
    def __init__(self, path):
        self.c = canvas.Canvas(str(path), pagesize=A4)
        self.page_no = 0

    def start_page(self, title=None):
        self.page_no += 1
        self.c.setFillColor(colors.black)
        self.c.setFont("Helvetica-Bold", 8)
        self.c.drawString(LEFT, PAGE_H - 18, "HashVera Academic Record Network")
        self.c.drawRightString(PAGE_W - RIGHT, PAGE_H - 18, "Final Project Report")
        self.c.setStrokeColor(colors.black)
        self.c.line(LEFT, PAGE_H - 28, PAGE_W - RIGHT, PAGE_H - 28)
        self.c.setFillColor(colors.black)
        if title:
            self.c.setFont("Helvetica-Bold", 18)
            self.c.drawString(LEFT, PAGE_H - TOP, title)
            return PAGE_H - TOP - 30
        return PAGE_H - TOP

    def end_page(self):
        self.c.setStrokeColor(colors.black)
        self.c.line(LEFT, 40, PAGE_W - RIGHT, 40)
        self.c.setFont("Helvetica", 9)
        self.c.setFillColor(colors.black)
        self.c.drawCentredString(PAGE_W / 2, 25, f"Page {self.page_no}")
        self.c.showPage()

    def paragraph(self, text, x, y, size=10.5, leading=14, width=88, font="Helvetica"):
        self.c.setFont(font, size)
        self.c.setFillColor(colors.black)
        for line in wrap(clean(text), width):
            self.c.drawString(x, y, line)
            y -= leading
        return y - 4

    def bullets(self, items, x, y, size=10.5, leading=14, width=84):
        self.c.setFont("Helvetica", size)
        for item in items:
            lines = wrap(clean(item), width)
            self.c.drawString(x, y, u"\u2022")
            self.c.drawString(x + 14, y, lines[0])
            y -= leading
            for line in lines[1:]:
                self.c.drawString(x + 14, y, line)
                y -= leading
        return y - 4

    def subheading(self, text, x, y):
        self.c.setFont("Helvetica-Bold", 12)
        self.c.setFillColor(colors.black)
        self.c.drawString(x, y, text)
        self.c.setFillColor(colors.black)
        return y - 18

    def table(self, data, x, y, col_widths=None, font_size=8.5):
        if col_widths is None:
            col_widths = [CONTENT_W / len(data[0])] * len(data[0])
        t = Table(data, colWidths=col_widths, repeatRows=1)
        t.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.white),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
                    ("FONTSIZE", (0, 0), (-1, -1), font_size),
                    ("GRID", (0, 0), (-1, -1), 0.35, colors.black),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.white]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        w, h = t.wrapOn(self.c, CONTENT_W, y)
        t.drawOn(self.c, x, y - h)
        return y - h - 14

    def image(self, path, x, y, w, h, caption=None):
        img_path = Path(path)
        if not img_path.exists():
            self.c.setFillColor(colors.white)
            self.c.rect(x, y - h, w, h, fill=True, stroke=False)
            self.c.setFillColor(colors.black)
            self.c.drawString(x + 8, y - 20, f"Missing image: {img_path.name}")
        else:
            img = ImageReader(str(img_path))
            iw, ih = img.getSize()
            scale = min(w / iw, h / ih)
            dw, dh = iw * scale, ih * scale
            self.c.drawImage(img, x + (w - dw) / 2, y - dh, dw, dh, preserveAspectRatio=True, mask="auto")
            self.c.setStrokeColor(colors.black)
            self.c.rect(x, y - h, w, h, fill=False, stroke=True)
        if caption:
            self.c.setFont("Helvetica-Bold", 9)
            self.c.setFillColor(colors.black)
            self.c.drawCentredString(x + w / 2, y - h - 12, caption)
        return y - h - 28

    def save(self):
        self.c.save()


def add_text_page(r, title, paragraphs=None, bullets=None, table=None):
    y = r.start_page(title)
    for p in paragraphs or []:
        y = r.paragraph(p, LEFT, y)
    if bullets:
        y = r.bullets(bullets, LEFT, y)
    if table:
        y = r.table(table["data"], LEFT, y, table.get("widths"), table.get("font_size", 8.5))
    r.end_page()


def main():
    r = Report(OUTPUT)

    # Page 1
    y = r.start_page()
    r.c.setFont("Helvetica-Bold", 24)
    r.c.setFillColor(colors.black)
    r.c.drawCentredString(PAGE_W / 2, PAGE_H - 130, "Final Project Report")
    r.c.setFont("Helvetica-Bold", 18)
    r.c.drawCentredString(PAGE_W / 2, PAGE_H - 165, "Secure Decentralized Data Storage for EdTech")
    r.c.setFont("Helvetica", 13)
    r.c.setFillColor(colors.black)
    r.c.drawCentredString(PAGE_W / 2, PAGE_H - 205, "Project Name: HashVera Academic Record Network")
    r.c.drawCentredString(PAGE_W / 2, PAGE_H - 230, "Domain: Educational Technology and Blockchain-inspired Verification")
    r.c.drawCentredString(PAGE_W / 2, PAGE_H - 255, "Technology: Python, Flask, SQLite, HTML, CSS, Jinja2, JavaScript")
    y = PAGE_H - 310
    y = r.paragraph(
        "HashVera is a secure academic record management system that uses hash chaining to protect certificates, marksheets, transcripts, and other institutional records from tampering. The system includes role-based access, public verification, peer-node synchronization, audit logging, support tickets, backups, and report export tools.",
        LEFT,
        y,
        size=11.5,
        leading=16,
        width=82,
    )
    r.end_page()

    # Page 2
    y = r.start_page("Table of Contents")
    toc = [
        ["Sl. No.", "Heading", "Page No."],
        ["1", "Executive Summary", "3"],
        ["2", "Background", "4"],
        ["2.1", "Aim", "5"],
        ["2.2", "Technologies", "6"],
        ["2.3", "Hardware Architecture", "7"],
        ["2.4", "Software Architecture", "8"],
        ["3", "System", "9"],
        ["3.1", "Requirements", "10"],
        ["3.1.1", "Functional Requirements", "11"],
        ["3.1.2", "User Requirements", "12"],
        ["3.1.3", "Environmental Requirements", "13"],
        ["3.2", "Design and Architecture", "14"],
        ["3.2.1", "Architecture Diagram", "15"],
        ["3.2.2", "Database Design", "16"],
        ["3.2.3", "Authentication Design", "17"],
        ["3.2.4", "Blockchain Record Design", "18"],
        ["3.2.5", "Peer Sync Design", "19"],
        ["3.2.6", "GUI Design Overview", "20"],
        ["3.3", "Implementation", "21"],
        ["3.3.1", "Authentication Implementation", "22"],
        ["3.3.2", "Record Implementation", "23"],
        ["3.3.3", "Admin Implementation", "24"],
        ["3.3.4", "Verification Implementation", "25"],
        ["3.4", "Testing", "26"],
        ["3.4.1", "Functional Testing", "27"],
        ["3.4.2", "Security Testing", "28"],
        ["3.5", "Graphical User Interface (GUI) Layout", "29"],
        ["3.6", "Customer Testing", "32"],
        ["3.7", "Evaluation", "34"],
        ["4", "Snapshots of the Project", "36"],
        ["5", "Conclusions", "38"],
        ["6", "Further Development or Research", "39"],
        ["7", "References and Appendix", "40"],
    ]
    r.table(toc, LEFT, y, [58, 350, 70], font_size=7.5)
    r.end_page()

    add_text_page(
        r,
        "Executive Summary",
        [
            "HashVera Academic Record Network is a web-based secure academic record system designed for Educational Technology environments. The system addresses tampering, limited traceability, and centralized dependency in traditional academic record storage.",
            "Each academic record is stored as a block containing the record payload, timestamp, previous hash, current hash, nonce, owner, certificate ID, and node signature. This creates a tamper-evident ledger where unauthorized modification can be detected by recalculating hashes.",
            "The project supports campus identity activation, role-based access control, student record viewing, record minting by authorized staff, correction requests, public verification, peer-node synchronization, audit logging, backup and recovery, notifications, and support ticket handling.",
            "The system is implemented using Python Flask with SQLite as the database. HTML, CSS, Jinja2 templates, and JavaScript are used for the frontend. SHA-256 hashing protects record integrity and PBKDF2 protects passwords.",
        ],
    )

    pages = [
        (
            "Background",
            [
                "Educational institutions generate and manage large volumes of student records such as marksheets, course certificates, transcripts, internship letters, scholarship approvals, and identity records. In many existing systems, these records are stored in centralized databases or file repositories.",
                "Centralized record systems may be easy to operate, but they can suffer from tampering risk, limited transparency, single-point failure, and slow manual verification. External organizations often need a reliable way to verify student credentials quickly.",
                "HashVera was created to demonstrate a secure and transparent approach to academic record management. It introduces tamper-evident storage using a hash-linked ledger and provides public verification for issued credentials.",
            ],
            [
                "Records should be verifiable without depending on manual office checks.",
                "Sensitive student information should be protected by role-based access.",
                "Administrative actions should be recorded for accountability.",
            ],
        ),
        (
            "Aim",
            [
                "The main aim of HashVera is to design and implement a secure decentralized-style academic record storage system for EdTech use cases.",
                "The project demonstrates how blockchain concepts can be applied practically to educational record integrity without requiring a full public blockchain network.",
            ],
            [
                "Provide a secure web portal for managing academic records.",
                "Use SHA-256 hash chaining for tamper detection.",
                "Support role-based access for Students, Faculty, Exam Cell, and Administrators.",
                "Allow students to view records and request corrections.",
                "Allow public users to verify credentials by certificate ID or block hash.",
                "Maintain audit logs for sensitive actions.",
            ],
        ),
        (
            "Technologies",
            ["The project uses a lightweight but complete web stack suitable for academic demonstration and extension."],
            None,
        ),
    ]
    for title, paragraphs, bullets in pages:
        if title == "Technologies":
            add_text_page(
                r,
                title,
                paragraphs,
                table={
                    "data": [
                        ["Layer", "Technology", "Purpose"],
                        ["Backend", "Python, Flask", "Routes, sessions, application logic"],
                        ["Database", "SQLite", "Stores users, blocks, requests, logs, nodes"],
                        ["Frontend", "HTML, CSS, Jinja2, JavaScript", "Pages, styling, dynamic UI"],
                        ["Security", "SHA-256, PBKDF2, CSRF", "Integrity, password protection, form safety"],
                        ["Reporting", "ReportLab", "PDF certificates and reports"],
                        ["Testing", "Pytest", "Automated route and workflow testing"],
                    ],
                    "widths": [100, 150, 228],
                },
            )
        else:
            add_text_page(r, title, paragraphs, bullets)

    add_text_page(
        r,
        "Hardware Architecture",
        [
            "HashVera can run on a standard laptop, laboratory computer, or server. For project demonstration, all components can run on one machine. For a wider deployment, each institution can operate a separate HashVera node.",
        ],
        table={
            "data": [
                ["Component", "Minimum", "Recommended"],
                ["Processor", "Dual-core CPU", "Quad-core CPU or better"],
                ["RAM", "4 GB", "8 GB or more"],
                ["Storage", "1 GB free space", "SSD with backup storage"],
                ["Network", "Localhost for demo", "LAN/Internet for peer sync"],
                ["Client", "Modern browser", "Chrome, Edge, Firefox"],
            ],
            "widths": [120, 170, 188],
        },
    )

    add_text_page(
        r,
        "Software Architecture",
        [
            "HashVera follows a modular monolith architecture. The application is one Flask project, but responsibilities are separated into blueprints and utility modules.",
        ],
        table={
            "data": [
                ["Layer", "Components"],
                ["Presentation Layer", "Jinja templates, CSS, JavaScript"],
                ["Route Layer", "Authentication, main, records, admin, API blueprints"],
                ["Business Logic Layer", "Blockchain, records, notifications, audit, reporting utilities"],
                ["Data Access Layer", "SQLite connection and schema helpers"],
                ["Storage Layer", "Database file, uploaded documents, backups"],
            ],
            "widths": [150, 328],
        },
    )

    add_text_page(
        r,
        "System",
        [
            "HashVera is a role-based academic record platform. The system starts with campus identity activation. A user enters a campus ID, and the application checks the preloaded campus directory.",
            "After login, the dashboard changes based on the user role. Students see their own records and portfolio. Faculty and Exam Cell users can create records and review requests. Administrators can manage users, peer nodes, audit logs, support tickets, backups, imports, exports, and security scans.",
        ],
        table={
            "data": [
                ["Actor", "Main Responsibility"],
                ["Student", "View own records and submit requests"],
                ["Faculty", "Create and review records"],
                ["Exam Cell", "Edit, archive, restore, and bulk mint records"],
                ["Administrator", "Manage users, nodes, audit, backup, support"],
                ["Public Verifier", "Verify record authenticity"],
                ["Peer Node", "Share blockchain data with another node"],
            ],
            "widths": [140, 338],
        },
    )

    add_text_page(
        r,
        "Requirements",
        [
            "The requirements define what the system must do, who will use it, and under which environment it should run.",
        ],
        bullets=[
            "The system must allow secure account creation from a campus directory.",
            "The system must authenticate users through campus email and password.",
            "The system must enforce role-based access.",
            "The system must store academic records in a hash-linked ledger.",
            "The system must detect tampering through chain validation.",
            "The system must allow public credential verification.",
            "The system must keep audit logs for sensitive activities.",
        ],
    )

    add_text_page(
        r,
        "Functional Requirements",
        table={
            "data": [
                ["ID", "Requirement"],
                ["FR-01", "Activate account using campus ID."],
                ["FR-02", "Validate campus ID using campus directory."],
                ["FR-03", "Allow login using campus email and password."],
                ["FR-04", "Hash passwords using PBKDF2."],
                ["FR-05", "Provide role-based dashboards."],
                ["FR-06", "Allow authorized users to add academic records."],
                ["FR-07", "Store each academic record as a hash-linked block."],
                ["FR-08", "Generate certificate ID for verification."],
                ["FR-09", "Allow students to view only their own records."],
                ["FR-10", "Allow students to submit new record and correction requests."],
                ["FR-11", "Allow staff to review student requests."],
                ["FR-12", "Verify blockchain integrity."],
                ["FR-13", "Expose public verification pages."],
                ["FR-14", "Allow administrators to manage users, peers, backups, and exports."],
            ],
            "widths": [60, 418],
            "font_size": 8,
        },
    )

    add_text_page(
        r,
        "User Requirements",
        bullets=[
            "Students must be able to activate accounts, log in, view their own records, submit requests, and manage profile details.",
            "Faculty users must be able to create records, review student requests, and view permitted profile directory entries.",
            "Exam Cell users must be able to create, edit, archive, restore, and bulk mint records.",
            "Administrators must be able to manage users, peer nodes, support tickets, audit logs, backups, imports, and exports.",
            "External verifiers must be able to check record authenticity without logging in.",
        ],
    )

    add_text_page(
        r,
        "Environmental Requirements",
        table={
            "data": [
                ["Area", "Requirement"],
                ["Operating System", "Windows or Linux"],
                ["Runtime", "Python 3.x with Flask"],
                ["Database", "SQLite for demo, PostgreSQL recommended for production"],
                ["Browser", "Chrome, Edge, Firefox, or equivalent"],
                ["Network", "Localhost for demo, LAN/Internet for peer sync"],
                ["Security", "Strong secret keys, protected peer token, HTTPS in production"],
            ],
            "widths": [150, 328],
        },
    )

    add_text_page(
        r,
        "Design and Architecture",
        [
            "The design separates public, authenticated, record, admin, and API routes. Common behavior such as hashing, blockchain validation, file uploads, notifications, audit logging, and report generation is placed in utility modules.",
        ],
        table={
            "data": [
                ["Blueprint", "URL Area", "Main Features"],
                ["auth_bp", "/login, /register", "Authentication and recovery"],
                ["records_bp", "/dashboard, /my-records", "Records and user dashboard"],
                ["admin_bp", "/admin/*", "Administration and operations"],
                ["main_bp", "/verify, /support", "Public and common pages"],
                ["api_bp", "/api/*", "Peer-node API"],
            ],
            "widths": [100, 150, 228],
        },
    )

    # Page 15 custom architecture diagram
    y = r.start_page("Architecture Diagram")
    r.c.setFont("Helvetica", 10)
    boxes = [
        ("User Browser", 215, 690),
        ("Flask Application", 215, 610),
        ("Authentication", 54, 520),
        ("Records", 190, 520),
        ("Admin", 326, 520),
        ("Public Verify", 430, 520),
        ("SQLite Database", 190, 420),
        ("Upload Storage", 54, 350),
        ("Backup Storage", 326, 350),
        ("Peer Node", 430, 420),
    ]
    for label, x, yy in boxes:
        r.c.setFillColor(colors.white)
        r.c.roundRect(x, yy, 112, 42, 8, fill=True, stroke=True)
        r.c.setFillColor(colors.black)
        r.c.setFont("Helvetica-Bold", 9)
        r.c.drawCentredString(x + 56, yy + 17, label)
    r.c.setStrokeColor(colors.black)
    for x1, y1, x2, y2 in [
        (271, 690, 271, 652),
        (271, 610, 110, 562),
        (271, 610, 246, 562),
        (271, 610, 382, 562),
        (271, 610, 486, 562),
        (246, 520, 246, 462),
        (110, 520, 246, 462),
        (382, 520, 246, 462),
        (486, 520, 486, 462),
        (246, 420, 110, 392),
        (246, 420, 382, 392),
    ]:
        r.c.line(x1, y1, x2, y2)
    y = 300
    y = r.paragraph("The architecture shows browser requests entering the Flask application and being routed to authentication, records, administration, public verification, and API modules. SQLite stores application data, while upload and backup storage handle files. Peer nodes exchange validated chain data through protected API routes.", LEFT, y)
    r.end_page()

    section_pages = [
        (
            "Database Design",
            "HashVera uses SQLite as a lightweight relational database. The schema is created and maintained by hashvera/database.py.",
            [["Table", "Purpose"], ["users", "Accounts, roles, credentials, profile details"], ["campus_directory", "Preapproved campus identities"], ["blocks", "Blockchain-style academic records"], ["nodes", "Local, peer, and simulated nodes"], ["audit_logs", "Sensitive system actions"], ["notifications", "User alerts"], ["record_requests", "Student new-record and correction requests"], ["support_tickets", "Support requests and admin responses"]],
        ),
        (
            "Authentication Design",
            "Authentication uses campus email and password login. Accounts are activated from the campus directory and protected with PBKDF2 password hashing.",
            [["Step", "Description"], ["1", "User enters campus ID for registration."], ["2", "System checks campus_directory."], ["3", "Password is validated and hashed."], ["4", "User row is created and directory row is marked registered."], ["5", "Login verifies email, password hash, and disabled status."], ["6", "Session stores username, user ID, role, email, and campus ID."]],
        ),
        (
            "Blockchain Record Design",
            "Each academic record is stored as a block. Any unauthorized change to payload or chain order changes the recalculated hash.",
            [["Field", "Purpose"], ["block_index", "Chain sequence number"], ["payload", "Academic record JSON"], ["previous_hash", "Hash of previous block"], ["block_hash", "Hash of current block"], ["nonce", "Random value used in hash creation"], ["certificate_id", "Public verification ID"], ["block_signature", "Node signature"]],
        ),
        (
            "Peer Sync Design",
            "Peer synchronization demonstrates decentralized-style storage by allowing trusted HashVera nodes to exchange chain data.",
            [["Endpoint", "Purpose"], ["/api/health", "Return node health and chain summary"], ["/api/chain", "Return serialized blockchain records"], ["/api/chain/sync", "Accept a newer valid chain"], ["Admin peer test", "Checks peer connectivity"], ["Admin sync", "Validates and adopts newer valid chain"]],
        ),
        (
            "GUI Design Overview",
            "The graphical interface is designed for institutional workflows with role-aware navigation, cards, filters, tables, status badges, and clear action buttons.",
            [["GUI Area", "Pages"], ["Authentication", "Login, register, forgot password, OTP, reset password"], ["Student", "Dashboard, records, portfolio, notifications, support"], ["Staff", "Dashboard, review queue, profile directory, chain explorer"], ["Admin", "Users, peers, audit logs, system, support inbox, security audit"], ["Public", "Verify portal, public verification, public audit, FAQ"]],
        ),
    ]
    for title, para, data in section_pages:
        add_text_page(r, title, [para], table={"data": data, "widths": [150, 328]})

    add_text_page(
        r,
        "Implementation",
        [
            "The project is implemented as a Flask package. The application factory initializes configuration, database tables, blueprints, CSRF checks, template globals, and error handlers.",
        ],
        table={
            "data": [
                ["Path", "Purpose"],
                ["app.py", "Compatibility launcher"],
                ["run.py", "Main app launcher"],
                ["hashvera/__init__.py", "Application creation and blueprint registration"],
                ["hashvera/routes/", "Route controllers"],
                ["hashvera/utils/", "Shared helper modules"],
                ["templates/", "HTML templates"],
                ["static/", "CSS, JavaScript, images, fonts"],
                ["tests/", "Automated test suite"],
            ],
            "widths": [180, 298],
        },
    )

    add_text_page(
        r,
        "Authentication Implementation",
        table={
            "data": [
                ["Route", "Purpose"],
                ["/login", "Login page and authentication"],
                ["/logout", "Logout and clear session"],
                ["/register", "Campus account activation"],
                ["/register/campus-lookup", "Dynamic campus identity lookup"],
                ["/forgot-password", "Start recovery by email link or OTP"],
                ["/forgot-password/verify", "Verify SMS OTP"],
                ["/forgot-password/reset", "Reset password after OTP"],
                ["/reset-password/<token>", "Reset password by email token"],
                ["/change-password", "Change password after login"],
            ],
            "widths": [180, 298],
        },
    )

    add_text_page(
        r,
        "Record Implementation",
        [
            "Record functionality is implemented mainly in hashvera/routes/records.py and hashvera/utils/blockchain.py.",
        ],
        table={
            "data": [
                ["Route", "Purpose"],
                ["/dashboard", "Role-based dashboard"],
                ["/my-records", "Student record center"],
                ["/portfolio", "Student portfolio"],
                ["/add", "Add record to ledger"],
                ["/records/<block_id>", "View record details"],
                ["/blocks/<block_id>/edit", "Edit existing record"],
                ["/archived", "Archived records"],
                ["/bulk-mint", "Bulk CSV record minting"],
            ],
            "widths": [180, 298],
        },
    )

    add_text_page(
        r,
        "Admin Implementation",
        table={
            "data": [
                ["Admin Page", "Route", "Purpose"],
                ["User Management", "/admin/users", "Manage users, roles, campus IDs"],
                ["Node Management", "/admin/peers", "Register, test, update, sync peers"],
                ["Audit Logs", "/admin/audit-logs", "View business audit history"],
                ["Support Inbox", "/admin/support-inbox", "Manage support tickets"],
                ["System", "/admin/system", "Backup, import, export, email test"],
                ["Security Audit", "/admin/security-audit", "Run deep ledger scan"],
            ],
            "widths": [130, 150, 198],
            "font_size": 8,
        },
    )

    add_text_page(
        r,
        "Verification Implementation",
        [
            "Verification functionality is implemented through public and authenticated pages. A public record is marked valid only when the block exists, the chain is valid, and the selected record is not archived.",
        ],
        table={
            "data": [
                ["Route", "Purpose"],
                ["/verify", "Search by certificate ID or block hash"],
                ["/verify/record/<block_hash>", "Public record authenticity result"],
                ["/verify/student/<campus_id>", "Public student verification page"],
                ["/network/audit", "Public network audit page"],
                ["/ledger/verify", "Verify entire ledger"],
                ["/chain/explorer", "Visual blockchain explorer"],
                ["/certificate/preview/<block_id>", "Certificate-style record preview"],
            ],
            "widths": [200, 278],
            "font_size": 8,
        },
    )

    add_text_page(
        r,
        "Testing",
        [
            "Testing checks whether the application meets its functional, security, and usability goals. The project includes an automated test suite in tests/test_app.py.",
        ],
        bullets=[
            "Verify authentication workflows.",
            "Verify campus directory account activation.",
            "Verify role-based access control.",
            "Verify record creation and student access restrictions.",
            "Verify review queue workflows.",
            "Verify notifications, backup, import, peer API, and public verification.",
        ],
    )

    add_text_page(
        r,
        "Functional Testing",
        table={
            "data": [
                ["Test ID", "Test Case", "Expected Result"],
                ["FT-01", "Open login page", "Login form is displayed"],
                ["FT-02", "Register with valid campus ID", "Account is created"],
                ["FT-03", "Login with valid credentials", "Dashboard opens"],
                ["FT-04", "Student opens own records", "Own records are displayed"],
                ["FT-05", "Staff creates record", "Block is added to ledger"],
                ["FT-06", "Student submits correction request", "Request enters review queue"],
                ["FT-07", "Public verifies certificate", "Authenticity result is displayed"],
                ["FT-08", "Admin creates backup", "Backup file is generated"],
            ],
            "widths": [55, 210, 213],
            "font_size": 8,
        },
    )

    add_text_page(
        r,
        "Security Testing",
        table={
            "data": [
                ["Test Area", "Purpose"],
                ["Password hashing", "Ensure passwords are not stored directly"],
                ["Invalid login", "Reject incorrect credentials"],
                ["Disabled account", "Prevent disabled users from signing in"],
                ["Role protection", "Prevent unauthorized route access"],
                ["Student isolation", "Prevent students from viewing others' records"],
                ["CSRF checks", "Reject invalid state-changing requests"],
                ["Peer token checks", "Prevent unauthorized API access"],
                ["Chain verification", "Detect hash mismatch and broken previous hash"],
            ],
            "widths": [160, 318],
        },
    )

    add_text_page(
        r,
        "Graphical User Interface (GUI) Layout",
        [
            "The login and registration pages use a clear form layout with project branding, page heading, fields, action buttons, and flash feedback. Forgot password, OTP verification, reset password, and change password pages use a similar pattern for consistency.",
        ],
        table={
            "data": [
                ["Page", "GUI Elements"],
                ["Login", "Campus email, password, sign in, create account, forgot password"],
                ["Register", "Campus ID lookup, identity details, password setup"],
                ["Dashboard", "Metrics, charts, record lists, role-based actions"],
                ["Record Detail", "Academic data, certificate ID, block hash, file details"],
                ["Admin Pages", "Tables, filters, action forms, status badges"],
            ],
            "widths": [120, 358],
        },
    )

    add_text_page(
        r,
        "Dashboard and Record GUI Layout",
        bullets=[
            "Dashboard shows metrics, charts, active records, staff summaries, student insights, and chain status.",
            "Student Records page shows personal record cards, search, filters, request forms, and correction options.",
            "Record Detail page shows academic details, certificate ID, block hash, previous hash, owner, status, and file information.",
            "Chain Explorer page visualizes connected blocks and highlights integrity issues.",
        ],
    )

    add_text_page(
        r,
        "Admin and Public GUI Layout",
        table={
            "data": [
                ["Area", "Layout Features"],
                ["Admin Users", "Search, sort, pagination, user action controls"],
                ["Admin Peers", "Peer registration, node status cards, sync actions"],
                ["Admin System", "Backup, import, export, email test panels"],
                ["Public Verify", "Certificate ID or block hash search"],
                ["Public Audit", "Network chain status and verification summary"],
                ["Support", "Ticket form and support history"],
            ],
            "widths": [140, 338],
        },
    )

    add_text_page(
        r,
        "Customer Testing",
        [
            "Customer testing evaluates the system from the perspective of real users such as students, faculty, exam cell staff, administrators, and public verifiers.",
        ],
        bullets=[
            "A student activates an account and opens personal records.",
            "A student submits a correction request.",
            "Faculty reviews the request.",
            "Exam Cell mints or updates a record.",
            "Administrator views audit logs and creates a backup.",
            "External verifier checks a certificate through the public portal.",
        ],
    )

    add_text_page(
        r,
        "Customer Testing Feedback",
        table={
            "data": [
                ["Area", "Feedback"],
                ["Login", "Campus email login is clear and institution-friendly"],
                ["Registration", "Campus ID lookup improves trust during activation"],
                ["Student Records", "Students can easily identify their records"],
                ["Verification", "Public verification is useful for employers and institutions"],
                ["Dashboard", "Metrics and charts make the system easier to present"],
                ["Admin Tools", "User and backup management support governance"],
            ],
            "widths": [130, 348],
        },
    )

    add_text_page(
        r,
        "Evaluation",
        table={
            "data": [
                ["Criterion", "Evaluation"],
                ["Security", "Strong for demo; uses hashing, sessions, CSRF, role checks"],
                ["Integrity", "Strong; hash chain detects tampering"],
                ["Usability", "Good; role-based pages and public verification are clear"],
                ["Maintainability", "Good; modular Flask blueprints and utilities"],
                ["Scalability", "Moderate; SQLite is suitable for demo"],
                ["Auditability", "Strong; sensitive actions are logged"],
                ["Extensibility", "Good; modules can be expanded"],
            ],
            "widths": [130, 348],
        },
    )

    add_text_page(
        r,
        "Evaluation Analysis",
        bullets=[
            "The project has a clear academic use case and secure campus identity activation.",
            "Role-based access control protects student and administrative workflows.",
            "The hash-linked ledger provides tamper-evident academic records.",
            "The public verification portal makes issued records easier to validate.",
            "SQLite and local file storage are suitable for demonstration but should be upgraded for production.",
            "Peer sync demonstrates decentralization but is not a full public blockchain consensus system.",
        ],
    )

    # Snapshots pages
    y = r.start_page("Snapshots of the Project")
    y = r.image(SNAPSHOTS / "01-login.png", LEFT, y, 230, 155, "Snapshot 1: Login Page")
    y += 183
    r.image(SNAPSHOTS / "02-register.png", LEFT + 248, PAGE_H - TOP - 30, 230, 155, "Snapshot 2: Campus Account Activation")
    y = PAGE_H - TOP - 230
    y = r.paragraph("The login and registration screens show the user entry points of the project. The account activation page uses campus identity, which is a central feature of the HashVera workflow.", LEFT, y)
    r.end_page()

    y = r.start_page("Verification and Audit Snapshots")
    r.image(SNAPSHOTS / "03-public-verify.png", LEFT, y, 230, 145, "Snapshot 3: Public Verification Portal")
    r.image(SNAPSHOTS / "04-public-audit.png", LEFT + 248, y, 230, 145, "Snapshot 4: Public Network Audit")
    y -= 205
    r.image(SNAPSHOTS / "05-support.png", LEFT, y, 230, 145, "Snapshot 5: Support Page")
    r.image(SNAPSHOTS / "06-faq.png", LEFT + 248, y, 230, 145, "Snapshot 6: FAQ Page")
    r.end_page()

    add_text_page(
        r,
        "Conclusions",
        [
            "HashVera Academic Record Network successfully demonstrates a secure and practical approach to academic record management using blockchain-inspired hash chaining. The project solves an important problem in EdTech: how to preserve the integrity and authenticity of student academic records while keeping the system usable for students, faculty, exam cell staff, administrators, and external verifiers.",
            "The application includes account activation, login, dashboard, record minting, student requests, review queue, certificate verification, public audit, peer sync, notifications, support tickets, backups, imports, exports, and audit logs.",
            "The final conclusion is that HashVera meets the project aim and provides a strong foundation for secure decentralized academic record storage in EdTech environments.",
        ],
    )

    add_text_page(
        r,
        "Further Development or Research",
        bullets=[
            "Migrate from SQLite to PostgreSQL for production scale.",
            "Store uploaded documents in cloud object storage or IPFS.",
            "Add encrypted file storage for sensitive documents.",
            "Add digital signatures using institutional certificates.",
            "Add two-factor authentication for administrators and staff.",
            "Add Merkle tree based record proofs and public blockchain anchoring.",
            "Add department-wise dashboards and QR codes on certificate previews.",
        ],
    )

    y = r.start_page("References and Appendix")
    y = r.table(
        [
            ["Sl. No.", "Reference"],
            ["1", "Python Software Foundation, Python Documentation"],
            ["2", "Flask Documentation"],
            ["3", "SQLite Documentation"],
            ["4", "SHA-256 Secure Hash Algorithm references"],
            ["5", "PBKDF2 password hashing references"],
            ["6", "OWASP Web Security Guidelines"],
            ["7", "ReportLab PDF generation documentation"],
            ["8", "Project source code: HashVera Academic Record Network"],
        ],
        LEFT,
        y,
        [60, 418],
    )
    y = r.subheading("Appendix: Important Project Files", LEFT, y)
    r.table(
        [
            ["File / Folder", "Description"],
            ["app.py", "Compatibility launcher"],
            ["run.py", "Main application launcher"],
            ["hashvera/routes/auth.py", "Authentication routes"],
            ["hashvera/routes/records.py", "Record and dashboard routes"],
            ["hashvera/routes/admin.py", "Admin routes"],
            ["hashvera/routes/api.py", "Peer API routes"],
            ["templates/", "GUI templates"],
            ["tests/test_app.py", "Automated test suite"],
        ],
        LEFT,
        y,
        [180, 298],
        font_size=8,
    )
    r.end_page()

    r.save()
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
