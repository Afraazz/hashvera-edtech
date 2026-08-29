from flask import session, flash, redirect, url_for, current_app
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from datetime import datetime, timezone

def require_login():
    if "user" not in session:
        flash("Please log in to continue.", "error")
        return False
    return True

def require_admin():
    if not require_login():
        return False
    if session.get("role") != "Administrator":
        flash("Administrator access required.", "error")
        return False
    return True

def can_create_records():
    role = (session.get("role") or "").strip().lower()
    return role in {"administrator", "faculty", "exam cell"}

def can_edit_records():
    role = (session.get("role") or "").strip().lower()
    return role in {"administrator", "faculty", "exam cell"}

def can_archive_records():
    role = (session.get("role") or "").strip().lower()
    return role in {"administrator", "faculty", "exam cell"}

def can_view_profile_directory():
    role = (session.get("role") or "").strip().lower()
    return role in {"administrator", "faculty", "exam cell"}

def can_view_my_records():
    return session.get("role") == "Student"

def can_review_requests():
    role = (session.get("role") or "").strip().lower()
    return role in {"administrator", "faculty", "exam cell"}

def require_peer_token():
    from flask import request
    import hmac
    from ..config import AppConfig
    
    provided_token = request.headers.get("X-HashVera-Token", "").strip()
    if not AppConfig.PEER_SHARED_TOKEN:
        return False, ("Peer networking is not configured on this node.", 503)
    if not hmac.compare_digest(provided_token, AppConfig.PEER_SHARED_TOKEN):
        return False, ("Peer authentication failed.", 401)
    return True, None

import random
import string
from datetime import timedelta
from .common import utc_now

def create_otp_code():
    return "".join(random.choices(string.digits, k=6))


def store_otp(conn, email, otp):
    expiry = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()

    conn.execute(
        "UPDATE password_resets SET is_verified = 1 WHERE email = ? AND is_verified = 0",
        (email,),
    )
    
    conn.execute(
        "INSERT INTO password_resets(email, otp_code, expiry, created_at) VALUES (?, ?, ?, ?)",
        (email, otp, expiry, utc_now())
    )


def generate_otp(conn, email):
    # 6-digit numeric OTP
    otp = create_otp_code()
    store_otp(conn, email, otp)
    return otp

def verify_otp(conn, email, otp):
    row = conn.execute(
        """
        SELECT id FROM password_resets 
        WHERE email = ? AND otp_code = ? AND is_verified = 0 AND expiry > ?
        ORDER BY id DESC LIMIT 1
        """,
        (email, otp, datetime.now(timezone.utc).isoformat())
    ).fetchone()
    
    if row:
        conn.execute("UPDATE password_resets SET is_verified = 1 WHERE id = ?", (row["id"],))
        return True
    return False

def get_serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

def generate_reset_token(email):
    # We now use OTP, but keeping this for potential link fallback
    return get_serializer().dumps(email, salt="hashvera-reset-password")

def verify_reset_token(token, max_age=1800):
    try:
        return get_serializer().loads(token, salt="hashvera-reset-password", max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None
