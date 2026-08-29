from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory, Response
from ..database import get_connection, list_database_backups, backup_database_file, validate_database_file
from ..utils.auth_helpers import require_admin, require_login
from ..utils.common import get_request_page, paginate_items, utc_now, normalize_campus_id
from ..utils.email import get_mail_service_status, send_admin_reset_email, send_email_message
from ..utils.hashing import hash_password, validate_password_strength
from ..utils.audit import log_audit_action
from ..utils.notifications import create_notification
from ..utils.files import delete_profile_photo
from ..utils.blockchain import fetch_chain_records, validate_chain_payload, should_adopt_chain, replace_chain, sync_nodes, current_chain_summary, add_record, check_chain_validity
from ..utils.records import parse_payload
from ..utils.reporting import generate_admin_ledger_report
from ..config import AppConfig
import sqlite3
import os
import shutil
import csv
import json
from io import StringIO
from urllib import request as urlrequest, error as urlerror
from urllib.parse import urljoin

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _peer_headers(node):
    headers = {"Accept": "application/json"}
    peer_token = (node["api_token"] or AppConfig.PEER_SHARED_TOKEN or "").strip()
    if peer_token:
        headers["X-HashVera-Token"] = peer_token
    return headers


def _request_peer_json(node, path, method="GET", payload=None):
    base_url = (node["peer_url"] or "").strip().rstrip("/")
    if not base_url:
        raise ValueError("Peer base URL is not configured.")

    body = None
    headers = _peer_headers(node)
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request_obj = urlrequest.Request(
        urljoin(base_url + "/", path.lstrip("/")),
        data=body,
        headers=headers,
        method=method,
    )

    with urlrequest.urlopen(request_obj, timeout=AppConfig.PEER_REQUEST_TIMEOUT) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        raw_body = response.read().decode(charset)
        return json.loads(raw_body or "{}")


def _update_peer_sync_state(conn, node_id, *, status, result, synced_block=None, synced_hash=None):
    conn.execute(
        """
        UPDATE nodes
        SET status = ?,
            last_sync_status = ?,
            last_sync_result = ?,
            last_sync_attempt_at = ?,
            last_sync_time = COALESCE(?, last_sync_time),
            last_synced_block = COALESCE(?, last_synced_block),
            integrity_hash = COALESCE(?, integrity_hash)
        WHERE id = ?
        """,
        (
            "Online" if status == "success" else "Issue",
            status,
            result,
            utc_now(),
            utc_now() if synced_block is not None or synced_hash is not None else None,
            synced_block,
            synced_hash,
            node_id,
        ),
    )

@admin_bp.route("/users")
def admin_users():
    if not require_admin():
        return redirect(url_for("auth.login"))

    search_query = request.args.get("q", "").strip().lower()
    sort_key = request.args.get("sort", "latest").strip()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, username, campus_id, email, role, force_password_change, disabled, disabled_at, disabled_reason, last_login_at, created_at
        FROM users
        ORDER BY created_at DESC
        """
    )
    users = list(cur.fetchall())
    conn.close()
    
    if search_query:
        users = [
            user
            for user in users
            if search_query in " ".join(
                [user["username"], user["campus_id"] or "", user["email"] or "", user["role"], user["created_at"], user["last_login_at"] or "", user["disabled_reason"] or ""]
            ).lower()
        ]
    
    if sort_key == "username":
        users.sort(key=lambda user: user["username"].lower())
    elif sort_key == "role":
        users.sort(key=lambda user: (user["role"].lower(), user["username"].lower()))
    else:
        sort_key = "latest"
        users.sort(key=lambda user: user["created_at"], reverse=True)
        
    users_page = get_request_page("page")
    users, users_pagination = paginate_items(users, users_page, 6)
    mail_ready, mail_status_message = get_mail_service_status()
    
    return render_template(
        "admin_users.html",
        users=users,
        mail_ready=mail_ready,
        mail_status_message=mail_status_message,
        search_query=search_query,
        sort_key=sort_key,
        users_pagination=users_pagination,
    )

@admin_bp.route("/support-inbox")
def support_inbox():
    if not require_admin():
        return redirect(url_for("auth.login"))
        
    search_query = request.args.get("q", "").strip().lower()
    status_filter = request.args.get("status", "").strip()
    
    show_archived = request.args.get("archived", "0") == "1"
    
    conn = get_connection()
    cur = conn.cursor()
    # Join with campus_directory to get more student info
    query = f"""
        SELECT t.*, d.department
        FROM support_tickets t
        LEFT JOIN campus_directory d ON t.username = d.campus_id
        WHERE t.is_archived = {1 if show_archived else 0}
    """
    params = []
    
    conditions = []
    if status_filter:
        conditions.append("t.status = ?")
        params.append(status_filter)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
        
    query += " ORDER BY t.created_at DESC"
    
    tickets = list(cur.execute(query, params).fetchall())
    conn.close()
    
    if search_query:
        tickets = [
            t for t in tickets
            if search_query in t["name"].lower()
            or search_query in t["email"].lower()
            or search_query in t["message"].lower()
            or search_query in t["category"].lower()
        ]
        
    return render_template("admin/support_inbox.html", tickets=tickets, search_query=search_query, status_filter=status_filter, show_archived=show_archived)

@admin_bp.route("/support-inbox/update/<int:ticket_id>", methods=["POST"])
def update_support_ticket(ticket_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
        
    status = request.form.get("status")
    priority = request.form.get("priority", "Medium")
    admin_note = request.form.get("admin_note")
    
    conn = get_connection()
    ticket = conn.execute("SELECT name, username FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    
    conn.execute(
        "UPDATE support_tickets SET status = ?, priority = ?, admin_note = ?, updated_at = ? WHERE id = ?",
        (status, priority, admin_note, utc_now(), ticket_id)
    )
    conn.commit()
    
    if ticket and ticket["username"]:
        create_notification(
            conn,
            ticket["username"],
            "Support",
            "Update on your Support Request",
            f"Your support request status is now '{status}'. Note from Admin: {admin_note or 'The team is looking into it.'}",
            url_for('records.dashboard')
        )
    
    conn.close()
    
    flash("Support ticket updated successfully.", "success")
    return redirect(url_for("admin.support_inbox"))

@admin_bp.route("/support-inbox/archive/<int:ticket_id>", methods=["POST"])
def archive_support_ticket(ticket_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
        
    conn = get_connection()
    conn.execute("UPDATE support_tickets SET is_archived = 1, updated_at = ? WHERE id = ?", (utc_now(), ticket_id))
    conn.commit()
    conn.close()
    
    flash("Ticket archived.", "success")
    return redirect(url_for("admin.support_inbox"))

@admin_bp.route("/support-inbox/unarchive/<int:ticket_id>", methods=["POST"])
def unarchive_support_ticket(ticket_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
        
    conn = get_connection()
    conn.execute("UPDATE support_tickets SET is_archived = 0, updated_at = ? WHERE id = ?", (utc_now(), ticket_id))
    conn.commit()
    conn.close()
    
    flash("Ticket restored to inbox.", "success")
    return redirect(url_for("admin.support_inbox"))

@admin_bp.route("/support-inbox/delete/<int:ticket_id>", methods=["POST"])
def delete_support_ticket(ticket_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
        
    conn = get_connection()
    conn.execute("DELETE FROM support_tickets WHERE id = ?", (ticket_id,))
    conn.commit()
    conn.close()
    
    flash("Ticket permanently deleted.", "danger")
    return redirect(url_for("admin.support_inbox"))

@admin_bp.route("/peers", methods=["GET", "POST"])
def admin_peers():
    if not require_admin():
        return redirect(url_for("auth.login"))

    search_query = request.args.get("q", "").strip().lower()
    sort_key = request.args.get("sort", "name").strip()
    conn = get_connection()
    cur = conn.cursor()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        location = request.form.get("location", "").strip()
        peer_url = request.form.get("peer_url", "").strip()
        api_token = request.form.get("api_token", "").strip()
        signing_key_id = request.form.get("signing_key_id", "").strip()
        signing_secret = request.form.get("signing_secret", "").strip()
        is_active = 1 if request.form.get("is_active") == "1" else 0

        if not name or not peer_url:
            conn.close()
            flash("Peer name and peer URL are required.", "error")
            return redirect(url_for("admin.admin_peers"))

        try:
            cur.execute(
                """
                INSERT INTO nodes(
                    name, location, status, last_synced_block, integrity_hash, last_sync_time,
                    peer_url, node_type, api_token, signing_key_id, signing_secret, is_active
                ) VALUES (?, ?, ?, 0, 'GENESIS', ?, ?, 'peer', ?, ?, ?, ?)
                """,
                (
                    name,
                    location or "Remote Peer",
                    "Online" if is_active else "Disabled",
                    utc_now(),
                    peer_url,
                    api_token or None,
                    signing_key_id or None,
                    signing_secret or None,
                    is_active,
                ),
            )
            node_id = cur.lastrowid
            log_audit_action(conn, session.get("user", "admin"), "ADD_PEER_NODE", "node", node_id, f"Registered peer {name} at {peer_url}.")
            conn.commit()
            flash("Peer node added successfully.", "success")
        except sqlite3.IntegrityError:
            flash("A peer node with that name already exists.", "error")
        conn.close()
        return redirect(url_for("admin.admin_peers"))

    cur.execute("SELECT * FROM nodes WHERE node_type = 'local' ORDER BY name")
    local_nodes = cur.fetchall()
    cur.execute("SELECT * FROM nodes WHERE node_type = 'peer' ORDER BY name")
    peer_nodes = list(cur.fetchall())
    cur.execute("SELECT * FROM nodes WHERE node_type = 'simulated' ORDER BY name")
    simulated_nodes = cur.fetchall()
    conn.close()

    if search_query:
        peer_nodes = [
            node for node in peer_nodes
            if search_query in " ".join(
                [
                    node["name"],
                    node["location"],
                    node["peer_url"] or "",
                    node["status"],
                    node["last_sync_status"] or "",
                    node["last_sync_result"] or "",
                    node["signing_key_id"] or "",
                ]
            ).lower()
        ]

    if sort_key == "status":
        peer_nodes.sort(key=lambda node: ((node["last_sync_status"] or node["status"]).lower(), node["name"].lower()))
    elif sort_key == "latest_sync":
        peer_nodes.sort(key=lambda node: node["last_sync_attempt_at"] or node["last_sync_time"] or "", reverse=True)
    else:
        sort_key = "name"
        peer_nodes.sort(key=lambda node: node["name"].lower())
    
    return render_template(
        "admin_peers.html",
        local_nodes=local_nodes,
        peer_nodes=peer_nodes,
        simulated_nodes=simulated_nodes,
        local_node_name=AppConfig.LOCAL_NODE_NAME,
        local_signing_key_id=AppConfig.LOCAL_SIGNING_KEY_ID,
        search_query=search_query,
        sort_key=sort_key,
    )


@admin_bp.route("/peers/<int:node_id>/save", methods=["POST"])
def save_peer_node(node_id):
    if not require_admin():
        return redirect(url_for("auth.login"))

    name = request.form.get("name", "").strip()
    location = request.form.get("location", "").strip()
    peer_url = request.form.get("peer_url", "").strip()
    api_token = request.form.get("api_token", "").strip()
    signing_key_id = request.form.get("signing_key_id", "").strip()
    signing_secret = request.form.get("signing_secret", "").strip()
    is_active = 1 if request.form.get("is_active") == "1" else 0

    if not name or not peer_url:
        flash("Peer name and peer URL are required.", "error")
        return redirect(url_for("admin.admin_peers"))

    conn = get_connection()
    cur = conn.cursor()
    existing = cur.execute("SELECT * FROM nodes WHERE id = ? AND node_type = 'peer'", (node_id,)).fetchone()
    if not existing:
        conn.close()
        flash("Peer node not found.", "error")
        return redirect(url_for("admin.admin_peers"))

    duplicate = cur.execute("SELECT id FROM nodes WHERE name = ? AND id != ?", (name, node_id)).fetchone()
    if duplicate:
        conn.close()
        flash("Another node already uses that name.", "error")
        return redirect(url_for("admin.admin_peers"))

    cur.execute(
        """
        UPDATE nodes
        SET name = ?, location = ?, peer_url = ?, api_token = ?, signing_key_id = ?, signing_secret = ?,
            is_active = ?, status = ?
        WHERE id = ?
        """,
        (
            name,
            location or "Remote Peer",
            peer_url,
            api_token or None,
            signing_key_id or None,
            signing_secret or None,
            is_active,
            "Online" if is_active else "Disabled",
            node_id,
        ),
    )
    log_audit_action(conn, session.get("user", "admin"), "UPDATE_PEER_NODE", "node", node_id, f"Updated peer {name}.")
    conn.commit()
    conn.close()
    flash("Peer node updated.", "success")
    return redirect(url_for("admin.admin_peers"))


@admin_bp.route("/peers/<int:node_id>/delete", methods=["POST"])
def delete_peer_node(node_id):
    if not require_admin():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    existing = cur.execute("SELECT name FROM nodes WHERE id = ? AND node_type = 'peer'", (node_id,)).fetchone()
    if not existing:
        conn.close()
        flash("Peer node not found.", "error")
        return redirect(url_for("admin.admin_peers"))

    cur.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
    log_audit_action(conn, session.get("user", "admin"), "DELETE_PEER_NODE", "node", node_id, f"Deleted peer {existing['name']}.")
    conn.commit()
    conn.close()
    flash("Peer node deleted.", "success")
    return redirect(url_for("admin.admin_peers"))


@admin_bp.route("/peers/<int:node_id>/test", methods=["POST"])
def test_peer_node(node_id):
    if not require_admin():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    node = cur.execute("SELECT * FROM nodes WHERE id = ? AND node_type = 'peer'", (node_id,)).fetchone()
    if not node:
        conn.close()
        flash("Peer node not found.", "error")
        return redirect(url_for("admin.admin_peers"))

    try:
        payload = _request_peer_json(node, "/api/health")
        message = (
            f"Connected to {node['name']}. Node {payload.get('node_name', node['name'])} "
            f"reports length {payload.get('length', 0)} and latest hash {payload.get('latest_hash', 'GENESIS')}."
        )
        _update_peer_sync_state(
            conn,
            node_id,
            status="success",
            result=message,
            synced_block=payload.get("length"),
            synced_hash=payload.get("latest_hash"),
        )
        log_audit_action(conn, session.get("user", "admin"), "TEST_PEER_CONNECTION", "node", node_id, message)
        conn.commit()
        flash(message, "success")
    except (ValueError, urlerror.URLError, urlerror.HTTPError, json.JSONDecodeError) as exc:
        message = f"Peer connection test failed for {node['name']}: {exc}"
        _update_peer_sync_state(conn, node_id, status="failed", result=message)
        log_audit_action(conn, session.get("user", "admin"), "TEST_PEER_CONNECTION", "node", node_id, message)
        conn.commit()
        flash(message, "error")
    finally:
        conn.close()

    return redirect(url_for("admin.admin_peers"))


@admin_bp.route("/peers/<int:node_id>/sync", methods=["POST"])
def sync_peer_node(node_id):
    if not require_admin():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    node = cur.execute("SELECT * FROM nodes WHERE id = ? AND node_type = 'peer'", (node_id,)).fetchone()
    if not node:
        conn.close()
        flash("Peer node not found.", "error")
        return redirect(url_for("admin.admin_peers"))

    try:
        payload = _request_peer_json(node, "/api/chain")
        incoming_blocks = payload.get("blocks", [])
        valid, issues, normalized_rows = validate_chain_payload(incoming_blocks)
        if not valid:
            message = f"Peer sync rejected for {node['name']}: {'; '.join(issues) or 'Invalid chain payload.'}"
            _update_peer_sync_state(conn, node_id, status="failed", result=message)
            log_audit_action(conn, session.get("user", "admin"), "SYNC_PEER_NODE", "node", node_id, message)
            conn.commit()
            flash(message, "error")
            return redirect(url_for("admin.admin_peers"))

        local_rows = fetch_chain_records(conn)
        peer_length = payload.get("length", len(normalized_rows))
        peer_hash = payload.get("latest_hash", normalized_rows[-1]["block_hash"] if normalized_rows else "GENESIS")
        adopted = should_adopt_chain(local_rows, normalized_rows)
        if adopted:
            replace_chain(conn, normalized_rows)
            latest_index = normalized_rows[-1]["block_index"] if normalized_rows else 0
            latest_hash = normalized_rows[-1]["block_hash"] if normalized_rows else "GENESIS"
            sync_nodes(conn, latest_hash, latest_index)
            message = f"Synchronized from {node['name']} and adopted a newer valid chain with {latest_index} blocks."
            _update_peer_sync_state(conn, node_id, status="success", result=message, synced_block=latest_index, synced_hash=latest_hash)
        else:
            message = f"Peer {node['name']} responded successfully, but the local chain is already up to date."
            _update_peer_sync_state(conn, node_id, status="success", result=message, synced_block=peer_length, synced_hash=peer_hash)

        log_audit_action(conn, session.get("user", "admin"), "SYNC_PEER_NODE", "node", node_id, message)
        conn.commit()
        flash(message, "success")
    except (ValueError, urlerror.URLError, urlerror.HTTPError, json.JSONDecodeError) as exc:
        message = f"Peer sync failed for {node['name']}: {exc}"
        _update_peer_sync_state(conn, node_id, status="failed", result=message)
        log_audit_action(conn, session.get("user", "admin"), "SYNC_PEER_NODE", "node", node_id, message)
        conn.commit()
        flash(message, "error")
    finally:
        conn.close()

    return redirect(url_for("admin.admin_peers"))

@admin_bp.route("/audit-logs")
def audit_logs():
    if not require_admin():
        return redirect(url_for("auth.login"))

    search_query = request.args.get("q", "").strip().lower()
    sort_key = request.args.get("sort", "latest").strip()
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM audit_logs ORDER BY id DESC LIMIT 500")
    logs = list(cur.fetchall())
    conn.close()
    
    if search_query:
        logs = [
            log
            for log in logs
            if search_query in " ".join(
                [
                    log["action"],
                    log["user_name"],
                    log["target_type"],
                    str(log["target_id"]),
                    log["details"],
                    log["created_at"],
                ]
            ).lower()
        ]
        
    if sort_key == "oldest":
        logs.sort(key=lambda log: log["id"])
    else:
        sort_key = "latest"
        logs.sort(key=lambda log: log["id"], reverse=True)
        
    logs_page = get_request_page("page")
    logs, logs_pagination = paginate_items(logs, logs_page, 12)
    
    return render_template(
        "audit_logs.html",
        logs=logs,
        search_query=search_query,
        sort_key=sort_key,
        logs_pagination=logs_pagination,
    )

@admin_bp.route("/system/bulk-issue", methods=["GET", "POST"])
def admin_bulk_issue():
    if not require_admin():
        return redirect(url_for("auth.login"))
        
    if request.method == "POST":
        uploaded = request.files.get("csv_file")
        if not uploaded or not uploaded.filename.endswith(".csv"):
            flash("Please upload a valid CSV file.", "error")
            return redirect(url_for("admin.admin_bulk_issue"))
            
        try:
            stream = StringIO(uploaded.stream.read().decode("UTF8", errors="replace"), newline=None)
            csv_input = csv.DictReader(stream)
            
            success_count = 0
            error_count = 0
            
            for row in csv_input:
                try:
                    form_data = {
                        "student_id": row.get("student_id", "").strip(),
                        "student_name": row.get("student_name", "").strip(),
                        "course": row.get("course", "").strip(),
                        "document_name": row.get("document_name", "").strip(),
                        "record_type": row.get("record_type", "Certificate").strip() or "Certificate",
                        "record_status": "Active",
                        "certificate_id": row.get("certificate_id", "").strip(),
                        "storage_node": "Academic Registry",
                        "record_notes": row.get("record_notes", "Bulk issued via Admin Panel").strip(),
                        "marks_obtained": row.get("marks_obtained", "").strip(),
                        "max_marks": row.get("max_marks", "").strip()
                    }
                    
                    if not form_data["student_id"] or not form_data["document_name"]:
                        error_count += 1
                        continue
                        
                    add_record(session["user"], form_data, None)
                    success_count += 1
                except Exception as e:
                    error_count += 1
            
            conn = get_connection()
            log_audit_action(conn, session["user"], "BULK_ISSUE", "system", str(success_count), f"Bulk issued {success_count} records via CSV.")
            create_notification(conn, session["user"], "admin", "Bulk Issuance Complete", f"Successfully issued {success_count} records. {error_count} failed or skipped.", url_for("admin.admin_bulk_issue"))
            conn.commit()
            conn.close()
            
            flash(f"Bulk issuance complete. {success_count} records added successfully, {error_count} failed or skipped.", "success" if success_count > 0 else "error")
        except Exception as e:
            flash(f"Error processing CSV: {str(e)}", "error")
            
        return redirect(url_for("admin.admin_bulk_issue"))
        
    return render_template("admin_bulk_issue.html")

@admin_bp.route("/system")
def admin_system():
    if not require_admin():
        return redirect(url_for("auth.login"))
    
    search_query = request.args.get("q", "").strip().lower()
    sort_key = request.args.get("sort", "latest").strip()
    backups = list_database_backups()
    
    if search_query:
        backups = [
            backup
            for backup in backups
            if search_query in " ".join([backup["name"], backup["size"], backup["created_at"]]).lower()
        ]
        
    if sort_key == "oldest":
        backups = list(reversed(backups))
    elif sort_key == "name":
        backups.sort(key=lambda backup: backup["name"].lower())
    else:
        sort_key = "latest"
        
    backups_page = get_request_page("page")
    backups, backups_pagination = paginate_items(backups, backups_page, 6)
    mail_ready, mail_status_message = get_mail_service_status()
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT id, user_name, action, target_type, target_id, details, created_at
        FROM audit_logs
        WHERE action IN ('BACKUP_DATABASE', 'DOWNLOAD_BACKUP', 'DELETE_BACKUP', 'IMPORT_DATABASE', 'EXPORT_CSV', 'EXPORT_PDF', 'TEST_EMAIL')
        ORDER BY id DESC
        LIMIT 10
        """
    )
    system_history = cur.fetchall()
    conn.close()
    
    return render_template(
        "admin_system.html",
        backups=backups,
        search_query=search_query,
        sort_key=sort_key,
        backups_pagination=backups_pagination,
        mail_ready=mail_ready,
        mail_status_message=mail_status_message,
        default_test_email=session.get("email") or AppConfig.MAIL_FROM or "",
        system_history=system_history,
    )


@admin_bp.route("/system/test-email", methods=["POST"])
def admin_test_email():
    if not require_admin():
        return redirect(url_for("auth.login"))

    recipient_email = request.form.get("recipient_email", "").strip().lower()
    if "@" not in recipient_email or "." not in recipient_email:
        flash("Enter a valid campus email ID.", "error")
        return redirect(url_for("admin.admin_system"))

    sent, message = send_email_message(
        recipient_email,
        "HashVera Campus Email Test",
        "This is a HashVera campus email test message.",
    )

    conn = get_connection()
    log_audit_action(
        conn,
        session.get("user", "admin"),
        "TEST_EMAIL",
        "system",
        recipient_email,
        f"Campus email test status: {message}",
    )
    conn.commit()
    conn.close()

    flash(message if sent else f"Campus email test failed: {message}", "success" if sent else "error")
    return redirect(url_for("admin.admin_system"))


@admin_bp.route("/system/backup", methods=["POST"])
def admin_backup_database():
    if not require_admin():
        return redirect(url_for("auth.login"))

    backup_path = backup_database_file("manual")
    backup_name = os.path.basename(backup_path)

    conn = get_connection()
    log_audit_action(
        conn,
        session.get("user", "admin"),
        "BACKUP_DATABASE",
        "backup",
        backup_name,
        f"Created database backup {backup_name}.",
    )
    conn.commit()
    conn.close()

    return redirect(url_for("admin.admin_download_backup", file_name=backup_name))


@admin_bp.route("/system/import", methods=["POST"])
def admin_import_database():
    if not require_admin():
        return redirect(url_for("auth.login"))

    uploaded = request.files.get("database_file")
    if not uploaded or not uploaded.filename:
        flash("Choose a backup file to import.", "error")
        return redirect(url_for("admin.admin_system"))

    temp_dir = os.path.join(AppConfig.INSTANCE_DIR, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    temp_path = os.path.join(temp_dir, uploaded.filename)
    uploaded.save(temp_path)

    try:
        validate_database_file(temp_path)
        safety_backup = backup_database_file("pre-import")
        shutil.copy2(temp_path, AppConfig.DB_PATH)

        conn = get_connection()
        log_audit_action(
            conn,
            session.get("user", "admin"),
            "IMPORT_DATABASE",
            "database",
            os.path.basename(uploaded.filename),
            f"Imported database from {uploaded.filename}. Safety backup: {os.path.basename(safety_backup)}.",
        )
        conn.commit()
        conn.close()
        flash("Backup imported successfully.", "success")
    except Exception as exc:
        flash(f"Backup import failed: {exc}", "error")
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return redirect(url_for("admin.admin_system"))


@admin_bp.route("/system/backups/<path:file_name>")
def admin_download_backup(file_name):
    if not require_admin():
        return redirect(url_for("auth.login"))

    backup_path = os.path.join(AppConfig.BACKUP_DIR, file_name)
    if not os.path.exists(backup_path):
        flash("Backup file not found.", "error")
        return redirect(url_for("admin.admin_system"))

    conn = get_connection()
    log_audit_action(
        conn,
        session.get("user", "admin"),
        "DOWNLOAD_BACKUP",
        "backup",
        file_name,
        f"Downloaded backup file {file_name}.",
    )
    conn.commit()
    conn.close()

    return send_from_directory(AppConfig.BACKUP_DIR, file_name, as_attachment=True)


@admin_bp.route("/system/backups/<path:file_name>/delete", methods=["POST"])
def admin_delete_backup(file_name):
    if not require_admin():
        return redirect(url_for("auth.login"))

    backup_path = os.path.join(AppConfig.BACKUP_DIR, file_name)
    if not os.path.exists(backup_path):
        flash("Backup file not found.", "error")
        return redirect(url_for("admin.admin_system"))

    os.remove(backup_path)

    conn = get_connection()
    log_audit_action(
        conn,
        session.get("user", "admin"),
        "DELETE_BACKUP",
        "backup",
        file_name,
        f"Deleted backup file {file_name}.",
    )
    conn.commit()
    conn.close()

    flash("Backup deleted successfully.", "success")
    return redirect(url_for("admin.admin_system"))

@admin_bp.route("/users/<int:user_id>/update-campus-id", methods=["POST"])
def admin_update_user_campus_id(user_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
    campus_id = normalize_campus_id(request.form.get("campus_id", ""))
    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT id, username, campus_id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User account not found.", "error")
        return redirect(url_for("admin.admin_users"))

    if campus_id:
        existing = cur.execute("SELECT id FROM users WHERE campus_id = ? AND id != ?", (campus_id, user_id)).fetchone()
        if existing:
            conn.close()
            flash("That campus ID is already in use.", "error")
            return redirect(url_for("admin.admin_users"))

    cur.execute("UPDATE users SET campus_id = ? WHERE id = ?", (campus_id or None, user_id))
    create_notification(
        conn,
        user["username"],
        "account",
        "Campus ID updated",
        f"Your campus ID was updated to {campus_id or 'Not set'} by the administrator.",
        url_for("records.profile_settings"),
    )
    log_audit_action(conn, session.get("user", "admin"), "UPDATE_USER_CAMPUS_ID", "user", str(user_id), f"Updated campus ID for {user['username']} to {campus_id or 'Not set'}.")
    conn.commit()
    conn.close()
    flash("Campus ID updated.", "success")
    return redirect(url_for("admin.admin_users"))

@admin_bp.route("/users/<int:user_id>/update-role", methods=["POST"])
def admin_update_user_role(user_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
    new_role = request.form.get("role", "").strip()
    allowed_roles = {"Student", "Faculty", "Exam Cell", "Administrator"}
    if new_role not in allowed_roles:
        flash("Invalid role selected.", "error")
        return redirect(url_for("admin.admin_users"))

    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT id, username, role, campus_id FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User account not found.", "error")
        return redirect(url_for("admin.admin_users"))

    if new_role == "Student" and not user["campus_id"]:
        conn.close()
        flash("Set a campus ID before assigning the Student role.", "error")
        return redirect(url_for("admin.admin_users"))

    if user["id"] == session.get("user_id") and user["role"] == "Administrator" and new_role != "Administrator":
        conn.close()
        flash("Current signed-in administrator role cannot be removed here.", "error")
        return redirect(url_for("admin.admin_users"))

    if user["role"] == "Administrator" and new_role != "Administrator":
        active_admin_count = cur.execute(
            "SELECT COUNT(*) AS total FROM users WHERE role = 'Administrator' AND disabled = 0"
        ).fetchone()["total"]
        if active_admin_count <= 1:
            conn.close()
            flash("The last active administrator cannot lose the administrator role.", "error")
            return redirect(url_for("admin.admin_users"))

    cur.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    create_notification(
        conn,
        user["username"],
        "account",
        "Role updated",
        f"Your role was updated from {user['role']} to {new_role}.",
        url_for("records.profile_settings"),
    )
    log_audit_action(conn, session.get("user", "admin"), "UPDATE_USER_ROLE", "user", str(user_id), f"Updated role for {user['username']} from {user['role']} to {new_role}.")
    conn.commit()
    conn.close()
    flash("User role updated.", "success")
    return redirect(url_for("admin.admin_users"))

@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
def admin_reset_user_password(user_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
    new_password = request.form.get("new_password", "")
    password_error = validate_password_strength(new_password)
    if password_error:
        flash(password_error, "error")
        return redirect(url_for("admin.admin_users"))

    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT id, username, email FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User account not found.", "error")
        return redirect(url_for("admin.admin_users"))

    password_hash, salt = hash_password(new_password)
    cur.execute(
        "UPDATE users SET password_hash = ?, password_salt = ?, force_password_change = 1 WHERE id = ?",
        (password_hash, salt, user_id),
    )

    sent = False
    mail_message = "Campus email delivery is unavailable, so the administrator must share the temporary password manually."
    if user["email"]:
        sent, mail_message = send_admin_reset_email(user["email"], user["username"], new_password)

    create_notification(
        conn,
        user["username"],
        "account",
        "Password reset",
        "An administrator issued a temporary password for your account. Please change it after logging in.",
        url_for("auth.login"),
    )
    log_audit_action(conn, session.get("user", "admin"), "RESET_USER_PASSWORD", "user", str(user_id), f"Temporary password set for {user['username']}. Email status: {mail_message}")
    conn.commit()
    conn.close()
    flash("Temporary password set. " + ("Email sent successfully." if sent else mail_message), "success" if sent else "error")
    return redirect(url_for("admin.admin_users"))

@admin_bp.route("/users/<int:user_id>/enable", methods=["POST"])
def admin_enable_user(user_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT id, username, disabled FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User account not found.", "error")
        return redirect(url_for("admin.admin_users"))

    cur.execute("UPDATE users SET disabled = 0, disabled_at = NULL WHERE id = ?", (user_id,))
    create_notification(
        conn,
        user["username"],
        "account",
        "Account enabled",
        "Your account was enabled by the administrator. You can sign in again.",
        url_for("auth.login"),
    )
    log_audit_action(conn, session.get("user", "admin"), "ENABLE_USER", "user", str(user_id), f"Enabled account for {user['username']}.")
    conn.commit()
    conn.close()
    flash("User account enabled.", "success")
    return redirect(url_for("admin.admin_users"))

@admin_bp.route("/users/<int:user_id>/disable", methods=["POST"])
def admin_disable_user(user_id):
    if not require_admin():
        return redirect(url_for("auth.login"))
    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute("SELECT id, username, role, disabled FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User account not found.", "error")
        return redirect(url_for("admin.admin_users"))

    if user["id"] == session.get("user_id"):
        conn.close()
        flash("Current signed-in account cannot be disabled here.", "error")
        return redirect(url_for("admin.admin_users"))

    if user["role"] == "Administrator":
        active_admin_count = cur.execute(
            "SELECT COUNT(*) AS total FROM users WHERE role = 'Administrator' AND disabled = 0"
        ).fetchone()["total"]
        if active_admin_count <= 1 and not user["disabled"]:
            conn.close()
            flash("The last active administrator cannot be disabled.", "error")
            return redirect(url_for("admin.admin_users"))

    cur.execute("UPDATE users SET disabled = 1, disabled_at = ? WHERE id = ?", (utc_now(), user_id))
    create_notification(
        conn,
        user["username"],
        "account",
        "Account disabled",
        "Your account was disabled by the administrator.",
        "",
    )
    log_audit_action(conn, session.get("user", "admin"), "DISABLE_USER", "user", str(user_id), f"Disabled account for {user['username']}.")
    conn.commit()
    conn.close()
    flash("User account disabled.", "success")
    return redirect(url_for("admin.admin_users"))

@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
def admin_delete_user(user_id):
    if not require_admin():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    user = cur.execute(
        """
        SELECT id, username, campus_id, email, role, disabled, profile_photo
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        conn.close()
        flash("User account not found.", "error")
        return redirect(url_for("admin.admin_users"))

    if user["id"] == session.get("user_id"):
        conn.close()
        flash("Current signed-in account cannot be removed here.", "error")
        return redirect(url_for("admin.admin_users"))

    if user["role"] == "Administrator":
        active_admin_count = cur.execute(
            "SELECT COUNT(*) AS total FROM users WHERE role = 'Administrator' AND disabled = 0"
        ).fetchone()["total"]
        if active_admin_count <= 1 and not user["disabled"]:
            conn.close()
            flash("The last active administrator cannot be removed.", "error")
            return redirect(url_for("admin.admin_users"))

    delete_profile_photo(user["profile_photo"])
    cur.execute("DELETE FROM notifications WHERE recipient_username = ?", (user["username"],))
    cur.execute(
        """
        UPDATE campus_directory
        SET is_registered = 0,
            registered_user_id = NULL,
            registered_at = NULL
        WHERE registered_user_id = ?
           OR campus_id = ?
        """,
        (user["id"], user["campus_id"] or ""),
    )
    cur.execute("DELETE FROM users WHERE id = ?", (user["id"],))
    log_audit_action(
        conn,
        session.get("user", "admin"),
        "DELETE_USER",
        "user",
        str(user["id"]),
        f"Deleted user {user['username']} ({user['role']}, {user['email'] or 'no campus email'}).",
    )
    conn.commit()
    conn.close()

    flash("User account deleted.", "success")
    return redirect(url_for("admin.admin_users"))

@admin_bp.route("/export-pdf")
def export_pdf_report():
    if not require_admin():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    rows = list(cur.execute("SELECT * FROM blocks ORDER BY block_index ASC").fetchall())
    
    # Get metrics
    metrics, chain_valid = current_chain_summary(conn)
    
    blocks = [parse_payload(row) for row in rows]
    
    pdf_content = generate_admin_ledger_report(blocks, metrics)
    
    log_audit_action(conn, session.get("user", "admin"), "EXPORT_PDF", "ledger", "all", "Generated administrative blockchain ledger PDF report.")
    conn.commit()
    conn.close()

    response = Response(pdf_content, mimetype="application/pdf")
    response.headers["Content-Disposition"] = "attachment; filename=HashVera_Ledger_Report.pdf"
    return response

@admin_bp.route("/export")
def export_csv():
    if not require_login():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_index ASC")
    rows = cur.fetchall()
    
    cur.execute("SELECT id FROM users WHERE username = ?", (session["user"],))
    user = cur.fetchone()
    if user:
        log_audit_action(conn, session["user"], "EXPORT_CSV", "ledger", user["id"], "Exported blockchain CSV.")
        conn.commit()
    conn.close()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["block_index", "student_id", "student_name", "course", "document_name", "record_type", "record_status"])
    for row in rows:
        writer.writerow([row["block_index"], "N/A", "N/A", "N/A", "N/A", row["record_type"], row["record_status"]])
        
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=hashvera_ledger.csv"}
    )

@admin_bp.route("/security-audit")
def security_audit():
    if not require_admin():
        return redirect(url_for("auth.login"))

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM blocks ORDER BY block_index ASC")
    rows = cur.fetchall()
    
    from ..utils.blockchain import check_chain_validity
    valid, issues = check_chain_validity(rows, conn)

    total_blocks = len(rows)
    affected_blocks = sorted({issue["block_index"] for issue in issues})
    issue_summary = {}
    for issue in issues:
        issue_summary[issue["issue_type"]] = issue_summary.get(issue["issue_type"], 0) + 1

    cur.execute("SELECT COUNT(*) AS count FROM blocks WHERE LOWER(COALESCE(record_status, '')) = 'active'")
    active_row = cur.fetchone()
    active_count = active_row["count"] if active_row else 0
    cur.execute("SELECT COUNT(*) AS count FROM blocks WHERE LOWER(COALESCE(record_status, '')) = 'archived'")
    archived_row = cur.fetchone()
    archived_count = archived_row["count"] if archived_row else 0
    cur.execute("SELECT COUNT(*) AS count FROM nodes")
    node_row = cur.fetchone()
    node_count = node_row["count"] if node_row else 0

    latest_block = rows[-1] if rows else None
    risk_score = 100 if valid else max(0, 100 - (len(issues) * 18))
    audit_metrics = {
        "scan_time": utc_now(),
        "risk_score": risk_score,
        "issue_count": len(issues),
        "affected_blocks": len(affected_blocks),
        "verified_blocks": max(total_blocks - len(affected_blocks), 0),
        "active_records": active_count,
        "archived_records": archived_count,
        "node_count": node_count,
        "latest_block": latest_block["block_index"] if latest_block else 0,
        "latest_hash": latest_block["block_hash"] if latest_block else "GENESIS",
        "signing_node": AppConfig.LOCAL_NODE_NAME,
        "signing_key_id": AppConfig.LOCAL_SIGNING_KEY_ID,
    }
    
    cur.execute("SELECT id FROM users WHERE username = ?", (session["user"],))
    user = cur.fetchone()
    if user:
        log_audit_action(conn, session["user"], "SECURITY_AUDIT", "ledger", user["id"], "Ran deep cryptographic integrity scan.")
        conn.commit()
    conn.close()

    return render_template(
        "admin/security_audit.html",
        valid=valid,
        issues=issues,
        issue_summary=issue_summary,
        total_blocks=total_blocks,
        audit_metrics=audit_metrics,
        nav_active="admin"
    )
