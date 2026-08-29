# HashVera Records Blueprint - v1.0.2-patch
# HashVera Records Blueprint - v1.0.2-patch
print("DEBUG: RECORDS MODULE LOADED - CHAIN EXPLORER IS ACTIVE")
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, Response, make_response
from ..database import get_connection
from ..utils.auth_helpers import require_login, can_view_my_records, can_review_requests, can_create_records, can_view_profile_directory, can_edit_records, can_archive_records
from ..utils.records import parse_payload, current_student_campus_id, student_record_matches_user, can_view_record_details, get_form_record_data, normalize_record_data, build_record_payload
from ..utils.common import get_request_page, paginate_items, utc_now, normalize_campus_id
from ..utils.audit import log_audit_action
from ..utils.notifications import create_notification, notify_roles, notify_user_for_campus_id, fetch_notifications, count_unread_notifications
from ..utils.blockchain import add_record, check_chain_validity, current_chain_summary
from ..utils.files import save_uploaded_file, save_profile_photo, delete_profile_photo
from ..utils.hashing import validate_password_strength, build_block_hash, sign_block_data, serialize_payload
from ..config import AppConfig
import json
import os
import csv
import io
from datetime import datetime, timezone

records_bp = Blueprint("records", __name__)


@records_bp.route("/ledger/verify/ajax", endpoint="verify_chain_ajax")
def verify_chain_ajax():
    if not require_login():
        return jsonify({"error": "Unauthorized"}), 401

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_index ASC")
    rows = cur.fetchall()
    valid, issues = check_chain_validity(rows, conn)
    
    str_issues = [f"Block {issue['block_index']}: {issue['description']}" for issue in issues]
    
    cur.execute("SELECT id FROM users WHERE username = ?", (session["user"],))
    user = cur.fetchone()
    if user:
        log_audit_action(conn, session["user"], "VERIFY_CHAIN", "ledger", user["id"], "Blockchain integrity verified (AJAX).")
        conn.commit()
    conn.close()

    session["last_verification_issues"] = str_issues
    return jsonify({
        "valid": valid,
        "issue_count": len(issues),
        "issues": str_issues
    })




def _profile_photo_url(profile):
    if not profile or not profile["profile_photo"]:
        return ""
    return url_for("main.uploaded_media_file", stored_name=profile["profile_photo"])


def _account_status_label(profile):
    return "Disabled" if profile["disabled"] else "Active"


def _build_dashboard_chart_data(all_blocks, users, logs):
    type_counts = {}
    course_counts = {}
    active_count = 0
    archived_count = 0
    for block in all_blocks:
        type_counts[block["record_type"]] = type_counts.get(block["record_type"], 0) + 1
        course_counts[block["course"]] = course_counts.get(block["course"], 0) + 1
        if block["record_status"] == "Archived":
            archived_count += 1
        else:
            active_count += 1

    role_counts = {}
    for user in users:
        role_counts[user["role"]] = role_counts.get(user["role"], 0) + 1

    activity_counts = {}
    label_map = {
        "LOGIN": "Login",
        "LOGOUT": "Logout",
        "SECURITY_AUDIT": "Audit",
        "RECOVERY_VERIFY": "Verify",
        "CREATE_PROFILE": "Profile",
        "ADD_RECORD": "Mint",
        "UPDATE_RECORD": "Update",
        "ARCHIVE_RECORD": "Archive"
    }
    for log in logs:
        raw_action = log["action"]
        display_action = label_map.get(raw_action, raw_action.replace("_", " ").title())
        activity_counts[display_action] = activity_counts.get(display_action, 0) + 1

    return {
        "overview_labels": ["Total Blocks", "Active Records", "Archived", "Verified Users", "Nodes"],
        "overview_values": [len(all_blocks), active_count, archived_count, len(users), 1],
        "type_labels": list(type_counts.keys()) or ["Academic Record"],
        "type_values": list(type_counts.values()) or [0],
        "role_labels": list(role_counts.keys()) or ["No Users"],
        "role_values": list(role_counts.values()) or [0],
        "course_labels": list(course_counts.keys()) or ["No Course Data"],
        "course_values": list(course_counts.values()) or [0],
        "trend_labels": ["Current Week"],
        "trend_added_values": [active_count],
        "trend_archived_values": [archived_count],
        "activity_labels": list(activity_counts.keys())[:6] or ["None"],
        "activity_values": list(activity_counts.values())[:6] or [0],
    }


def _build_staff_dashboard_summary(conn):
    rows = list(
        conn.execute(
            """
            SELECT id, request_type, requester_username, campus_id, status, reviewer_username, reviewer_note,
                   requested_payload, request_note, created_at, updated_at, linked_block_id
            FROM record_requests
            ORDER BY id DESC
            LIMIT 60
            """
        ).fetchall()
    )

    pending_requests = []
    recently_approved = []
    recently_corrected = []

    for row in rows:
        item = dict(row)
        try:
            payload = json.loads(item.get("requested_payload") or "{}")
        except json.JSONDecodeError:
            payload = {}
        item["payload"] = payload
        item["display_name"] = payload.get("document_name") or payload.get("course") or (item.get("campus_id") or "Campus record")
        item["review_summary"] = item.get("reviewer_note") or item.get("request_note") or "No note added."

        if item["status"] == "Pending" and len(pending_requests) < 5:
            pending_requests.append(item)
        if item["status"] == "Approved" and len(recently_approved) < 5:
            recently_approved.append(item)
        if item["status"] == "Approved" and item["request_type"] == "CORRECTION" and len(recently_corrected) < 5:
            recently_corrected.append(item)

    return {
        "pending_total": sum(1 for row in rows if row["status"] == "Pending"),
        "approved_total": sum(1 for row in rows if row["status"] == "Approved"),
        "correction_total": sum(1 for row in rows if row["request_type"] == "CORRECTION" and row["status"] == "Approved"),
        "pending_requests": pending_requests,
        "recently_approved": recently_approved,
        "recently_corrected": recently_corrected,
    }


def _rebuild_chain_from(conn, start_block_index):
    cur = conn.cursor()
    rows = list(
        cur.execute(
            """
            SELECT id, block_index, timestamp, payload, previous_hash, block_hash, nonce, owner,
                   file_name, file_path, file_size, record_type, record_status, updated_at,
                   last_modified_by, signer_node, signer_key_id, block_signature
            FROM blocks
            WHERE block_index >= ?
            ORDER BY block_index ASC
            """,
            (start_block_index,),
        ).fetchall()
    )
    if not rows:
        return

    previous = cur.execute(
        "SELECT block_hash FROM blocks WHERE block_index < ? ORDER BY block_index DESC LIMIT 1",
        (start_block_index,),
    ).fetchone()
    previous_hash = previous["block_hash"] if previous else "GENESIS"

    for row in rows:
        block_hash = build_block_hash(
            row["block_index"],
            row["timestamp"],
            row["payload"],
            previous_hash,
            row["owner"],
            row["nonce"],
        )
        block_signature = sign_block_data(
            row["block_index"],
            row["timestamp"],
            row["payload"],
            previous_hash,
            row["owner"],
            row["nonce"],
            block_hash,
            AppConfig.LOCAL_NODE_NAME,
            AppConfig.LOCAL_SIGNING_KEY_ID,
            AppConfig.LOCAL_SIGNING_SECRET,
        )
        cur.execute(
            """
            UPDATE blocks
            SET previous_hash = ?, block_hash = ?, signer_node = ?, signer_key_id = ?, block_signature = ?
            WHERE id = ?
            """,
            (
                previous_hash,
                block_hash,
                AppConfig.LOCAL_NODE_NAME,
                AppConfig.LOCAL_SIGNING_KEY_ID,
                block_signature,
                row["id"],
            ),
        )
        previous_hash = block_hash


@records_bp.route("/chain/explorer")
def chain_explorer():
    """Visual blockchain explorer showing connected blocks with hash links."""
    if not require_login():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
    valid_chain, issues = check_chain_validity(rows, conn)
    conn.close()

    blocks = [parse_payload(row) for row in rows]

    return render_template(
        "chain_explorer.html",
        blocks=blocks,
        chain_valid=valid_chain,
        issues=issues,
        total_blocks=len(blocks),
        can_view_record_details=can_view_record_details,
    )

@records_bp.route("/")
@records_bp.route("/dashboard")
def dashboard():
    if not require_login():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()

    block_rows_desc = list(cur.execute("SELECT * FROM blocks ORDER BY block_index DESC").fetchall())
    block_rows_asc = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
    all_blocks = [parse_payload(row) for row in block_rows_desc]
    active_blocks_all = [b for b in all_blocks if b["record_status"] != "Archived"]
    archived_blocks_all = [b for b in all_blocks if b["record_status"] == "Archived"]
    users = list(cur.execute("SELECT id, username, role, profile_photo, created_at FROM users ORDER BY created_at DESC").fetchall())
    nodes = list(cur.execute("SELECT * FROM nodes ORDER BY name ASC").fetchall())
    audit_logs = list(cur.execute("SELECT action FROM audit_logs ORDER BY id DESC LIMIT 50").fetchall())
    current_user = cur.execute("SELECT profile_photo FROM users WHERE username = ?", (session["user"],)).fetchone()
    staff_summary = _build_staff_dashboard_summary(conn) if can_review_requests() else None
    
    student_insights = None
    student_profile = None
    if session.get("role") == "Student":
        student_campus_id = current_student_campus_id()
        student_blocks = [b for b in active_blocks_all if normalize_campus_id(b.get("student_id")) == normalize_campus_id(student_campus_id)]
        student_insights = _build_student_insights(student_blocks)
        student_profile = cur.execute("SELECT * FROM users WHERE username = ?", (session["user"],)).fetchone()
        if student_profile:
            student_profile = dict(student_profile)
            # Add campus directory info if available
            dir_entry = cur.execute("SELECT * FROM campus_directory WHERE campus_id = ?", (student_campus_id,)).fetchone()
            if dir_entry:
                student_profile.update(dict(dir_entry))
        
        my_tickets = list(cur.execute("SELECT * FROM support_tickets WHERE username = ? ORDER BY created_at DESC", (session["user"],)).fetchall())
    else:
        my_tickets = []

    search_query = request.args.get("q", "").strip().lower()
    course_filter = request.args.get("course", "").strip()
    node_filter = request.args.get("node", "").strip()

    def matches_dashboard_filters(block):
        searchable = " ".join(
            [
                block.get("student_id", ""),
                block.get("student_name", ""),
                block.get("course", ""),
                block.get("document_name", ""),
                block.get("certificate_id", ""),
                block.get("storage_node", ""),
                block.get("record_notes", ""),
                block.get("submitted_by", ""),
                block.get("record_type", ""),
                block.get("record_status", ""),
            ]
        ).lower()
        if search_query and search_query not in searchable:
            return False
        if course_filter and block.get("course") != course_filter:
            return False
        if node_filter and block.get("storage_node") != node_filter:
            return False
        return True

    filtered_active_blocks = [block for block in active_blocks_all if matches_dashboard_filters(block)]
    chain_valid, issues = check_chain_validity(block_rows_asc, conn)
    chart_data = _build_dashboard_chart_data(all_blocks, users, audit_logs)

    # Compute sidebar badge counts safely
    notification_unread_count = 0
    review_queue_pending_count = 0
    try:
        from hashvera.utils.notifications import count_unread_notifications
        notification_unread_count = count_unread_notifications(conn, session.get("user"))
        if can_review_requests():
            row = conn.execute("SELECT COUNT(*) as cnt FROM record_requests WHERE status = 'Pending'").fetchone()
            review_queue_pending_count = row["cnt"] if row else 0
    except Exception:
        pass

    conn.close()

    blocks_page = get_request_page("blocks_page")
    paged_active_blocks, active_pagination = paginate_items(filtered_active_blocks, blocks_page, 5)

    is_admin_role = session.get("role") in ("Administrator", "Faculty", "Exam Cell")

    return render_template(
        "dashboard.html",
        blocks=filtered_active_blocks,
        active_blocks=paged_active_blocks,
        active_pagination=active_pagination,
        all_block_count=len(all_blocks),
        search_query=request.args.get("q", "").strip(),
        course_filter=course_filter,
        node_filter=node_filter,
        course_options=sorted({block["course"] for block in all_blocks if block.get("course")}),
        node_options=sorted({block["storage_node"] for block in all_blocks if block.get("storage_node")}),
        nodes=nodes,
        chain_valid=chain_valid,
        issues=session.pop("last_verification_issues", []) or issues,
        my_tickets=my_tickets,
        dashboard_profile_photo_url=_profile_photo_url(current_user) if current_user else "",
        metrics={
            "total_blocks": len(all_blocks),
            "total_users": len(users),
            "verified_users": len([u for u in users if u["role"] != "Guest"]),
            "active_nodes": max(len(nodes), 1),
            "chain_status": "Verified" if chain_valid else "Review Required",
            "active_records": len(active_blocks_all),
            "archived_records": len(archived_blocks_all),
        },
        chart_data=chart_data,
        staff_summary=staff_summary,
        student_friendly_dashboard=session.get("role") == "Student",
        student_insights=student_insights,
        student_profile=student_profile,
        can_archive_records=can_archive_records(),
        can_create_records=can_create_records(),
        can_edit_records=can_edit_records(),
        can_review_requests=can_review_requests(),
        is_admin=session.get("role") == "Administrator",
        is_admin_role=is_admin_role,
        notification_unread_count=notification_unread_count,
        review_queue_pending_count=review_queue_pending_count,
    )

def _build_student_insights(student_blocks):
    if not student_blocks:
        return None
    
    marks_list = []
    for b in student_blocks:
        try:
            obt = float(b.get("marks_obtained", 0))
            max_m = float(b.get("max_marks", 0))
            if max_m > 0:
                marks_list.append((obt / max_m) * 100)
        except:
            continue
            
    avg_perf = sum(marks_list) / len(marks_list) if marks_list else 0
    
    return {
        "avg_performance": round(avg_perf, 1),
        "total_records": len(student_blocks),
        "active_records": len([b for b in student_blocks if b.get("record_status") == "Active"]),
        "cert_count": len([b for b in student_blocks if b.get("record_type") == "Certificate"]),
        "marksheet_count": len([b for b in student_blocks if b.get("record_type") == "Marksheet"])
    }

@records_bp.route("/portfolio")
def student_portfolio():
    if not require_login():
        return redirect(url_for("auth.login"))
        
    conn = get_connection()
    cur = conn.cursor()
    student_id = current_student_campus_id()
    
    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index DESC").fetchall())
    all_blocks = [parse_payload(row) for row in rows]
    student_blocks = [b for b in all_blocks if normalize_campus_id(b.get("student_id")) == normalize_campus_id(student_id)]
    
    student_profile = cur.execute("SELECT * FROM users WHERE username = ?", (session["user"],)).fetchone()
    dir_entry = cur.execute("SELECT * FROM campus_directory WHERE campus_id = ?", (student_id,)).fetchone()
    
    conn.close()
    
    certs = [b for b in student_blocks if b.get("record_type") == "Certificate" and b.get("record_status") == "Active"]
    marksheets = [b for b in student_blocks if b.get("record_type") == "Marksheet" and b.get("record_status") == "Active"]
    others = [b for b in student_blocks if b.get("record_type") not in ["Certificate", "Marksheet"] and b.get("record_status") == "Active"]
    
    return render_template(
        "student_portfolio.html",
        student_profile=dict(student_profile) if student_profile else {},
        dir_entry=dict(dir_entry) if dir_entry else {},
        certs=certs,
        marksheets=marksheets,
        others=others,
        student_insights=_build_student_insights(student_blocks)
    )

@records_bp.route("/my-records")
def my_records():
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_view_my_records():
        flash("Only student accounts can open Records.", "error")
        return redirect(url_for("records.dashboard"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_index DESC")
    block_rows = cur.fetchall()
    cur.execute(
        """
        SELECT *
        FROM record_requests
        WHERE requester_username = ?
        ORDER BY id DESC
        LIMIT 6
        """,
        (session["user"],),
    )
    student_requests = list(cur.fetchall())
    conn.close()

    all_blocks = [parse_payload(row) for row in block_rows]
    student_blocks = [block for block in all_blocks if student_record_matches_user(block, current_student_campus_id())]
    search_query = request.args.get("q", "").strip().lower()
    status_filter = request.args.get("status", "").strip()

    if search_query:
        student_blocks = [
            block
            for block in student_blocks
            if search_query in " ".join(
                [
                    block.get("student_id", ""),
                    block.get("student_name", ""),
                    block.get("course", ""),
                    block.get("document_name", ""),
                    block.get("certificate_id", ""),
                    block.get("record_notes", ""),
                    block.get("record_type", ""),
                    block.get("record_status", ""),
                ]
            ).lower()
        ]
    if status_filter:
        student_blocks = [block for block in student_blocks if block.get("record_status") == status_filter]

    records_page = get_request_page("page")
    student_blocks, records_pagination = paginate_items(student_blocks, records_page, 6)
    
    return render_template(
        "my_records.html",
        student_blocks=student_blocks,
        records_pagination=records_pagination,
        student_requests=student_requests,
        search_query=request.args.get("q", "").strip(),
        status_filter=status_filter,
    )

@records_bp.route("/add", methods=["POST"])
def add_block():
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_create_records():
        flash("Only faculty, exam cell, and administrators can add records.", "error")
        return redirect(url_for("records.dashboard"))

    form_data = get_form_record_data(request.form)
    try:
        form_data = normalize_record_data(form_data)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("records.dashboard"))

    if not all([form_data.get(k) for k in ["student_id", "student_name", "course", "document_name", "storage_node", "record_notes", "record_type"]]):
        flash("Fill in all record fields before adding a block.", "error")
        return redirect(url_for("records.dashboard"))

    try:
        file_meta = save_uploaded_file(request.files.get("document_file"))
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("records.dashboard"))

    block_id = add_record(session["user"], form_data, file_meta)
    conn = get_connection()
    notify_user_for_campus_id(
        conn,
        form_data["student_id"],
        "record",
        "Record added",
        f"{form_data['document_name']} was added to HashVera for campus ID {form_data['student_id']}.",
        url_for("records.view_record", block_id=block_id),
    )
    conn.commit()
    conn.close()
    flash("Academic record secured and replicated across nodes.", "success")
    return redirect(url_for("records.dashboard"))

@records_bp.route("/ledger/verify")
def verify_chain():
    if not require_login():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_index ASC")
    rows = cur.fetchall()
    valid, issues = check_chain_validity(rows, conn)
    
    str_issues = [f"Block {issue['block_index']}: {issue['description']}" for issue in issues]
    
    cur.execute("SELECT id FROM users WHERE username = ?", (session["user"],))
    user = cur.fetchone()
    if user:
        log_audit_action(conn, session["user"], "VERIFY_CHAIN", "ledger", user["id"], "Blockchain integrity verified.")
        conn.commit()
    conn.close()

    if valid:
        flash("Blockchain integrity verified successfully.", "success")
    else:
        flash("Blockchain verification failed.", "error")

    session["last_verification_issues"] = str_issues
    
    # Try to redirect back to where we came from
    referrer = request.referrer
    if referrer and (url_for('records.dashboard') in referrer or url_for('records.chain_explorer') in referrer):
        return redirect(referrer)
        
    return redirect(url_for("records.dashboard"))

@records_bp.route("/records/<int:block_id>")
def view_record(block_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))
        
    block = parse_payload(row)
    if not can_view_record_details(block):
        flash("You do not have permission to view this record.", "error")
        return redirect(url_for("records.dashboard"))
        
    inline_preview = bool(block.get("file_name", "").lower().endswith((".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".txt"))) if block.get("file_name") else False
    student_view = session.get("role") == "Student"
    return render_template("record_view.html", block=block, inline_preview=inline_preview, student_view=student_view)

@records_bp.route("/notifications")
def notifications_page():
    if not require_login():
        return redirect(url_for("auth.login"))

    search_query = request.args.get("q", "").strip().lower()
    category_filter = request.args.get("category", "").strip().lower()
    read_filter = request.args.get("read", "").strip().lower()
    sort_key = request.args.get("sort", "latest").strip().lower()
    conn = get_connection()
    notifications = fetch_notifications(conn, session["user"], 200)
    unread_total = count_unread_notifications(conn, session["user"])
    conn.close()

    if search_query:
        notifications = [
            item for item in notifications
            if search_query in " ".join(
                [
                    item["title"],
                    item["message"],
                    item["category"],
                    item["created_at"],
                ]
            ).lower()
        ]
    if category_filter:
        notifications = [item for item in notifications if item["category"].lower() == category_filter]
    if read_filter == "unread":
        notifications = [item for item in notifications if not item["is_read"]]
    elif read_filter == "read":
        notifications = [item for item in notifications if item["is_read"]]

    if sort_key == "oldest":
        notifications.sort(key=lambda item: item["id"])
    else:
        sort_key = "latest"
        notifications.sort(key=lambda item: item["id"], reverse=True)
    
    page = get_request_page("page")
    notifications, pagination = paginate_items(notifications, page, 10)
    
    return render_template(
        "notifications.html",
        notifications=notifications,
        notifications_pagination=pagination,
        search_query=request.args.get("q", "").strip(),
        category_filter=category_filter,
        read_filter=read_filter,
        sort_key=sort_key,
        unread_total=unread_total,
    )

@records_bp.route("/notifications/mark-read", methods=["POST"])
def mark_notifications_read():
    if not require_login():
        return redirect(url_for("auth.login"))
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE notifications SET is_read = 1 WHERE recipient_username = ? AND is_read = 0", (session["user"],))
    conn.commit()
    conn.close()
    
    flash("All notifications marked as read.", "success")
    return redirect(url_for("records.notifications_page"))


@records_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
def mark_notification_read(notification_id):
    if not require_login():
        return redirect(url_for("auth.login"))

    next_url = request.form.get("next", "").strip()
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT id, link_url FROM notifications WHERE id = ? AND recipient_username = ?",
        (notification_id, session["user"]),
    ).fetchone()
    if not row:
        conn.close()
        flash("Notification not found.", "error")
        return redirect(url_for("records.notifications_page"))

    cur.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()

    if next_url:
        return redirect(next_url)
    if row["link_url"]:
        return redirect(row["link_url"])
    return redirect(url_for("records.notifications_page"))

@records_bp.route("/profile/settings", methods=["GET", "POST"])
def profile_settings():
    if not require_login():
        return redirect(url_for("auth.login"))
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE username = ?", (session["user"],))
    profile = cur.fetchone()
    if not profile:
        conn.close()
        flash("Profile not found.", "error")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        profile_action = request.form.get("profile_action", "save").strip()

        if profile_action == "remove_photo":
            updated_photo = delete_profile_photo(profile["profile_photo"])
            cur.execute("UPDATE users SET profile_photo = ? WHERE id = ?", (updated_photo, profile["id"]))
            log_audit_action(conn, session["user"], "REMOVE_PROFILE_PHOTO", "user", profile["id"], "Removed profile photo.")
            conn.commit()
            flash("Profile photo removed.", "success")
            cur.execute("SELECT * FROM users WHERE id = ?", (profile["id"],))
            profile = cur.fetchone()
        else:
            username = request.form.get("username", "").strip()
            campus_id = normalize_campus_id(request.form.get("campus_id", ""))
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            about_info = request.form.get("about_info", "").strip()

            if not username or len(username) < 3:
                conn.close()
                flash("Username must be at least 3 characters long.", "error")
                return redirect(url_for("records.profile_settings"))

            if email and ("@" not in email or "." not in email):
                conn.close()
                flash("Enter a valid campus email ID.", "error")
                return redirect(url_for("records.profile_settings"))

            existing_username = cur.execute(
                "SELECT id FROM users WHERE lower(username) = lower(?) AND id != ?",
                (username, profile["id"]),
            ).fetchone()
            if existing_username:
                conn.close()
                flash("That username is already in use.", "error")
                return redirect(url_for("records.profile_settings"))

            if email:
                existing_email = cur.execute(
                    "SELECT id FROM users WHERE lower(email) = ? AND id != ?",
                    (email, profile["id"]),
                ).fetchone()
                if existing_email:
                    conn.close()
                    flash("That campus email ID is already in use.", "error")
                    return redirect(url_for("records.profile_settings"))

            if campus_id:
                existing_campus_id = cur.execute(
                    "SELECT id FROM users WHERE campus_id = ? AND id != ?",
                    (campus_id, profile["id"]),
                ).fetchone()
                if existing_campus_id:
                    conn.close()
                    flash("That campus ID is already in use.", "error")
                    return redirect(url_for("records.profile_settings"))

            try:
                profile_photo = save_profile_photo(request.files.get("profile_photo"), profile["profile_photo"])
            except ValueError as exc:
                conn.close()
                flash(str(exc), "error")
                return redirect(url_for("records.profile_settings"))

            old_username = profile["username"]
            cur.execute(
                """
                UPDATE users
                SET username = ?, campus_id = ?, email = ?, phone = ?, about_info = ?, profile_photo = ?
                WHERE id = ?
                """,
                (username, campus_id or None, email or None, phone or None, about_info or None, profile_photo, profile["id"]),
            )
            if old_username != username:
                cur.execute("UPDATE notifications SET recipient_username = ? WHERE recipient_username = ?", (username, old_username))
                cur.execute("UPDATE audit_logs SET user_name = ? WHERE user_name = ?", (username, old_username))

            log_audit_action(conn, username, "UPDATE_PROFILE", "user", profile["id"], "Updated profile settings.")
            create_notification(conn, username, "account", "Profile Updated", "Your profile details and settings were successfully updated.", url_for("records.profile_settings"))
            conn.commit()

            session["user"] = username
            session["email"] = email or ""
            session["campus_id"] = campus_id or ""
            flash("Profile updated successfully.", "success")
            cur.execute("SELECT * FROM users WHERE id = ?", (profile["id"],))
            profile = cur.fetchone()

    conn.close()

    completed_fields = [
        bool(profile["username"]),
        bool(profile["campus_id"]),
        bool(profile["email"]),
        bool(profile["phone"]),
        bool(profile["about_info"]),
        bool(profile["profile_photo"]),
    ]
    missing = []
    if not profile["campus_id"]:
        missing.append("campus ID")
    if not profile["email"]:
        missing.append("campus email ID")
    if not profile["phone"]:
        missing.append("phone")
    if not profile["about_info"]:
        missing.append("about")
    if not profile["profile_photo"]:
        missing.append("profile photo")

    completeness = {
        "percent": round((sum(completed_fields) / len(completed_fields)) * 100),
        "completed": sum(completed_fields),
        "total": len(completed_fields),
        "missing": missing,
    }
    profile_photo_url = (
        url_for("main.uploaded_media_file", stored_name=profile["profile_photo"])
        if profile["profile_photo"]
        else None
    )

    return render_template(
        "profile_settings.html",
        profile=profile,
        completeness=completeness,
        account_status_label=lambda u: "Disabled" if u["disabled"] else "Active",
        profile_photo_url=profile_photo_url,
    )

@records_bp.route("/profiles")
def profile_directory():
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_view_profile_directory():
        flash("Only faculty, exam cell, and administrators can open the profile directory.", "error")
        return redirect(url_for("records.dashboard"))

    search_query = request.args.get("q", "").strip().lower()
    sort_key = request.args.get("sort", "username").strip()

    conn = get_connection()
    cur = conn.cursor()
    rows = list(
        cur.execute(
            """
            SELECT id, username, campus_id, email, phone, about_info, role, disabled, created_at, last_login_at, profile_photo
            FROM users
            ORDER BY created_at DESC
            """
        ).fetchall()
    )
    conn.close()

    if session.get("role") != "Administrator":
        rows = [row for row in rows if row["role"] != "Administrator"]

    profiles = []
    for row in rows:
        item = dict(row)
        if search_query:
            searchable = " ".join(
                [
                    item.get("username", ""),
                    item.get("campus_id") or "",
                    item.get("role", ""),
                    item.get("about_info") or "",
                ]
            ).lower()
            if search_query not in searchable:
                continue
        item["profile_photo_url"] = _profile_photo_url(item)
        profiles.append(item)

    if sort_key == "latest":
        profiles.sort(key=lambda item: item["created_at"], reverse=True)
    elif sort_key == "role":
        profiles.sort(key=lambda item: (item["role"].lower(), item["username"].lower()))
    else:
        sort_key = "username"
        profiles.sort(key=lambda item: item["username"].lower())

    page = get_request_page("page")
    profiles, profiles_pagination = paginate_items(profiles, page, 8)
    directory_scope = "all" if session.get("role") == "Administrator" else "limited"

    return render_template(
        "profile_directory.html",
        profiles=profiles,
        profiles_pagination=profiles_pagination,
        search_query=request.args.get("q", "").strip(),
        sort_key=sort_key,
        directory_scope=directory_scope,
        directory_title="Campus Directory" if directory_scope == "all" else "Student and Staff Profiles",
        directory_message="Browse full user details and campus identity information." if directory_scope == "all" else "Browse non-administrator profile photos and identity details for academic coordination.",
    )

@records_bp.route("/review-queue")
def review_queue():
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_review_requests():
        flash("Access denied.", "error")
        return redirect(url_for("records.dashboard"))
    search_query = request.args.get("q", "").strip().lower()
    status_filter = request.args.get("status", "").strip()
    type_filter = request.args.get("request_type", "").strip()

    conn = get_connection()
    cur = conn.cursor()
    rows = list(cur.execute("SELECT * FROM record_requests ORDER BY id DESC").fetchall())
    conn.close()

    requests = []
    for row in rows:
        item = dict(row)
        try:
            item["payload"] = json.loads(item["requested_payload"] or "{}")
        except json.JSONDecodeError:
            item["payload"] = {}
        requests.append(item)

    if search_query:
        requests = [
            item for item in requests
            if search_query in " ".join([
                item.get("requester_username", ""),
                item.get("campus_id", "") or "",
                item.get("request_note", "") or "",
                item["payload"].get("document_name", "") or "",
                item["payload"].get("course", "") or "",
            ]).lower()
        ]
    if status_filter:
        requests = [item for item in requests if item.get("status") == status_filter]
    if type_filter:
        requests = [item for item in requests if item.get("request_type") == type_filter]

    page = get_request_page("page")
    requests, queue_pagination = paginate_items(requests, page, 8)
    return render_template(
        "review_queue.html",
        requests=requests,
        queue_pagination=queue_pagination,
        search_query=search_query,
        status_filter=status_filter,
        type_filter=type_filter,
    )

@records_bp.route("/review-queue/<int:request_id>/action", methods=["POST"])
def review_request_action(request_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_review_requests():
        flash("Access denied.", "error")
        return redirect(url_for("records.dashboard"))

    decision = request.form.get("decision", "").strip().lower()
    if decision not in {"approve", "reject"}:
        flash("Invalid review decision.", "error")
        return redirect(url_for("records.review_queue"))

    reviewer_note = request.form.get("reviewer_note", "").strip()
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM record_requests WHERE id = ?", (request_id,)).fetchone()
    if not row:
        conn.close()
        flash("Request not found.", "error")
        return redirect(url_for("records.review_queue"))

    new_status = "Approved" if decision == "approve" else "Rejected"
    linked_block_id = row["linked_block_id"]
    if decision == "approve" and row["request_type"] == "NEW_RECORD":
        try:
            payload = json.loads(row["requested_payload"] or "{}")
        except json.JSONDecodeError:
            payload = {}

        requester = cur.execute(
            "SELECT username, campus_id FROM users WHERE username = ?",
            (row["requester_username"],),
        ).fetchone()
        directory_entry = cur.execute(
            "SELECT full_name FROM campus_directory WHERE campus_id = ?",
            (row["campus_id"],),
        ).fetchone()
        student_name = (
            directory_entry["full_name"]
            if directory_entry
            else (requester["username"] if requester else row["requester_username"])
        )
        form_data = normalize_record_data(
            {
                "student_id": row["campus_id"] or (requester["campus_id"] if requester else ""),
                "student_name": student_name,
                "course": (payload.get("course") or "").strip(),
                "document_name": (payload.get("document_name") or "").strip(),
                "certificate_id": (payload.get("certificate_id") or "").strip().upper(),
                "storage_node": "Academic Registry",
                "record_notes": reviewer_note or row["request_note"],
                "record_type": (payload.get("record_type") or "Certificate").strip() or "Certificate",
                "record_status": "Active",
                "marks_obtained": "",
                "max_marks": "",
            }
        )
        if not all([form_data["student_id"], form_data["student_name"], form_data["course"], form_data["document_name"]]):
            conn.close()
            flash("This request is missing enough data to create a record.", "error")
            return redirect(url_for("records.review_queue"))
        conn.close()
        linked_block_id = add_record(session["user"], form_data, None)
        conn = get_connection()
        cur = conn.cursor()
        notify_user_for_campus_id(
            conn,
            form_data["student_id"],
            "record",
            "Record approved and created",
            f"{form_data['document_name']} was approved and added to HashVera.",
            url_for("records.view_record", block_id=linked_block_id),
        )
    elif decision == "approve" and row["request_type"] == "CORRECTION" and row["related_block_id"]:
        linked_block_id = row["related_block_id"]

    cur.execute(
        """
        UPDATE record_requests
        SET status = ?, reviewer_username = ?, reviewer_note = ?, linked_block_id = ?, updated_at = ?
        WHERE id = ?
        """,
        (new_status, session["user"], reviewer_note or None, linked_block_id, utc_now(), request_id),
    )
    create_notification(
        conn,
        row["requester_username"],
        "request",
        f"Request {new_status.lower()}",
        f"Your {row['request_type'].replace('_', ' ').lower()} request was {new_status.lower()} by {session['user']}.",
        url_for("records.view_record", block_id=linked_block_id) if linked_block_id and new_status == "Approved" else url_for("records.my_records"),
    )
    log_audit_action(conn, session["user"], "REVIEW_REQUEST", "request", str(request_id), f"{new_status} {row['request_type']} request from {row['requester_username']}.")
    conn.commit()
    conn.close()
    flash("Request action processed.", "success")
    return redirect(url_for("records.review_queue"))

@records_bp.route("/certificate/verify")
def certificate_verify():
    if not require_login():
        return redirect(url_for("auth.login"))
    certificate_id = request.args.get("certificate_id", "").strip().upper()
    verification_result = None

    if certificate_id:
        conn = get_connection()
        cur = conn.cursor()
        rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
        valid_chain, issues = check_chain_validity(rows, conn)
        matched_row = None
        for row in reversed(rows):
            block = parse_payload(row)
            if (block.get("certificate_id") or "").strip().upper() == certificate_id:
                matched_row = block
                break

        verification_result = {
            "found": bool(matched_row),
            "valid": bool(matched_row and valid_chain and matched_row.get("record_status") != "Archived"),
            "issues": issues,
            "record": matched_row,
        }
        if matched_row:
            user = cur.execute("SELECT id FROM users WHERE username = ?", (session["user"],)).fetchone()
            if user:
                log_audit_action(conn, session["user"], "VERIFY_CERTIFICATE", "certificate", matched_row["id"], f"Verified {certificate_id}.")
                conn.commit()
        conn.close()

    return render_template("certificate_verify.html", certificate_id=certificate_id, verification_result=verification_result)

@records_bp.route("/certificate/preview/<int:block_id>")
def certificate_preview(block_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,))
    row = cur.fetchone()
    conn.close()
    
    if not row:
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))
        
    block = parse_payload(row)
    if not can_view_record_details(block):
        flash("You do not have permission to preview this certificate.", "error")
        return redirect(url_for("records.dashboard"))
    return render_template("certificate_preview.html", block=block)

@records_bp.route("/certificate/pdf/<int:block_id>")
def certificate_pdf(block_id):
    """Generate and download a PDF certificate for a given block."""
    if not require_login():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))

    block = parse_payload(row)
    if not can_view_record_details(block):
        flash("You do not have permission to download this certificate.", "error")
        return redirect(url_for("records.dashboard"))

    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        flash("PDF generation library is not installed.", "error")
        return redirect(url_for("records.certificate_preview", block_id=block_id))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
    )

    styles = getSampleStyleSheet()
    primary_color = HexColor("#0f766e")
    dark_color = HexColor("#0f172a")
    muted_color = HexColor("#64748b")
    success_color = HexColor("#10b981")
    line_color = HexColor("#e2e8f0")
    bg_color = HexColor("#f8fafc")

    title_style = ParagraphStyle(
        "CertTitle",
        parent=styles["Heading1"],
        fontSize=22,
        leading=28,
        textColor=dark_color,
        alignment=TA_CENTER,
        spaceAfter=4 * mm,
    )
    subtitle_style = ParagraphStyle(
        "CertSubtitle",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=muted_color,
        alignment=TA_CENTER,
        spaceAfter=8 * mm,
    )
    heading_style = ParagraphStyle(
        "CertHeading",
        parent=styles["Heading2"],
        fontSize=12,
        leading=16,
        textColor=primary_color,
        spaceBefore=6 * mm,
        spaceAfter=3 * mm,
    )
    label_style = ParagraphStyle(
        "CertLabel",
        parent=styles["Normal"],
        fontSize=7,
        leading=10,
        textColor=muted_color,
        spaceAfter=1 * mm,
    )
    value_style = ParagraphStyle(
        "CertValue",
        parent=styles["Normal"],
        fontSize=11,
        leading=14,
        textColor=dark_color,
        spaceAfter=4 * mm,
    )
    hash_style = ParagraphStyle(
        "CertHash",
        parent=styles["Normal"],
        fontSize=7,
        leading=10,
        textColor=primary_color,
        fontName="Courier",
        alignment=TA_CENTER,
        spaceAfter=3 * mm,
    )
    footer_style = ParagraphStyle(
        "CertFooter",
        parent=styles["Normal"],
        fontSize=7,
        leading=10,
        textColor=muted_color,
        alignment=TA_CENTER,
    )
    seal_style = ParagraphStyle(
        "CertSeal",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
        textColor=success_color,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )

    elements = []

    # Header
    elements.append(Paragraph("HashVera Academic Record Network", subtitle_style))
    elements.append(Paragraph("Official Academic Record Certificate", title_style))
    elements.append(Paragraph(
        f"Certificate ID: {block.get('certificate_id', 'N/A')} &nbsp;|&nbsp; "
        f"Block #{block.get('block_index', 'N/A')}",
        subtitle_style,
    ))
    elements.append(HRFlowable(width="100%", thickness=1, color=line_color, spaceAfter=6 * mm))

    # Validation Seal
    elements.append(Paragraph("✓ BLOCKCHAIN VERIFIED", seal_style))
    elements.append(Paragraph(
        "This record is active, linked to the blockchain, and has passed integrity verification.",
        footer_style,
    ))
    elements.append(Spacer(1, 6 * mm))

    # Record Details Table
    detail_data = [
        ["Student Name", block.get("student_name", "N/A")],
        ["Campus ID", block.get("student_id", "N/A")],
        ["Course / Program", block.get("course", "N/A")],
        ["Document Name", block.get("document_name", "N/A")],
        ["Record Type", block.get("record_type", "N/A")],
        ["Record Status", block.get("record_status", "N/A")],
        ["Certificate ID", block.get("certificate_id", "N/A")],
    ]
    if block.get("marks_obtained") and block.get("max_marks"):
        detail_data.append(["Marks", f"{block['marks_obtained']} / {block['max_marks']}"])

    detail_data.extend([
        ["Issued By", block.get("submitted_by", "N/A")],
        ["Issue Date", block.get("timestamp", "N/A")],
        ["Block Index", str(block.get("block_index", "N/A"))],
        ["Storage Node", block.get("storage_node", "N/A")],
    ])

    col_widths = [45 * mm, 120 * mm]
    detail_table = Table(detail_data, colWidths=col_widths, hAlign="LEFT")
    detail_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), muted_color),
        ("TEXTCOLOR", (1, 0), (1, -1), dark_color),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, line_color),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (-1, -1), bg_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    elements.append(detail_table)
    elements.append(Spacer(1, 6 * mm))

    # Notes
    if block.get("record_notes"):
        elements.append(Paragraph("Notes", heading_style))
        elements.append(Paragraph(block["record_notes"], value_style))

    # Blockchain Proof
    elements.append(HRFlowable(width="100%", thickness=0.5, color=line_color, spaceBefore=4 * mm, spaceAfter=4 * mm))
    elements.append(Paragraph("BLOCKCHAIN PROOF", ParagraphStyle(
        "ProofHeader",
        parent=styles["Normal"],
        fontSize=8,
        leading=12,
        textColor=primary_color,
        alignment=TA_CENTER,
        spaceAfter=2 * mm,
    )))
    elements.append(Paragraph(f"Block Hash: {block.get('block_hash', 'N/A')}", hash_style))
    elements.append(Paragraph(f"Previous Hash: {block.get('previous_hash', 'N/A')}", hash_style))

    # QR code info
    verify_url = url_for("main.public_verify", block_hash=block["block_hash"], _external=True)
    elements.append(Spacer(1, 4 * mm))
    elements.append(Paragraph(
        f'Verify online: <link href="{verify_url}">{verify_url}</link>',
        ParagraphStyle("VerifyLink", parent=footer_style, textColor=primary_color, fontSize=7),
    ))

    # Footer
    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=line_color, spaceAfter=3 * mm))
    elements.append(Paragraph(
        f"Generated by HashVera Academic Record Network &nbsp;|&nbsp; "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        footer_style,
    ))
    elements.append(Paragraph(
        "This document is a digital export. Verify authenticity at the HashVera verification portal.",
        footer_style,
    ))

    doc.build(elements)
    buffer.seek(0)

    safe_cert_id = block.get("certificate_id", "record").replace(" ", "_")
    response = make_response(buffer.getvalue())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f"attachment; filename=HashVera_{safe_cert_id}.pdf"
    return response

@records_bp.route("/archived")
def archived_records():
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_archive_records():
        flash("Only exam cell and administrator accounts can open archived records.", "error")
        return redirect(url_for("records.dashboard"))

    search_query = request.args.get("q", "").strip().lower()
    course_filter = request.args.get("course", "").strip()
    node_filter = request.args.get("node", "").strip()
    sort_key = request.args.get("sort", "latest").strip()

    conn = get_connection()
    cur = conn.cursor()
    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index DESC").fetchall())
    conn.close()

    archived_blocks = [parse_payload(row) for row in rows if parse_payload(row)["record_status"] == "Archived"]
    all_archived_count = len(archived_blocks)

    if search_query:
        archived_blocks = [
            block for block in archived_blocks
            if search_query in " ".join(
                [
                    block.get("student_id", ""),
                    block.get("student_name", ""),
                    block.get("course", ""),
                    block.get("document_name", ""),
                    block.get("certificate_id", ""),
                    block.get("storage_node", ""),
                    block.get("record_notes", ""),
                ]
            ).lower()
        ]
    if course_filter:
        archived_blocks = [block for block in archived_blocks if block.get("course") == course_filter]
    if node_filter:
        archived_blocks = [block for block in archived_blocks if block.get("storage_node") == node_filter]

    if sort_key == "oldest":
        archived_blocks.sort(key=lambda block: block["block_index"])
    elif sort_key == "student":
        archived_blocks.sort(key=lambda block: (block.get("student_name", "").lower(), -int(block["block_index"])))
    else:
        sort_key = "latest"
        archived_blocks.sort(key=lambda block: block["block_index"], reverse=True)

    page = get_request_page("page")
    archived_blocks, archived_pagination = paginate_items(archived_blocks, page, 6)
    all_blocks = [parse_payload(row) for row in rows]

    return render_template(
        "archived_records.html",
        archived_blocks=archived_blocks,
        archived_pagination=archived_pagination,
        search_query=request.args.get("q", "").strip(),
        course_filter=course_filter,
        node_filter=node_filter,
        sort_key=sort_key,
        course_options=sorted({block["course"] for block in all_blocks if block.get("course")}),
        node_options=sorted({block["storage_node"] for block in all_blocks if block.get("storage_node")}),
        all_archived_count=all_archived_count,
    )

@records_bp.route("/blocks/<int:block_id>/edit", methods=["GET", "POST"])
def edit_block(block_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_edit_records():
        flash("Only teachers, exam cell, and administrator accounts can edit records.", "error")
        return redirect(url_for("records.dashboard"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))

    block = parse_payload(row)
    if request.method == "POST":
        form_data = get_form_record_data(request.form)
        try:
            form_data = normalize_record_data(form_data)
        except ValueError as exc:
            conn.close()
            flash(str(exc), "error")
            return redirect(url_for("records.edit_block", block_id=block_id))

        if not all([form_data.get(k) for k in ["student_id", "student_name", "course", "document_name", "storage_node", "record_notes", "record_type"]]):
            conn.close()
            flash("Fill in all record fields before saving changes.", "error")
            return redirect(url_for("records.edit_block", block_id=block_id))

        try:
            new_file_meta = save_uploaded_file(request.files.get("document_file"))
        except ValueError as exc:
            conn.close()
            flash(str(exc), "error")
            return redirect(url_for("records.edit_block", block_id=block_id))

        existing_file_meta = {
            "file_name": block.get("file_name"),
            "file_path": block.get("file_path"),
            "file_size": block.get("file_size") or 0,
        } if block.get("file_name") else None
        file_meta = new_file_meta or existing_file_meta
        if new_file_meta and block.get("file_path"):
            old_path = os.path.join(AppConfig.UPLOAD_DIR, str(block["file_path"]).replace("/", os.sep))
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                except OSError:
                    pass

        payload = serialize_payload(build_record_payload(form_data, file_meta))
        cur.execute(
            """
            UPDATE blocks
            SET payload = ?, file_name = ?, file_path = ?, file_size = ?, record_type = ?, record_status = ?,
                updated_at = ?, last_modified_by = ?
            WHERE id = ?
            """,
            (
                payload,
                file_meta["file_name"] if file_meta else None,
                file_meta["file_path"] if file_meta else None,
                file_meta["file_size"] if file_meta else 0,
                form_data["record_type"],
                form_data["record_status"],
                utc_now(),
                session["user"],
                block_id,
            ),
        )
        _rebuild_chain_from(conn, row["block_index"])
        notify_user_for_campus_id(
            conn,
            form_data["student_id"],
            "record",
            "Record updated",
            f"{form_data['document_name']} was updated in HashVera.",
            url_for("records.view_record", block_id=block_id),
        )
        log_audit_action(conn, session["user"], "EDIT_RECORD", "block", str(block_id), f"Updated {form_data['document_name']} for {form_data['student_id']}.")
        conn.commit()
        conn.close()
        flash("Record updated successfully.", "success")
        return redirect(url_for("records.view_record", block_id=block_id))

    conn.close()
    return render_template("edit_block.html", block=block)

@records_bp.route("/blocks/<int:block_id>/archive", methods=["POST"])
def archive_block(block_id):
    if not can_archive_records():
        flash("Only teachers, exam cell, and administrator accounts can archive records.", "error")
        return redirect(url_for("records.dashboard"))
        
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,)).fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))
    block = parse_payload(row)
    cur.execute(
        "UPDATE blocks SET record_status = 'Archived', updated_at = ?, last_modified_by = ? WHERE id = ?",
        (utc_now(), session["user"], block_id),
    )
    notify_user_for_campus_id(
        conn,
        block.get("student_id"),
        "record",
        "Record archived",
        f"{block.get('document_name', 'Record')} was archived.",
        url_for("records.view_record", block_id=block_id),
    )
    conn.commit()
    conn.close()
    flash("Record archived.", "success")
    return redirect(url_for("records.dashboard"))

@records_bp.route("/blocks/<int:block_id>/delete", methods=["POST"])
def delete_block(block_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_edit_records():
        flash("You do not have permission to delete records.", "error")
        return redirect(url_for("records.dashboard"))
        
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,)).fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))
        
    cur.execute("DELETE FROM blocks WHERE id = ?", (block_id,))
    conn.commit()
    conn.close()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({"success": True, "message": "Record permanently deleted."})

    flash("Record permanently deleted.", "success")
    return redirect(request.referrer or url_for("records.dashboard"))

@records_bp.route("/blocks/<int:block_id>/restore", methods=["POST"])
def restore_block(block_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,)).fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "error")
        return redirect(url_for("records.dashboard"))
    block = parse_payload(row)
    cur.execute(
        "UPDATE blocks SET record_status = 'Active', updated_at = ?, last_modified_by = ? WHERE id = ?",
        (utc_now(), session["user"], block_id),
    )
    notify_user_for_campus_id(
        conn,
        block.get("student_id"),
        "record",
        "Record restored",
        f"{block.get('document_name', 'Record')} was restored.",
        url_for("records.view_record", block_id=block_id),
    )
    conn.commit()
    conn.close()
    flash("Record restored.", "success")
    return redirect(url_for("records.dashboard"))

@records_bp.route("/submit-request", methods=["POST"])
def submit_record_request():
    if not require_login():
        return redirect(url_for("auth.login"))
    campus_id = current_student_campus_id()
    payload = {
        "course": request.form.get("course", "").strip(),
        "document_name": request.form.get("document_name", "").strip(),
        "record_type": request.form.get("record_type", "").strip() or "Certificate",
        "certificate_id": request.form.get("certificate_id", "").strip().upper(),
    }
    request_note = request.form.get("request_note", "").strip()
    if not all([payload["course"], payload["document_name"], request_note]):
        flash("Fill in the request details before submitting.", "error")
        return redirect(url_for("records.my_records"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO record_requests(
            request_type, requester_username, requester_role, campus_id, related_block_id,
            requested_payload, request_note, status, reviewer_username, reviewer_note,
            linked_block_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, NULL, ?, ?, 'Pending', NULL, NULL, NULL, ?, ?)
        """,
        ("NEW_RECORD", session["user"], session.get("role", ""), campus_id, json.dumps(payload), request_note, utc_now(), utc_now()),
    )
    request_id = cur.lastrowid
    notify_roles(
        conn,
        ["Faculty", "Exam Cell", "Administrator"],
        "request",
        "New record request",
        f"{session['user']} submitted a new record request for campus ID {campus_id or 'Not set'}.",
        url_for("records.review_queue"),
    )
    log_audit_action(conn, session["user"], "SUBMIT_RECORD_REQUEST", "request", str(request_id), f"Submitted new record request for {campus_id or 'no campus id'}.")
    conn.commit()
    conn.close()
    flash("Record request submitted for review.", "success")
    return redirect(url_for("records.my_records"))

@records_bp.route("/records/<int:block_id>/correction", methods=["POST"])
def request_record_correction(block_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    correction_note = request.form.get("correction_note", "").strip()
    if not correction_note:
        flash("Enter a correction note before sending the request.", "error")
        return redirect(url_for("records.my_records"))

    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute("SELECT * FROM blocks WHERE id = ?", (block_id,)).fetchone()
    if not row:
        conn.close()
        flash("Record not found.", "error")
        return redirect(url_for("records.my_records"))
    block = parse_payload(row)
    cur.execute(
        """
        INSERT INTO record_requests(
            request_type, requester_username, requester_role, campus_id, related_block_id,
            requested_payload, request_note, status, reviewer_username, reviewer_note,
            linked_block_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'Pending', NULL, NULL, ?, ?, ?)
        """,
        (
            "CORRECTION",
            session["user"],
            session.get("role", ""),
            block.get("student_id"),
            block_id,
            json.dumps({"document_name": block.get("document_name"), "course": block.get("course"), "record_type": block.get("record_type")}),
            correction_note,
            block_id,
            utc_now(),
            utc_now(),
        ),
    )
    request_id = cur.lastrowid
    notify_roles(
        conn,
        ["Faculty", "Exam Cell", "Administrator"],
        "request",
        "Correction requested",
        f"{session['user']} requested a correction for {block.get('document_name', 'a record')}.",
        url_for("records.review_queue"),
    )
    log_audit_action(
        conn,
        session["user"],
        "REQUEST_RECORD_CORRECTION",
        "request",
        str(request_id),
        f"Requested correction for block {block_id}: {correction_note}",
    )
    conn.commit()
    conn.close()
    flash("Correction request sent to academic team.", "success")
    return redirect(url_for("records.my_records"))

@records_bp.route("/profiles/<int:user_id>")
def view_user_profile(user_id):
    if not require_login():
        return redirect(url_for("auth.login"))
    if not can_view_profile_directory():
        flash("Only faculty, exam cell, and administrators can open profile details.", "error")
        return redirect(url_for("records.dashboard"))

    conn = get_connection()
    cur = conn.cursor()
    profile = cur.execute(
        """
        SELECT id, username, campus_id, email, phone, about_info, role, disabled, created_at, last_login_at, profile_photo
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    conn.close()
    if not profile:
        flash("Profile not found.", "error")
        return redirect(url_for("records.profile_directory"))

    visibility_scope = "all" if session.get("role") == "Administrator" else "limited"
    if visibility_scope != "all" and profile["role"] == "Administrator":
        flash("Administrator profiles are hidden in this view.", "error")
        return redirect(url_for("records.profile_directory"))

    return render_template(
        "profile_view.html",
        profile=profile,
        profile_photo_url=_profile_photo_url(profile),
        visibility_scope=visibility_scope,
        account_status_label=_account_status_label,
    )

@records_bp.route("/bulk-mint", methods=["GET", "POST"])
def bulk_mint():
    if not require_login():
        return redirect(url_for("auth.login"))
    if session.get("role") not in ["Administrator", "Exam Cell"]:
        flash("Unauthorized access to Bulk Minting Console.", "error")
        return redirect(url_for("records.dashboard"))

    if request.method == "POST":
        file = request.files.get("bulk_file")
        if not file or not file.filename.endswith(".csv"):
            flash("Please upload a valid CSV file.", "error")
            return redirect(url_for("records.bulk_mint"))

        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            reader = csv.DictReader(stream)
            
            success_count = 0
            error_count = 0
            errors = []
            
            conn = get_connection()
            cur = conn.cursor()
            
            # Fetch starting index and hash for this batch
            cur.execute("SELECT block_index, block_hash FROM blocks ORDER BY block_index DESC LIMIT 1")
            last_block = cur.fetchone()
            
            current_idx = (last_block['block_index'] or 0) + 1 if last_block else 1
            current_prev_hash = last_block['block_hash'] if last_block else "GENESIS"
            
            for i, row in enumerate(reader):
                try:
                    # Basic validation
                    campus_id = row.get("Campus ID", "").strip()
                    student_name = row.get("Student Name", "").strip()
                    course = row.get("Course", "").strip()
                    doc_name = row.get("Document Name", "").strip()
                    cert_id = row.get("Certificate ID", "").strip()
                    marks = row.get("Marks Obtained", "").strip()
                    max_marks = row.get("Max Marks", "").strip()
                    
                    if not all([campus_id, student_name, course, doc_name]):
                        error_count += 1
                        errors.append(f"Row {i+1}: Missing required fields (Campus ID, Name, Course, or Document Name).")
                        continue

                    # Prepare record data
                    record_data = {
                        "student_id": campus_id,
                        "student_name": student_name,
                        "course": course,
                        "document_name": doc_name,
                        "certificate_id": cert_id,
                        "marks_obtained": marks,
                        "max_marks": max_marks,
                        "record_type": row.get("Record Type", "Academic Record"),
                        "record_status": "Active",
                        "record_notes": row.get("Notes", "Bulk Minted"),
                        "storage_node": AppConfig.LOCAL_NODE_NAME,
                        "submitted_by": session.get("user")
                    }
                    
                    # Normalize and Add to Blockchain
                    norm_data = normalize_record_data(record_data)
                    
                    # Mint the block manually so we can track the hash
                    # We'll use a modified add_record or just do the logic here.
                    # Let's use a new helper in blockchain.py for this.
                    from hashvera.utils.blockchain import add_record_to_batch
                    new_block_id, new_block_hash = add_record_to_batch(
                        session.get("user"), norm_data, None, conn, current_idx, current_prev_hash
                    )
                    
                    # Update for next iteration
                    current_idx += 1
                    current_prev_hash = new_block_hash
                    success_count += 1
                    
                except Exception as row_err:
                    error_count += 1
                    errors.append(f"Row {i+1}: {str(row_err)}")
            if success_count > 0:
                try:
                    log_audit_action(conn, session.get("user"), "BULK_MINT", "system", str(success_count), f"Minted {success_count} records via CSV")
                except Exception:
                    pass  # Audit logging is non-critical
            conn.commit()
            conn.close()
            
            if success_count > 0:
                flash(f"Successfully minted {success_count} records to the blockchain!", "success")
            
            if error_count > 0:
                return render_template("bulk_mint_results.html", success_count=success_count, error_count=error_count, errors=errors)
                
            return redirect(url_for("records.dashboard"))
            
        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "error")
            return redirect(url_for("records.bulk_mint"))

    return render_template("bulk_mint.html")

@records_bp.route("/bulk-mint/template")
def bulk_mint_template():
    if not require_login():
        return redirect(url_for("auth.login"))
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Campus ID", "Student Name", "Course", "Document Name", 
        "Certificate ID", "Marks Obtained", "Max Marks", 
        "Record Type", "Notes"
    ])
    writer.writerow([
        "10482", "Aswin", "BCA", "Degree Certificate", 
        "CERT26-9001", "582", "600", 
        "Degree", "Initial bulk upload"
    ])
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=hashvera_bulk_template.csv"}
    )


