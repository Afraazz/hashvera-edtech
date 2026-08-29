from flask import Blueprint, send_from_directory, abort, request, redirect, url_for, session, render_template
from ..utils.auth_helpers import require_login
from ..utils.records import parse_payload, can_view_record_details
from ..utils.auth_helpers import can_view_profile_directory
from ..utils.blockchain import check_chain_validity
from ..database import get_connection
from ..config import AppConfig
import os

main_bp = Blueprint("main", __name__)

@main_bp.route("/uploads/<path:stored_name>")
def uploaded_file(stored_name):
    if not require_login():
        return redirect(url_for("auth.login"))
    file_path = os.path.join(AppConfig.UPLOAD_DIR, stored_name)
    if not os.path.exists(file_path):
        abort(404)
    conn = get_connection()
    cur = conn.cursor()
    profile_owner = cur.execute(
        "SELECT username, role FROM users WHERE profile_photo = ? LIMIT 1",
        (stored_name,),
    ).fetchone()
    if profile_owner:
        role = session.get("role")
        allowed = (
            session.get("user") == profile_owner["username"]
            or role == "Administrator"
            or (role in {"Faculty", "Exam Cell"} and profile_owner["role"] != "Administrator" and can_view_profile_directory())
        )
        conn.close()
        if not allowed:
            abort(403)
        download_mode = request.args.get("download", "").lower() in {"1", "true", "yes", "download"}
        return send_from_directory(AppConfig.UPLOAD_DIR, stored_name, as_attachment=download_mode)

    block_row = cur.execute("SELECT * FROM blocks WHERE file_path = ? LIMIT 1", (stored_name,)).fetchone()
    conn.close()
    if block_row:
        if not can_view_record_details(parse_payload(block_row)):
            abort(403)
        download_mode = request.args.get("download", "").lower() in {"1", "true", "yes", "download"}
        return send_from_directory(AppConfig.UPLOAD_DIR, stored_name, as_attachment=download_mode)

    download_mode = request.args.get("download", "").lower() in {"1", "true", "yes", "download"}
    return send_from_directory(AppConfig.UPLOAD_DIR, stored_name, as_attachment=download_mode)

@main_bp.route("/media/<path:stored_name>")
def uploaded_media_file(stored_name):
    if not require_login():
        return redirect(url_for("auth.login"))
    file_path = os.path.join(AppConfig.UPLOAD_DIR, stored_name)
    if not os.path.exists(file_path):
        abort(404)
    conn = get_connection()
    cur = conn.cursor()
    profile_owner = cur.execute(
        "SELECT username, role FROM users WHERE profile_photo = ? LIMIT 1",
        (stored_name,),
    ).fetchone()
    if profile_owner:
        role = session.get("role")
        allowed = (
            session.get("user") == profile_owner["username"]
            or role == "Administrator"
            or (role in {"Faculty", "Exam Cell"} and profile_owner["role"] != "Administrator" and can_view_profile_directory())
        )
        conn.close()
        if not allowed:
            abort(403)
        return send_from_directory(AppConfig.UPLOAD_DIR, stored_name, as_attachment=False)

    block_row = cur.execute("SELECT * FROM blocks WHERE file_path = ? LIMIT 1", (stored_name,)).fetchone()
    conn.close()
    if block_row:
        if not can_view_record_details(parse_payload(block_row)):
            abort(403)
        return send_from_directory(AppConfig.UPLOAD_DIR, stored_name, as_attachment=False)

    return send_from_directory(AppConfig.UPLOAD_DIR, stored_name, as_attachment=False)

@main_bp.route("/verify/record/<block_hash>")
def public_verify(block_hash):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM blocks WHERE block_hash = ? LIMIT 1", (block_hash,)).fetchone()
    
    if not row:
        conn.close()
        return render_template("404.html", message="Verification link is invalid or the record does not exist."), 404
        
    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
    valid_chain, issues = check_chain_validity(rows, conn)
    conn.close()

    block = parse_payload(row)
    
    is_valid = valid_chain and block.get("record_status") != "Archived"
    
    return render_template("public_verify.html", block=block, is_valid=is_valid, issues=issues)

@main_bp.route("/verify/student/<campus_id>")
def public_student_verify(campus_id):
    from ..utils.common import normalize_campus_id
    
    conn = get_connection()
    cur = conn.cursor()
    
    student_profile = cur.execute("SELECT * FROM users WHERE campus_id = ?", (campus_id,)).fetchone()
    if not student_profile:
        dir_entry = cur.execute("SELECT * FROM campus_directory WHERE campus_id = ?", (campus_id,)).fetchone()
        if not dir_entry:
            conn.close()
            return render_template("404.html", message="Student record not found."), 404
        profile_name = dir_entry["full_name"]
        profile_dept = dir_entry["department"]
        profile_photo = None
    else:
        profile_name = student_profile["full_name"] or student_profile["username"]
        profile_dept = student_profile["department"]
        profile_photo = student_profile["profile_photo"]

    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
    valid_chain, issues = check_chain_validity(rows, conn)
    conn.close()

    all_blocks = [parse_payload(row) for row in rows]
    student_blocks = [b for b in all_blocks if normalize_campus_id(b.get("student_id")) == normalize_campus_id(campus_id)]
    
    active_blocks = [b for b in student_blocks if b.get("record_status") == "Active"]
    
    return render_template(
        "public_student_verify.html", 
        campus_id=campus_id,
        student_name=profile_name,
        department=profile_dept,
        profile_photo=profile_photo,
        active_blocks=active_blocks,
        is_valid=valid_chain, 
        issues=issues
    )

@main_bp.route("/support")
def support():
    my_tickets = []
    if session.get("user"):
        conn = get_connection()
        my_tickets = list(conn.execute("SELECT * FROM support_tickets WHERE username = ? ORDER BY created_at DESC", (session.get("user"),)).fetchall())
        conn.close()
    return render_template("support_history.html", my_tickets=my_tickets)

@main_bp.route("/support/new", methods=["GET", "POST"])
def support_new():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        category = request.form.get("category")
        message = request.form.get("message")
        
        if not all([name, email, category, message]):
            return render_template("support_new.html", error="All fields are required.")
            
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        
        conn = get_connection()
        conn.execute(
            """
            INSERT INTO support_tickets (name, email, category, message, username, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, email, category, message, session.get("user"), now, now)
        )
        conn.commit()
        conn.close()
        
        return render_template("support_new.html", success=True)
        
    return render_template("support_new.html")

@main_bp.route("/verify", methods=["GET", "POST"])
def verify_portal():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        if not identifier:
            return render_template("public_verify_portal.html", error="Please enter a Certificate ID or Block Hash.")
            
        conn = get_connection()
        cur = conn.cursor()
        
        # Search by Block Hash or Certificate ID column (high performance)
        row = cur.execute(
            "SELECT * FROM blocks WHERE block_hash = ? OR certificate_id = ? LIMIT 1",
            (identifier, identifier)
        ).fetchone()
        
        if not row:
            conn.close()
            return render_template("public_verify_portal.html", error="No record found with that identifier. Please check and try again.")
            
        conn.close()
        # Redirect to the existing public_verify route
        block = parse_payload(row)
        return redirect(url_for("main.public_verify", block_hash=block["block_hash"]))
        
    return render_template("public_verify_portal.html")

@main_bp.route("/terms")
def terms():
    return render_template("terms.html")

@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")

@main_bp.route("/faq")
def faq():
    return render_template("faq.html")

@main_bp.route("/network/audit")
def public_audit():
    conn = get_connection()
    cur = conn.cursor()
    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
    valid_chain, issues = check_chain_validity(rows, conn)
    conn.close()
    
    total_blocks = len(rows)
    return render_template("public_audit.html", 
                           total_blocks=total_blocks, 
                           valid=valid_chain, 
                           issues=issues if not valid_chain else [])



