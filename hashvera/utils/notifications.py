from .common import utc_now, normalize_campus_id

def create_notification(conn, recipient_username, category, title, message, link_url=""):
    if not recipient_username:
        return
    conn.execute(
        """
        INSERT INTO notifications(recipient_username, category, title, message, link_url, is_read, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?)
        """,
        (recipient_username, category, title, message, link_url or "", utc_now()),
    )

def notify_roles(conn, roles, category, title, message, link_url=""):
    if not roles:
        return
    placeholders = ",".join("?" for _ in roles)
    rows = conn.execute(
        f"SELECT username FROM users WHERE role IN ({placeholders}) AND disabled = 0",
        tuple(roles),
    ).fetchall()
    seen = set()
    for row in rows:
        username = row["username"]
        if username in seen:
            continue
        seen.add(username)
        create_notification(conn, username, category, title, message, link_url)

def notify_user_for_campus_id(conn, campus_id, category, title, message, link_url=""):
    campus_id = normalize_campus_id(campus_id)
    if not campus_id:
        return
    user = conn.execute(
        "SELECT username FROM users WHERE campus_id = ? LIMIT 1",
        (campus_id,),
    ).fetchone()
    if user:
        create_notification(conn, user["username"], category, title, message, link_url)

def fetch_notifications(conn, username, limit=12):
    if not username:
        return []
    rows = conn.execute(
        """
        SELECT *
        FROM notifications
        WHERE recipient_username = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (username, limit),
    ).fetchall()
    return list(rows)

def count_unread_notifications(conn, username):
    if not username:
        return 0
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM notifications WHERE recipient_username = ? AND is_read = 0",
        (username,),
    ).fetchone()
    return row["total"] if row else 0

def get_notification_summary():
    from flask import session
    from ..database import get_connection
    
    if not session.get("user"):
        return {"items": [], "unread": 0}
    conn = get_connection()
    rows = fetch_notifications(conn, session.get("user"), 6)
    unread = count_unread_notifications(conn, session.get("user"))
    conn.close()
    return {"items": rows, "unread": unread}
